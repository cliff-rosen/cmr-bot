# Workflow System Migration

## Goal
Migrate from the agent's custom workflow system to the graph-based workflow engine, enabling chat-based workflow template creation and maintenance.

---

## Current State: Two Systems

### OLD: Agent Workflow Builder (`workflow_builder.py`)

**What it does:**
- Agent designs a "workflow plan" as JSON
- Linear steps with descriptions, tools, input sources
- No execution engine - just a plan document

**Output format:**
```json
{
  "title": "Compare Cloud Providers",
  "goal": "Research and compare AWS, GCP, Azure",
  "steps": [
    {
      "description": "Research each provider",
      "input_sources": ["user"],
      "output_description": "Provider details",
      "method": {
        "approach": "Use map_reduce",
        "tools": ["map_reduce", "deep_research"],
        "reasoning": "Need to compare multiple items"
      }
    }
  ]
}
```

**Limitations:**
- Not executable - just a specification
- No checkpoints for user review
- No loops or conditionals
- No integration with workflow engine

---

### NEW: Graph-Based Engine (`workflows/engine.py`)

**What it does:**
- Executes workflows defined as directed graphs
- Nodes = execute steps OR checkpoints
- Edges = transitions (can have conditions for branching/loops)
- Real-time event streaming to UI

**Definition format:**
```python
WorkflowGraph(
    id="vendor_finder",
    name="Vendor Finder",
    nodes={
        "search": StepNode(
            id="search",
            node_type="execute",
            execute_fn=search_vendors,  # <-- Python function
        ),
        "review": StepNode(
            id="review",
            node_type="checkpoint",
            checkpoint_config=CheckpointConfig(title="Review Results")
        ),
    },
    edges=[
        Edge(from_node="search", to_node="review"),
    ],
    entry_node="search"
)
```

**The Problem:**
`execute_fn` requires a Python function. Agent can't generate Python code dynamically.

---

## Migration Path

### Key Insight
We need **declarative step definitions** that can be:
1. Created/edited by the agent (as JSON/data)
2. Executed by a generic step runner (interprets the definition)

### New Step Definition Schema

Instead of Python functions, steps are defined as data:

```python
@dataclass
class StepDefinition:
    """Declarative step that can be created by agent and executed by engine."""
    id: str
    name: str
    description: str

    # What this step should accomplish
    goal: str

    # Which tools this step can use
    tools: List[str]  # ["web_search", "deep_research", "iterate", etc.]

    # Input/output schema
    input_fields: List[str]   # Which context fields to read
    output_field: str         # Where to store result

    # LLM prompt template for execution
    prompt_template: str

    # Optional: specific instructions
    instructions: Optional[str] = None
```

### Generic Step Executor

A single Python function that executes any `StepDefinition`:

```python
async def execute_dynamic_step(context: WorkflowContext) -> StepOutput:
    """
    Generic executor that runs declarative step definitions.
    Reads step config from context, executes via LLM with tools.
    """
    step_def = context.get_step_definition()

    # Gather inputs
    inputs = {field: context.get_variable(field) for field in step_def.input_fields}

    # Build prompt
    prompt = step_def.prompt_template.format(**inputs)

    # Execute with available tools
    result = await run_agent_with_tools(
        prompt=prompt,
        tools=step_def.tools,
        goal=step_def.goal
    )

    # Store output
    context.set_variable(step_def.output_field, result)

    return StepOutput(success=True, data=result)
```

---

## New Workflow Format

Workflows become JSON-serializable:

```json
{
  "id": "restaurant_finder",
  "name": "Restaurant Finder",
  "description": "Find and compare restaurants",

  "nodes": {
    "understand": {
      "id": "understand",
      "type": "execute",
      "step": {
        "name": "Understand Requirements",
        "goal": "Extract user's restaurant preferences",
        "tools": [],
        "input_fields": ["user_query"],
        "output_field": "criteria",
        "prompt_template": "Extract restaurant criteria from: {user_query}"
      }
    },
    "search": {
      "id": "search",
      "type": "execute",
      "step": {
        "name": "Search Restaurants",
        "goal": "Find restaurants matching criteria",
        "tools": ["web_search"],
        "input_fields": ["criteria"],
        "output_field": "restaurants",
        "prompt_template": "Search for restaurants matching: {criteria}"
      }
    },
    "review_checkpoint": {
      "id": "review_checkpoint",
      "type": "checkpoint",
      "checkpoint": {
        "title": "Review Restaurant List",
        "description": "Review the restaurants found",
        "allowed_actions": ["approve", "edit", "reject"]
      }
    }
  },

  "edges": [
    {"from": "understand", "to": "search"},
    {"from": "search", "to": "review_checkpoint"}
  ],

  "entry_node": "understand"
}
```

---

## Agent Tools for Workflow Management

### 1. `design_workflow` (MODIFY existing)
- Keep conversation with user
- Output NEW format (graph with declarative steps)
- Show visual representation of the graph

### 2. `edit_workflow` (NEW)
- Modify existing workflow definition
- Add/remove/edit nodes
- Add/remove/edit edges
- Edit step definitions

### 3. `save_workflow` (NEW)
- Save workflow to database/file
- Register with workflow engine
- Make available for execution

### 4. `list_workflows` (NEW)
- Show available workflow templates
- Both built-in and user-created

### 5. `run_workflow` (NEW or modify existing)
- Execute a workflow through the engine
- Stream progress to chat

---

## Implementation Steps

### Phase 1: Schema & Executor
1. Create `StepDefinition` dataclass
2. Create `execute_dynamic_step()` function
3. Add JSON serialization to `WorkflowGraph`
4. Test with a simple workflow

### Phase 2: Migrate design_workflow
1. Update output format to graph-based
2. Update system prompt for new schema
3. Add graph visualization in UI

### Phase 3: CRUD Tools
1. `save_workflow` - persist to DB
2. `edit_workflow` - modify definitions
3. `list_workflows` - enumerate available

### Phase 4: Deprecate Old
1. Remove old workflow plan format
2. Update any dependent code

---

## Open Questions

1. **Storage**: Where to persist user workflows? Database table? JSON files?
2. **Permissions**: Can users share workflows? Per-conversation or global?
3. **Versioning**: Track workflow changes?
4. **Built-ins**: Keep hardcoded templates (vendor_finder) or migrate to JSON too?

---

## Files to Modify

| File | Changes |
|------|---------|
| `backend/schemas/workflow.py` | Add `StepDefinition`, JSON serialization |
| `backend/workflows/engine.py` | Support dynamic step execution |
| `backend/tools/builtin/workflow_builder.py` | Output new graph format |
| `backend/tools/builtin/workflow_crud.py` | NEW - save/edit/list/delete tools |
| `backend/routers/workflows.py` | Endpoints for user workflows |
| `frontend/...` | Workflow editor UI (future) |
