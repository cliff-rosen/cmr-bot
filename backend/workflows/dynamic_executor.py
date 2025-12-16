"""
Dynamic Step Executor

Executes declarative StepDefinition nodes based on their step_type:

1. tool_call: Execute a specific tool with mapped inputs
   - Maps context fields to tool parameters
   - Calls the tool directly
   - Stores structured result

2. llm_transform: LLM transforms input to structured output
   - Gathers input fields from context
   - Calls LLM with structured output mode
   - Enforces output_schema

3. llm_decision: LLM makes enumerated choice
   - Gathers input fields from context
   - LLM must pick from choices list
   - Stores the decision for edge conditions
"""

import logging
import json
import re
from typing import AsyncGenerator, Union, Any, Dict, List

import anthropic

from schemas.workflow import (
    StepDefinition,
    StepOutput,
    StepProgress,
    WorkflowContext,
)
from tools.registry import get_tool, ToolResult, ToolProgress

logger = logging.getLogger(__name__)

# LLM configuration
EXECUTOR_MODEL = "claude-sonnet-4-20250514"
EXECUTOR_MAX_TOKENS = 4096

# Lazy-loaded client
_client = None


def _get_client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    return _client


async def execute_dynamic_step(
    step_def: StepDefinition,
    context: WorkflowContext
) -> AsyncGenerator[Union[StepProgress, StepOutput], None]:
    """
    Execute a declarative step definition based on its step_type.

    Routes to the appropriate executor:
    - tool_call -> _execute_tool_call
    - llm_transform -> _execute_llm_transform
    - llm_decision -> _execute_llm_decision

    Args:
        step_def: The declarative step definition
        context: The workflow runtime context

    Yields:
        StepProgress during execution
        StepOutput when complete
    """
    yield StepProgress(
        message=f"Starting: {step_def.name}",
        progress=0.0,
        details={"step_type": step_def.step_type}
    )

    try:
        if step_def.step_type == "tool_call":
            async for item in _execute_tool_call(step_def, context):
                yield item

        elif step_def.step_type == "llm_transform":
            async for item in _execute_llm_transform(step_def, context):
                yield item

        elif step_def.step_type == "llm_decision":
            async for item in _execute_llm_decision(step_def, context):
                yield item

        else:
            yield StepOutput(
                success=False,
                error=f"Unknown step_type: {step_def.step_type}"
            )

    except Exception as e:
        logger.exception(f"Error executing step {step_def.id}")
        yield StepOutput(
            success=False,
            error=str(e)
        )


# =============================================================================
# Tool Call Executor
# =============================================================================

async def _execute_tool_call(
    step_def: StepDefinition,
    context: WorkflowContext
) -> AsyncGenerator[Union[StepProgress, StepOutput], None]:
    """
    Execute a tool_call step.

    1. Resolve input_mapping templates with context values
    2. Call the tool with resolved parameters
    3. Store result in output_field
    """
    yield StepProgress(
        message=f"Preparing tool call: {step_def.tool}",
        progress=0.1
    )

    # Get the tool
    tool = get_tool(step_def.tool)
    if not tool:
        yield StepOutput(
            success=False,
            error=f"Tool '{step_def.tool}' not found"
        )
        return

    # Resolve input_mapping with context values
    params = _resolve_input_mapping(step_def.input_mapping or {}, context)

    yield StepProgress(
        message=f"Calling {step_def.tool}",
        progress=0.3,
        details={"params": _truncate_for_display(params)}
    )

    # Execute the tool
    try:
        result_data = None

        # Import execute_tool from registry
        from tools.registry import execute_tool

        async for item in execute_tool(
            step_def.tool,
            params,
            db=None,  # Tools may need DB - context should provide
            user_id=0,  # TODO: Get from context
            context={"workflow_instance_id": context.instance_id}
        ):
            if isinstance(item, ToolProgress):
                yield StepProgress(
                    message=item.message or f"Tool progress: {item.stage}",
                    progress=0.3 + (item.progress or 0) * 0.5,
                    details=item.data
                )
            elif isinstance(item, ToolResult):
                result_data = item.data if item.data else {"text": item.text}

        yield StepProgress(
            message=f"Completed: {step_def.tool}",
            progress=0.9
        )

        # Store in output_field
        if step_def.output_field:
            context.set_variable(step_def.output_field, result_data)

        yield StepOutput(
            success=True,
            data=result_data,
            display_title=step_def.name,
            display_content=_format_for_display(result_data),
            content_type="json"
        )

    except Exception as e:
        logger.exception(f"Tool execution error: {step_def.tool}")
        yield StepOutput(
            success=False,
            error=f"Tool execution failed: {str(e)}"
        )


def _resolve_input_mapping(
    mapping: Dict[str, str],
    context: WorkflowContext
) -> Dict[str, Any]:
    """
    Resolve input_mapping templates with context values.

    Templates use {field_name} syntax:
    - {"query": "{name} {company}"} with context {name: "John", company: "Acme"}
    - Resolves to {"query": "John Acme"}

    Non-template values are passed through:
    - {"max_results": "10"} -> {"max_results": "10"}
    """
    resolved = {}

    for param, template in mapping.items():
        if not isinstance(template, str):
            resolved[param] = template
            continue

        # Check if it's a template (contains {field})
        if '{' in template:
            result = template
            # Find all {field} patterns
            fields = re.findall(r'\{(\w+)\}', template)
            for field in fields:
                value = _get_context_value(field, context)
                if value is not None:
                    # Convert to string for template substitution
                    str_value = json.dumps(value) if isinstance(value, (dict, list)) else str(value)
                    result = result.replace(f'{{{field}}}', str_value)
            resolved[param] = result
        else:
            # Not a template - pass through (maybe convert numbers)
            resolved[param] = template

    return resolved


def _get_context_value(field: str, context: WorkflowContext) -> Any:
    """Get a value from context by field name."""
    # Check variables (where step outputs are stored)
    if field in context.variables:
        return context.variables[field]
    # Check step_data
    if field in context.step_data:
        return context.step_data[field]
    # Check initial_input
    if field in context.initial_input:
        return context.initial_input[field]
    return None


# =============================================================================
# LLM Transform Executor
# =============================================================================

async def _execute_llm_transform(
    step_def: StepDefinition,
    context: WorkflowContext
) -> AsyncGenerator[Union[StepProgress, StepOutput], None]:
    """
    Execute an llm_transform step.

    1. Gather input_fields from context
    2. Build prompt with goal and inputs
    3. Call LLM with structured output mode (enforces output_schema)
    4. Store result in output_field
    """
    yield StepProgress(
        message=f"Gathering inputs for {step_def.name}",
        progress=0.1
    )

    # Gather inputs
    inputs = _gather_inputs(step_def.input_fields, context)

    yield StepProgress(
        message=f"Running LLM transform: {step_def.name}",
        progress=0.3,
        details={"input_count": len(inputs)}
    )

    # Build the prompt
    prompt = _build_transform_prompt(step_def.goal or "", inputs)

    # Call LLM with structured output
    client = _get_client()

    try:
        # Use tool_use to enforce JSON schema output
        response = client.messages.create(
            model=EXECUTOR_MODEL,
            max_tokens=EXECUTOR_MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}],
            tools=[{
                "name": "output",
                "description": "Provide the structured output",
                "input_schema": step_def.output_schema or {"type": "object"}
            }],
            tool_choice={"type": "tool", "name": "output"}
        )

        # Extract the tool use result
        result_data = None
        for block in response.content:
            if block.type == "tool_use" and block.name == "output":
                result_data = block.input
                break

        if result_data is None:
            # Fallback: try to parse text response
            for block in response.content:
                if hasattr(block, 'text'):
                    result_data = _try_parse_json(block.text)
                    break

        yield StepProgress(
            message=f"Completed: {step_def.name}",
            progress=0.9
        )

        # Store in output_field
        if step_def.output_field and result_data is not None:
            context.set_variable(step_def.output_field, result_data)

        yield StepOutput(
            success=True,
            data=result_data,
            display_title=step_def.name,
            display_content=_format_for_display(result_data),
            content_type="json"
        )

    except Exception as e:
        logger.exception(f"LLM transform error: {step_def.name}")
        yield StepOutput(
            success=False,
            error=f"LLM transform failed: {str(e)}"
        )


def _gather_inputs(fields: List[str], context: WorkflowContext) -> Dict[str, Any]:
    """Gather specified fields from context."""
    inputs = {}
    for field in fields:
        value = _get_context_value(field, context)
        if value is not None:
            inputs[field] = value
    return inputs


def _build_transform_prompt(goal: str, inputs: Dict[str, Any]) -> str:
    """Build prompt for LLM transform."""
    prompt = f"**Goal:** {goal}\n\n"

    if inputs:
        prompt += "**Input Data:**\n\n"
        for key, value in inputs.items():
            if isinstance(value, (dict, list)):
                prompt += f"### {key}\n```json\n{json.dumps(value, indent=2)}\n```\n\n"
            else:
                prompt += f"### {key}\n{value}\n\n"

    prompt += "Analyze the input data and produce output matching the required schema."

    return prompt


# =============================================================================
# LLM Decision Executor
# =============================================================================

async def _execute_llm_decision(
    step_def: StepDefinition,
    context: WorkflowContext
) -> AsyncGenerator[Union[StepProgress, StepOutput], None]:
    """
    Execute an llm_decision step.

    1. Gather input_fields from context
    2. Build prompt with goal and choices
    3. LLM must select exactly one choice
    4. Store decision in output_field (for edge conditions)
    """
    yield StepProgress(
        message=f"Gathering inputs for decision: {step_def.name}",
        progress=0.1
    )

    # Gather inputs
    inputs = _gather_inputs(step_def.input_fields, context)

    yield StepProgress(
        message=f"Making decision: {step_def.name}",
        progress=0.3
    )

    # Build the prompt
    prompt = _build_decision_prompt(step_def.goal or "", inputs, step_def.choices)

    # Call LLM with structured output (enum choice)
    client = _get_client()

    try:
        response = client.messages.create(
            model=EXECUTOR_MODEL,
            max_tokens=256,  # Decisions should be short
            messages=[{"role": "user", "content": prompt}],
            tools=[{
                "name": "decide",
                "description": "Make a decision by selecting one of the valid choices",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "choice": {
                            "type": "string",
                            "enum": step_def.choices,
                            "description": "The selected choice"
                        },
                        "reasoning": {
                            "type": "string",
                            "description": "Brief explanation for the decision"
                        }
                    },
                    "required": ["choice"]
                }
            }],
            tool_choice={"type": "tool", "name": "decide"}
        )

        # Extract the decision
        decision = None
        reasoning = None
        for block in response.content:
            if block.type == "tool_use" and block.name == "decide":
                decision = block.input.get("choice")
                reasoning = block.input.get("reasoning")
                break

        if decision is None:
            yield StepOutput(
                success=False,
                error="LLM failed to make a decision"
            )
            return

        # Validate decision is in choices
        if decision not in step_def.choices:
            yield StepOutput(
                success=False,
                error=f"Invalid decision '{decision}'. Valid choices: {step_def.choices}"
            )
            return

        yield StepProgress(
            message=f"Decision: {decision}",
            progress=0.9,
            details={"choice": decision, "reasoning": reasoning}
        )

        # Store in output_field
        if step_def.output_field:
            context.set_variable(step_def.output_field, decision)

        result_data = {
            "choice": decision,
            "reasoning": reasoning
        }

        yield StepOutput(
            success=True,
            data=result_data,
            display_title=f"Decision: {decision}",
            display_content=reasoning or f"Selected: {decision}",
            content_type="text"
        )

    except Exception as e:
        logger.exception(f"LLM decision error: {step_def.name}")
        yield StepOutput(
            success=False,
            error=f"LLM decision failed: {str(e)}"
        )


def _build_decision_prompt(goal: str, inputs: Dict[str, Any], choices: List[str]) -> str:
    """Build prompt for LLM decision."""
    prompt = f"**Decision Required:** {goal}\n\n"

    if inputs:
        prompt += "**Context:**\n\n"
        for key, value in inputs.items():
            if isinstance(value, (dict, list)):
                prompt += f"### {key}\n```json\n{json.dumps(value, indent=2)}\n```\n\n"
            else:
                prompt += f"### {key}\n{value}\n\n"

    prompt += f"**Valid Choices:** {', '.join(choices)}\n\n"
    prompt += "Based on the context above, select exactly ONE of the valid choices."

    return prompt


# =============================================================================
# Helpers
# =============================================================================

def _try_parse_json(text: str) -> Any:
    """Try to parse JSON from text, handling markdown blocks."""
    text = text.strip()

    # Handle markdown code blocks
    if text.startswith("```"):
        lines = text.split("\n")
        start_idx = 1
        end_idx = len(lines)
        for i, line in enumerate(lines[1:], 1):
            if line.strip() == "```":
                end_idx = i
                break
        text = "\n".join(lines[start_idx:end_idx]).strip()
        if text.startswith("json"):
            text = text[4:].strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"text": text}


def _format_for_display(data: Any) -> str:
    """Format data for UI display."""
    if data is None:
        return "No output"
    if isinstance(data, dict):
        if "text" in data and len(data) == 1:
            return data["text"]
        return json.dumps(data, indent=2)
    if isinstance(data, list):
        return json.dumps(data, indent=2)
    return str(data)


def _truncate_for_display(data: Any, max_len: int = 200) -> Any:
    """Truncate data for logging/display."""
    if isinstance(data, str) and len(data) > max_len:
        return data[:max_len] + "..."
    if isinstance(data, dict):
        return {k: _truncate_for_display(v, max_len) for k, v in data.items()}
    if isinstance(data, list) and len(data) > 5:
        return data[:5] + ["..."]
    return data
