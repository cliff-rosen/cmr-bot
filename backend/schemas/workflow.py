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
    Declarative step definition with three distinct types for predictable data flow.

    Step Types:
    -----------
    1. tool_call: Execute a specific tool with mapped inputs
       - tool: which tool to call
       - input_mapping: how to map context fields to tool parameters
       - output_field: where to store the tool's result
       - Tool output schema is defined by the tool itself

    2. llm_transform: LLM transforms input data to structured output
       - goal: what transformation to perform
       - input_fields: context fields the LLM can see
       - output_schema: JSON Schema the output MUST match (enforced)
       - output_field: where to store the result

    3. llm_decision: LLM makes an enumerated choice (for branching)
       - goal: what decision to make
       - input_fields: context fields to consider
       - choices: list of valid choices (LLM must pick one)
       - output_field: where to store the chosen value

    This design ensures:
    - Clear contracts between steps (schemas, not hopes)
    - Predictable tool execution (not LLM pretending to use tools)
    - Validated data flow at design time
    """
    id: str
    name: str
    description: str

    # Step type determines which fields are used and how execution works
    step_type: Literal["tool_call", "llm_transform", "llm_decision"]

    # Common: where to store the result in context
    output_field: str = ""

    # === For tool_call ===
    # The tool to execute
    tool: Optional[str] = None
    # Map tool parameters to context fields or templates
    # e.g., {"query": "{name} {company} site:linkedin.com", "max_results": "10"}
    # Templates use {field_name} for substitution from context
    input_mapping: Optional[Dict[str, str]] = None

    # === For llm_transform and llm_decision ===
    # What the LLM should accomplish
    goal: Optional[str] = None
    # Context fields to include in the prompt
    input_fields: List[str] = field(default_factory=list)

    # === For llm_transform only ===
    # JSON Schema that output MUST conform to (uses structured output)
    output_schema: Optional[Dict[str, Any]] = None

    # === For llm_decision only ===
    # Valid choices the LLM must pick from
    choices: List[str] = field(default_factory=list)

    def validate(self) -> List[str]:
        """Validate this step definition. Returns list of errors."""
        errors = []

        if not self.id:
            errors.append("Step missing 'id'")
        if not self.name:
            errors.append(f"Step '{self.id}' missing 'name'")
        if not self.output_field:
            errors.append(f"Step '{self.id}' missing 'output_field'")

        if self.step_type == "tool_call":
            if not self.tool:
                errors.append(f"Step '{self.id}' (tool_call) missing 'tool'")
            if not self.input_mapping:
                errors.append(f"Step '{self.id}' (tool_call) missing 'input_mapping'")

        elif self.step_type == "llm_transform":
            if not self.goal:
                errors.append(f"Step '{self.id}' (llm_transform) missing 'goal'")
            if not self.output_schema:
                errors.append(f"Step '{self.id}' (llm_transform) missing 'output_schema'")

        elif self.step_type == "llm_decision":
            if not self.goal:
                errors.append(f"Step '{self.id}' (llm_decision) missing 'goal'")
            if not self.choices or len(self.choices) < 2:
                errors.append(f"Step '{self.id}' (llm_decision) needs at least 2 'choices'")

        else:
            errors.append(f"Step '{self.id}' has invalid step_type: {self.step_type}")

        return errors

    def get_referenced_fields(self) -> List[str]:
        """Get all context fields this step references (for validation)."""
        fields = set()

        # input_fields are explicit references
        fields.update(self.input_fields)

        # input_mapping may contain {field} templates
        if self.input_mapping:
            import re
            for value in self.input_mapping.values():
                # Extract {field_name} patterns
                matches = re.findall(r'\{(\w+)\}', str(value))
                fields.update(matches)

        return list(fields)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        result = {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "step_type": self.step_type,
            "output_field": self.output_field,
        }

        if self.step_type == "tool_call":
            result["tool"] = self.tool
            result["input_mapping"] = self.input_mapping

        elif self.step_type == "llm_transform":
            result["goal"] = self.goal
            result["input_fields"] = self.input_fields
            result["output_schema"] = self.output_schema

        elif self.step_type == "llm_decision":
            result["goal"] = self.goal
            result["input_fields"] = self.input_fields
            result["choices"] = self.choices

        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StepDefinition":
        """Create from dict."""
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            description=data.get("description", ""),
            step_type=data.get("step_type", "llm_transform"),
            output_field=data.get("output_field", ""),
            tool=data.get("tool"),
            input_mapping=data.get("input_mapping"),
            goal=data.get("goal"),
            input_fields=data.get("input_fields", []),
            output_schema=data.get("output_schema"),
            choices=data.get("choices", []),
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
        Validate the workflow graph structure.
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

    def validate_data_flow(self, tool_validator: Optional[Callable[[str], bool]] = None) -> List[str]:
        """
        Validate data flow through the workflow.

        Checks:
        1. Each step definition is internally valid (required fields for its type)
        2. All referenced fields will be available when the node runs
        3. Tool exists for tool_call steps
        4. No output_field conflicts

        Args:
            tool_validator: Optional function that returns True if a tool name exists

        Returns:
            List of error messages (empty if valid)
        """
        errors = []

        # Get fields available from input_schema
        schema_fields = set()
        if self.input_schema and "properties" in self.input_schema:
            schema_fields = set(self.input_schema["properties"].keys())

        # Build predecessor map for topological analysis
        predecessors: Dict[str, set] = {node_id: set() for node_id in self.nodes}
        for edge in self.edges:
            if edge.to_node in predecessors:
                predecessors[edge.to_node].add(edge.from_node)

        # Track which fields each node produces
        node_outputs: Dict[str, str] = {}  # node_id -> output_field
        for node_id, node in self.nodes.items():
            if node.node_type == "execute" and node.step_definition:
                if node.step_definition.output_field:
                    node_outputs[node_id] = node.step_definition.output_field

        # First pass: validate each step definition internally
        for node_id, node in self.nodes.items():
            if node.node_type == "execute" and node.step_definition:
                step_errors = node.step_definition.validate()
                for err in step_errors:
                    errors.append(f"Node '{node_id}': {err}")

                # Validate tool exists for tool_call steps
                if node.step_definition.step_type == "tool_call" and tool_validator:
                    if node.step_definition.tool and not tool_validator(node.step_definition.tool):
                        errors.append(f"Node '{node_id}': tool '{node.step_definition.tool}' does not exist")

        # Compute fields available at each node using topological traversal
        fields_at_node: Dict[str, set] = {}
        visited = set()
        queue = [self.entry_node] if self.entry_node else []

        while queue:
            node_id = queue.pop(0)
            if node_id in visited:
                continue

            # Check if all predecessors have been processed
            unprocessed_preds = predecessors[node_id] - visited
            if unprocessed_preds and node_id != self.entry_node:
                queue.append(node_id)
                continue

            visited.add(node_id)

            # Compute available fields at this node
            if node_id == self.entry_node:
                available = schema_fields.copy()
            else:
                pred_fields = []
                for pred_id in predecessors[node_id]:
                    if pred_id in fields_at_node:
                        pred_available = fields_at_node[pred_id].copy()
                        if pred_id in node_outputs:
                            pred_available.add(node_outputs[pred_id])
                        pred_fields.append(pred_available)

                if pred_fields:
                    available = pred_fields[0]
                    for pf in pred_fields[1:]:
                        available = available.intersection(pf)
                else:
                    available = schema_fields.copy()

            fields_at_node[node_id] = available

            # Validate this node's field references
            node = self.nodes[node_id]
            if node.node_type == "execute" and node.step_definition:
                step_def = node.step_definition
                referenced_fields = step_def.get_referenced_fields()

                for field in referenced_fields:
                    if field not in available:
                        all_possible = schema_fields.copy()
                        for nid, output in node_outputs.items():
                            all_possible.add(output)

                        if field in all_possible:
                            errors.append(
                                f"Node '{node_id}': field '{field}' may not be available on all paths. "
                                f"Guaranteed: {sorted(available)}"
                            )
                        else:
                            errors.append(
                                f"Node '{node_id}': field '{field}' does not exist. "
                                f"Available: {sorted(available)}, All possible: {sorted(all_possible)}"
                            )

            # Queue successors
            for edge in self.edges:
                if edge.from_node == node_id and edge.to_node not in visited:
                    queue.append(edge.to_node)

        # Check for output_field conflicts
        output_to_nodes: Dict[str, List[str]] = {}
        for node_id, output in node_outputs.items():
            if output not in output_to_nodes:
                output_to_nodes[output] = []
            output_to_nodes[output].append(node_id)

        for output, writers in output_to_nodes.items():
            if len(writers) > 1:
                errors.append(
                    f"Multiple nodes write to '{output}': {writers}. "
                    f"This may cause conflicts unless on mutually exclusive paths."
                )

        return errors

    def validate_all(self, tool_validator: Optional[Callable[[str], bool]] = None) -> List[str]:
        """
        Run all validations (structure + data flow).

        Args:
            tool_validator: Optional function that returns True if a tool name exists

        Returns:
            List of all error messages (empty if valid)
        """
        errors = self.validate()  # Structure validation
        errors.extend(self.validate_data_flow(tool_validator))  # Data flow validation
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
