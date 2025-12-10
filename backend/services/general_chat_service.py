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
            system_prompt = self._build_system_prompt(request.context)
            user_prompt = request.message

            # Build message history
            messages = [
                {"role": msg.role, "content": msg.content}
                for msg in request.conversation_history
            ]
            messages.append({"role": "user", "content": user_prompt})

            # Get all available tools
            tools = get_all_tools()
            tools_by_name = {tool.name: tool for tool in tools}
            anthropic_tools = get_tools_for_anthropic() if tools else None

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

                if tool_use_blocks:
                    # Handle tool call
                    tool_block = tool_use_blocks[0]
                    tool_name = tool_block.name
                    tool_input = tool_block.input
                    tool_use_id = tool_block.id

                    logger.info(f"Tool call: {tool_name} with input: {tool_input}")

                    # Send tool status
                    tool_status = ChatStatusResponse(
                        status=f"Using {tool_name}...",
                        payload={"tool": tool_name},
                        error=None,
                        debug=None
                    )
                    yield tool_status.model_dump_json()

                    # Execute tool
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
                                tool_output_data = tool_result.data
                            elif isinstance(tool_result, str):
                                tool_result_str = tool_result
                                tool_output_data = None
                            else:
                                tool_result_str = str(tool_result)
                                tool_output_data = None

                        except Exception as e:
                            logger.error(f"Tool execution error: {e}", exc_info=True)
                            tool_result_str = f"Error executing tool: {str(e)}"
                            tool_output_data = None
                    else:
                        tool_result_str = f"Unknown tool: {tool_name}"
                        tool_output_data = None

                    # Record tool call in history
                    tool_call_history.append({
                        "tool_name": tool_name,
                        "input": tool_input,
                        "output": tool_output_data if tool_output_data else tool_result_str
                    })

                    # Add tool interaction to messages for next iteration
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
                    messages.append({
                        "role": "assistant",
                        "content": assistant_content
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

                    # Update api_kwargs with new messages for next iteration
                    api_kwargs["messages"] = messages

                    # Reset collected_text for next iteration (tool responses get new text)
                    collected_text = ""
                    continue

                else:
                    # No tool call - we're done
                    logger.info(f"No tool call, response complete. Collected text length: {len(collected_text)}")
                    break

            # Build final payload
            logger.info(f"Building final payload with collected_text length: {len(collected_text)}, tool_calls: {len(tool_call_history)}")
            final_payload = ChatResponsePayload(
                message=collected_text,
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

    def _build_system_prompt(self, context: Dict[str, Any]) -> str:
        """Build the system prompt for the primary agent."""

        # Get list of available tools for the prompt
        tools = get_all_tools()
        tool_descriptions = "\n".join([
            f"- **{t.name}**: {t.description}"
            for t in tools
        ])

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

        ## Context

        The user is interacting with you through the main chat interface. The workspace panel on the right can display assets and results from your work together.

        Remember: You have real capabilities. Use them to actually help, not just to describe what you could theoretically do.
        """
