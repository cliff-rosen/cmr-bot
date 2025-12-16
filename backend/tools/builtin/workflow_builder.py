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
from typing import Any, Dict, Generator
from sqlalchemy.orm import Session
import anthropic

from tools.registry import ToolConfig, ToolResult, ToolProgress, register_tool
from schemas.workflow import WorkflowGraph, StepNode, StepDefinition, Edge, CheckpointConfig, CheckpointAction

logger = logging.getLogger(__name__)

WORKFLOW_BUILDER_MODEL = "claude-sonnet-4-20250514"
WORKFLOW_BUILDER_MAX_TOKENS = 4096

# Comprehensive system prompt for the workflow builder agent
WORKFLOW_BUILDER_SYSTEM_PROMPT = """You are a Workflow Architect - a specialized agent that designs executable graph-based workflows.

## Your Role
You design EXECUTABLE graph-based workflows that:
1. Can be run by the workflow engine
2. Include checkpoints for user review
3. Use declarative step definitions (not code)
4. Support loops and branching via edge conditions

## Workflow Structure

Workflows are DIRECTED GRAPHS with:
- **Nodes**: Either "execute" (do something) or "checkpoint" (wait for user)
- **Edges**: Define transitions between nodes
- **Entry node**: Where execution starts

## Node Types

### Execute Nodes
Run a step using an LLM with optional tools.
```json
{
  "id": "research",
  "name": "Research Topic",
  "description": "Research the topic thoroughly",
  "node_type": "execute",
  "step_definition": {
    "goal": "Research and summarize the topic",
    "tools": ["web_search"],
    "input_fields": ["user_query"],
    "output_field": "research_results",
    "prompt_template": "Research this topic: {user_query}"
  }
}
```

### Checkpoint Nodes
Pause for user review/approval before continuing.
```json
{
  "id": "review_results",
  "name": "Review Results",
  "description": "User reviews the research",
  "node_type": "checkpoint",
  "checkpoint_config": {
    "title": "Review Research Results",
    "description": "Review the findings and approve or request changes",
    "allowed_actions": ["approve", "edit", "reject"],
    "editable_fields": ["research_results"]
  }
}
```

## Available Tools for Steps

- **web_search**: Search the web for information
- **fetch_webpage**: Fetch and read a specific URL
- **deep_research**: Comprehensive multi-source research
- **map_reduce**: Process a list and aggregate results
- **iterate**: Apply same operation to each item in a list

## Edge Conditions

For loops or branching, add `condition_expr` to edges:
```json
{"from_node": "process", "to_node": "process", "condition_expr": "items_remaining == True", "label": "continue"}
{"from_node": "process", "to_node": "finalize", "condition_expr": "items_remaining == False", "label": "done"}
```

## Output Format

Return a complete workflow graph as JSON:
```json
{
  "id": "workflow_id",
  "name": "Workflow Name",
  "description": "What this workflow does",
  "icon": "search",
  "category": "research",

  "nodes": {
    "step_1": {
      "id": "step_1",
      "name": "Step Name",
      "description": "What this step does",
      "node_type": "execute",
      "step_definition": {
        "goal": "The goal of this step",
        "tools": ["tool_name"],
        "input_fields": ["field_from_context"],
        "output_field": "result_field",
        "prompt_template": "Instructions with {field_from_context}"
      }
    },
    "review_1": {
      "id": "review_1",
      "name": "Review Step 1",
      "description": "User reviews output",
      "node_type": "checkpoint",
      "checkpoint_config": {
        "title": "Review",
        "description": "Review and approve",
        "allowed_actions": ["approve", "reject"],
        "editable_fields": []
      }
    }
  },

  "edges": [
    {"from_node": "step_1", "to_node": "review_1"}
  ],

  "entry_node": "step_1",

  "input_schema": {
    "type": "object",
    "properties": {
      "query": {"type": "string", "description": "The user's request"}
    },
    "required": ["query"]
  }
}
```

## Design Principles

1. **Add checkpoints after significant steps** - Let users review before proceeding
2. **Keep step goals focused** - One clear objective per step
3. **Use tools appropriately** - web_search for finding info, deep_research for comprehensive topics
4. **Design for reusability** - Workflows can be saved as templates
5. **2-5 execute nodes typical** - Don't over-engineer

## Example: "Research and compare cloud providers"

```json
{
  "id": "cloud_comparison",
  "name": "Cloud Provider Comparison",
  "description": "Research and compare cloud providers for a specific use case",

  "nodes": {
    "gather_requirements": {
      "id": "gather_requirements",
      "name": "Understand Requirements",
      "description": "Extract comparison criteria from user request",
      "node_type": "execute",
      "step_definition": {
        "goal": "Extract what the user wants to compare and their criteria",
        "tools": [],
        "input_fields": ["user_query"],
        "output_field": "criteria",
        "prompt_template": "Extract comparison criteria from: {user_query}"
      }
    },
    "review_criteria": {
      "id": "review_criteria",
      "name": "Review Criteria",
      "description": "User confirms comparison criteria",
      "node_type": "checkpoint",
      "checkpoint_config": {
        "title": "Review Comparison Criteria",
        "description": "Confirm these are the right criteria to compare",
        "allowed_actions": ["approve", "edit", "reject"],
        "editable_fields": ["criteria"]
      }
    },
    "research_providers": {
      "id": "research_providers",
      "name": "Research Providers",
      "description": "Research each cloud provider",
      "node_type": "execute",
      "step_definition": {
        "goal": "Research each provider based on the criteria",
        "tools": ["map_reduce", "web_search"],
        "input_fields": ["criteria"],
        "output_field": "provider_analysis",
        "prompt_template": "Research cloud providers based on: {criteria}"
      }
    },
    "synthesize": {
      "id": "synthesize",
      "name": "Synthesize Comparison",
      "description": "Create final comparison and recommendation",
      "node_type": "execute",
      "step_definition": {
        "goal": "Synthesize findings into comparison table and recommendation",
        "tools": [],
        "input_fields": ["criteria", "provider_analysis"],
        "output_field": "comparison",
        "prompt_template": "Create a comparison based on criteria: {criteria} and research: {provider_analysis}"
      }
    },
    "final_review": {
      "id": "final_review",
      "name": "Review Comparison",
      "description": "User reviews final comparison",
      "node_type": "checkpoint",
      "checkpoint_config": {
        "title": "Review Final Comparison",
        "description": "Review the comparison and recommendation",
        "allowed_actions": ["approve", "reject"],
        "editable_fields": []
      }
    }
  },

  "edges": [
    {"from_node": "gather_requirements", "to_node": "review_criteria"},
    {"from_node": "review_criteria", "to_node": "research_providers"},
    {"from_node": "research_providers", "to_node": "synthesize"},
    {"from_node": "synthesize", "to_node": "final_review"}
  ],

  "entry_node": "gather_requirements"
}
```

Now design an executable workflow graph for the user's request."""


def execute_design_workflow(
    params: Dict[str, Any],
    db: Session,
    user_id: int,
    context: Dict[str, Any]
) -> Generator[ToolProgress, None, ToolResult]:
    """
    Design an executable graph-based workflow for a given goal.

    Creates a WorkflowGraph that can be executed by the workflow engine.
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

    # Build the user prompt
    user_prompt = f"""Design an executable workflow graph for this task:

**Goal**: {goal}
"""

    if initial_input:
        user_prompt += f"\n**Initial Input/Context**: {initial_input}\n"

    if constraints:
        user_prompt += f"\n**Constraints/Preferences**: {constraints}\n"

    user_prompt += """
Return ONLY the JSON workflow graph. No other text. Follow the exact schema from your instructions."""

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
        workflow_data = _parse_workflow_json(response_text)

        if not workflow_data:
            yield ToolProgress(
                stage="error",
                message="Failed to parse workflow graph",
                data={"raw_response": response_text[:500]}
            )
            return ToolResult(
                text=f"Failed to parse workflow graph. Raw response:\n{response_text}",
                data={"error": "parse_error", "raw": response_text}
            )

        # Convert to WorkflowGraph and validate
        try:
            workflow_graph = WorkflowGraph.from_dict(workflow_data)
            validation_errors = workflow_graph.validate()

            if validation_errors:
                yield ToolProgress(
                    stage="validation_warning",
                    message=f"Workflow has validation issues: {', '.join(validation_errors)}",
                    data={"errors": validation_errors}
                )
        except Exception as e:
            logger.warning(f"Could not validate workflow graph: {e}")
            validation_errors = [str(e)]

        yield ToolProgress(
            stage="complete",
            message=f"Designed workflow: {workflow_data.get('name', 'Untitled')}",
            data={"nodes": len(workflow_data.get('nodes', {}))}
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
            "workflow": workflow_data
        }

        return ToolResult(
            text=f"""I've designed an executable workflow graph.

{summary}

**To execute this workflow**, the user can approve it and it will be run through the workflow engine with checkpoints for review at each stage.

```payload
{json.dumps(workflow_payload, indent=2)}
```""",
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


def _validate_workflow(workflow: Dict[str, Any]) -> list[str]:
    """Validate workflow graph structure and return list of errors."""
    errors = []

    if not workflow.get("name"):
        errors.append("Missing name")

    if not workflow.get("entry_node"):
        errors.append("Missing entry_node")

    nodes = workflow.get("nodes", {})
    if not nodes:
        errors.append("No nodes defined")
        return errors

    # Check entry node exists
    if workflow.get("entry_node") and workflow["entry_node"] not in nodes:
        errors.append(f"Entry node '{workflow['entry_node']}' not in nodes")

    # Validate each node
    for node_id, node in nodes.items():
        if not node.get("node_type"):
            errors.append(f"Node '{node_id}': missing node_type")
            continue

        if node["node_type"] == "execute":
            if not node.get("step_definition"):
                errors.append(f"Node '{node_id}': execute node missing step_definition")
            else:
                step_def = node["step_definition"]
                if not step_def.get("goal"):
                    errors.append(f"Node '{node_id}': step_definition missing goal")

        elif node["node_type"] == "checkpoint":
            if not node.get("checkpoint_config"):
                errors.append(f"Node '{node_id}': checkpoint node missing checkpoint_config")

    # Validate edges
    edges = workflow.get("edges", [])
    for i, edge in enumerate(edges):
        if not edge.get("from_node"):
            errors.append(f"Edge {i}: missing from_node")
        elif edge["from_node"] not in nodes:
            errors.append(f"Edge {i}: from_node '{edge['from_node']}' not in nodes")

        if not edge.get("to_node"):
            errors.append(f"Edge {i}: missing to_node")
        elif edge["to_node"] not in nodes:
            errors.append(f"Edge {i}: to_node '{edge['to_node']}' not in nodes")

    return errors


DESIGN_WORKFLOW_TOOL = ToolConfig(
    name="design_workflow",
    description="""Design an executable graph-based workflow to accomplish a complex task.

Use this tool when:
- A task requires multiple coordinated steps
- User review/approval is needed at certain stages
- The workflow should be reusable as a template

This tool creates an executable workflow graph with:
- Execute nodes: Steps that perform work using LLM + tools
- Checkpoint nodes: Pause points for user review
- Edges with conditions: Support for loops and branching

The workflow can be executed by the workflow engine with real-time progress updates.""",
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
