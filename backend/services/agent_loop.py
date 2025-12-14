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
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional, Tuple, Union

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
class AgentMessage(AgentEvent):
    """Emitted when the agent produces a text response."""
    text: str
    iteration: int


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
# Internal Result Types (for helper generators)
# =============================================================================

@dataclass
class _ModelResult:
    """Final result from _call_model generator."""
    response: Any
    text: str


@dataclass
class _ToolsResult:
    """Final result from _process_tools generator."""
    tool_results: List[Dict]
    tool_records: List[Dict]


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
# Main Agent Loop
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
    context = context or {}
    cancellation_token = cancellation_token or CancellationToken()

    # Setup
    api_kwargs = _build_api_kwargs(model, max_tokens, temperature, system_prompt, messages, tools)
    collected_text = ""
    tool_call_history: List[Dict[str, Any]] = []

    yield AgentThinking(message="Starting...")

    try:
        for iteration in range(1, max_iterations + 1):
            if cancellation_token.is_cancelled:
                yield AgentCancelled(text=collected_text, tool_calls=tool_call_history)
                return

            logger.debug(f"Agent loop iteration {iteration}")

            # 1. Call model
            response = None
            async for event in _call_model(client, api_kwargs, stream_text, cancellation_token):
                if isinstance(event, _ModelResult):
                    response = event.response
                    collected_text += event.text
                else:
                    yield event

            if cancellation_token.is_cancelled:
                yield AgentCancelled(text=collected_text, tool_calls=tool_call_history)
                return

            # 2. Check for tool use
            tool_use_blocks = [b for b in response.content if b.type == "tool_use"]

            if not tool_use_blocks:
                logger.info(f"Agent loop complete after {iteration} iterations")
                yield AgentComplete(text=collected_text, tool_calls=tool_call_history)
                return

            # 3. Process tools
            tool_results = None
            async for event in _process_tools(
                tool_use_blocks, tools, db, user_id, context, cancellation_token
            ):
                if isinstance(event, _ToolsResult):
                    tool_results = event.tool_results
                    tool_call_history.extend(event.tool_records)
                else:
                    yield event

            # 4. Update messages for next iteration
            _append_tool_exchange(messages, response, tool_results)
            api_kwargs["messages"] = messages

            if stream_text:
                collected_text += "\n\n"
                yield AgentTextDelta(text="\n\n")

        # Max iterations reached
        logger.warning(f"Agent loop reached max iterations ({max_iterations})")
        yield AgentComplete(text=collected_text, tool_calls=tool_call_history)

    except asyncio.CancelledError:
        yield AgentCancelled(text=collected_text, tool_calls=tool_call_history)
    except Exception as e:
        logger.error(f"Agent loop error: {e}", exc_info=True)
        yield AgentError(
            error=_format_error_message(e),
            text=collected_text,
            tool_calls=tool_call_history
        )



# =============================================================================
# Helper: Call Model
# =============================================================================

async def _call_model(
    client: anthropic.AsyncAnthropic,
    api_kwargs: Dict,
    stream_text: bool,
    cancellation_token: CancellationToken
) -> AsyncGenerator[Union[AgentEvent, _ModelResult], None]:
    """
    Call the model and yield events.

    Yields:
        AgentTextDelta events (if streaming)
        AgentMessage event (if not streaming)
        _ModelResult as final item with response and collected text
    """
    collected_text = ""

    if stream_text:
        async with client.messages.stream(**api_kwargs) as stream:
            async for event in stream:
                if cancellation_token.is_cancelled:
                    raise asyncio.CancelledError("Cancelled during streaming")

                if hasattr(event, 'type'):
                    if event.type == 'content_block_delta' and hasattr(event, 'delta'):
                        if hasattr(event.delta, 'text'):
                            text = event.delta.text
                            collected_text += text
                            yield AgentTextDelta(text=text)

            response = await stream.get_final_message()
    else:
        response = await client.messages.create(**api_kwargs)

        for block in response.content:
            if hasattr(block, 'text'):
                collected_text += block.text

        if collected_text:
            yield AgentMessage(text=collected_text, iteration=0)

    yield _ModelResult(response=response, text=collected_text)


# =============================================================================
# Helper: Process Tools
# =============================================================================

async def _process_tools(
    tool_use_blocks: List,
    tools: Dict[str, ToolConfig],
    db: Session,
    user_id: int,
    context: Dict[str, Any],
    cancellation_token: CancellationToken
) -> AsyncGenerator[Union[AgentEvent, _ToolsResult], None]:
    """
    Process all tool calls and yield events.

    Yields:
        AgentToolStart, AgentToolProgress, AgentToolComplete events
        _ToolsResult as final item with results and records
    """
    tool_results = []
    tool_records = []

    for tool_block in tool_use_blocks:
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
        tool_workspace_payload = None

        if not tool_config:
            tool_result_str = f"Unknown tool: {tool_name}"
        elif tool_config.streaming:
            async for progress_or_result in execute_streaming_tool(
                tool_config, tool_input, db, user_id, context, cancellation_token
            ):
                if cancellation_token.is_cancelled:
                    raise asyncio.CancelledError(f"Tool {tool_name} cancelled")

                if isinstance(progress_or_result, ToolProgress):
                    yield AgentToolProgress(tool_name=tool_name, progress=progress_or_result)
                elif isinstance(progress_or_result, tuple):
                    tool_result_str, tool_result_data, tool_workspace_payload = progress_or_result
        else:
            tool_result_str, tool_result_data, tool_workspace_payload = await execute_tool(
                tool_config, tool_input, db, user_id, context
            )

        if cancellation_token.is_cancelled:
            raise asyncio.CancelledError("Cancelled after tool execution")

        # Record tool call
        tool_record = {
            "tool_name": tool_name,
            "input": tool_input,
            "output": tool_result_data if tool_result_data else tool_result_str
        }
        if tool_workspace_payload:
            tool_record["workspace_payload"] = tool_workspace_payload
        tool_records.append(tool_record)

        # Collect result for message
        tool_results.append({
            "type": "tool_result",
            "tool_use_id": tool_use_id,
            "content": tool_result_str
        })

        yield AgentToolComplete(
            tool_name=tool_name,
            result_text=tool_result_str,
            result_data=tool_result_data
        )

    yield _ToolsResult(tool_results=tool_results, tool_records=tool_records)


# =============================================================================
# Utility Functions
# =============================================================================

def _build_api_kwargs(
    model: str,
    max_tokens: int,
    temperature: float,
    system_prompt: str,
    messages: List[Dict],
    tools: Dict[str, ToolConfig]
) -> Dict:
    """Build kwargs for Anthropic API call."""
    api_kwargs = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "system": system_prompt,
        "messages": messages
    }

    if tools:
        api_kwargs["tools"] = [
            {
                "name": config.name,
                "description": config.description,
                "input_schema": config.input_schema
            }
            for config in tools.values()
        ]
        logger.info(f"Agent loop with {len(tools)} tools: {list(tools.keys())}")
    else:
        logger.warning("Agent loop with NO TOOLS")

    return api_kwargs


def _append_tool_exchange(messages: List[Dict], response: Any, tool_results: List[Dict]):
    """Append assistant content and tool results to messages."""
    assistant_content = []
    for block in response.content:
        if block.type == "text":
            assistant_content.append({"type": "text", "text": block.text})
        elif block.type == "tool_use":
            assistant_content.append({
                "type": "tool_use",
                "id": block.id,
                "name": block.name,
                "input": block.input
            })

    messages.append({"role": "assistant", "content": assistant_content})
    messages.append({"role": "user", "content": tool_results})


def _format_error_message(e: Exception) -> str:
    """Convert exception to user-friendly error message."""
    error_str = str(e)

    if "credit balance is too low" in error_str.lower():
        return "API credit balance is too low. Please add credits to your Anthropic account."
    elif "rate limit" in error_str.lower() or "429" in error_str:
        return "Rate limit exceeded. Please wait a moment and try again."
    elif "invalid_api_key" in error_str.lower() or "authentication" in error_str.lower():
        return "API authentication failed. Please check your API key configuration."
    elif "timeout" in error_str.lower():
        return "Request timed out. Please try again."
    elif "connection" in error_str.lower():
        return "Connection error. Please check your internet connection and try again."

    return error_str


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

        try:
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
                stream_text=False,
                temperature=temperature
            ):
                if on_event:
                    on_event(event)

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
        finally:
            await client.close()

        return final_text, final_tool_calls, error

    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(_run())
    finally:
        try:
            loop.run_until_complete(loop.shutdown_asyncgens())
        except Exception:
            pass
        loop.close()
