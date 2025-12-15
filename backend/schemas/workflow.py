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
# Graph-Based Workflow Definition
# =============================================================================

@dataclass
class StepNode:
    """
    A node in the workflow graph.

    Nodes are either:
    - "execute": Run an async Python function
    - "checkpoint": Pause and wait for user input
    """
    id: str
    name: str
    description: str
    node_type: Literal["execute", "checkpoint"]

    # For execute nodes: the async function to run
    # Signature: async (context: WorkflowContext) -> StepOutput
    execute_fn: Optional[Callable[["WorkflowContext"], Awaitable[StepOutput]]] = None

    # For checkpoint nodes: configuration
    checkpoint_config: Optional[CheckpointConfig] = None

    # UI hint for frontend rendering
    ui_component: Optional[str] = None


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

        # Check execute nodes have functions
        for node_id, node in self.nodes.items():
            if node.node_type == "execute" and node.execute_fn is None:
                errors.append(f"Execute node '{node_id}' has no execute_fn")
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
