"""
Step Execution Service

A lightweight agent that executes individual workflow steps with fresh context.
Streams status updates via SSE for real-time feedback.
"""

from typing import Dict, Any, List, Optional, AsyncGenerator, Generator
from dataclasses import dataclass, field
from sqlalchemy.orm import Session
import anthropic
import asyncio
import os
import logging
import json
import types

from services.chat_payloads import get_all_tools, ToolResult, ToolProgress

logger = logging.getLogger(__name__)

STEP_MODEL = "claude-sonnet-4-20250514"
STEP_MAX_TOKENS = 4096
MAX_TOOL_ITERATIONS = 10  # Allow more iterations for complex tasks


@dataclass
class StepAssignment:
    """What the main agent sends to the step executor."""
    step_number: int
    description: str
    input_data: str
    output_format: str
    available_tools: List[str]  # Tool names to enable


@dataclass
class ToolCallRecord:
    """Record of a tool call made during execution."""
    tool_name: str
    input: Dict[str, Any]
    output: str


@dataclass
class StepResult:
    """What the step executor returns."""
    success: bool
    output: str
    content_type: str  # 'document', 'data', 'code'
    tool_calls: List[ToolCallRecord] = field(default_factory=list)
    error: Optional[str] = None


@dataclass
class ToolProgressUpdate:
    """Progress update from within a streaming tool."""
    stage: str
    message: str
    data: Optional[Dict[str, Any]] = None
    progress: Optional[float] = None


@dataclass
class StepStatusUpdate:
    """A status update during step execution."""
    status: str  # 'thinking', 'tool_start', 'tool_progress', 'tool_complete', 'complete', 'error'
    message: str
    tool_name: Optional[str] = None
    tool_input: Optional[Dict[str, Any]] = None
    tool_output: Optional[str] = None
    # Tool progress (only on 'tool_progress')
    tool_progress: Optional[ToolProgressUpdate] = None
    # Final result (only on 'complete')
    result: Optional[StepResult] = None

    def to_json(self) -> str:
        data = {
            "status": self.status,
            "message": self.message
        }
        if self.tool_name:
            data["tool_name"] = self.tool_name
        if self.tool_input:
            data["tool_input"] = self.tool_input
        if self.tool_output:
            data["tool_output"] = self.tool_output[:500] if self.tool_output else None  # Truncate for status
        if self.tool_progress:
            data["tool_progress"] = {
                "stage": self.tool_progress.stage,
                "message": self.tool_progress.message,
                "data": self.tool_progress.data,
                "progress": self.tool_progress.progress
            }
        if self.result:
            data["result"] = {
                "success": self.result.success,
                "output": self.result.output,
                "content_type": self.result.content_type,
                "tool_calls": [
                    {"tool_name": tc.tool_name, "input": tc.input, "output": tc.output[:500] if tc.output else ""}
                    for tc in self.result.tool_calls
                ],
                "error": self.result.error
            }
        return json.dumps(data)


class StepExecutionService:
    """Executes a single workflow step with fresh context."""

    def __init__(self, db: Session, user_id: int):
        self.db = db
        self.user_id = user_id
        self.async_client = anthropic.AsyncAnthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))

    async def execute_streaming(self, assignment: StepAssignment) -> AsyncGenerator[StepStatusUpdate, None]:
        """Execute a step assignment, yielding status updates along the way."""
        tool_calls: List[ToolCallRecord] = []

        try:
            # Get tools
            all_tools = get_all_tools()
            enabled_set = set(assignment.available_tools)
            tools = [t for t in all_tools if t.name in enabled_set]
            tools_by_name = {t.name: t for t in tools}

            anthropic_tools = [
                {
                    "name": t.name,
                    "description": t.description,
                    "input_schema": t.input_schema
                }
                for t in tools
            ] if tools else None

            tool_list = ", ".join(assignment.available_tools) if assignment.available_tools else "None"

            system_prompt = f"""You are a task execution agent. Execute the task and return ONLY the output.

            ## Task
            {assignment.description}

            ## Input Data
            {assignment.input_data}

            ## Required Output
            {assignment.output_format}

            ## Available Tools
            {tool_list}

            ## CRITICAL RULES
            1. DO NOT describe what you will do - just DO IT
            2. DO NOT say "I'll research..." or "Let me..." - USE THE TOOLS NOW
            3. Your response must BE the deliverable, not a description of it
            4. If tools are available and needed, call them IMMEDIATELY
            5. Return the actual content/data requested, not commentary about it

            WRONG: "I'll search for Beatles albums and compile a list..."
            RIGHT: [Actually call web_search, then return the compiled list]
            """

            messages = [{"role": "user", "content": "Execute now. Return only the deliverable."}]

            api_kwargs = {
                "model": STEP_MODEL,
                "max_tokens": STEP_MAX_TOKENS,
                "temperature": 0.5,
                "system": system_prompt,
                "messages": messages
            }
            if anthropic_tools:
                api_kwargs["tools"] = anthropic_tools

            # Initial status
            yield StepStatusUpdate(
                status="thinking",
                message="Starting step execution..."
            )

            # Execution loop
            iteration = 0
            collected_text = ""

            while iteration < MAX_TOOL_ITERATIONS:
                iteration += 1
                logger.info(f"Step execution iteration {iteration}")

                response = await self.async_client.messages.create(**api_kwargs)

                # Collect text from this response
                for block in response.content:
                    if block.type == "text":
                        collected_text += block.text

                # Check for tool use
                tool_use_blocks = [b for b in response.content if b.type == "tool_use"]

                if not tool_use_blocks:
                    # No more tool calls - we're done
                    break

                # Handle tool call
                tool_block = tool_use_blocks[0]
                tool_name = tool_block.name
                tool_input = tool_block.input
                tool_use_id = tool_block.id

                logger.info(f"Step agent tool call: {tool_name}")

                # Yield tool start status
                yield StepStatusUpdate(
                    status="tool_start",
                    message=f"Running {tool_name}...",
                    tool_name=tool_name,
                    tool_input=tool_input
                )

                # Execute the tool (may be streaming)
                tool_config = tools_by_name.get(tool_name)
                tool_result_str = ""

                if tool_config and tool_config.streaming:
                    # Streaming tool - yields progress updates
                    async for progress_or_result in self._execute_streaming_tool(
                        tool_name, tool_input, tools_by_name
                    ):
                        if isinstance(progress_or_result, ToolProgress):
                            # Yield progress update
                            yield StepStatusUpdate(
                                status="tool_progress",
                                message=progress_or_result.message,
                                tool_name=tool_name,
                                tool_progress=ToolProgressUpdate(
                                    stage=progress_or_result.stage,
                                    message=progress_or_result.message,
                                    data=progress_or_result.data,
                                    progress=progress_or_result.progress
                                )
                            )
                        else:
                            # Final result
                            tool_result_str = progress_or_result
                else:
                    # Non-streaming tool
                    tool_result_str = await self._execute_tool(
                        tool_name, tool_input, tools_by_name
                    )

                # Record the tool call
                tool_calls.append(ToolCallRecord(
                    tool_name=tool_name,
                    input=tool_input,
                    output=tool_result_str
                ))

                # Yield tool complete status
                yield StepStatusUpdate(
                    status="tool_complete",
                    message=f"Completed {tool_name}",
                    tool_name=tool_name,
                    tool_output=tool_result_str
                )

                # Add to messages for next iteration
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
                messages.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": tool_use_id,
                        "content": tool_result_str
                    }]
                })
                api_kwargs["messages"] = messages

            # If we exited because of iteration limit but haven't got text output,
            # make one more call asking for synthesis
            if not collected_text.strip() and tool_calls:
                yield StepStatusUpdate(
                    status="thinking",
                    message="Synthesizing results..."
                )

                # Add a message asking for synthesis
                messages.append({
                    "role": "user",
                    "content": "Now compile and return the final output based on all the information gathered. Return ONLY the deliverable content."
                })
                api_kwargs["messages"] = messages

                # Remove tools to force text response
                if "tools" in api_kwargs:
                    del api_kwargs["tools"]

                response = await self.async_client.messages.create(**api_kwargs)
                for block in response.content:
                    if block.type == "text":
                        collected_text += block.text

            # Determine content type from output
            content_type = self._infer_content_type(collected_text, assignment.output_format)

            # Yield final result
            result = StepResult(
                success=True,
                output=collected_text,
                content_type=content_type,
                tool_calls=tool_calls
            )
            yield StepStatusUpdate(
                status="complete",
                message="Step completed",
                result=result
            )

        except Exception as e:
            logger.error(f"Step execution error: {e}", exc_info=True)
            result = StepResult(
                success=False,
                output="",
                content_type="document",
                tool_calls=tool_calls,
                error=str(e)
            )
            yield StepStatusUpdate(
                status="error",
                message=str(e),
                result=result
            )

    async def _execute_tool(
        self,
        tool_name: str,
        tool_input: Dict[str, Any],
        tools_by_name: Dict[str, Any]
    ) -> str:
        """Execute a non-streaming tool and return result string."""
        tool_config = tools_by_name.get(tool_name)

        if not tool_config:
            return f"Unknown tool: {tool_name}"

        try:
            context = {}  # Fresh context for step execution
            tool_result = await asyncio.to_thread(
                tool_config.executor,
                tool_input,
                self.db,
                self.user_id,
                context
            )

            if isinstance(tool_result, ToolResult):
                return tool_result.text
            elif isinstance(tool_result, str):
                return tool_result
            else:
                return str(tool_result)

        except Exception as e:
            logger.error(f"Tool execution error: {e}", exc_info=True)
            return f"Error executing tool: {str(e)}"

    async def _execute_streaming_tool(
        self,
        tool_name: str,
        tool_input: Dict[str, Any],
        tools_by_name: Dict[str, Any]
    ) -> AsyncGenerator[ToolProgress | str, None]:
        """Execute a streaming tool, yielding progress updates and final result."""
        tool_config = tools_by_name.get(tool_name)

        if not tool_config:
            yield f"Unknown tool: {tool_name}"
            return

        try:
            context = {}  # Fresh context for step execution

            # Get the generator from the tool
            def run_generator():
                return tool_config.executor(
                    tool_input,
                    self.db,
                    self.user_id,
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

                try:
                    while True:
                        item, return_value = await asyncio.to_thread(get_next_safe)

                        if item is _STOP:
                            # Generator finished
                            if return_value is not None:
                                if isinstance(return_value, ToolResult):
                                    final_result = return_value.text
                                elif isinstance(return_value, str):
                                    final_result = return_value
                                else:
                                    final_result = str(return_value)
                            break

                        if isinstance(item, ToolProgress):
                            yield item
                        elif isinstance(item, ToolResult):
                            final_result = item.text
                except Exception as e:
                    logger.error(f"Streaming tool iteration error: {e}", exc_info=True)
                    yield f"Error during tool execution: {str(e)}"
                    return

                yield final_result or ""
            else:
                # Not a generator - treat as regular result
                if isinstance(generator, ToolResult):
                    yield generator.text
                elif isinstance(generator, str):
                    yield generator
                else:
                    yield str(generator)

        except Exception as e:
            logger.error(f"Streaming tool execution error: {e}", exc_info=True)
            yield f"Error executing tool: {str(e)}"

    def _infer_content_type(self, output: str, output_format: str) -> str:
        """Infer content type from output and format hint."""
        format_lower = output_format.lower()

        if any(word in format_lower for word in ['code', 'script', 'function', 'implementation']):
            return 'code'
        elif any(word in format_lower for word in ['data', 'json', 'list', 'table', 'structured']):
            return 'data'
        else:
            return 'document'
