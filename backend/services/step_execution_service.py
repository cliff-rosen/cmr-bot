"""
Step Execution Service

A lightweight agent that executes individual workflow steps with fresh context.
Streams status updates via SSE for real-time feedback.

Uses the generic agent_loop for the agentic processing.
"""

from typing import Any, Dict, List, Optional, AsyncGenerator
from dataclasses import dataclass, field
from datetime import datetime
from sqlalchemy.orm import Session
import anthropic
import os
import logging
import json

from tools import get_all_tools
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

STEP_MODEL = "claude-sonnet-4-20250514"
STEP_MAX_TOKENS = 4096
MAX_TOOL_ITERATIONS = 10


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class StepInputSource:
    """Input from a single source."""
    content: str
    data: Optional[Any] = None


@dataclass
class StepAssignment:
    """What the main agent sends to the step executor."""
    step_number: int
    description: str
    input_data: Dict[str, StepInputSource]
    output_format: str
    available_tools: List[str]


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
    content_type: str
    data: Optional[Any] = None
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
    status: str
    message: str
    tool_name: Optional[str] = None
    tool_input: Optional[Dict[str, Any]] = None
    tool_output: Optional[str] = None
    tool_progress: Optional[ToolProgressUpdate] = None
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
            data["tool_output"] = self.tool_output[:500] if self.tool_output else None
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
                "data": self.result.data,
                "tool_calls": [
                    {"tool_name": tc.tool_name, "input": tc.input, "output": tc.output[:500] if tc.output else ""}
                    for tc in self.result.tool_calls
                ],
                "error": self.result.error
            }
        return json.dumps(data)


# =============================================================================
# Service
# =============================================================================

class StepExecutionService:
    """Executes a single workflow step with fresh context."""

    def __init__(self, db: Session, user_id: int):
        self.db = db
        self.user_id = user_id
        self.async_client = anthropic.AsyncAnthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))

    async def execute_streaming(
        self,
        assignment: StepAssignment,
        cancellation_token: Optional[CancellationToken] = None
    ) -> AsyncGenerator[StepStatusUpdate, None]:
        """Execute a step assignment, yielding status updates along the way."""
        tool_calls: List[ToolCallRecord] = []
        last_tool_data = None

        try:
            # Get tools
            all_tools = get_all_tools()
            enabled_set = set(assignment.available_tools)
            tools = {t.name: t for t in all_tools if t.name in enabled_set}

            tool_list = ", ".join(assignment.available_tools) if assignment.available_tools else "None"

            # Format input data
            input_dict = {}
            for key, source in assignment.input_data.items():
                input_dict[key] = {
                    "content": source.content,
                    **({"data": source.data} if source.data is not None else {})
                }
            input_section = json.dumps(input_dict, indent=2)

            current_date = datetime.now().strftime("%Y-%m-%d")

            system_prompt = f"""You are a task execution agent. Execute the task and return ONLY the output.

            **IMPORTANT - Current Date: {current_date}** (Use this date for all time-relative references.)

            ## Task
            {assignment.description}

            ## Input Data (JSON with named sources)
            {input_section}

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

            # Run the agent loop
            collected_text = ""
            async for event in run_agent_loop(
                client=self.async_client,
                model=STEP_MODEL,
                max_tokens=STEP_MAX_TOKENS,
                max_iterations=MAX_TOOL_ITERATIONS,
                system_prompt=system_prompt,
                messages=messages,
                tools=tools,
                db=self.db,
                user_id=self.user_id,
                context={},
                cancellation_token=cancellation_token,
                stream_text=False,
                temperature=0.5
            ):
                # Map AgentEvent to StepStatusUpdate
                update = self._map_event_to_status(event, tool_calls)
                if update:
                    yield update

                # Track state from events
                if isinstance(event, AgentToolComplete):
                    tool_calls.append(ToolCallRecord(
                        tool_name=event.tool_name,
                        input={},  # Not tracked in event
                        output=event.result_text
                    ))
                    if event.result_data is not None:
                        last_tool_data = event.result_data

                elif isinstance(event, (AgentComplete, AgentCancelled)):
                    collected_text = event.text

                elif isinstance(event, AgentError):
                    collected_text = event.text
                    result = StepResult(
                        success=False,
                        output="",
                        content_type="document",
                        tool_calls=tool_calls,
                        error=event.error
                    )
                    yield StepStatusUpdate(
                        status="error",
                        message=event.error,
                        result=result
                    )
                    return

            # If we didn't get text but have tool calls, ask for synthesis
            if not collected_text.strip() and tool_calls:
                yield StepStatusUpdate(
                    status="thinking",
                    message="Synthesizing results..."
                )

                # Add synthesis request
                messages.append({
                    "role": "user",
                    "content": "Now compile and return the final output based on all the information gathered. Return ONLY the deliverable content."
                })

                # Call without tools to force text response
                response = await self.async_client.messages.create(
                    model=STEP_MODEL,
                    max_tokens=STEP_MAX_TOKENS,
                    temperature=0.5,
                    system=system_prompt,
                    messages=messages
                )
                for block in response.content:
                    if hasattr(block, 'text'):
                        collected_text += block.text

            # Determine content type
            content_type = self._infer_content_type(collected_text, assignment.output_format)
            result_data = last_tool_data if content_type == 'data' else None

            # Yield final result
            result = StepResult(
                success=True,
                output=collected_text,
                content_type=content_type,
                data=result_data,
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

    def _map_event_to_status(
        self,
        event: AgentEvent,
        tool_calls: List[ToolCallRecord]
    ) -> Optional[StepStatusUpdate]:
        """Map an AgentEvent to a StepStatusUpdate."""
        if isinstance(event, AgentThinking):
            return StepStatusUpdate(
                status="thinking",
                message=event.message
            )

        elif isinstance(event, AgentToolStart):
            return StepStatusUpdate(
                status="tool_start",
                message=f"Running {event.tool_name}...",
                tool_name=event.tool_name,
                tool_input=event.tool_input
            )

        elif isinstance(event, AgentToolProgress):
            return StepStatusUpdate(
                status="tool_progress",
                message=event.progress.message,
                tool_name=event.tool_name,
                tool_progress=ToolProgressUpdate(
                    stage=event.progress.stage,
                    message=event.progress.message,
                    data=event.progress.data,
                    progress=event.progress.progress
                )
            )

        elif isinstance(event, AgentToolComplete):
            return StepStatusUpdate(
                status="tool_complete",
                message=f"Completed {event.tool_name}",
                tool_name=event.tool_name,
                tool_output=event.result_text
            )

        elif isinstance(event, AgentCancelled):
            return StepStatusUpdate(
                status="cancelled",
                message="Step execution cancelled"
            )

        # AgentComplete and AgentError are handled in the main loop
        return None

    def _infer_content_type(self, output: str, output_format: str) -> str:
        """Infer content type from output and format hint."""
        format_lower = output_format.lower()

        if any(word in format_lower for word in ['code', 'script', 'function', 'implementation']):
            return 'code'
        elif any(word in format_lower for word in ['data', 'json', 'list', 'table', 'structured']):
            return 'data'
        else:
            return 'document'
