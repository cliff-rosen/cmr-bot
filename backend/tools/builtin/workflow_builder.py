"""
Workflow Builder Tool

A specialized agent that designs optimal multi-step workflows.
When the main agent decides a workflow is needed, it calls this tool
to get a well-designed plan that leverages advanced patterns like
MapReduce, parallel processing, and multi-source inputs.
"""

import json
import logging
import os
from typing import Any, Dict, Generator
from sqlalchemy.orm import Session
import anthropic

from tools.registry import ToolConfig, ToolResult, ToolProgress, register_tool

logger = logging.getLogger(__name__)

WORKFLOW_BUILDER_MODEL = "claude-sonnet-4-20250514"
WORKFLOW_BUILDER_MAX_TOKENS = 4096

# Comprehensive system prompt for the workflow builder agent
WORKFLOW_BUILDER_SYSTEM_PROMPT = """You are a Workflow Architect - a specialized agent that designs optimal multi-step workflows.

## Your Role
When given a complex task, you design a workflow plan that:
1. Breaks the task into logical steps
2. Chooses the best tools and patterns for each step
3. Optimizes for parallelism and efficiency
4. Structures data flow between steps

## Available Tools (for steps to use)

### Research & Information Gathering
- **deep_research**: Comprehensive research on a topic. Automatically searches, fetches pages, extracts info, and synthesizes findings. Use for single research topics.
- **web_search**: Quick web search. Returns search results with titles, URLs, snippets.
- **fetch_webpage**: Fetch and extract content from a URL.

### List Processing (VERY IMPORTANT)
- **iterate**: Process each item in a list with the same operation (LLM prompt or tool call). Runs in PARALLEL.
  - Use when: You need to apply the same operation to multiple items independently
  - Example: "Summarize each of these 5 documents"

- **map_reduce**: Two-phase processing: MAP each item in parallel, then REDUCE all results into one output.
  - Use when: You need to process multiple items AND combine/aggregate the results
  - Example: "Research 5 companies and compare them" → Map: research each, Reduce: synthesize comparison
  - Example: "Analyze these papers and identify common themes" → Map: extract themes from each, Reduce: find commonalities
  - THIS IS YOUR MOST POWERFUL TOOL FOR MULTI-ITEM TASKS WITH SYNTHESIS

### Memory & Assets
- **save_memory**: Save information to long-term memory
- **recall_memory**: Retrieve information from memory
- **list_assets**: List user's saved assets
- **get_asset**: Retrieve a specific asset

## Workflow Patterns

### Pattern 1: Simple Sequential
Use when steps must happen in order and each depends on the previous.
```
Step 1 → Step 2 → Step 3
```

### Pattern 2: Parallel Independent (use iterate)
Use when the same operation applies to multiple items independently.
```
[Item1, Item2, Item3] → iterate(operation) → [Result1, Result2, Result3]
```

### Pattern 3: MapReduce (use map_reduce)
Use when you need to process multiple items AND synthesize/aggregate results.
```
[Item1, Item2, Item3] → map(analyze each) → reduce(combine findings) → Final Result
```
**THIS IS CRITICAL**: When the user wants to research/analyze MULTIPLE things and get a COMBINED answer, use map_reduce!

### Pattern 4: Multi-Source Inputs
Steps can pull from multiple prior steps using `input_sources` array.
```
Step 1 (user input) ─┐
                     ├→ Step 3 (combines both)
Step 2 (user input) ─┘
```

## Output Format

Return a JSON workflow plan:
```json
{
  "title": "Short descriptive title",
  "goal": "What this workflow accomplishes",
  "steps": [
    {
      "description": "What this step does",
      "input_description": "What input this step needs",
      "input_sources": ["user"],  // or [1, 2] for prior steps, or ["user", 1]
      "output_description": "What this step produces",
      "method": {
        "approach": "How to accomplish this step",
        "tools": ["tool_name"],  // Tools this step should use
        "reasoning": "Why this approach"
      }
    }
  ]
}
```

## Decision Guide: When to Use What

| Scenario | Pattern | Why |
|----------|---------|-----|
| Research one topic deeply | deep_research | Single comprehensive research |
| Research N topics, report each | iterate + deep_research | Parallel independent research |
| Research N topics, COMPARE/COMBINE | map_reduce | Need synthesis across all |
| Analyze document | Single step | Just one item |
| Analyze N documents separately | iterate | Independent parallel analysis |
| Analyze N documents, find patterns | map_reduce | Need to aggregate findings |
| Transform a list | iterate | Apply same transform to each |
| Aggregate a list | map_reduce | Combine into summary/stats |

## Critical Rules

1. **ALWAYS use map_reduce** when the user wants to:
   - Compare multiple things
   - Find common themes/patterns across items
   - Aggregate or synthesize information from multiple sources
   - Get ONE answer derived from MANY inputs

2. **Use iterate** when:
   - Processing items independently
   - Each result stands alone
   - No combination/synthesis needed

3. **Multi-source inputs** when:
   - A step needs data from multiple prior steps
   - You're merging different types of information

4. Keep workflows concise - typically 2-4 steps
5. Prefer parallel processing when possible
6. Each step should have a clear, singular purpose

## Examples

### Example 1: "Compare AWS, GCP, and Azure for startups"
BAD: Three sequential research steps, then compare
GOOD: Single map_reduce step
```json
{
  "title": "Cloud Provider Comparison",
  "goal": "Compare AWS, GCP, and Azure for startup use cases",
  "steps": [
    {
      "description": "Research and compare cloud providers",
      "input_description": "List of cloud providers to compare",
      "input_sources": ["user"],
      "output_description": "Comparative analysis with recommendation",
      "method": {
        "approach": "Use map_reduce: map researches each provider's startup offerings, reduce synthesizes into comparison",
        "tools": ["map_reduce"],
        "reasoning": "map_reduce is ideal for researching multiple items and synthesizing findings"
      }
    }
  ]
}
```

### Example 2: "Summarize each of these 5 articles"
```json
{
  "title": "Article Summaries",
  "goal": "Create individual summaries for each article",
  "steps": [
    {
      "description": "Summarize each article",
      "input_description": "List of articles to summarize",
      "input_sources": ["user"],
      "output_description": "Individual summaries for each article",
      "method": {
        "approach": "Use iterate with LLM prompt to summarize each article independently",
        "tools": ["iterate"],
        "reasoning": "iterate is perfect for applying the same operation to multiple items without synthesis"
      }
    }
  ]
}
```

### Example 3: "Research quantum computing, then find companies working on it"
```json
{
  "title": "Quantum Computing Research & Companies",
  "goal": "Understand quantum computing and identify key players",
  "steps": [
    {
      "description": "Research quantum computing fundamentals",
      "input_description": "Topic: quantum computing",
      "input_sources": ["user"],
      "output_description": "Comprehensive overview of quantum computing",
      "method": {
        "approach": "Deep research on quantum computing concepts and state of the field",
        "tools": ["deep_research"],
        "reasoning": "Need thorough understanding before identifying companies"
      }
    },
    {
      "description": "Identify and research key companies",
      "input_description": "Quantum computing context from step 1",
      "input_sources": [1],
      "output_description": "Analysis of major quantum computing companies",
      "method": {
        "approach": "Use map_reduce to research each major company and compare their approaches",
        "tools": ["map_reduce"],
        "reasoning": "Multiple companies to research with comparison needed"
      }
    }
  ]
}
```

Now design an optimal workflow for the user's request. Think carefully about whether map_reduce should be used."""


def execute_design_workflow(
    params: Dict[str, Any],
    db: Session,
    user_id: int,
    context: Dict[str, Any]
) -> Generator[ToolProgress, None, ToolResult]:
    """
    Design an optimal workflow for a given goal.

    This is a specialized agent that creates workflow plans leveraging
    advanced patterns like MapReduce, parallel processing, etc.
    """
    goal = params.get("goal", "")
    initial_input = params.get("initial_input", "")
    constraints = params.get("constraints", "")

    if not goal:
        return ToolResult(text="Error: No goal provided for workflow design")

    yield ToolProgress(
        stage="analyzing",
        message="Analyzing task and designing workflow...",
        data={"goal": goal}
    )

    # Build the user prompt
    user_prompt = f"""Design an optimal workflow for this task:

**Goal**: {goal}
"""

    if initial_input:
        user_prompt += f"\n**Initial Input/Context**: {initial_input}\n"

    if constraints:
        user_prompt += f"\n**Constraints/Preferences**: {constraints}\n"

    user_prompt += """
Return ONLY the JSON workflow plan, no other text. The JSON should follow the exact format specified in your instructions."""

    try:
        client = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))

        response = client.messages.create(
            model=WORKFLOW_BUILDER_MODEL,
            max_tokens=WORKFLOW_BUILDER_MAX_TOKENS,
            temperature=0.3,
            system=WORKFLOW_BUILDER_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}]
        )

        response_text = response.content[0].text.strip()

        # Parse the JSON response
        workflow_plan = _parse_workflow_json(response_text)

        if not workflow_plan:
            yield ToolProgress(
                stage="error",
                message="Failed to parse workflow plan",
                data={"raw_response": response_text[:500]}
            )
            return ToolResult(
                text=f"Failed to parse workflow plan. Raw response:\n{response_text}",
                data={"error": "parse_error", "raw": response_text}
            )

        # Validate the workflow structure
        validation_errors = _validate_workflow(workflow_plan)
        if validation_errors:
            yield ToolProgress(
                stage="validation_warning",
                message=f"Workflow has validation issues: {', '.join(validation_errors)}",
                data={"errors": validation_errors}
            )

        yield ToolProgress(
            stage="complete",
            message=f"Designed workflow: {workflow_plan.get('title', 'Untitled')}",
            data={"steps": len(workflow_plan.get('steps', []))}
        )

        # Build the payload JSON that the agent should present to the user
        plan_payload = {
            "type": "plan",
            "title": workflow_plan.get("title", "Workflow Plan"),
            "goal": workflow_plan.get("goal", goal),
            "initial_input": initial_input or goal,
            "steps": workflow_plan.get("steps", [])
        }

        payload_json = json.dumps(plan_payload, indent=2)

        # Return with explicit instructions to present as payload
        return ToolResult(
            text=f"""I've designed a workflow plan for this task.

**IMPORTANT**: You must now present this plan to the user for approval. Include the following payload block at the end of your response:

```payload
{payload_json}
```

Briefly explain the workflow approach to the user, then include the payload above. Do NOT execute any steps yet - wait for the user to approve the plan first.""",
            data={
                "type": "workflow_plan",
                "workflow": workflow_plan,
                "payload": plan_payload
            }
        )

    except Exception as e:
        logger.error(f"Workflow design error: {e}", exc_info=True)
        yield ToolProgress(
            stage="error",
            message=f"Error designing workflow: {str(e)}",
            data={"error": str(e)}
        )
        return ToolResult(text=f"Error designing workflow: {str(e)}")


def _parse_workflow_json(text: str) -> Dict[str, Any] | None:
    """Parse JSON from LLM response, handling markdown code blocks."""
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
    except json.JSONDecodeError as e:
        logger.warning(f"JSON parse error: {e}")
        return None


def _validate_workflow(workflow: Dict[str, Any]) -> list[str]:
    """Validate workflow structure and return list of errors."""
    errors = []

    if not workflow.get("title"):
        errors.append("Missing title")

    if not workflow.get("goal"):
        errors.append("Missing goal")

    steps = workflow.get("steps", [])
    if not steps:
        errors.append("No steps defined")
        return errors

    for i, step in enumerate(steps):
        step_num = i + 1

        if not step.get("description"):
            errors.append(f"Step {step_num}: missing description")

        if not step.get("input_sources"):
            errors.append(f"Step {step_num}: missing input_sources")
        else:
            # Validate input_sources references
            for source in step.get("input_sources", []):
                if source != "user" and isinstance(source, int):
                    if source < 1 or source >= step_num:
                        errors.append(f"Step {step_num}: invalid input_source {source}")

        method = step.get("method", {})
        if not method.get("approach"):
            errors.append(f"Step {step_num}: missing method.approach")
        if not method.get("tools"):
            errors.append(f"Step {step_num}: missing method.tools")

    return errors


DESIGN_WORKFLOW_TOOL = ToolConfig(
    name="design_workflow",
    description="""Design an optimal multi-step workflow to accomplish a complex task.

Use this tool when:
- A task requires multiple coordinated steps
- Research or analysis of multiple items is needed
- Parallel processing could be beneficial
- Data needs to flow between steps

This tool is a specialized workflow architect that knows about advanced patterns like:
- MapReduce for processing lists and aggregating results
- Parallel iteration for independent operations
- Multi-source inputs for combining data from multiple steps

It will design an efficient workflow plan that can then be executed step by step.""",
    input_schema={
        "type": "object",
        "properties": {
            "goal": {
                "type": "string",
                "description": "The goal to accomplish with this workflow"
            },
            "initial_input": {
                "type": "string",
                "description": "Initial input or context for the workflow (optional)"
            },
            "constraints": {
                "type": "string",
                "description": "Any constraints or preferences for the workflow design (optional)"
            }
        },
        "required": ["goal"]
    },
    output_schema={
        "type": "object",
        "properties": {
            "type": {"type": "string", "const": "workflow_plan"},
            "workflow": {
                "type": "object",
                "description": "The designed workflow",
                "properties": {
                    "title": {"type": "string", "description": "Workflow title"},
                    "goal": {"type": "string", "description": "Workflow goal"},
                    "steps": {
                        "type": "array",
                        "description": "Workflow steps",
                        "items": {
                            "type": "object",
                            "properties": {
                                "description": {"type": "string"},
                                "input_description": {"type": "string"},
                                "input_sources": {"type": "array"},
                                "output_description": {"type": "string"},
                                "method": {
                                    "type": "object",
                                    "properties": {
                                        "approach": {"type": "string"},
                                        "tools": {"type": "array", "items": {"type": "string"}},
                                        "reasoning": {"type": "string"}
                                    }
                                }
                            }
                        }
                    }
                }
            },
            "payload": {
                "type": "object",
                "description": "Payload to present to user for approval"
            }
        },
        "required": ["type", "workflow", "payload"]
    },
    executor=execute_design_workflow,
    category="workflow",
    streaming=True
)


def register_workflow_builder_tools():
    """Register the workflow builder tool."""
    register_tool(DESIGN_WORKFLOW_TOOL)
    logger.info("Registered design_workflow tool")
