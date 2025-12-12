"""
Shared utilities for tool execution.

Contains common logic used by both step_execution_service and general_chat_service.
"""

import asyncio
import types
import logging
from typing import Any, Dict, AsyncGenerator, Tuple, Union

from services.chat_payloads import ToolResult, ToolProgress, ToolConfig

logger = logging.getLogger(__name__)


async def execute_streaming_tool(
    tool_config: ToolConfig,
    tool_input: Dict[str, Any],
    db: Any,
    user_id: int,
    context: Dict[str, Any]
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

    Yields:
        ToolProgress instances for progress updates, then a final (text, data) tuple
    """
    try:
        # Get the generator from the tool executor
        def run_generator():
            return tool_config.executor(
                tool_input,
                db,
                user_id,
                context
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
                item, return_value = await asyncio.to_thread(get_next_safe)

                if item is _STOP:
                    # Generator finished - return_value is the final result
                    if return_value is not None:
                        if isinstance(return_value, ToolResult):
                            yield (return_value.text, return_value.data)
                        elif isinstance(return_value, str):
                            yield (return_value, None)
                        else:
                            yield (str(return_value), None)
                    elif final_result:
                        yield (final_result.text, final_result.data)
                    else:
                        yield ("", None)
                    return

                # Yield progress updates
                if isinstance(item, ToolProgress):
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
