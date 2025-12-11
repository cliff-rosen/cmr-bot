"""
General Chat Service for CMR Bot

Handles the primary agent's chat interactions with tool support.
"""

from typing import Dict, Any, AsyncGenerator, List, Optional, Tuple
from sqlalchemy.orm import Session
import anthropic
import asyncio
import os
import logging

from schemas.general_chat import ChatResponsePayload
from services.chat_payloads import (
    get_all_tools,
    ToolResult
)
from services.conversation_service import ConversationService
from services.memory_service import MemoryService
from services.asset_service import AssetService
from services.profile_service import ProfileService

logger = logging.getLogger(__name__)

CHAT_MODEL = "claude-sonnet-4-20250514"
CHAT_MAX_TOKENS = 4096
MAX_TOOL_ITERATIONS = 10


class GeneralChatService:
    """Service for primary agent chat interactions."""

    def __init__(self, db: Session, user_id: int):
        self.db = db
        self.user_id = user_id
        self.async_client = anthropic.AsyncAnthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
        self.conv_service = ConversationService(db, user_id)

    # =========================================================================
    # Public API
    # =========================================================================

    async def stream_chat_message(self, request) -> AsyncGenerator[str, None]:
        """
        Stream a chat message response with tool support via SSE.
        """
        from routers.general_chat import ChatStreamChunk, ChatStatusResponse

        try:
            user_prompt = request.message

            # Handle conversation persistence
            conversation_id = self._setup_conversation(request, user_prompt)

            # Load message history
            messages = self._load_message_history(conversation_id)

            # Get tools configuration
            tools_by_name, anthropic_tools, tool_descriptions, tool_executor_context = self._get_tools_config(
                enabled_tools=request.enabled_tools,
                conversation_id=conversation_id,
                request_context=request.context
            )

            # Build system prompt
            system_prompt = self._build_system_prompt(
                tool_descriptions,
                user_message=user_prompt,
                include_profile=request.include_profile
            )

            # Send initial status
            yield ChatStatusResponse(
                status="Thinking...",
                payload=None,
                error=None,
                debug=None
            ).model_dump_json()

            # Chat loop state
            iteration = 0
            collected_text = ""
            tool_call_history = []

            api_kwargs = {
                "model": CHAT_MODEL,
                "max_tokens": CHAT_MAX_TOKENS,
                "temperature": 0.7,
                "system": system_prompt,
                "messages": messages
            }
            if anthropic_tools:
                api_kwargs["tools"] = anthropic_tools

            while iteration < MAX_TOOL_ITERATIONS:
                iteration += 1
                logger.info(f"Loop iteration {iteration}")

                async with self.async_client.messages.stream(**api_kwargs) as stream:
                    async for event in stream:
                        if hasattr(event, 'type'):
                            if event.type == 'content_block_delta' and hasattr(event, 'delta'):
                                if hasattr(event.delta, 'text'):
                                    text = event.delta.text
                                    collected_text += text
                                    yield ChatStreamChunk(
                                        token=text,
                                        response_text=None,
                                        payload=None,
                                        status="streaming",
                                        error=None,
                                        debug=None
                                    ).model_dump_json()

                    final_response = await stream.get_final_message()
                    response_content = final_response.content

                # Check for tool use
                tool_use_blocks = [b for b in response_content if b.type == "tool_use"]

                if not tool_use_blocks:
                    logger.info(f"No tool call, response complete.")
                    break

                # Handle tool call
                tool_block = tool_use_blocks[0]
                tool_name = tool_block.name
                tool_input = tool_block.input
                tool_use_id = tool_block.id

                logger.info(f"Tool call: {tool_name}")

                yield ChatStatusResponse(
                    status=f"Running {tool_name}...",
                    payload={"tool": tool_name, "phase": "running"},
                    error=None,
                    debug=None
                ).model_dump_json()

                tool_result_str, tool_output_data = await self._execute_tool(
                    tool_name, tool_input, tools_by_name, tool_executor_context
                )

                tool_call_history.append({
                    "tool_name": tool_name,
                    "input": tool_input,
                    "output": tool_output_data if tool_output_data else tool_result_str
                })

                yield ChatStatusResponse(
                    status=f"Completed {tool_name}",
                    payload={"tool": tool_name, "phase": "completed"},
                    error=None,
                    debug=None
                ).model_dump_json()

                # Add tool interaction to messages
                assistant_content = self._format_assistant_content(response_content)
                messages.append({"role": "assistant", "content": assistant_content})
                messages.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": tool_use_id,
                        "content": tool_result_str
                    }]
                })
                api_kwargs["messages"] = messages

                # Add separator
                separator = "\n\n"
                collected_text += separator
                yield ChatStreamChunk(
                    token=separator,
                    response_text=None,
                    payload=None,
                    status="streaming",
                    error=None,
                    debug=None
                ).model_dump_json()

            # Save assistant message
            self.conv_service.add_message(
                conversation_id=conversation_id,
                role="assistant",
                content=collected_text,
                tool_calls=tool_call_history if tool_call_history else None
            )

            # Build and yield final payload
            final_payload = ChatResponsePayload(
                message=collected_text,
                conversation_id=conversation_id,
                suggested_values=None,
                suggested_actions=None,
                custom_payload={"type": "tool_history", "data": tool_call_history} if tool_call_history else None
            )

            yield ChatStreamChunk(
                token=None,
                response_text=None,
                payload=final_payload,
                status="complete",
                error=None,
                debug=None
            ).model_dump_json()

        except Exception as e:
            logger.error(f"Error in chat service: {str(e)}", exc_info=True)
            yield ChatStreamChunk(
                token=None,
                response_text=None,
                payload=None,
                status=None,
                error=f"Service error: {str(e)}",
                debug={"error_type": type(e).__name__}
            ).model_dump_json()

    # =========================================================================
    # Conversation Helpers
    # =========================================================================

    def _setup_conversation(self, request, user_prompt: str) -> int:
        """Set up conversation and save user message. Returns conversation_id."""
        if request.conversation_id:
            conversation = self.conv_service.get_conversation(request.conversation_id)
            if not conversation:
                raise ValueError(f"Conversation {request.conversation_id} not found")
            conversation_id = conversation.conversation_id
        else:
            conversation = self.conv_service.create_conversation()
            conversation_id = conversation.conversation_id

        self.conv_service.add_message(
            conversation_id=conversation_id,
            role="user",
            content=user_prompt
        )
        self.conv_service.auto_title_if_needed(conversation_id)

        return conversation_id

    def _load_message_history(self, conversation_id: int) -> List[Dict[str, str]]:
        """Load message history from database."""
        db_messages = self.conv_service.get_messages(conversation_id)
        return [
            {"role": msg.role, "content": msg.content}
            for msg in db_messages
        ]

    # =========================================================================
    # System Prompt Building
    # =========================================================================

    def _build_system_prompt(
        self,
        tool_descriptions: str,
        user_message: Optional[str] = None,
        include_profile: bool = True
    ) -> str:
        """
        Build the system prompt for the primary agent.

        Args:
            tool_descriptions: Pre-formatted tool descriptions
            user_message: The user's current message (for semantic memory search)
            include_profile: Whether to include user profile information
        """
        context_section = self._build_context_section(user_message, include_profile)

        return f"""You are CMR Bot, a personal AI assistant with full access to tools and capabilities.

        You are the primary agent in a personal AI system designed for deep integration and autonomy. You help the user with research, information gathering, analysis, and various tasks.

        ## Your Capabilities

        You have access to the following tools:
        {tool_descriptions}

        ## Guidelines

        1. **Be proactive**: Use your tools when they would help answer the user's question or complete their task.

        2. **Be thorough**: When researching, gather enough information to give a complete answer.

        3. **Be transparent**: Explain what you're doing and why, especially when using tools.

        4. **Be conversational**: You're a personal assistant, not a formal system. Be helpful and natural.

        5. **Work iteratively**: For complex tasks, break them down and tackle them step by step.

        ## Memory Management

        You have the ability to remember things about the user across conversations using the save_memory tool. Proactively save important information when the user shares:
        - Personal details (name, job, location, timezone)
        - Preferences (communication style, likes/dislikes, how they want things done)
        - Projects they're working on
        - People, companies, or things they reference frequently
        - Important context that would be useful in future conversations

        If you notice the user correcting something you remembered wrong, use delete_memory to remove the incorrect information and save the correct version.
        {context_section}
        ## Workspace Payloads

        The user has a workspace panel that can display structured content alongside your chat messages. When your response would benefit from structured presentation, include a payload block at the END of your response using this exact format:

        ```payload
        {{
        "type": "<payload_type>",
        "title": "<short title>",
        "content": "<the structured content>"
        }}
        ```

        **Payload types and when to use them:**

        - `draft` - For any written content the user might want to iterate on: emails, letters, documents, messages, blog posts, code, etc. The user can edit these directly in the workspace.

        - `summary` - For summarized information from research, articles, or analysis. Use when presenting key takeaways or condensed information.

        - `data` - For structured data like weather, statistics, comparisons, lists of items with properties, etc. Format the content as a readable summary.

        - `code` - For code snippets, scripts, or technical implementations. The user can copy or save these easily.

        - `plan` - For action plans, step-by-step instructions, or project outlines.

        **Examples:**

        User asks "Write me an email declining a meeting":
        - Provide a brief conversational response
        - Include a `draft` payload with the email text

        User asks "What's the weather in NYC?":
        - Provide a conversational summary
        - Include a `data` payload with the weather details

        User asks "Summarize the key points from that article":
        - Provide brief commentary
        - Include a `summary` payload with the bullet points

        **Important:**
        - Only include ONE payload per response
        - The payload must be valid JSON inside the code block
        - Always provide some conversational text BEFORE the payload
        - Not every response needs a payload - use them when structured content adds value
        - The payload appears in the workspace panel where users can edit, save, or act on it

        ## Interface

        The user is interacting with you through the main chat interface. The workspace panel on the right displays payloads and assets from your collaboration.

        Remember: You have real capabilities. Use them to actually help, not just to describe what you could theoretically do.
        """

    # =========================================================================
    # Context Building Helpers
    # =========================================================================

    def _build_context_section(
        self,
        user_message: Optional[str] = None,
        include_profile: bool = True
    ) -> str:
        """
        Build the complete user context section for system prompt.

        Args:
            user_message: Current message for semantic memory search
            include_profile: Whether to include profile info

        Returns:
            Formatted context section string
        """
        profile_context = self._get_profile_context(include_profile)
        memory_context = self._get_memory_context(user_message)
        asset_context = self._get_asset_context()

        if not any([profile_context, memory_context, asset_context]):
            return ""

        context_section = "\n## User Context\n"
        if profile_context:
            context_section += f"\n{profile_context}\n"
        if memory_context:
            context_section += f"\n{memory_context}\n"
        if asset_context:
            context_section += f"\n{asset_context}\n"

        logger.info(f"Profile context: {profile_context}")
        logger.info(f"Memory context: {memory_context}")
        logger.info(f"Asset context: {asset_context}")

        return context_section

    def _get_profile_context(self, include_profile: bool = True) -> str:
        """Get formatted user profile for system prompt."""
        if not include_profile:
            return ""

        profile_service = ProfileService(self.db, self.user_id)
        return profile_service.format_for_prompt()

    def _get_memory_context(self, user_message: Optional[str] = None) -> str:
        """Get formatted memories for system prompt."""
        memory_service = MemoryService(self.db, self.user_id)
        return memory_service.format_for_prompt(include_relevant=user_message)

    def _get_asset_context(self) -> str:
        """Get formatted assets for system prompt."""
        asset_service = AssetService(self.db, self.user_id)
        return asset_service.format_for_prompt()

    # =========================================================================
    # Tool Configuration
    # =========================================================================

    def _get_tools_config(
        self,
        enabled_tools: Optional[List[str]] = None,
        conversation_id: Optional[int] = None,
        request_context: Optional[Dict[str, Any]] = None
    ) -> Tuple[Dict[str, Any], Optional[List[Dict[str, Any]]], str, Dict[str, Any]]:
        """
        Get all tool-related configuration.

        Args:
            enabled_tools: List of tool IDs to enable (None = all tools)
            conversation_id: Current conversation ID (for tool executor context)
            request_context: Additional context from request (for tool executor context)

        Returns:
            Tuple of (tools_by_name, anthropic_tools, tool_descriptions, tool_executor_context)
        """
        tools = self._get_filtered_tools(enabled_tools)

        # Build lookup dict
        tools_by_name = {tool.name: tool for tool in tools}

        # Build Anthropic API format
        anthropic_tools = [
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.input_schema
            }
            for tool in tools
        ] if tools else None

        # Build descriptions for system prompt
        tool_descriptions = "\n".join([
            f"- **{t.name}**: {t.description}"
            for t in tools
        ]) if tools else "No tools currently enabled."

        # Build context passed to tool executors
        tool_executor_context = {
            **(request_context or {}),
            "conversation_id": conversation_id
        }

        return tools_by_name, anthropic_tools, tool_descriptions, tool_executor_context

    def _get_filtered_tools(self, enabled_tools: Optional[List[str]] = None) -> List[Any]:
        """Get tools filtered by enabled list."""
        all_tools = get_all_tools()
        if enabled_tools is not None:
            enabled_set = set(enabled_tools)
            return [t for t in all_tools if t.name in enabled_set]
        return all_tools

    # =========================================================================
    # Tool Execution
    # =========================================================================

    async def _execute_tool(
        self,
        tool_name: str,
        tool_input: Dict[str, Any],
        tools_by_name: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Tuple[str, Any]:
        """Execute a tool and return (result_str, output_data)."""
        tool_config = tools_by_name.get(tool_name)

        if not tool_config:
            return f"Unknown tool: {tool_name}", None

        try:
            tool_result = await asyncio.to_thread(
                tool_config.executor,
                tool_input,
                self.db,
                self.user_id,
                context
            )

            if isinstance(tool_result, ToolResult):
                return tool_result.text, tool_result.data
            elif isinstance(tool_result, str):
                return tool_result, None
            else:
                return str(tool_result), None

        except Exception as e:
            logger.error(f"Tool execution error: {e}", exc_info=True)
            return f"Error executing tool: {str(e)}", None

    def _format_assistant_content(self, response_content: list) -> list:
        """Format response content blocks for Anthropic API."""
        assistant_content = []
        for block in response_content:
            if block.type == "text":
                assistant_content.append({"type": "text", "text": block.text})
            elif block.type == "tool_use":
                assistant_content.append({
                    "type": "tool_use",
                    "id": block.id,
                    "name": block.name,
                    "input": block.input
                })
        return assistant_content
