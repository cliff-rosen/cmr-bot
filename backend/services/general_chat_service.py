"""
General Chat Service for CMR Bot

Handles the primary agent's chat interactions with tool support.
Uses the generic agent_loop for the agentic processing.
"""

from typing import Dict, Any, AsyncGenerator, List, Optional, Tuple
from datetime import datetime
from sqlalchemy.orm import Session
import anthropic
import os
import logging

from schemas.general_chat import (
    ChatResponsePayload,
    TextDeltaEvent,
    StatusEvent,
    ToolStartEvent,
    ToolProgressEvent,
    ToolCompleteEvent,
    CompleteEvent,
    ErrorEvent,
    CancelledEvent,
)
from tools import get_all_tools
from services.conversation_service import ConversationService
from services.memory_service import MemoryService
from services.asset_service import AssetService
from services.profile_service import ProfileService
from services.agent_loop import (
    run_agent_loop,
    CancellationToken,
    AgentEvent,
    AgentThinking,
    AgentTextDelta,
    AgentToolStart,
    AgentToolProgress,
    AgentToolComplete,
    AgentComplete,
    AgentCancelled,
    AgentError,
)

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
            tools_by_name, tool_descriptions, tool_executor_context = self._get_tools_config(
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
            yield StatusEvent(message="Thinking...").model_dump_json()

            # Run the agent loop
            collected_text = ""
            tool_call_history = []
            tool_call_index = 0  # Track index for [[tool:N]] markers

            async for event in run_agent_loop(
                client=self.async_client,
                model=CHAT_MODEL,
                max_tokens=CHAT_MAX_TOKENS,
                max_iterations=MAX_TOOL_ITERATIONS,
                system_prompt=system_prompt,
                messages=messages,
                tools=tools_by_name,
                db=self.db,
                user_id=self.user_id,
                context=tool_executor_context,
                cancellation_token=cancellation_token,
                stream_text=True,
                temperature=0.7
            ):
                if isinstance(event, AgentThinking):
                    yield StatusEvent(message=event.message).model_dump_json()

                elif isinstance(event, AgentTextDelta):
                    collected_text += event.text
                    yield TextDeltaEvent(text=event.text).model_dump_json()

                elif isinstance(event, AgentToolStart):
                    yield ToolStartEvent(
                        tool=event.tool_name,
                        input=event.tool_input,
                        tool_use_id=event.tool_use_id
                    ).model_dump_json()

                elif isinstance(event, AgentToolProgress):
                    yield ToolProgressEvent(
                        tool=event.tool_name,
                        stage=event.progress.stage or "",
                        message=event.progress.message or "",
                        progress=event.progress.progress or 0.0,
                        data=event.progress.data
                    ).model_dump_json()

                elif isinstance(event, AgentToolComplete):
                    # Emit [[tool:N]] marker in text stream
                    tool_marker = f"[[tool:{tool_call_index}]]"
                    collected_text += tool_marker
                    yield TextDeltaEvent(text=tool_marker).model_dump_json()
                    # Emit tool complete event with index for frontend to match
                    yield ToolCompleteEvent(
                        tool=event.tool_name,
                        index=tool_call_index
                    ).model_dump_json()
                    tool_call_index += 1

                elif isinstance(event, (AgentComplete, AgentCancelled)):
                    tool_call_history = event.tool_calls
                    if isinstance(event, AgentCancelled):
                        yield CancelledEvent().model_dump_json()

                elif isinstance(event, AgentError):
                    yield ErrorEvent(message=event.error).model_dump_json()
                    return

            # Save assistant message
            self.conv_service.add_message(
                conversation_id=conversation_id,
                role="assistant",
                content=collected_text,
                tool_calls=tool_call_history if tool_call_history else None
            )

            # Extract workspace_payload from the last tool that returned one
            # This takes precedence over any payload block in the LLM's message text
            workspace_payload = None
            if tool_call_history:
                for tool_call in reversed(tool_call_history):
                    if tool_call.get("workspace_payload"):
                        workspace_payload = tool_call["workspace_payload"]
                        break

            # Build and yield final payload
            final_payload = ChatResponsePayload(
                message=collected_text,
                conversation_id=conversation_id,
                suggested_values=None,
                suggested_actions=None,
                custom_payload={"type": "tool_history", "data": tool_call_history} if tool_call_history else None,
                workspace_payload=workspace_payload
            )

            yield CompleteEvent(payload=final_payload).model_dump_json()

        except Exception as e:
            logger.error(f"Error in chat service: {str(e)}", exc_info=True)
            yield ErrorEvent(message=f"Service error: {str(e)}").model_dump_json()

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
        current_date = datetime.now().strftime("%Y-%m-%d")

        context_section = self._build_context_section(user_message, include_profile)
        workflow_section = self._build_workflow_section(has_workflow_builder)

        return f"""You are CMR Bot, a personal AI assistant with full access to tools and capabilities.

        You are the primary agent in a personal AI system designed for deep integration and autonomy. You help the user with research, information gathering, analysis, and various tasks.

        **IMPORTANT - Current Date: {current_date}** (Use this date for all time-relative queries like "recent", "last month", etc.)

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
        Build the workflow section of the system prompt.

        Args:
            has_workflow_builder: Whether the design_workflow tool is available

        Returns:
            Workflow section string
        """
        if not has_workflow_builder:
            return ""

        return """## Workflows

        For complex multi-step tasks, use the `design_workflow` tool. It will design an executable workflow with checkpoints for user review.

        When to use it:
        - Tasks with multiple distinct phases
        - Research or comparison of multiple items
        - Projects needing user review at intermediate steps

        The tool handles everything - just call it with the goal and let the workspace display the result.

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
    ) -> Tuple[Dict[str, Any], str, Dict[str, Any]]:
        """
        Get all tool-related configuration.

        Args:
            enabled_tools: List of tool IDs to enable (None = all tools)
            conversation_id: Current conversation ID (for tool executor context)
            request_context: Additional context from request (for tool executor context)

        Returns:
            Tuple of (tools_by_name, tool_descriptions, tool_executor_context)
        """
        tools = self._get_filtered_tools(enabled_tools)

        # Build lookup dict (name -> ToolConfig)
        tools_by_name = {tool.name: tool for tool in tools}

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

        return tools_by_name, tool_descriptions, tool_executor_context

    def _get_filtered_tools(self, enabled_tools: Optional[List[str]] = None) -> List[Any]:
        """Get tools filtered by enabled list."""
        all_tools = get_all_tools()
        if enabled_tools is not None:
            enabled_set = set(enabled_tools)
            return [t for t in all_tools if t.name in enabled_set]
        return all_tools
