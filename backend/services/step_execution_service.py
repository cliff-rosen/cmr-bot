"""
Step Execution Service

A lightweight agent that executes individual workflow steps with fresh context.
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from sqlalchemy.orm import Session
import anthropic
import asyncio
import os
import logging

from services.chat_payloads import get_all_tools, ToolResult

logger = logging.getLogger(__name__)

STEP_MODEL = "claude-sonnet-4-20250514"
STEP_MAX_TOKENS = 4096
MAX_TOOL_ITERATIONS = 5


@dataclass
class StepAssignment:
    """What the main agent sends to the step executor."""
    step_number: int
    description: str
    input_data: str
    output_format: str
    available_tools: List[str]  # Tool names to enable


@dataclass
class StepResult:
    """What the step executor returns."""
    success: bool
    output: str
    content_type: str  # 'document', 'data', 'code'
    error: Optional[str] = None


class StepExecutionService:
    """Executes a single workflow step with fresh context."""

    def __init__(self, db: Session, user_id: int):
        self.db = db
        self.user_id = user_id
        self.async_client = anthropic.AsyncAnthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))

    async def execute(self, assignment: StepAssignment) -> StepResult:
        """Execute a step assignment and return the result."""
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

            system_prompt = f"""You are a task execution agent. Your only job is to complete the assigned task.

            ## Your Task
            {assignment.description}

            ## Input
            {assignment.input_data}

            ## Expected Output Format
            {assignment.output_format}

            ## Available Tools
            {tool_list}

            ## Guidelines
            - Focus ONLY on completing this specific task
            - Use tools as needed to gather information or perform actions
            - Return your final output clearly - this will be shown to the user
            - Do not ask questions or engage in conversation
            - If you cannot complete the task, explain why clearly
            """

            messages = [{"role": "user", "content": "Please execute the task described in your instructions."}]

            api_kwargs = {
                "model": STEP_MODEL,
                "max_tokens": STEP_MAX_TOKENS,
                "temperature": 0.5,
                "system": system_prompt,
                "messages": messages
            }
            if anthropic_tools:
                api_kwargs["tools"] = anthropic_tools

            # Execution loop
            iteration = 0
            collected_text = ""

            while iteration < MAX_TOOL_ITERATIONS:
                iteration += 1
                logger.info(f"Step execution iteration {iteration}")

                response = await self.async_client.messages.create(**api_kwargs)

                # Collect text
                for block in response.content:
                    if block.type == "text":
                        collected_text += block.text

                # Check for tool use
                tool_use_blocks = [b for b in response.content if b.type == "tool_use"]

                if not tool_use_blocks:
                    break

                # Handle tool call
                tool_block = tool_use_blocks[0]
                tool_name = tool_block.name
                tool_input = tool_block.input
                tool_use_id = tool_block.id

                logger.info(f"Step agent tool call: {tool_name}")

                tool_result_str = await self._execute_tool(
                    tool_name, tool_input, tools_by_name
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

            # Determine content type from output
            content_type = self._infer_content_type(collected_text, assignment.output_format)

            return StepResult(
                success=True,
                output=collected_text,
                content_type=content_type
            )

        except Exception as e:
            logger.error(f"Step execution error: {e}", exc_info=True)
            return StepResult(
                success=False,
                output="",
                content_type="document",
                error=str(e)
            )

    async def _execute_tool(
        self,
        tool_name: str,
        tool_input: Dict[str, Any],
        tools_by_name: Dict[str, Any]
    ) -> str:
        """Execute a tool and return result string."""
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

    def _infer_content_type(self, output: str, output_format: str) -> str:
        """Infer content type from output and format hint."""
        format_lower = output_format.lower()

        if any(word in format_lower for word in ['code', 'script', 'function', 'implementation']):
            return 'code'
        elif any(word in format_lower for word in ['data', 'json', 'list', 'table', 'structured']):
            return 'data'
        else:
            return 'document'
