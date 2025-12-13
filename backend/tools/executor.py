"""
Tool Execution Utilities

Contains common logic used by both step_execution_service and general_chat_service
for executing tools (both streaming and non-streaming).
"""

import asyncio
import types
import logging
from dataclasses import dataclass
from typing import Any, Coroutine, Dict, AsyncGenerator, Optional, Tuple, TypeVar, Union, TYPE_CHECKING

from tools.registry import ToolResult, ToolProgress, ToolConfig

if TYPE_CHECKING:
    from services.general_chat_service import CancellationToken

logger = logging.getLogger(__name__)

T = TypeVar('T')


@dataclass
class ToolExecutionResult:
    """Result of executing a tool (streaming or non-streaming)."""
    text: str
    data: Optional[Dict[str, Any]]
    success: bool
    error: Optional[str] = None


def _consume_tool_generator(generator) -> ToolExecutionResult:
    """
    Consume a streaming tool generator and return the final result.

    Handles both generators that YIELD ToolResult and those that RETURN ToolResult.
    Also checks the result's data.success field to determine if the tool reported failure.

    Args:
        generator: A generator from a streaming tool executor

    Returns:
        ToolExecutionResult with the tool's output and success status
    """
    final_result = None

    try:
        while True:
            item = next(generator)
            if isinstance(item, ToolResult):
                final_result = item
            # ToolProgress items are ignored when consuming synchronously
    except StopIteration as e:
        # The generator's return value is in e.value
        if e.value is not None:
            if isinstance(e.value, ToolResult):
                final_result = e.value
            elif isinstance(e.value, str):
                final_result = ToolResult(text=e.value, data=None)

    if final_result:
        # Check if tool indicated failure in its data
        success = True
        error = None
        if final_result.data and isinstance(final_result.data, dict):
            if final_result.data.get("success") is False:
                success = False
                error = final_result.data.get("error") or final_result.data.get("reason") or "Tool reported failure"
        return ToolExecutionResult(
            text=final_result.text,
            data=final_result.data,
            success=success,
            error=error
        )
    else:
        return ToolExecutionResult(
            text="",
            data=None,
            success=False,
            error="Tool returned no result"
        )


def execute_tool_sync(
    tool_config: ToolConfig,
    tool_input: Dict[str, Any],
    db: Any,
    user_id: int,
    context: Optional[Dict[str, Any]] = None
) -> ToolExecutionResult:
    """
    Execute a tool synchronously and return the result.

    Handles both streaming (generator) and non-streaming tools.

    Args:
        tool_config: The tool configuration
        tool_input: Parameters to pass to the tool
        db: Database session
        user_id: Current user ID
        context: Optional execution context

    Returns:
        ToolExecutionResult with the tool's output and success status
    """
    try:
        result = tool_config.executor(tool_input, db, user_id, context or {})

        # Handle streaming tools (generators)
        if hasattr(result, '__iter__') and hasattr(result, '__next__'):
            return _consume_tool_generator(result)
        elif isinstance(result, ToolResult):
            # Check if tool indicated failure in its data
            success = True
            error = None
            if result.data and isinstance(result.data, dict):
                if result.data.get("success") is False:
                    success = False
                    error = result.data.get("error") or result.data.get("reason") or "Tool reported failure"
            return ToolExecutionResult(text=result.text, data=result.data, success=success, error=error)
        elif isinstance(result, str):
            return ToolExecutionResult(text=result, data=None, success=True)
        else:
            return ToolExecutionResult(text=str(result), data=None, success=True)

    except Exception as e:
        logger.error(f"Tool execution error: {e}", exc_info=True)
        return ToolExecutionResult(text="", data=None, success=False, error=str(e))


async def execute_streaming_tool(
    tool_config: ToolConfig,
    tool_input: Dict[str, Any],
    db: Any,
    user_id: int,
    context: Dict[str, Any],
    cancellation_token: Optional["CancellationToken"] = None
) -> AsyncGenerator[Union[ToolProgress, Tuple[str, Any]], None]:
    """
    Execute a streaming tool, yielding progress updates and finally the result.

    This is shared logic for handling streaming tools that yield ToolProgress
    updates before returning a final ToolResult.

    Args:
        tool_config: The tool configuration with executor function
        tool_input: Parameters to pass to the tool
        db: Database session
        user_id: Current user ID
        context: Additional execution context
        cancellation_token: Optional token to check for cancellation

    Yields:
        ToolProgress instances for progress updates, then a final (text, data) tuple
    """
    try:
        # Add cancellation token to context so tools can check it
        execution_context = {
            **context,
            "cancellation_token": cancellation_token
        }

        # Get the generator from the tool executor
        def run_generator():
            return tool_config.executor(
                tool_input,
                db,
                user_id,
                execution_context
            )

        generator = await asyncio.to_thread(run_generator)

        # If it's a generator, iterate through it
        if isinstance(generator, types.GeneratorType):
            final_result = None

            # Sentinel to indicate StopIteration (can't propagate through asyncio.to_thread)
            _STOP = object()

            def get_next_safe():
                """Get next item, returning sentinel tuple on StopIteration."""
                try:
                    return (next(generator), None)
                except StopIteration as e:
                    return (_STOP, e.value)

            while True:
                # Check for cancellation between iterations
                if cancellation_token and cancellation_token.is_cancelled:
                    logger.info("Tool execution cancelled")
                    yield ("Operation cancelled", None)
                    return

                item, return_value = await asyncio.to_thread(get_next_safe)

                if item is _STOP:
                    # Generator finished - return_value is the final result
                    if return_value is not None:
                        if isinstance(return_value, ToolResult):
                            logger.debug(f"Streaming tool completed with ToolResult: {return_value.text[:100] if return_value.text else '(empty)'}...")
                            yield (return_value.text, return_value.data)
                        elif isinstance(return_value, str):
                            logger.debug(f"Streaming tool completed with string: {return_value[:100]}...")
                            yield (return_value, None)
                        else:
                            logger.warning(f"Streaming tool returned unexpected type: {type(return_value)}")
                            yield (str(return_value), None)
                    elif final_result:
                        logger.debug(f"Streaming tool completed with collected result: {final_result.text[:100] if final_result.text else '(empty)'}...")
                        yield (final_result.text, final_result.data)
                    else:
                        logger.warning("Streaming tool completed with no result")
                        yield ("", None)
                    return

                # Yield progress updates
                if isinstance(item, ToolProgress):
                    logger.info(f"execute_streaming_tool yielding ToolProgress: {item.stage} - {item.message}")
                    yield item
                elif isinstance(item, ToolResult):
                    final_result = item
        else:
            # Not a generator - treat as regular result
            if isinstance(generator, ToolResult):
                yield (generator.text, generator.data)
            elif isinstance(generator, str):
                yield (generator, None)
            else:
                yield (str(generator), None)

    except Exception as e:
        logger.error(f"Streaming tool execution error: {e}", exc_info=True)
        yield (f"Error executing tool: {str(e)}", None)


async def execute_tool(
    tool_config: ToolConfig,
    tool_input: Dict[str, Any],
    db: Any,
    user_id: int,
    context: Dict[str, Any]
) -> Tuple[str, Any]:
    """
    Execute a non-streaming tool and return the result.

    Args:
        tool_config: The tool configuration with executor function
        tool_input: Parameters to pass to the tool
        db: Database session
        user_id: Current user ID
        context: Additional execution context

    Returns:
        Tuple of (result_text, result_data)
    """
    try:
        tool_result = await asyncio.to_thread(
            tool_config.executor,
            tool_input,
            db,
            user_id,
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


def run_async(coro: Coroutine[Any, Any, T]) -> T:
    """
    Run an async coroutine from a sync context.

    This is used by tool executors that need to call async services
    (like SearchService, WebRetrievalService) from their sync executor functions.

    Uses asyncio.run() which properly creates and cleans up an event loop.
    This is safe because tool executors run in a separate thread via asyncio.to_thread().

    Args:
        coro: The coroutine to run

    Returns:
        The result of the coroutine
    """
    return asyncio.run(coro)

