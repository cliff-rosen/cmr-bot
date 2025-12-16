"""
Dynamic Step Executor

Executes declarative StepDefinition nodes by:
1. Gathering inputs from context
2. Building a prompt
3. Running an LLM with specified tools
4. Storing results

This enables agent-created workflows where steps are defined as JSON data
rather than Python code.
"""

import logging
import json
from typing import AsyncGenerator, Union, Any, Dict, List

import anthropic

from schemas.workflow import (
    StepDefinition,
    StepOutput,
    StepProgress,
    WorkflowContext,
)

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
    Execute a declarative step definition.

    This is the generic executor that interprets StepDefinition data
    and runs the step using an LLM with tools.

    Args:
        step_def: The declarative step definition
        context: The workflow runtime context

    Yields:
        StepProgress during execution
        StepOutput when complete
    """
    yield StepProgress(
        message=f"Starting: {step_def.name}",
        progress=0.0
    )

    try:
        # Gather inputs from context
        inputs = _gather_inputs(step_def, context)

        yield StepProgress(
            message=f"Gathered inputs for {step_def.name}",
            progress=0.1,
            details={"input_fields": step_def.input_fields}
        )

        # Build the prompt
        prompt = _build_prompt(step_def, inputs)

        yield StepProgress(
            message=f"Executing: {step_def.name}",
            progress=0.2
        )

        # Execute based on mode
        if step_def.mode == "llm":
            result = await _execute_llm_only(step_def, prompt)
        elif step_def.mode == "tool":
            result = await _execute_tool_only(step_def, inputs, context)
        else:  # llm_with_tools
            result = await _execute_llm_with_tools(step_def, prompt, context)

        yield StepProgress(
            message=f"Completed: {step_def.name}",
            progress=0.9
        )

        # Store in output field if specified
        if step_def.output_field:
            context.set_variable(step_def.output_field, result)

        yield StepOutput(
            success=True,
            data=result,
            display_title=step_def.name,
            display_content=_format_result_for_display(result),
            content_type="markdown"
        )

    except Exception as e:
        logger.exception(f"Error executing dynamic step {step_def.id}")
        yield StepOutput(
            success=False,
            error=str(e)
        )


def _gather_inputs(step_def: StepDefinition, context: WorkflowContext) -> Dict[str, Any]:
    """Gather inputs from context based on input_fields."""
    inputs = {}

    # Always include initial_input
    inputs["user_query"] = context.initial_input.get("query", "")
    inputs["initial_input"] = context.initial_input

    # Gather specified input fields from step_data and variables
    for field in step_def.input_fields:
        # First check step_data (outputs from previous nodes)
        if field in context.step_data:
            inputs[field] = context.step_data[field]
        # Then check variables
        elif field in context.variables:
            inputs[field] = context.variables[field]
        # Check initial_input
        elif field in context.initial_input:
            inputs[field] = context.initial_input[field]
        else:
            inputs[field] = None

    return inputs


def _build_prompt(step_def: StepDefinition, inputs: Dict[str, Any]) -> str:
    """Build the execution prompt from template and inputs."""
    # Start with the goal
    prompt = f"**Goal:** {step_def.goal}\n\n"

    # Add instructions if provided
    if step_def.instructions:
        prompt += f"**Instructions:**\n{step_def.instructions}\n\n"

    # Add the prompt template with substituted values
    if step_def.prompt_template:
        try:
            # Simple string formatting
            template_prompt = step_def.prompt_template

            # Replace {field} placeholders with actual values
            for key, value in inputs.items():
                placeholder = f"{{{key}}}"
                if placeholder in template_prompt:
                    if isinstance(value, dict) or isinstance(value, list):
                        value_str = json.dumps(value, indent=2)
                    else:
                        value_str = str(value) if value is not None else ""
                    template_prompt = template_prompt.replace(placeholder, value_str)

            prompt += template_prompt
        except Exception as e:
            logger.warning(f"Error formatting prompt template: {e}")
            prompt += step_def.prompt_template

    # Add context from inputs
    if inputs:
        prompt += "\n\n**Available Context:**\n"
        for key, value in inputs.items():
            if value is not None and key not in ["initial_input"]:
                if isinstance(value, dict) or isinstance(value, list):
                    prompt += f"- {key}: {json.dumps(value, indent=2)[:500]}...\n"
                else:
                    prompt += f"- {key}: {str(value)[:500]}\n"

    return prompt


async def _execute_llm_only(step_def: StepDefinition, prompt: str) -> Any:
    """Execute step using LLM only (no tools)."""
    client = _get_client()

    response = client.messages.create(
        model=EXECUTOR_MODEL,
        max_tokens=EXECUTOR_MAX_TOKENS,
        messages=[{"role": "user", "content": prompt}]
    )

    result_text = response.content[0].text

    # Try to parse as JSON if it looks like JSON
    if result_text.strip().startswith("{") or result_text.strip().startswith("["):
        try:
            return json.loads(result_text)
        except json.JSONDecodeError:
            pass

    # Try to extract JSON from markdown code block
    if "```json" in result_text:
        try:
            json_str = result_text.split("```json")[1].split("```")[0].strip()
            return json.loads(json_str)
        except (IndexError, json.JSONDecodeError):
            pass

    return {"text": result_text}


async def _execute_tool_only(
    step_def: StepDefinition,
    inputs: Dict[str, Any],
    context: WorkflowContext
) -> Any:
    """Execute a single tool directly."""
    if not step_def.tools:
        raise ValueError("No tools specified for tool-only execution")

    tool_name = step_def.tools[0]

    # Import tool registry and execute
    from tools.registry import get_tool, execute_tool

    tool = get_tool(tool_name)
    if not tool:
        raise ValueError(f"Tool '{tool_name}' not found")

    # Build tool params from inputs
    # This is a simplified version - in production you'd want more sophisticated mapping
    params = inputs.copy()

    # Execute the tool
    result = None
    async for item in execute_tool(tool_name, params, None, context.instance_id, {}):
        if hasattr(item, "data"):
            result = item.data

    return result


async def _execute_llm_with_tools(
    step_def: StepDefinition,
    prompt: str,
    context: WorkflowContext
) -> Any:
    """Execute step using LLM with tool access."""
    if not step_def.tools:
        # No tools specified, fall back to LLM only
        return await _execute_llm_only(step_def, prompt)

    # For now, use LLM only with tool names mentioned in prompt
    # Full tool integration would require more complex implementation
    tool_hint = f"\n\n**Available tools you can describe using:** {', '.join(step_def.tools)}"

    return await _execute_llm_only(step_def, prompt + tool_hint)


def _format_result_for_display(result: Any) -> str:
    """Format result for display in UI."""
    if isinstance(result, dict):
        if "text" in result:
            return result["text"]
        return json.dumps(result, indent=2)
    elif isinstance(result, list):
        return json.dumps(result, indent=2)
    else:
        return str(result)
