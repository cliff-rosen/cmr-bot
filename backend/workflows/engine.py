"""
Graph-Based Workflow Engine

Executes workflows defined as directed graphs.

The engine:
1. Loads workflow graphs from the registry
2. Executes nodes by traversing edges
3. Handles checkpoints by pausing and waiting for user input
4. Uses edge conditions to handle loops and branching
5. Emits events for UI updates via async generators
"""

import logging
from typing import Any, AsyncGenerator, Dict, Optional, Callable
from datetime import datetime
from dataclasses import dataclass

from schemas.workflow import (
    WorkflowGraph,
    WorkflowInstance,
    WorkflowStatus,
    WorkflowContext,
    StepNode,
    StepState,
    StepOutput,
    CheckpointAction,
)
from .registry import workflow_registry

logger = logging.getLogger(__name__)


@dataclass
class EngineEvent:
    """Event emitted by the workflow engine during execution."""
    event_type: str  # "step_start", "step_complete", "checkpoint", "error", "complete", "cancelled"
    instance_id: str
    node_id: Optional[str] = None
    node_name: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class WorkflowEngine:
    """
    Executes workflow instances defined as graphs.

    The engine traverses the graph by:
    1. Executing the current node
    2. Evaluating outgoing edges to find the next node
    3. Repeating until no valid edge or checkpoint reached
    """

    def __init__(self):
        # In-memory store of running instances
        self._instances: Dict[str, WorkflowInstance] = {}

        # Callbacks for persistence (optional)
        self._on_instance_updated: Optional[Callable[[WorkflowInstance], None]] = None

    def set_persistence_callback(self, callback: Callable[[WorkflowInstance], None]):
        """Set a callback to be called when an instance is updated."""
        self._on_instance_updated = callback

    def _persist(self, instance: WorkflowInstance):
        """Persist instance state."""
        instance.updated_at = datetime.utcnow()
        self._instances[instance.id] = instance
        if self._on_instance_updated:
            self._on_instance_updated(instance)

    def get_instance(self, instance_id: str) -> Optional[WorkflowInstance]:
        """Get a workflow instance by ID."""
        return self._instances.get(instance_id)

    def create_instance(
        self,
        workflow_id: str,
        initial_input: Dict[str, Any],
        conversation_id: Optional[int] = None
    ) -> WorkflowInstance:
        """Create a new workflow instance from a registered workflow."""
        graph = workflow_registry.get(workflow_id)
        if not graph:
            raise ValueError(f"Workflow '{workflow_id}' not found in registry")

        # Validate the graph
        errors = graph.validate()
        if errors:
            raise ValueError(f"Invalid workflow graph: {errors}")

        instance = WorkflowInstance.create(
            graph=graph,
            initial_input=initial_input,
            conversation_id=conversation_id
        )

        self._persist(instance)
        logger.info(f"Created workflow instance {instance.id} for workflow {workflow_id}")
        return instance

    def create_instance_from_graph(
        self,
        graph: WorkflowGraph,
        initial_input: Dict[str, Any],
        conversation_id: Optional[int] = None
    ) -> WorkflowInstance:
        """Create a new workflow instance from a graph definition (for dynamic workflows)."""
        # Validate the graph
        errors = graph.validate()
        if errors:
            raise ValueError(f"Invalid workflow graph: {errors}")

        instance = WorkflowInstance.create(
            graph=graph,
            initial_input=initial_input,
            conversation_id=conversation_id
        )

        self._persist(instance)
        logger.info(f"Created workflow instance {instance.id} from dynamic graph {graph.id}")
        return instance

    async def start(
        self,
        instance_id: str
    ) -> AsyncGenerator[EngineEvent, None]:
        """
        Start executing a workflow instance.

        Yields events as execution progresses.
        Will pause at checkpoints and return.
        """
        instance = self.get_instance(instance_id)
        if not instance:
            yield EngineEvent(
                event_type="error",
                instance_id=instance_id,
                error=f"Instance {instance_id} not found"
            )
            return

        if instance.status not in [WorkflowStatus.PENDING, WorkflowStatus.WAITING]:
            yield EngineEvent(
                event_type="error",
                instance_id=instance_id,
                error=f"Cannot start instance in status {instance.status}"
            )
            return

        instance.status = WorkflowStatus.RUNNING
        self._persist(instance)

        # Execute until we hit a checkpoint or complete
        async for event in self._execute_graph(instance):
            yield event

    async def resume(
        self,
        instance_id: str,
        action: CheckpointAction,
        user_data: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[EngineEvent, None]:
        """
        Resume a workflow from a checkpoint.

        Args:
            instance_id: The workflow instance ID
            action: The action the user took at the checkpoint
            user_data: Any data the user provided (edits, etc.)
        """
        instance = self.get_instance(instance_id)
        if not instance:
            yield EngineEvent(
                event_type="error",
                instance_id=instance_id,
                error=f"Instance {instance_id} not found"
            )
            return

        if instance.status != WorkflowStatus.WAITING:
            yield EngineEvent(
                event_type="error",
                instance_id=instance_id,
                error=f"Cannot resume instance in status {instance.status}"
            )
            return

        current_node = instance.context.graph.get_node(instance.current_node_id)
        if not current_node:
            yield EngineEvent(
                event_type="error",
                instance_id=instance_id,
                error=f"Current node {instance.current_node_id} not found"
            )
            return

        # Handle the checkpoint action
        if action == CheckpointAction.REJECT:
            instance.status = WorkflowStatus.CANCELLED
            self._persist(instance)
            yield EngineEvent(
                event_type="cancelled",
                instance_id=instance_id,
                node_id=current_node.id
            )
            return

        if action == CheckpointAction.EDIT and user_data:
            # Store user edits
            instance.context.user_edits[current_node.id] = user_data
            # Also update step_data with edits
            if current_node.id in instance.context.step_data:
                instance.context.step_data[current_node.id].update(user_data)
            else:
                instance.context.step_data[current_node.id] = user_data

        # Mark checkpoint node as complete
        node_state = instance.context.node_states.get(current_node.id)
        if node_state:
            node_state.status = "completed"
            node_state.completed_at = datetime.utcnow()

        # Find next node by evaluating edges
        next_node_id = self._get_next_node(instance.context.graph, current_node.id, instance.context)

        if not next_node_id:
            # Workflow complete
            instance.status = WorkflowStatus.COMPLETED
            instance.completed_at = datetime.utcnow()
            instance.final_output = instance.context.step_data
            self._persist(instance)
            yield EngineEvent(
                event_type="complete",
                instance_id=instance_id,
                data=instance.final_output
            )
            return

        instance.current_node_id = next_node_id
        instance.context.current_node_id = next_node_id
        instance.status = WorkflowStatus.RUNNING
        self._persist(instance)

        # Continue execution
        async for event in self._execute_graph(instance):
            yield event

    def _get_next_node(
        self,
        graph: WorkflowGraph,
        from_node_id: str,
        context: WorkflowContext
    ) -> Optional[str]:
        """
        Evaluate outgoing edges to find the next node.

        Edges are evaluated in order. The first edge with a matching condition
        (or no condition) is taken.
        """
        outgoing_edges = graph.get_outgoing_edges(from_node_id)

        for edge in outgoing_edges:
            if edge.condition is None:
                # No condition = always take this edge
                return edge.to_node
            try:
                if edge.condition(context):
                    return edge.to_node
            except Exception as e:
                logger.error(f"Error evaluating edge condition {from_node_id} -> {edge.to_node}: {e}")
                continue

        return None  # No valid edge = end of workflow

    async def _execute_graph(
        self,
        instance: WorkflowInstance
    ) -> AsyncGenerator[EngineEvent, None]:
        """
        Execute the workflow graph until we hit a checkpoint or complete.
        """
        while instance.current_node_id:
            node = instance.context.graph.get_node(instance.current_node_id)
            if not node:
                instance.status = WorkflowStatus.FAILED
                self._persist(instance)
                yield EngineEvent(
                    event_type="error",
                    instance_id=instance.id,
                    error=f"Node {instance.current_node_id} not found"
                )
                return

            # Initialize node state if not exists
            if node.id not in instance.context.node_states:
                instance.context.node_states[node.id] = StepState(
                    node_id=node.id,
                    status="pending"
                )

            node_state = instance.context.node_states[node.id]

            # Handle node based on type
            if node.node_type == "execute":
                async for event in self._execute_node(instance, node, node_state):
                    yield event
                    if event.event_type == "error":
                        return

                # After successful execution, find next node
                if node_state.status == "completed":
                    next_node_id = self._get_next_node(
                        instance.context.graph,
                        node.id,
                        instance.context
                    )

                    if next_node_id:
                        instance.current_node_id = next_node_id
                        instance.context.current_node_id = next_node_id
                        self._persist(instance)
                    else:
                        # No next node = workflow complete
                        instance.status = WorkflowStatus.COMPLETED
                        instance.completed_at = datetime.utcnow()
                        instance.final_output = instance.context.step_data
                        instance.current_node_id = None
                        instance.context.current_node_id = None
                        self._persist(instance)
                        yield EngineEvent(
                            event_type="complete",
                            instance_id=instance.id,
                            data=instance.final_output
                        )
                        return
                else:
                    # Node didn't complete successfully
                    return

            elif node.node_type == "checkpoint":
                # Pause at checkpoint
                yield EngineEvent(
                    event_type="checkpoint",
                    instance_id=instance.id,
                    node_id=node.id,
                    node_name=node.name,
                    data={
                        "checkpoint_config": {
                            "title": node.checkpoint_config.title,
                            "description": node.checkpoint_config.description,
                            "allowed_actions": [a.value for a in node.checkpoint_config.allowed_actions],
                            "editable_fields": node.checkpoint_config.editable_fields,
                        } if node.checkpoint_config else None,
                        "step_data": instance.context.step_data,
                        "ui_component": node.ui_component
                    }
                )
                instance.status = WorkflowStatus.WAITING
                node_state.status = "running"  # Waiting at checkpoint
                node_state.started_at = datetime.utcnow()
                self._persist(instance)
                return  # Pause execution, wait for resume()

    async def _execute_node(
        self,
        instance: WorkflowInstance,
        node: StepNode,
        node_state: StepState
    ) -> AsyncGenerator[EngineEvent, None]:
        """Execute an execute-type node."""
        node_state.status = "running"
        node_state.started_at = datetime.utcnow()
        node_state.execution_count += 1
        self._persist(instance)

        yield EngineEvent(
            event_type="step_start",
            instance_id=instance.id,
            node_id=node.id,
            node_name=node.name
        )

        try:
            if not node.execute_fn:
                raise ValueError(f"Node {node.id} has no execute function")

            # Execute the node function
            output = await node.execute_fn(instance.context)

            if output.success:
                node_state.status = "completed"
                node_state.output = output
                node_state.completed_at = datetime.utcnow()

                # Store output data
                instance.context.step_data[node.id] = output.data

                yield EngineEvent(
                    event_type="step_complete",
                    instance_id=instance.id,
                    node_id=node.id,
                    node_name=node.name,
                    data={
                        "output": output.data,
                        "display_title": output.display_title,
                        "display_content": output.display_content,
                        "content_type": output.content_type
                    }
                )
            else:
                node_state.status = "failed"
                node_state.error = output.error
                instance.status = WorkflowStatus.FAILED
                self._persist(instance)

                yield EngineEvent(
                    event_type="error",
                    instance_id=instance.id,
                    node_id=node.id,
                    error=output.error
                )

        except Exception as e:
            logger.exception(f"Error executing node {node.id}")
            node_state.status = "failed"
            node_state.error = str(e)
            instance.status = WorkflowStatus.FAILED
            self._persist(instance)

            yield EngineEvent(
                event_type="error",
                instance_id=instance.id,
                node_id=node.id,
                error=str(e)
            )

        self._persist(instance)

    def cancel(self, instance_id: str) -> bool:
        """Cancel a running workflow."""
        instance = self.get_instance(instance_id)
        if not instance:
            return False

        if instance.status in [WorkflowStatus.COMPLETED, WorkflowStatus.CANCELLED]:
            return False

        instance.status = WorkflowStatus.CANCELLED
        self._persist(instance)
        logger.info(f"Cancelled workflow instance {instance_id}")
        return True

    def pause(self, instance_id: str) -> bool:
        """Pause a running workflow."""
        instance = self.get_instance(instance_id)
        if not instance:
            return False

        if instance.status != WorkflowStatus.RUNNING:
            return False

        instance.status = WorkflowStatus.PAUSED
        self._persist(instance)
        return True

    def get_instance_state(self, instance_id: str) -> Optional[Dict[str, Any]]:
        """Get the current state of a workflow instance for API response."""
        instance = self.get_instance(instance_id)
        if not instance:
            return None

        current_node = None
        if instance.current_node_id:
            node = instance.context.graph.get_node(instance.current_node_id)
            if node:
                current_node = {
                    "id": node.id,
                    "name": node.name,
                    "description": node.description,
                    "node_type": node.node_type,
                    "ui_component": node.ui_component
                }

        return {
            "id": instance.id,
            "workflow_id": instance.workflow_id,
            "status": instance.status.value,
            "current_node": current_node,
            "step_data": instance.context.step_data,
            "node_states": {
                node_id: {
                    "status": state.status,
                    "execution_count": state.execution_count,
                    "error": state.error
                }
                for node_id, state in instance.context.node_states.items()
            },
            "created_at": instance.created_at.isoformat(),
            "updated_at": instance.updated_at.isoformat(),
            "completed_at": instance.completed_at.isoformat() if instance.completed_at else None
        }


# Global engine instance
workflow_engine = WorkflowEngine()
