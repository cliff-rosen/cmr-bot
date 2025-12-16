"""
Workflow Engine Schema

Defines the core types for graph-based workflow definitions and execution state.

A workflow is defined as a directed graph:
- Nodes are either "execute" (run a function) or "checkpoint" (wait for user)
- Edges define transitions between nodes, optionally with conditions
- Loops and conditionals are just edges with conditions pointing to different nodes
"""

from typing import Any, Callable, Dict, List, Optional, Literal, Awaitable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import uuid


class CheckpointAction(str, Enum):
    """Actions a user can take at a checkpoint."""
    APPROVE = "approve"      # Accept and continue
    EDIT = "edit"            # Modify the data, then continue
    REJECT = "reject"        # Go back or abort
    SKIP = "skip"            # Skip this step


class WorkflowStatus(str, Enum):
    """Status of a workflow instance."""
    PENDING = "pending"          # Created but not started
    RUNNING = "running"          # Currently executing a step
    WAITING = "waiting"          # At a checkpoint, waiting for user
    PAUSED = "paused"            # User paused execution
    COMPLETED = "completed"      # Successfully finished
    FAILED = "failed"            # Error occurred
    CANCELLED = "cancelled"      # User cancelled


@dataclass
class StepProgress:
    """Progress update during step execution."""
    message: str
    progress: Optional[float] = None  # 0.0 to 1.0
    details: Optional[Dict[str, Any]] = None


@dataclass
class StepOutput:
    """Output from a step execution."""
    success: bool
    data: Any = None
    error: Optional[str] = None
    # For UI display
    display_title: Optional[str] = None
    display_content: Optional[str] = None
    content_type: Literal["text", "markdown", "json", "table"] = "markdown"


@dataclass
class CheckpointConfig:
    """Configuration for a checkpoint node."""
    title: str
    description: str
    allowed_actions: List[CheckpointAction] = field(default_factory=lambda: [
        CheckpointAction.APPROVE,
        CheckpointAction.EDIT,
        CheckpointAction.REJECT
    ])
    # Fields that can be edited at this checkpoint
    editable_fields: List[str] = field(default_factory=list)
    # Whether to auto-proceed if no user action within timeout
    auto_proceed: bool = False
    auto_proceed_timeout_seconds: Optional[int] = None


# =============================================================================
# Declarative Step Definitions (for agent-created workflows)
# =============================================================================

@dataclass
class StepDefinition:
    """
    Declarative step definition that can be created by an agent as JSON.

    Instead of requiring Python code, steps are defined as data:
    - goal: what the step should accomplish
    - tools: which tools the step can use
    - prompt_template: how to instruct the LLM
    - input/output fields: data flow

    A generic executor interprets these definitions at runtime.
    """
    id: str
    name: str
    description: str

    # What this step should accomplish (instruction for executor)
    goal: str

    # Which tools this step is allowed to use
    tools: List[str] = field(default_factory=list)

    # Input/output schema for data flow
    input_fields: List[str] = field(default_factory=list)  # Fields to read from context
    output_field: str = ""  # Where to store the result

    # Prompt template for execution (uses {field_name} substitution)
    prompt_template: Optional[str] = None

    # Optional specific instructions
    instructions: Optional[str] = None

    # Execution mode
    mode: Literal["llm", "tool", "llm_with_tools"] = "llm_with_tools"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "goal": self.goal,
            "tools": self.tools,
            "input_fields": self.input_fields,
            "output_field": self.output_field,
            "prompt_template": self.prompt_template,
            "instructions": self.instructions,
            "mode": self.mode,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StepDefinition":
        """Create from dict."""
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            description=data.get("description", ""),
            goal=data.get("goal", ""),
            tools=data.get("tools", []),
            input_fields=data.get("input_fields", []),
            output_field=data.get("output_field", ""),
            prompt_template=data.get("prompt_template"),
            instructions=data.get("instructions"),
            mode=data.get("mode", "llm_with_tools"),
        )


# =============================================================================
# Graph-Based Workflow Definition
# =============================================================================

@dataclass
class StepNode:
    """
    A node in the workflow graph.

    Nodes are either:
    - "execute": Run an async Python function OR a declarative StepDefinition
    - "checkpoint": Pause and wait for user input
    """
    id: str
    name: str
    description: str
    node_type: Literal["execute", "checkpoint"]

    # For execute nodes: EITHER a Python function OR a declarative definition
    # Option 1: Async function - Signature: async (context: WorkflowContext) -> StepOutput
    execute_fn: Optional[Callable[["WorkflowContext"], Awaitable[StepOutput]]] = None

    # Option 2: Declarative step definition (for agent-created workflows)
    step_definition: Optional[StepDefinition] = None

    # For checkpoint nodes: configuration
    checkpoint_config: Optional[CheckpointConfig] = None

    # UI hint for frontend rendering
    ui_component: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict (for saving workflows)."""
        result = {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "node_type": self.node_type,
            "ui_component": self.ui_component,
        }
        if self.step_definition:
            result["step_definition"] = self.step_definition.to_dict()
        if self.checkpoint_config:
            result["checkpoint_config"] = {
                "title": self.checkpoint_config.title,
                "description": self.checkpoint_config.description,
                "allowed_actions": [a.value for a in self.checkpoint_config.allowed_actions],
                "editable_fields": self.checkpoint_config.editable_fields,
                "auto_proceed": self.checkpoint_config.auto_proceed,
                "auto_proceed_timeout_seconds": self.checkpoint_config.auto_proceed_timeout_seconds,
            }
        # Note: execute_fn cannot be serialized - only step_definition workflows can be saved
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StepNode":
        """Create from dict (for loading saved workflows)."""
        step_def = None
        if data.get("step_definition"):
            step_def = StepDefinition.from_dict(data["step_definition"])

        checkpoint_cfg = None
        if data.get("checkpoint_config"):
            cfg = data["checkpoint_config"]
            checkpoint_cfg = CheckpointConfig(
                title=cfg.get("title", ""),
                description=cfg.get("description", ""),
                allowed_actions=[CheckpointAction(a) for a in cfg.get("allowed_actions", [])],
                editable_fields=cfg.get("editable_fields", []),
                auto_proceed=cfg.get("auto_proceed", False),
                auto_proceed_timeout_seconds=cfg.get("auto_proceed_timeout_seconds"),
            )

        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            description=data.get("description", ""),
            node_type=data.get("node_type", "execute"),
            step_definition=step_def,
            checkpoint_config=checkpoint_cfg,
            ui_component=data.get("ui_component"),
        )


@dataclass
class Edge:
    """
    A directed edge between nodes in the workflow graph.

    Edges define transitions. When multiple edges leave a node,
    conditions are evaluated in order and the first matching edge is taken.
    An edge with no condition (None) always matches - use this for default paths.
    """
    from_node: str
    to_node: str
    # Condition function: (context) -> bool. None means always take this edge.
    condition: Optional[Callable[["WorkflowContext"], bool]] = None
    # Label for visualization/debugging
    label: Optional[str] = None
    # For declarative workflows: condition as a string expression
    # e.g., "retrieval_complete == True" - evaluated at runtime
    condition_expr: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "from_node": self.from_node,
            "to_node": self.to_node,
            "label": self.label,
            "condition_expr": self.condition_expr,
            # Note: condition function cannot be serialized
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Edge":
        """Create from dict."""
        return cls(
            from_node=data.get("from_node", ""),
            to_node=data.get("to_node", ""),
            label=data.get("label"),
            condition_expr=data.get("condition_expr"),
        )


@dataclass
class WorkflowGraph:
    """
    A workflow defined as a directed graph.

    The graph structure naturally supports:
    - Linear flows: A -> B -> C (edges with no conditions)
    - Conditionals: A -> B (if x), A -> C (if not x)
    - Loops: A -> B -> A (edge back with condition)

    Example loop pattern:
        edges = [
            Edge("step1", "step2"),
            Edge("step2", "step1", condition=lambda ctx: ctx.get_variable("should_loop")),
            Edge("step2", "step3", condition=lambda ctx: not ctx.get_variable("should_loop")),
        ]
    """
    id: str
    name: str
    description: str

    # The nodes in this workflow
    nodes: Dict[str, StepNode] = field(default_factory=dict)

    # The edges defining transitions
    edges: List[Edge] = field(default_factory=list)

    # ID of the entry node (first node to execute)
    entry_node: str = ""

    # Metadata
    icon: str = "workflow"
    category: str = "general"
    input_schema: Optional[Dict[str, Any]] = None
    output_schema: Optional[Dict[str, Any]] = None

    def get_node(self, node_id: str) -> Optional[StepNode]:
        """Get a node by ID."""
        return self.nodes.get(node_id)

    def get_outgoing_edges(self, node_id: str) -> List[Edge]:
        """Get all edges leaving a node."""
        return [e for e in self.edges if e.from_node == node_id]

    def validate(self) -> List[str]:
        """
        Validate the workflow graph.
        Returns a list of error messages (empty if valid).
        """
        errors = []

        # Check entry node exists
        if not self.entry_node:
            errors.append("No entry node specified")
        elif self.entry_node not in self.nodes:
            errors.append(f"Entry node '{self.entry_node}' not found in nodes")

        # Check all edge endpoints exist
        for edge in self.edges:
            if edge.from_node not in self.nodes:
                errors.append(f"Edge from unknown node: {edge.from_node}")
            if edge.to_node not in self.nodes:
                errors.append(f"Edge to unknown node: {edge.to_node}")

        # Check execute nodes have either functions OR step definitions
        for node_id, node in self.nodes.items():
            if node.node_type == "execute":
                if node.execute_fn is None and node.step_definition is None:
                    errors.append(f"Execute node '{node_id}' has no execute_fn or step_definition")
            if node.node_type == "checkpoint" and node.checkpoint_config is None:
                errors.append(f"Checkpoint node '{node_id}' has no checkpoint_config")

        # Check for unreachable nodes (except entry)
        reachable = {self.entry_node}
        changed = True
        while changed:
            changed = False
            for edge in self.edges:
                if edge.from_node in reachable and edge.to_node not in reachable:
                    reachable.add(edge.to_node)
                    changed = True

        unreachable = set(self.nodes.keys()) - reachable
        if unreachable:
            errors.append(f"Unreachable nodes: {unreachable}")

        return errors

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict (for saving workflows)."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "nodes": {node_id: node.to_dict() for node_id, node in self.nodes.items()},
            "edges": [edge.to_dict() for edge in self.edges],
            "entry_node": self.entry_node,
            "icon": self.icon,
            "category": self.category,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkflowGraph":
        """Create from dict (for loading saved workflows)."""
        nodes = {}
        for node_id, node_data in data.get("nodes", {}).items():
            nodes[node_id] = StepNode.from_dict(node_data)

        edges = []
        for edge_data in data.get("edges", []):
            edges.append(Edge.from_dict(edge_data))

        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            description=data.get("description", ""),
            nodes=nodes,
            edges=edges,
            entry_node=data.get("entry_node", ""),
            icon=data.get("icon", "workflow"),
            category=data.get("category", "general"),
            input_schema=data.get("input_schema"),
            output_schema=data.get("output_schema"),
        )

    def to_json(self) -> str:
        """Serialize to JSON string."""
        import json
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> "WorkflowGraph":
        """Deserialize from JSON string."""
        import json
        return cls.from_dict(json.loads(json_str))


# =============================================================================
# Runtime State
# =============================================================================

@dataclass
class StepState:
    """Runtime state of a node execution."""
    node_id: str
    status: Literal["pending", "running", "completed", "failed", "skipped"]
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    output: Optional[StepOutput] = None
    error: Optional[str] = None
    # Number of times this node has been executed (for loops)
    execution_count: int = 0


@dataclass
class WorkflowContext:
    """
    Runtime context passed to step functions.
    Contains all state needed to execute a step.
    """
    # The workflow instance ID
    instance_id: str

    # The workflow graph definition
    graph: WorkflowGraph

    # Initial input provided when starting the workflow
    initial_input: Dict[str, Any]

    # Accumulated data from previous steps
    # Key is node_id, value is the node's output data
    step_data: Dict[str, Any] = field(default_factory=dict)

    # Current node being executed
    current_node_id: Optional[str] = None

    # State of all nodes
    node_states: Dict[str, StepState] = field(default_factory=dict)

    # User edits made at checkpoints
    user_edits: Dict[str, Any] = field(default_factory=dict)

    # Variables that can be set/read by steps (like loop counters)
    variables: Dict[str, Any] = field(default_factory=dict)

    def get_step_output(self, node_id: str) -> Optional[Any]:
        """Get the output data from a previous node."""
        return self.step_data.get(node_id)

    def set_step_output(self, node_id: str, data: Any):
        """Set the output data for a node."""
        self.step_data[node_id] = data

    def set_variable(self, name: str, value: Any):
        """Set a context variable."""
        self.variables[name] = value

    def get_variable(self, name: str, default: Any = None) -> Any:
        """Get a context variable."""
        return self.variables.get(name, default)


@dataclass
class WorkflowInstance:
    """
    A running instance of a workflow.
    This is what gets persisted and tracks execution state.
    """
    id: str
    workflow_id: str  # References WorkflowGraph.id
    status: WorkflowStatus

    # The context containing all runtime state
    context: WorkflowContext

    # Current node (for quick access)
    current_node_id: Optional[str] = None

    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None

    # For associating with a conversation
    conversation_id: Optional[int] = None

    # Final output when completed
    final_output: Optional[Any] = None

    @classmethod
    def create(
        cls,
        graph: WorkflowGraph,
        initial_input: Dict[str, Any],
        conversation_id: Optional[int] = None
    ) -> "WorkflowInstance":
        """Create a new workflow instance from a graph definition."""
        instance_id = str(uuid.uuid4())

        context = WorkflowContext(
            instance_id=instance_id,
            graph=graph,
            initial_input=initial_input,
            step_data={},
            current_node_id=graph.entry_node,
            node_states={},
            user_edits={},
            variables={}
        )

        return cls(
            id=instance_id,
            workflow_id=graph.id,
            status=WorkflowStatus.PENDING,
            context=context,
            current_node_id=graph.entry_node,
            conversation_id=conversation_id
        )


# =============================================================================
# Backwards Compatibility Aliases (for gradual migration)
# =============================================================================

# These allow existing code to work while we migrate
WorkflowDefinition = WorkflowGraph  # Alias for migration
