"""
Workflow Builder Tool

A specialized agent that designs graph-based workflows that can be executed
by the workflow engine. Creates declarative workflow definitions with:
- StepNodes (execute or checkpoint)
- Edges (with optional conditions)
- StepDefinitions (declarative step configs)
"""

import json
import logging
import os
import textwrap
from typing import Any, Dict, Generator
from sqlalchemy.orm import Session
import anthropic

from tools.registry import ToolConfig, ToolResult, ToolProgress, register_tool, get_tool, get_all_tools
from schemas.workflow import WorkflowGraph, StepNode, StepDefinition, Edge, CheckpointConfig, CheckpointAction


def _tool_exists(tool_name: str) -> bool:
    """Check if a tool exists in the tool registry."""
    return get_tool(tool_name) is not None


def _get_available_tools_description() -> str:
    """
    Build a description of available tools for workflow steps.

    Excludes tools that don't make sense inside workflow steps
    (like design_workflow itself, or agent management tools).
    """
    # Tools to exclude from workflow steps
    excluded_tools = {
        "design_workflow",  # Can't nest workflow design
        "create_agent",     # Agent management
        "update_agent",
        "delete_agent",
        "list_agents",
    }

    tools = get_all_tools()
    available = [t for t in tools if t.name not in excluded_tools]

    if not available:
        return "No tools currently available."

    lines = []
    for t in available:
        # Truncate long descriptions
        desc = t.description
        if len(desc) > 150:
            desc = desc[:147] + "..."
        lines.append(f"- **{t.name}**: {desc}")

    return "\n".join(lines)

logger = logging.getLogger(__name__)

WORKFLOW_BUILDER_MODEL = "claude-sonnet-4-20250514"
WORKFLOW_BUILDER_MAX_TOKENS = 4096
MAX_VALIDATION_RETRIES = 2


def _build_system_prompt(available_tools: str) -> str:
    """Build the system prompt with dynamic tool list."""
    return textwrap.dedent(f"""\
        You are a Workflow Architect that designs executable graph-based workflows.

        ## CRITICAL: Output Format

        You MUST output ONLY valid JSON matching this EXACT schema. No other text.

        ## Required JSON Structure

        ```json
        {{
          "id": "string (snake_case identifier)",
          "name": "string (human readable name)",
          "description": "string (what this workflow does)",
          "nodes": {{
            "node_id": {{
              "id": "node_id (must match key)",
              "name": "string",
              "description": "string",
              "node_type": "execute" | "checkpoint",
              "step_definition": {{...}},  // REQUIRED for execute nodes
              "checkpoint_config": {{...}}  // REQUIRED for checkpoint nodes
            }}
          }},
          "edges": [
            {{"from_node": "node_id", "to_node": "node_id"}}
          ],
          "entry_node": "node_id (must exist in nodes)",
          "input_schema": {{
            "type": "object",
            "properties": {{"field_name": {{"type": "string", "description": "..."}}}},
            "required": ["field_name"]
          }}
        }}
        ```

        ## Execute Node step_definition (REQUIRED fields)

        ```json
        {{
          "id": "string",
          "name": "string",
          "description": "string",
          "goal": "string (what this step accomplishes)",
          "tools": ["tool_name"],
          "input_fields": ["field_name"],
          "output_field": "field_name",
          "mode": "llm_with_tools"
        }}
        ```

        ## Checkpoint Node checkpoint_config (REQUIRED fields)

        ```json
        {{
          "title": "string",
          "description": "string",
          "allowed_actions": ["approve", "edit", "reject"],
          "editable_fields": ["field_name"]
        }}
        ```

        ## DATA FLOW RULES (CRITICAL)

        Each step's `input_fields` MUST reference fields that exist when the step runs:

        1. **input_schema fields**: Available from workflow start (e.g., "query" if in input_schema)
        2. **Previous step output_field**: Available after that step completes

        Example valid data flow:
        - input_schema defines: "query"
        - Step A: input_fields=["query"], output_field="search_results"
        - Step B: input_fields=["query", "search_results"], output_field="analysis"

        INVALID: Referencing a field that doesn't exist or comes from a later step.

        ## Available Tools

        Steps can use these tools (specify in step_definition.tools array):

        {available_tools}

        Use `"tools": []` for steps that only need LLM reasoning without tools.

        ## Design Principles

        1. Add checkpoints after significant steps for user review
        2. Keep step goals focused - one clear objective per step
        3. 2-5 execute nodes is typical
        4. Ensure data flows correctly between steps

        ## Example

        ```json
        {{
          "id": "research_topic",
          "name": "Research Topic",
          "description": "Research a topic and compile findings",
          "nodes": {{
            "search": {{
              "id": "search",
              "name": "Search for Information",
              "description": "Search the web for relevant information",
              "node_type": "execute",
              "step_definition": {{
                "id": "search",
                "name": "Search",
                "description": "Search for information",
                "goal": "Find relevant information about the topic",
                "tools": ["web_search"],
                "input_fields": ["query"],
                "output_field": "search_results",
                "mode": "llm_with_tools"
              }}
            }},
            "review": {{
              "id": "review",
              "name": "Review Results",
              "description": "User reviews search results",
              "node_type": "checkpoint",
              "checkpoint_config": {{
                "title": "Review Search Results",
                "description": "Review the search results before proceeding",
                "allowed_actions": ["approve", "edit", "reject"],
                "editable_fields": ["search_results"]
              }}
            }},
            "summarize": {{
              "id": "summarize",
              "name": "Summarize Findings",
              "description": "Create a summary of the research",
              "node_type": "execute",
              "step_definition": {{
                "id": "summarize",
                "name": "Summarize",
                "description": "Summarize the findings",
                "goal": "Create a clear summary of the research findings",
                "tools": [],
                "input_fields": ["query", "search_results"],
                "output_field": "summary",
                "mode": "llm_with_tools"
              }}
            }}
          }},
          "edges": [
            {{"from_node": "search", "to_node": "review"}},
            {{"from_node": "review", "to_node": "summarize"}}
          ],
          "entry_node": "search",
          "input_schema": {{
            "type": "object",
            "properties": {{
              "query": {{"type": "string", "description": "The research topic"}}
            }},
            "required": ["query"]
          }}
        }}
        ```

        Output ONLY the JSON workflow. No explanations, no markdown.""")


def execute_design_workflow(
    params: Dict[str, Any],
    db: Session,
    user_id: int,
    context: Dict[str, Any]
) -> Generator[ToolProgress, None, ToolResult]:
    """
    Design an executable graph-based workflow for a given goal.

    Creates a WorkflowGraph that can be executed by the workflow engine.
    Includes validation retry loop to fix errors.
    """
    goal = params.get("goal", "")
    initial_input = params.get("initial_input", "")
    constraints = params.get("constraints", "")

    if not goal:
        return ToolResult(text="Error: No goal provided for workflow design")

    yield ToolProgress(
        stage="analyzing",
        message="Designing executable workflow graph...",
        data={"goal": goal}
    )

    # Get available tools dynamically
    available_tools = _get_available_tools_description()
    system_prompt = _build_system_prompt(available_tools)

    # Build the initial user prompt
    user_prompt = f"Design an executable workflow graph for this task:\n\n**Goal**: {goal}"
    if initial_input:
        user_prompt += f"\n\n**Initial Input/Context**: {initial_input}"
    if constraints:
        user_prompt += f"\n\n**Constraints/Preferences**: {constraints}"

    try:
        client = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))

        # Conversation messages for retry loop
        messages = [{"role": "user", "content": user_prompt}]

        workflow_data = None
        validation_errors = []

        # Retry loop for validation
        for attempt in range(MAX_VALIDATION_RETRIES + 1):
            response = client.messages.create(
                model=WORKFLOW_BUILDER_MODEL,
                max_tokens=WORKFLOW_BUILDER_MAX_TOKENS,
                temperature=0.2 if attempt == 0 else 0.1,  # Lower temp on retries
                system=system_prompt,
                messages=messages
            )

            response_text = response.content[0].text.strip()

            # Parse the JSON response
            workflow_data = _parse_workflow_json(response_text)

            if not workflow_data:
                if attempt < MAX_VALIDATION_RETRIES:
                    yield ToolProgress(
                        stage="retrying",
                        message=f"Failed to parse JSON (attempt {attempt + 1}), retrying...",
                        data={"attempt": attempt + 1}
                    )
                    # Add retry message to conversation
                    messages.append({"role": "assistant", "content": response_text})
                    messages.append({
                        "role": "user",
                        "content": "That response was not valid JSON. Please output ONLY the JSON workflow with no other text or markdown formatting."
                    })
                    continue
                else:
                    yield ToolProgress(
                        stage="error",
                        message="Failed to parse workflow graph after retries",
                        data={"raw_response": response_text[:500]}
                    )
                    return ToolResult(
                        text=f"Failed to parse workflow graph. Raw response:\n{response_text}",
                        data={"error": "parse_error", "raw": response_text}
                    )

            # Validate the workflow
            try:
                workflow_graph = WorkflowGraph.from_dict(workflow_data)
                validation_errors = workflow_graph.validate()
                data_flow_errors = workflow_graph.validate_data_flow(tool_validator=_tool_exists)
                validation_errors.extend(data_flow_errors)
            except Exception as e:
                validation_errors = [f"Schema error: {str(e)}"]

            if not validation_errors:
                # Valid workflow!
                yield ToolProgress(
                    stage="validated",
                    message="Workflow validated successfully",
                    data={"attempt": attempt + 1}
                )
                break

            # Validation failed - retry if we have attempts left
            if attempt < MAX_VALIDATION_RETRIES:
                yield ToolProgress(
                    stage="validation_failed",
                    message=f"Validation errors found (attempt {attempt + 1}), fixing...",
                    data={
                        "errors": validation_errors,
                        "attempt": attempt + 1
                    }
                )

                # Add the workflow and error feedback to conversation
                messages.append({"role": "assistant", "content": response_text})
                error_list = "\n".join(f"- {e}" for e in validation_errors)
                error_feedback = textwrap.dedent(f"""\
                    Your workflow has validation errors that must be fixed:

                    {error_list}

                    Please fix these issues and output the corrected JSON workflow. Remember:
                    - input_fields must reference fields from input_schema OR output_field from previous steps
                    - tools must be from the available tools list
                    - All required fields must be present""")
                messages.append({"role": "user", "content": error_feedback})
            else:
                # Out of retries - report the errors
                yield ToolProgress(
                    stage="validation_warning",
                    message=f"Workflow has {len(validation_errors)} validation issue(s) after {MAX_VALIDATION_RETRIES + 1} attempts",
                    data={"errors": validation_errors}
                )

        if not workflow_data:
            return ToolResult(
                text="Failed to design a valid workflow after multiple attempts.",
                data={"error": "design_failed"}
            )

        yield ToolProgress(
            stage="complete",
            message=f"Designed workflow: {workflow_data.get('name', 'Untitled')}",
            data={"nodes": len(workflow_data.get('nodes', {})), "validation_errors": len(validation_errors)}
        )

        # Build a summary for the user
        nodes = workflow_data.get("nodes", {})
        edges = workflow_data.get("edges", [])

        summary = f"## Workflow: {workflow_data.get('name', 'Untitled')}\n\n"
        summary += f"{workflow_data.get('description', '')}\n\n"
        summary += f"### Steps ({len(nodes)} nodes)\n\n"

        for node_id, node in nodes.items():
            node_type_icon = "⚙️" if node.get("node_type") == "execute" else "⏸️"
            summary += f"- {node_type_icon} **{node.get('name', node_id)}**: {node.get('description', '')}\n"

        summary += f"\n### Flow\n"
        summary += f"Entry: `{workflow_data.get('entry_node', 'unknown')}`\n"
        for edge in edges:
            arrow = f"{edge.get('from_node')} → {edge.get('to_node')}"
            if edge.get('condition_expr'):
                arrow += f" (if {edge.get('condition_expr')})"
            summary += f"- {arrow}\n"

        # Build payload for workspace view
        workflow_payload = {
            "type": "workflow_graph",
            "title": workflow_data.get('name', 'Workflow Design'),
            "content": summary,
            "workflow_graph_data": workflow_data
        }

        result_text = f"I've designed an executable workflow graph.\n\n{summary}\n\n**To execute this workflow**, you can run it from the workspace panel to test it."
        return ToolResult(
            text=result_text,
            data={
                "type": "workflow_graph",
                "workflow": workflow_data,
                "summary": summary
            },
            workspace_payload=workflow_payload
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


DESIGN_WORKFLOW_TOOL = ToolConfig(
    name="design_workflow",
    description=textwrap.dedent("""\
        Design an executable graph-based workflow to accomplish a complex task.

        Use this tool when:
        - A task requires multiple coordinated steps
        - User review/approval is needed at certain stages
        - The workflow should be reusable as a template

        This tool creates an executable workflow graph with:
        - Execute nodes: Steps that perform work using LLM + tools
        - Checkpoint nodes: Pause points for user review
        - Edges with conditions: Support for loops and branching

        The workflow can be executed by the workflow engine with real-time progress updates."""),
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
            "type": {"type": "string", "const": "workflow_graph"},
            "workflow": {
                "type": "object",
                "description": "The designed workflow graph",
                "properties": {
                    "id": {"type": "string"},
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "nodes": {"type": "object"},
                    "edges": {"type": "array"},
                    "entry_node": {"type": "string"}
                }
            },
            "summary": {"type": "string", "description": "Human-readable summary"}
        },
        "required": ["type", "workflow"]
    },
    executor=execute_design_workflow,
    category="workflow",
    streaming=True
)


def register_workflow_builder_tools():
    """Register the workflow builder tool."""
    register_tool(DESIGN_WORKFLOW_TOOL)
    logger.info("Registered design_workflow tool")
