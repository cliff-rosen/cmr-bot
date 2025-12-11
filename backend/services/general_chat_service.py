"""
General Chat Service for CMR Bot

Handles the primary agent's chat interactions with tool support.
"""

from typing import Dict, Any, AsyncGenerator, List, Optional
from sqlalchemy.orm import Session
import anthropic
import asyncio
import os
import logging

from schemas.general_chat import ChatResponsePayload
from services.chat_payloads import (
    get_tool,
    get_all_tools,
    get_tools_for_anthropic,
    ToolResult
)
from services.conversation_service import ConversationService
from services.memory_service import MemoryService
from services.asset_service import AssetService

logger = logging.getLogger(__name__)

CHAT_MODEL = "claude-sonnet-4-20250514"
CHAT_MAX_TOKENS = 4096
MAX_TOOL_ITERATIONS = 10


class GeneralChatService:
    """Service for primary agent chat interactions."""

    def __init__(self, db: Session, user_id: int):
        self.db = db
        self.user_id = user_id
        self.client = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
        self.async_client = anthropic.AsyncAnthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))

    async def stream_chat_message(self, request) -> AsyncGenerator[str, None]:
        """
        Stream a chat message response with tool support via SSE.
        """
        from routers.general_chat import ChatStreamChunk, ChatStatusResponse

        try:
            user_prompt = request.message

            # Handle conversation persistence
            conv_service = ConversationService(self.db, self.user_id)

            if request.conversation_id:
                # Continue existing conversation
                conversation = conv_service.get_conversation(request.conversation_id)
                if not conversation:
                    raise ValueError(f"Conversation {request.conversation_id} not found")
                conversation_id = conversation.conversation_id
            else:
                # Create new conversation
                conversation = conv_service.create_conversation()
                conversation_id = conversation.conversation_id

            # Save user message first
            conv_service.add_message(
                conversation_id=conversation_id,
                role="user",
                content=user_prompt
            )

            # Auto-title if this is the first message
            conv_service.auto_title_if_needed(conversation_id)

            # Load message history from database (excludes the message we just added since it's already there)
            db_messages = conv_service.get_messages(conversation_id)
            messages = [
                {"role": msg.role, "content": msg.content}
                for msg in db_messages
            ]

            # Build system prompt with semantic memory search based on user's message
            system_prompt = self._build_system_prompt(
                request.context,
                user_message=user_prompt,
                enabled_tools=request.enabled_tools,
                include_profile=request.include_profile
            )

            # Build tool context (passed to tool executors)
            tool_context = {
                **(request.context or {}),
                "conversation_id": conversation_id
            }

            # Get tools, filtered by enabled_tools if specified
            all_tools = get_all_tools()
            if request.enabled_tools is not None:
                # Filter to only enabled tools
                enabled_set = set(request.enabled_tools)
                tools = [t for t in all_tools if t.name in enabled_set]
            else:
                tools = all_tools

            tools_by_name = {tool.name: tool for tool in tools}

            # Build anthropic tools list from filtered tools
            anthropic_tools = [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.input_schema
                }
                for tool in tools
            ] if tools else None

            # Send initial status
            status_response = ChatStatusResponse(
                status="Thinking...",
                payload=None,
                error=None,
                debug=None
            )
            yield status_response.model_dump_json()

            iteration = 0
            collected_text = ""
            tool_call_history = []  # Track all tool calls with inputs and outputs

            # Build API call kwargs - only include tools if we have them
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

                # Always stream - collect response and check for tool use
                response_content = []
                current_text = ""

                async with self.async_client.messages.stream(**api_kwargs) as stream:
                    async for event in stream:
                        # Handle text streaming
                        if hasattr(event, 'type'):
                            if event.type == 'content_block_delta' and hasattr(event, 'delta'):
                                if hasattr(event.delta, 'text'):
                                    text = event.delta.text
                                    current_text += text
                                    collected_text += text
                                    token_response = ChatStreamChunk(
                                        token=text,
                                        response_text=None,
                                        payload=None,
                                        status="streaming",
                                        error=None,
                                        debug=None
                                    )
                                    yield token_response.model_dump_json()

                    # Get the final response to check for tool use
                    final_response = await stream.get_final_message()
                    response_content = final_response.content

                # Check for tool use in the response
                tool_use_blocks = [b for b in response_content if b.type == "tool_use"]

                # No tool call - we're done
                if not tool_use_blocks:
                    logger.info(f"No tool call, response complete. Collected text length: {len(collected_text)}")
                    break

                # Handle tool call
                tool_block = tool_use_blocks[0]
                tool_name = tool_block.name
                tool_input = tool_block.input
                tool_use_id = tool_block.id

                logger.info(f"Tool call: {tool_name} with input: {tool_input}")

                # Send tool starting status
                tool_status = ChatStatusResponse(
                    status=f"Running {tool_name}...",
                    payload={"tool": tool_name, "phase": "running"},
                    error=None,
                    debug=None
                )
                yield tool_status.model_dump_json()

                # Execute tool
                tool_result_str, tool_output_data = await self._execute_tool(
                    tool_name, tool_input, tools_by_name, tool_context
                )

                # Record tool call in history
                tool_call_history.append({
                    "tool_name": tool_name,
                    "input": tool_input,
                    "output": tool_output_data if tool_output_data else tool_result_str
                })

                # Send tool completed status
                tool_complete_status = ChatStatusResponse(
                    status=f"Completed {tool_name}",
                    payload={"tool": tool_name, "phase": "completed"},
                    error=None,
                    debug=None
                )
                yield tool_complete_status.model_dump_json()

                # Add tool interaction to messages for next iteration
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

                # Update api_kwargs with new messages for next iteration
                api_kwargs["messages"] = messages

                # Add newline separator before next iteration's text
                separator = "\n\n"
                collected_text += separator
                separator_response = ChatStreamChunk(
                    token=separator,
                    response_text=None,
                    payload=None,
                    status="streaming",
                    error=None,
                    debug=None
                )
                yield separator_response.model_dump_json()

            # Save assistant message
            conv_service.add_message(
                conversation_id=conversation_id,
                role="assistant",
                content=collected_text,
                tool_calls=tool_call_history if tool_call_history else None
            )

            # Build final payload
            logger.info(f"Building final payload with collected_text length: {len(collected_text)}, tool_calls: {len(tool_call_history)}")
            final_payload = ChatResponsePayload(
                message=collected_text,
                conversation_id=conversation_id,
                suggested_values=None,
                suggested_actions=None,
                custom_payload={"type": "tool_history", "data": tool_call_history} if tool_call_history else None
            )

            final_response = ChatStreamChunk(
                token=None,
                response_text=None,
                payload=final_payload,
                status="complete",
                error=None,
                debug=None
            )
            logger.info(f"Yielding final response with status=complete")
            yield final_response.model_dump_json()

        except Exception as e:
            logger.error(f"Error in chat service: {str(e)}", exc_info=True)
            error_response = ChatStreamChunk(
                token=None,
                response_text=None,
                payload=None,
                status=None,
                error=f"Service error: {str(e)}",
                debug={"error_type": type(e).__name__}
            )
            yield error_response.model_dump_json()

    def _build_system_prompt(
        self,
        context: Dict[str, Any],
        user_message: Optional[str] = None,
        enabled_tools: Optional[List[str]] = None,
        include_profile: bool = True
    ) -> str:
        """Build the system prompt for the primary agent.

        Args:
            context: Request context
            user_message: The user's current message (for semantic memory search)
            enabled_tools: List of enabled tool IDs (None = all tools)
            include_profile: Whether to include user profile information
        """

        # Get list of available tools for the prompt, filtered if needed
        all_tools = get_all_tools()
        if enabled_tools is not None:
            enabled_set = set(enabled_tools)
            tools = [t for t in all_tools if t.name in enabled_set]
        else:
            tools = all_tools

        tool_descriptions = "\n".join([
            f"- **{t.name}**: {t.description}"
            for t in tools
        ]) if tools else "No tools currently enabled."

        # Get user's memories and assets for context
        memory_service = MemoryService(self.db, self.user_id)
        asset_service = AssetService(self.db, self.user_id)

        # Include semantically relevant memories based on user's message
        memory_context = memory_service.format_for_prompt(include_relevant=user_message)
        asset_context = asset_service.format_for_prompt()

        # Get user profile if requested
        profile_context = ""
        if include_profile:
            from models import User, UserProfile
            user = self.db.query(User).filter(User.user_id == self.user_id).first()
            if user:
                profile_parts = []
                if user.full_name:
                    profile_parts.append(f"- Name: {user.full_name}")
                if user.profile:
                    if user.profile.display_name:
                        profile_parts.append(f"- Display name: {user.profile.display_name}")
                    if user.profile.bio:
                        profile_parts.append(f"- Bio: {user.profile.bio}")
                    if user.profile.preferences:
                        prefs = user.profile.preferences
                        if isinstance(prefs, dict):
                            for key, value in prefs.items():
                                profile_parts.append(f"- {key}: {value}")
                if profile_parts:
                    profile_context = "## User Profile\n" + "\n".join(profile_parts) + "\n"

        # Build context section
        context_section = ""
        if profile_context or memory_context or asset_context:
            context_section = "\n## User Context\n"
            if profile_context:
                context_section += f"\n{profile_context}\n"
            if memory_context:
                context_section += f"\n{memory_context}\n"
            if asset_context:
                context_section += f"\n{asset_context}\n"

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

    async def _execute_tool(
        self,
        tool_name: str,
        tool_input: Dict[str, Any],
        tools_by_name: Dict[str, Any],
        context: Dict[str, Any]
    ) -> tuple[str, Any]:
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
