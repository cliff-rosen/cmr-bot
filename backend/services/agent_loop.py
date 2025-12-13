"""
Generic Agentic Loop

A reusable async generator that runs an agentic loop with tool support.
Emits typed events that consumers can map to their specific output format.

Used by:
- GeneralChatService (SSE streaming)
- StepExecutionService (step status updates)
- Iterator tool (per-item agent processing)
"""

import asyncio
import logging
import os
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional, Tuple

import anthropic
from sqlalchemy.orm import Session

from tools import ToolConfig, ToolProgress, execute_streaming_tool, execute_tool

logger = logging.getLogger(__name__)


# =============================================================================
# Event Types
# =============================================================================

@dataclass
class AgentEvent:
    """Base class for events emitted during agentic loop."""
    pass


@dataclass
class AgentThinking(AgentEvent):
    """Emitted at start of loop or when processing."""
    message: str


@dataclass
class AgentTextDelta(AgentEvent):
    """Emitted when streaming text (only when stream_text=True)."""
    text: str


@dataclass
class AgentToolStart(AgentEvent):
    """Emitted when starting a tool call."""
    tool_name: str
    tool_input: Dict[str, Any]
    tool_use_id: str


@dataclass
class AgentToolProgress(AgentEvent):
    """Emitted during streaming tool execution."""
    tool_name: str
    progress: ToolProgress


@dataclass
class AgentToolComplete(AgentEvent):
    """Emitted when a tool call completes."""
    tool_name: str
    result_text: str
    result_data: Any


@dataclass
class AgentComplete(AgentEvent):
    """Emitted when the agent loop completes successfully."""
    text: str
    tool_calls: List[Dict[str, Any]]


@dataclass
class AgentCancelled(AgentEvent):
    """Emitted when the agent loop is cancelled."""
    text: str
    tool_calls: List[Dict[str, Any]]


@dataclass
class AgentError(AgentEvent):
    """Emitted when an error occurs."""
    error: str
    text: str = ""
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)


# =============================================================================
# Cancellation Token
# =============================================================================

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


# =============================================================================
# Main Agent Loop (Async)
# =============================================================================

async def run_agent_loop(
    client: anthropic.AsyncAnthropic,
    model: str,
    max_tokens: int,
    max_iterations: int,
    system_prompt: str,
    messages: List[Dict],
    tools: Dict[str, ToolConfig],
    db: Session,
    user_id: int,
    context: Optional[Dict[str, Any]] = None,
    cancellation_token: Optional[CancellationToken] = None,
    stream_text: bool = False,
    temperature: float = 0.7
) -> AsyncGenerator[AgentEvent, None]:
    """
    Generic agentic loop that yields events.

    Args:
        client: Anthropic async client
        model: Model to use (e.g., "claude-sonnet-4-20250514")
        max_tokens: Maximum tokens per response
        max_iterations: Maximum tool call iterations
        system_prompt: System prompt for the agent
        messages: Initial message history
        tools: Dict mapping tool name -> ToolConfig
        db: Database session
        user_id: User ID for tool execution
        context: Additional context passed to tool executors
        cancellation_token: Optional token to check for cancellation
        stream_text: If True, yield AgentTextDelta events for streaming
        temperature: Model temperature

    Yields:
        AgentEvent subclasses representing loop progress
    """
    if context is None:
        context = {}

    if cancellation_token is None:
        cancellation_token = CancellationToken()

    # Build Anthropic tools format
    anthropic_tools = [
        {
            "name": config.name,
            "description": config.description,
            "input_schema": config.input_schema
        }
        for config in tools.values()
    ] if tools else None

    # API kwargs
    api_kwargs = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "system": system_prompt,
        "messages": messages
    }
    if anthropic_tools:
        api_kwargs["tools"] = anthropic_tools

    # State
    iteration = 0
    collected_text = ""
    tool_call_history: List[Dict[str, Any]] = []

    yield AgentThinking(message="Starting...")

    try:
        while iteration < max_iterations:
            # Check for cancellation at start of each iteration
            if cancellation_token.is_cancelled:
                logger.info("Agent loop cancelled")
                yield AgentCancelled(text=collected_text, tool_calls=tool_call_history)
                return

            iteration += 1
            logger.debug(f"Agent loop iteration {iteration}")

            if stream_text:
                # Streaming mode - yield text deltas
                async with client.messages.stream(**api_kwargs) as stream:
                    async for event in stream:
                        # Check for cancellation during streaming
                        if cancellation_token.is_cancelled:
                            logger.info("Agent cancelled during streaming")
                            yield AgentCancelled(text=collected_text, tool_calls=tool_call_history)
                            return

                        if hasattr(event, 'type'):
                            if event.type == 'content_block_delta' and hasattr(event, 'delta'):
                                if hasattr(event.delta, 'text'):
                                    text = event.delta.text
                                    collected_text += text
                                    yield AgentTextDelta(text=text)

                    response = await stream.get_final_message()
            else:
                # Non-streaming mode - just get the response
                response = await client.messages.create(**api_kwargs)

                # Collect text from response
                for block in response.content:
                    if hasattr(block, 'text'):
                        collected_text += block.text

            # Check for cancellation after API call
            if cancellation_token.is_cancelled:
                yield AgentCancelled(text=collected_text, tool_calls=tool_call_history)
                return

            # Check for tool use
            tool_use_blocks = [b for b in response.content if b.type == "tool_use"]

            if not tool_use_blocks:
                # No tool calls - we're done
                logger.info(f"Agent loop complete after {iteration} iterations")
                yield AgentComplete(text=collected_text, tool_calls=tool_call_history)
                return

            # Handle tool calls (process first one)
            tool_block = tool_use_blocks[0]
            tool_name = tool_block.name
            tool_input = tool_block.input
            tool_use_id = tool_block.id

            logger.info(f"Agent tool call: {tool_name}")

            yield AgentToolStart(
                tool_name=tool_name,
                tool_input=tool_input,
                tool_use_id=tool_use_id
            )

            # Execute tool
            tool_config = tools.get(tool_name)
            tool_result_str = ""
            tool_result_data = None

            if not tool_config:
                tool_result_str = f"Unknown tool: {tool_name}"
            elif tool_config.streaming:
                # Streaming tool - yield progress updates
                async for progress_or_result in execute_streaming_tool(
                    tool_config, tool_input, db, user_id, context, cancellation_token
                ):
                    # Check cancellation between progress updates
                    if cancellation_token.is_cancelled:
                        logger.info(f"Tool {tool_name} cancelled")
                        yield AgentCancelled(text=collected_text, tool_calls=tool_call_history)
                        return

                    if isinstance(progress_or_result, ToolProgress):
                        yield AgentToolProgress(
                            tool_name=tool_name,
                            progress=progress_or_result
                        )
                    elif isinstance(progress_or_result, tuple):
                        tool_result_str, tool_result_data = progress_or_result
            else:
                # Non-streaming tool
                tool_result_str, tool_result_data = await execute_tool(
                    tool_config, tool_input, db, user_id, context
                )

            # Check cancellation after tool execution
            if cancellation_token.is_cancelled:
                yield AgentCancelled(text=collected_text, tool_calls=tool_call_history)
                return

            # Record tool call
            tool_call_history.append({
                "tool_name": tool_name,
                "input": tool_input,
                "output": tool_result_data if tool_result_data else tool_result_str
            })

            yield AgentToolComplete(
                tool_name=tool_name,
                result_text=tool_result_str,
                result_data=tool_result_data
            )

            # Add tool interaction to messages
            assistant_content = _format_assistant_content(response.content)
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

            # Add separator to collected text if streaming
            if stream_text:
                separator = "\n\n"
                collected_text += separator
                yield AgentTextDelta(text=separator)

        # Max iterations reached
        logger.warning(f"Agent loop reached max iterations ({max_iterations})")
        yield AgentComplete(text=collected_text, tool_calls=tool_call_history)

    except asyncio.CancelledError:
        yield AgentCancelled(text=collected_text, tool_calls=tool_call_history)
    except Exception as e:
        logger.error(f"Agent loop error: {e}", exc_info=True)
        yield AgentError(
            error=str(e),
            text=collected_text,
            tool_calls=tool_call_history
        )


def _format_assistant_content(response_content: list) -> list:
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


# =============================================================================
# Synchronous Wrapper (for use in ThreadPoolExecutor)
# =============================================================================

def run_agent_loop_sync(
    model: str,
    max_tokens: int,
    max_iterations: int,
    system_prompt: str,
    messages: List[Dict],
    tools: Dict[str, ToolConfig],
    db: Session,
    user_id: int,
    context: Optional[Dict[str, Any]] = None,
    cancellation_token: Optional[CancellationToken] = None,
    temperature: float = 0.7,
    on_event: Optional[Callable[[AgentEvent], None]] = None
) -> Tuple[str, List[Dict[str, Any]], Optional[str]]:
    """
    Synchronous wrapper for run_agent_loop.

    Runs the async agent loop in a new event loop. Safe to call from
    ThreadPoolExecutor threads which have no existing event loop.

    Args:
        ... (same as run_agent_loop, minus client and stream_text)
        on_event: Optional callback called with each AgentEvent

    Returns:
        Tuple of (final_text, tool_calls, error_or_none)
    """
    async def _run() -> Tuple[str, List[Dict[str, Any]], Optional[str]]:
        client = anthropic.AsyncAnthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
        final_text = ""
        final_tool_calls: List[Dict[str, Any]] = []
        error: Optional[str] = None

        async for event in run_agent_loop(
            client=client,
            model=model,
            max_tokens=max_tokens,
            max_iterations=max_iterations,
            system_prompt=system_prompt,
            messages=messages,
            tools=tools,
            db=db,
            user_id=user_id,
            context=context,
            cancellation_token=cancellation_token,
            stream_text=False,  # No streaming in sync mode
            temperature=temperature
        ):
            # Call event callback if provided
            if on_event:
                on_event(event)

            # Extract final state from terminal events
            if isinstance(event, AgentComplete):
                final_text = event.text
                final_tool_calls = event.tool_calls
            elif isinstance(event, AgentCancelled):
                final_text = event.text
                final_tool_calls = event.tool_calls
                error = "cancelled"
            elif isinstance(event, AgentError):
                final_text = event.text
                final_tool_calls = event.tool_calls
                error = event.error

        return final_text, final_tool_calls, error

    # Run in a new event loop (safe in ThreadPoolExecutor threads)
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_run())
    finally:
        loop.close()
