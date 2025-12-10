"""
General-purpose chat service
Handles LLM interaction for the chat system
"""

from typing import Dict, Any, AsyncGenerator, List
from sqlalchemy.orm import Session
import anthropic
import asyncio
import os
import logging

from schemas.general_chat import ChatResponsePayload
from services.chat_payloads import (
    get_page_payloads,
    get_page_context_builder,
    get_page_client_actions,
    get_page_tools,
    has_page_payloads,
    ToolConfig,
    ToolResult
)

logger = logging.getLogger(__name__)

CHAT_MODEL = "claude-sonnet-4-20250514"
CHAT_MAX_TOKENS = 2000
MAX_TOOL_ITERATIONS = 5


def _tools_to_anthropic_format(tools: List[ToolConfig]) -> List[Dict[str, Any]]:
    """Convert ToolConfig objects to Anthropic API tool format."""
    return [
        {
            "name": tool.name,
            "description": tool.description,
            "input_schema": tool.input_schema
        }
        for tool in tools
    ]


class GeneralChatService:
    def __init__(self, db: Session, user_id: int):
        self.db = db
        self.user_id = user_id
        self.client = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
        self.async_client = anthropic.AsyncAnthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))

    async def stream_chat_message(self, request) -> AsyncGenerator[str, None]:
        """
        Stream a chat message response with status updates via SSE.
        Supports an agentic loop where the LLM can call tools.
        """
        from routers.general_chat import ChatStreamChunk, ChatStatusResponse

        try:
            system_prompt = self._build_system_prompt(request.context)
            user_prompt = self._build_user_prompt(
                request.message,
                request.context,
                request.interaction_type
            )

            messages = [
                {"role": msg.role, "content": msg.content}
                for msg in request.conversation_history
            ]
            messages.append({"role": "user", "content": user_prompt})

            current_page = request.context.get("current_page", "unknown")
            page_tools = get_page_tools(current_page)
            tools_by_name = {tool.name: tool for tool in page_tools}
            anthropic_tools = _tools_to_anthropic_format(page_tools) if page_tools else None

            status_response = ChatStatusResponse(
                status="Thinking...",
                payload={"context": current_page},
                error=None,
                debug=None
            )
            yield status_response.model_dump_json()

            iteration = 0
            collected_text = ""
            accumulated_payload = None

            while iteration < MAX_TOOL_ITERATIONS:
                iteration += 1

                if anthropic_tools:
                    response = await self.async_client.messages.create(
                        model=CHAT_MODEL,
                        max_tokens=CHAT_MAX_TOKENS,
                        temperature=0.0,
                        system=system_prompt,
                        messages=messages,
                        tools=anthropic_tools
                    )

                    tool_use_blocks = [block for block in response.content if block.type == "tool_use"]
                    text_blocks = [block for block in response.content if block.type == "text"]

                    if tool_use_blocks:
                        tool_block = tool_use_blocks[0]
                        tool_name = tool_block.name
                        tool_input = tool_block.input
                        tool_use_id = tool_block.id

                        logger.info(f"Tool call: {tool_name} with input: {tool_input}")

                        tool_status = ChatStatusResponse(
                            status=f"Using {tool_name}...",
                            payload={"tool": tool_name},
                            error=None,
                            debug=None
                        )
                        yield tool_status.model_dump_json()

                        tool_config = tools_by_name.get(tool_name)
                        tool_result_str = ""
                        if tool_config:
                            try:
                                tool_result = await asyncio.to_thread(
                                    tool_config.executor,
                                    tool_input,
                                    self.db,
                                    self.user_id,
                                    request.context
                                )
                                if isinstance(tool_result, ToolResult):
                                    tool_result_str = tool_result.text
                                    if tool_result.payload:
                                        accumulated_payload = tool_result.payload
                                elif isinstance(tool_result, str):
                                    tool_result_str = tool_result
                                else:
                                    tool_result_str = str(tool_result)
                            except Exception as e:
                                logger.error(f"Tool execution error: {e}", exc_info=True)
                                tool_result_str = f"Error executing tool: {str(e)}"
                        else:
                            tool_result_str = f"Unknown tool: {tool_name}"

                        messages.append({
                            "role": "assistant",
                            "content": response.content
                        })
                        messages.append({
                            "role": "user",
                            "content": [
                                {
                                    "type": "tool_result",
                                    "tool_use_id": tool_use_id,
                                    "content": tool_result_str
                                }
                            ]
                        })
                        continue

                    else:
                        for block in text_blocks:
                            collected_text += block.text
                        for char in collected_text:
                            token_response = ChatStreamChunk(
                                token=char,
                                response_text=None,
                                payload=None,
                                status="streaming",
                                error=None,
                                debug=None
                            )
                            yield token_response.model_dump_json()
                        break

                else:
                    stream = self.client.messages.stream(
                        model=CHAT_MODEL,
                        max_tokens=CHAT_MAX_TOKENS,
                        temperature=0.0,
                        system=system_prompt,
                        messages=messages
                    )

                    with stream as stream_manager:
                        for text in stream_manager.text_stream:
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
                    break

            parsed = self._parse_llm_response(collected_text, request.context)
            custom_payload = accumulated_payload or parsed.get("custom_payload")

            final_payload = ChatResponsePayload(
                message=parsed["message"],
                suggested_values=parsed.get("suggested_values"),
                suggested_actions=parsed.get("suggested_actions"),
                custom_payload=custom_payload
            )

            final_response = ChatStreamChunk(
                token=None,
                response_text=None,
                payload=final_payload,
                status="complete",
                error=None,
                debug=None
            )
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

    def _get_response_format_instructions(self) -> str:
        """Get common response format instructions."""
        return """
        RESPONSE FORMAT:

        Always start with a conversational message:
        MESSAGE: [Your response to the user]

        Optional elements:

        1. SUGGESTED_VALUES (clickable quick replies):
        Format: Comma-separated values
        Example: SUGGESTED_VALUES: Yes, No, Tell me more

        2. SUGGESTED_ACTIONS (action buttons):
        Format: label|action|handler|style|data
        - Position 1 (label): Button text
        - Position 2 (action): Action identifier
        - Position 3 (handler): MUST be "client" OR "server"
        - Position 4 (style): "primary", "secondary", or "warning"
        - Position 5 (data): Optional JSON object

        Examples:
        SUGGESTED_ACTIONS: View Results|view_results|client|primary
        SUGGESTED_ACTIONS: Save|save|server|primary; Cancel|cancel|client|secondary
        """

    def _build_system_prompt(self, context: Dict[str, Any]) -> str:
        """Build system prompt based on user's context."""
        current_page = context.get("current_page", "unknown")

        if has_page_payloads(current_page):
            return self._build_payload_aware_prompt(current_page, context)

        return f"""You are a helpful AI assistant for CMR-Bot, a personal AI agent system.

        The user is currently on: {current_page}

        {self._get_response_format_instructions()}

        You can help users with:
        - Research tasks and web searches
        - Finding scientific literature
        - General questions and assistance
        - Working collaboratively on various tasks

        Keep responses helpful and conversational.
        """

    def _build_payload_aware_prompt(self, current_page: str, context: Dict[str, Any]) -> str:
        """Build system prompt dynamically based on registered payload types."""
        all_payload_configs = get_page_payloads(current_page)

        active_tab = context.get("active_tab")
        if active_tab:
            payload_configs = [
                config for config in all_payload_configs
                if config.relevant_tabs is None or active_tab in config.relevant_tabs
            ]
        else:
            payload_configs = all_payload_configs

        page_context = self._build_page_context(current_page, context)

        payload_instructions = "\n\n".join([
            f"{config.llm_instructions}"
            for config in payload_configs
        ])

        client_actions = get_page_client_actions(current_page)
        client_actions_text = ""
        if client_actions:
            actions_list = "\n".join([
                f"- {action.action}: {action.description}" +
                (f" (parameters: {', '.join(action.parameters)})" if action.parameters else "")
                for action in client_actions
            ])
            client_actions_text = f"""

            AVAILABLE CLIENT ACTIONS:
            {actions_list}
            """

        return f"""You are a helpful AI assistant for CMR-Bot.

        {page_context}

        {self._get_response_format_instructions()}

        {payload_instructions}
        {client_actions_text}
        """

    def _build_page_context(self, current_page: str, context: Dict[str, Any]) -> str:
        """Build page-specific context section."""
        context_builder = get_page_context_builder(current_page)

        if context_builder:
            return context_builder(context)
        return f"The user is currently on: {current_page}"

    def _build_user_prompt(
        self,
        message: str,
        context: Dict[str, Any],
        interaction_type: str
    ) -> str:
        """Build user prompt with context."""
        context_summary = "\n".join([f"{k}: {v}" for k, v in context.items()])

        return f"""User's current context:
        {context_summary}

        Interaction type: {interaction_type}

        User's message: {message}

        Respond with MESSAGE and optional SUGGESTED_VALUES or SUGGESTED_ACTIONS."""

    def _parse_llm_response(self, response_text: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Parse LLM response to extract structured components."""
        import json

        result = {
            "message": "",
            "suggested_values": None,
            "suggested_actions": None,
            "custom_payload": None
        }

        current_page = context.get("current_page", "unknown")
        all_payload_configs = get_page_payloads(current_page)

        active_tab = context.get("active_tab")
        if active_tab:
            payload_configs = [
                config for config in all_payload_configs
                if config.relevant_tabs is None or active_tab in config.relevant_tabs
            ]
        else:
            payload_configs = all_payload_configs

        payload_markers = {config.parse_marker: config for config in payload_configs}

        lines = response_text.split('\n')
        message_lines = []
        in_message = False
        current_payload_config = None
        payload_lines = []
        brace_count = 0

        for line in lines:
            stripped = line.strip()

            if stripped.startswith("MESSAGE:"):
                in_message = True
                current_payload_config = None
                content = stripped.replace("MESSAGE:", "").strip()
                if content:
                    message_lines.append(content)

            elif any(stripped.startswith(marker) for marker in payload_markers.keys()):
                in_message = False
                for marker, config in payload_markers.items():
                    if stripped.startswith(marker):
                        current_payload_config = config
                        payload_lines = []
                        brace_count = 0
                        content = stripped.replace(marker, "").strip()
                        if content:
                            payload_lines.append(content)
                            brace_count += content.count('{') - content.count('}')
                        break

            elif current_payload_config is not None:
                all_section_markers = ["MESSAGE:", "SUGGESTED_VALUES:", "SUGGESTED_ACTIONS:"] + list(payload_markers.keys())
                if any(stripped.startswith(marker) for marker in all_section_markers):
                    if payload_lines:
                        self._parse_and_save_payload(result, current_payload_config, payload_lines)
                    current_payload_config = None
                    payload_lines = []
                    continue
                else:
                    payload_lines.append(line.rstrip())
                    brace_count += line.count('{') - line.count('}')
                    if brace_count == 0 and len(payload_lines) > 0:
                        self._parse_and_save_payload(result, current_payload_config, payload_lines)
                        current_payload_config = None
                        payload_lines = []
                        continue

            elif in_message and not any(stripped.startswith(marker) for marker in ["SUGGESTED_VALUES:", "SUGGESTED_ACTIONS:"] + list(payload_markers.keys())):
                message_lines.append(line.rstrip())

            elif stripped.startswith("SUGGESTED_VALUES:"):
                in_message = False
                current_payload_config = None
                values_str = stripped.replace("SUGGESTED_VALUES:", "").strip()
                if values_str:
                    result["suggested_values"] = [
                        {"label": v.strip(), "value": v.strip()}
                        for v in values_str.split(",")
                    ]

            elif stripped.startswith("SUGGESTED_ACTIONS:"):
                in_message = False
                current_payload_config = None
                actions_str = stripped.replace("SUGGESTED_ACTIONS:", "").strip()
                if actions_str:
                    actions = []
                    for action_str in actions_str.split(";"):
                        parts = action_str.split("|")
                        if len(parts) >= 3:
                            handler = parts[2].strip()
                            if handler not in ["client", "server"]:
                                logger.warning(f"Invalid handler '{handler}' in action, skipping")
                                continue

                            action = {
                                "label": parts[0].strip(),
                                "action": parts[1].strip(),
                                "handler": handler
                            }
                            if len(parts) > 3:
                                style = parts[3].strip()
                                if style in ["primary", "secondary", "warning"]:
                                    action["style"] = style
                            if len(parts) > 4:
                                try:
                                    action["data"] = json.loads(parts[4])
                                except:
                                    pass
                            actions.append(action)
                    result["suggested_actions"] = actions

        if current_payload_config is not None and payload_lines:
            self._parse_and_save_payload(result, current_payload_config, payload_lines)

        if message_lines:
            result["message"] = "\n".join(message_lines).strip()

        if not result["message"]:
            result["message"] = response_text

        return result

    def _parse_and_save_payload(self, result: Dict[str, Any], config: Any, payload_lines: list):
        """Parse a payload using its registered parser and save to result."""
        try:
            payload_text = "\n".join(payload_lines).strip()
            parsed_payload = config.parser(payload_text)
            if parsed_payload:
                result["custom_payload"] = parsed_payload
        except Exception as e:
            logger.warning(f"Failed to parse {config.type} payload: {e}")
