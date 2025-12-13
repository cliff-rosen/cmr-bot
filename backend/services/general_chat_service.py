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
from tools import (
    get_all_tools,
    ToolResult,
    ToolProgress,
    execute_streaming_tool,
    execute_tool
)
from services.conversation_service import ConversationService
from services.memory_service import MemoryService
from services.asset_service import AssetService
from services.profile_service import ProfileService

logger = logging.getLogger(__name__)

CHAT_MODEL = "claude-sonnet-4-20250514"
CHAT_MAX_TOKENS = 4096
MAX_TOOL_ITERATIONS = 10


class CancellationToken:
    """Token for cancelling long-running operations."""

    def __init__(self):
        self._cancelled = False

    @property
    def is_cancelled(self) -> bool:
        return self._cancelled

    def cancel(self):
        self._cancelled = True

    def check(self) -> None:
        """Raise CancelledError if cancelled."""
        if self._cancelled:
            raise asyncio.CancelledError("Operation was cancelled")


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

    async def stream_chat_message(
        self,
        request,
        cancellation_token: Optional[CancellationToken] = None
    ) -> AsyncGenerator[str, None]:
        """
        Stream a chat message response with tool support via SSE.

        Args:
            request: The chat request
            cancellation_token: Optional token to check for cancellation
        """
        from routers.general_chat import ChatStreamChunk, ChatStatusResponse

        # Create a no-op token if none provided
        if cancellation_token is None:
            cancellation_token = CancellationToken()

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
                include_profile=request.include_profile,
                has_workflow_builder='design_workflow' in tools_by_name
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
                # Check for cancellation at start of each iteration
                if cancellation_token.is_cancelled:
                    logger.info("Request cancelled, exiting chat loop")
                    break

                iteration += 1
                logger.debug(f"Loop iteration {iteration}")

                async with self.async_client.messages.stream(**api_kwargs) as stream:
                    async for event in stream:
                        # Check for cancellation during streaming
                        if cancellation_token.is_cancelled:
                            logger.info("Request cancelled during streaming")
                            break

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

                    # Exit early if cancelled
                    if cancellation_token.is_cancelled:
                        break

                    final_response = await stream.get_final_message()
                    response_content = final_response.content

                # Exit if cancelled
                if cancellation_token.is_cancelled:
                    break

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

                # Emit started phase for frontend tool progress tracking
                yield ChatStatusResponse(
                    status=f"Running {tool_name}...",
                    payload={"tool": tool_name, "phase": "started"},
                    error=None,
                    debug=None
                ).model_dump_json()

                # Execute tool - may yield progress updates for streaming tools
                tool_result_str = ""
                tool_output_data = None
                tool_config = tools_by_name.get(tool_name)

                if tool_config and tool_config.streaming:
                    # Streaming tool - yield progress updates
                    progress_count = 0
                    got_final_result = False
                    async for progress_or_result in self._execute_streaming_tool_call(
                        tool_config, tool_input, tool_executor_context, cancellation_token
                    ):
                        # Check cancellation between progress updates
                        if cancellation_token.is_cancelled:
                            logger.info(f"Tool {tool_name} cancelled")
                            break

                        if isinstance(progress_or_result, ToolProgress):
                            progress_count += 1
                            # Yield progress update to frontend
                            yield ChatStatusResponse(
                                status=progress_or_result.message,
                                payload={
                                    "tool": tool_name,
                                    "phase": "progress",
                                    "stage": progress_or_result.stage,
                                    "data": progress_or_result.data,
                                    "progress": progress_or_result.progress
                                },
                                error=None,
                                debug=None
                            ).model_dump_json()
                        elif isinstance(progress_or_result, tuple):
                            # Final result (text, data)
                            got_final_result = True
                            tool_result_str, tool_output_data = progress_or_result
                            logger.info(f"Streaming tool {tool_name} completed after {progress_count} progress updates")
                        else:
                            logger.warning(f"Unexpected item from streaming tool {tool_name}: {type(progress_or_result)}")

                    if not got_final_result and not cancellation_token.is_cancelled:
                        logger.error(f"Streaming tool {tool_name} ended without yielding final result!")
                else:
                    # Non-streaming tool
                    tool_result_str, tool_output_data = await self._execute_tool_call(
                        tool_name, tool_input, tools_by_name, tool_executor_context
                    )

                # If cancelled during tool execution, exit
                if cancellation_token.is_cancelled:
                    break

                tool_call_history.append({
                    "tool_name": tool_name,
                    "input": tool_input,
                    "output": tool_output_data if tool_output_data else tool_result_str
                })

                # Sanity check: detect if we accidentally got a generator object as string
                if tool_result_str and ("<generator object" in tool_result_str or "Generator" in tool_result_str):
                    logger.error(f"BUG: Tool {tool_name} returned generator object instead of result: {tool_result_str[:200]}")

                # Log what the LLM will see as the tool result
                result_preview = tool_result_str[:500] if tool_result_str else "(empty)"
                if len(tool_result_str) > 500:
                    result_preview += f"... (truncated, total {len(tool_result_str)} chars)"
                logger.info(f"Tool result for {tool_name} (sending to LLM): {result_preview}")

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
        include_profile: bool = True,
        has_workflow_builder: bool = False
    ) -> str:
        """
        Build the system prompt for the primary agent.

        Args:
            tool_descriptions: Pre-formatted tool descriptions
            user_message: The user's current message (for semantic memory search)
            include_profile: Whether to include user profile information
            has_workflow_builder: Whether the design_workflow tool is available
        """
        from datetime import datetime
        current_date = datetime.now().strftime("%Y-%m-%d")

        context_section = self._build_context_section(user_message, include_profile)
        workflow_section = self._build_workflow_section(has_workflow_builder)

        return f"""You are CMR Bot, a personal AI assistant with full access to tools and capabilities.

        You are the primary agent in a personal AI system designed for deep integration and autonomy. You help the user with research, information gathering, analysis, and various tasks.

        **Today's date: {current_date}**

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

        **Standard Payload types:**

        - `draft` - For any written content the user might want to iterate on: emails, letters, documents, messages, blog posts, code, etc. The user can edit these directly in the workspace.

        - `summary` - For summarized information from research, articles, or analysis. Use when presenting key takeaways or condensed information.

        - `data` - For structured data like weather, statistics, comparisons, lists of items with properties, etc. Format the content as a readable summary.

        - `code` - For code snippets, scripts, or technical implementations. The user can copy or save these easily.

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

        {workflow_section}
        ## Executing Workflow Steps (WIP Outputs)

        When the user accepts a plan and asks you to execute a step, send your output as a **wip (work-in-progress)** payload. The user will review and either accept, request changes, or reject each step's output.

        **WIP payload format:**

        ```payload
        {{
        "type": "wip",
        "title": "<output title>",
        "content": "<the step's output>",
        "step_number": <which step this is for>,
        "content_type": "document" | "data" | "code"
        }}
        ```

        **Responding to workflow actions:**

        When you receive an action like `workflow_step_start`:
        1. Execute the step as described in the plan
        2. Use any available tools as needed
        3. Send the output as a `wip` payload
        4. Wait for user approval before proceeding

        When you receive `workflow_step_revise` or `workflow_step_redo`:
        - Revise the output based on feedback and send a new `wip` payload

        **Important payload notes:**
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

        return context_section

    def _build_workflow_section(self, has_workflow_builder: bool) -> str:
        """
        Build the workflow planning section of the system prompt.

        Args:
            has_workflow_builder: Whether the design_workflow tool is available

        Returns:
            Workflow section string
        """
        base_section = """## Workflow Plans

        For complex, multi-step tasks that require a structured approach, you can propose a **workflow plan**. Workflows are chains of steps where each step has an input, a method (how you'll accomplish it), and an output. The user reviews and approves each step's output before you proceed to the next.

        **When to propose a workflow:**
        - Tasks requiring multiple distinct phases (research → analyze → create)
        - Complex deliverables that need iteration
        - Projects where the user wants visibility into your process
        - Tasks where intermediate outputs might need user feedback
        - Research or analysis of MULTIPLE items that need synthesis
        - Comparison tasks (e.g., "compare these 5 options")

        """

        if has_workflow_builder:
            # When design_workflow is available, tell agent to use it
            return base_section + """**IMPORTANT: Use the design_workflow tool**

            When you decide a workflow is appropriate, DO NOT create the workflow plan yourself. Instead, call the `design_workflow` tool with the user's goal. This specialized workflow architect will design an optimal plan that leverages advanced patterns like:
            - **map_reduce**: For processing multiple items and synthesizing results (e.g., research 5 companies and compare them)
            - **iterate**: For applying the same operation to multiple items in parallel
            - **Multi-source inputs**: For steps that combine data from multiple prior steps

            Example: If the user asks "Research these 5 AI companies and compare them", call:
            ```
            design_workflow(goal="Research and compare 5 AI companies: OpenAI, Anthropic, Google DeepMind, Meta AI, and Mistral")
            ```

            **CRITICAL**: When design_workflow returns, it will give you a complete plan with a payload block. You MUST:
            1. Present the plan to the user by including the payload block in your response
            2. Do NOT start executing the workflow or calling other tools
            3. Wait for the user to approve the plan before doing anything else

            The tool result will contain the exact payload JSON to include - just copy it into your response.

            **Plan payload format (after receiving from design_workflow):**

            ```payload
            {{
            "type": "plan",
            "title": "<from workflow>",
            "goal": "<from workflow>",
            "initial_input": "<user's input>",
            "steps": [<steps from workflow>]
            }}
            ```

            **input_sources** indicates where each step gets its input:
            - `["user"]` - The initial input provided by the user
            - `[1]`, `[2]` - Output from a previous step
            - `["user", 1]` - Multiple sources combined

            """
        else:
            # When design_workflow is NOT available, agent creates workflows directly
            return base_section + """**Plan payload format:**

            ```payload
            {{
            "type": "plan",
            "title": "<workflow title>",
            "goal": "<what the workflow will achieve>",
            "initial_input": "<what the user is providing to start>",
            "steps": [
                {{
                "description": "<what this step does>",
                "input_description": "<what this step takes as input>",
                "input_sources": ["user"],
                "output_description": "<what this step produces>",
                "method": {{
                    "approach": "<how you'll accomplish this>",
                    "tools": ["<tool1>", "<tool2>"],
                    "reasoning": "<why this approach>"
                }}
                }}
            ]
            }}
            ```

            **input_sources** indicates where each step gets its input:
            - `["user"]` - The initial input provided by the user
            - `[1]`, `[2]` - Output from a previous step (by step number)
            - `["user", 1]` - Multiple sources combined

            **Tips for good workflow design:**
            - Keep workflows to 2-4 steps when possible
            - Consider using `map_reduce` tool when processing multiple items that need synthesis
            - Consider using `iterate` tool when applying the same operation to multiple items
            - Steps can have multiple input_sources to combine data from different steps

            """

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

    async def _execute_tool_call(
        self,
        tool_name: str,
        tool_input: Dict[str, Any],
        tools_by_name: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Tuple[str, Any]:
        """Execute a non-streaming tool and return (result_str, output_data)."""
        tool_config = tools_by_name.get(tool_name)

        if not tool_config:
            return f"Unknown tool: {tool_name}", None

        return await execute_tool(tool_config, tool_input, self.db, self.user_id, context)

    async def _execute_streaming_tool_call(
        self,
        tool_config: Any,
        tool_input: Dict[str, Any],
        context: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None
    ) -> AsyncGenerator[ToolProgress | Tuple[str, Any], None]:
        """Execute a streaming tool, yielding progress updates and finally the result tuple."""
        async for item in execute_streaming_tool(
            tool_config, tool_input, self.db, self.user_id, context, cancellation_token
        ):
            yield item

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
