"""
Workflow Engine

The core engine that executes workflow instances.
Handles step execution, checkpoints, conditionals, and loops.
"""

import logging
from typing import Any, AsyncGenerator, Dict, Optional, Callable
from datetime import datetime
from dataclasses import dataclass

from schemas.workflow import (
    WorkflowDefinition,
    WorkflowInstance,
    WorkflowStatus,
    WorkflowContext,
    StepDefinition,
    StepState,
    StepOutput,
    StepType,
    CheckpointAction,
)
from .registry import workflow_registry

logger = logging.getLogger(__name__)


@dataclass
class EngineEvent:
    """Event emitted by the workflow engine during execution."""
    event_type: str  # "step_start", "step_complete", "checkpoint", "error", "complete"
    instance_id: str
    step_id: Optional[str] = None
    step_name: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class WorkflowEngine:
    """
    Executes workflow instances.

    The engine:
    1. Loads workflow definitions from the registry
    2. Executes steps in order
    3. Handles checkpoints by pausing and waiting for user input
    4. Evaluates conditionals and loops
    5. Emits events for UI updates
    """

    def __init__(self):
        # In-memory store of running instances
        # In production, this would be backed by a database
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
        """Create a new workflow instance."""
        workflow_def = workflow_registry.get(workflow_id)
        if not workflow_def:
            raise ValueError(f"Workflow '{workflow_id}' not found in registry")

        instance = WorkflowInstance.create(
            workflow_def=workflow_def,
            initial_input=initial_input,
            conversation_id=conversation_id
        )

        self._persist(instance)
        logger.info(f"Created workflow instance {instance.id} for workflow {workflow_id}")
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
        async for event in self.execute_until_checkpoint(instance):
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

        current_step = instance.context.definition.get_step(instance.current_step_id)
        if not current_step:
            yield EngineEvent(
                event_type="error",
                instance_id=instance_id,
                error=f"Current step {instance.current_step_id} not found"
            )
            return

        # Handle the checkpoint action
        if action == CheckpointAction.REJECT:
            instance.status = WorkflowStatus.CANCELLED
            self._persist(instance)
            yield EngineEvent(
                event_type="cancelled",
                instance_id=instance_id,
                step_id=current_step.id
            )
            return

        if action == CheckpointAction.EDIT and user_data:
            # Store user edits
            instance.context.user_edits[current_step.id] = user_data
            # Also update step_data with edits
            if current_step.id in instance.context.step_data:
                instance.context.step_data[current_step.id].update(user_data)
            else:
                instance.context.step_data[current_step.id] = user_data

        # Mark checkpoint step as complete
        step_state = instance.context.step_states.get(current_step.id)
        if step_state:
            step_state.status = "completed"
            step_state.completed_at = datetime.utcnow()

        # Move to next step
        next_step_id = current_step.next_step_id
        if not next_step_id:
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

        instance.current_step_id = next_step_id
        instance.context.current_step_id = next_step_id
        instance.status = WorkflowStatus.RUNNING
        self._persist(instance)

        # Continue execution
        async for event in self._execute_until_checkpoint(instance):
            yield event

    async def _execute_until_checkpoint(
        self,
        instance: WorkflowInstance
    ) -> AsyncGenerator[EngineEvent, None]:
        """
        Execute steps until we hit a checkpoint or complete.
        """
        while instance.current_step_id:
            step = instance.context.definition.get_step(instance.current_step_id)
            if not step:
                instance.status = WorkflowStatus.FAILED
                self._persist(instance)
                yield EngineEvent(
                    event_type="error",
                    instance_id=instance.id,
                    error=f"Step {instance.current_step_id} not found"
                )
                return

            # Initialize step state if not exists
            if step.id not in instance.context.step_states:
                instance.context.step_states[step.id] = StepState(
                    step_id=step.id,
                    status="pending"
                )

            step_state = instance.context.step_states[step.id]

            # Handle different step types
            if step.step_type == StepType.EXECUTE:
                async for event in self._execute_step(instance, step, step_state):
                    yield event
                    if event.event_type == "error":
                        return

            elif step.step_type == StepType.CHECKPOINT:
                # Pause at checkpoint
                yield EngineEvent(
                    event_type="checkpoint",
                    instance_id=instance.id,
                    step_id=step.id,
                    step_name=step.name,
                    data={
                        "checkpoint_config": {
                            "title": step.checkpoint_config.title,
                            "description": step.checkpoint_config.description,
                            "allowed_actions": [a.value for a in step.checkpoint_config.allowed_actions],
                            "editable_fields": step.checkpoint_config.editable_fields,
                        } if step.checkpoint_config else None,
                        "step_data": instance.context.step_data,
                        "current_output": instance.context.step_data.get(
                            self._get_previous_step_id(instance, step.id)
                        )
                    }
                )
                instance.status = WorkflowStatus.WAITING
                step_state.status = "running"  # Waiting at checkpoint
                step_state.started_at = datetime.utcnow()
                self._persist(instance)
                return  # Pause execution

            elif step.step_type == StepType.CONDITIONAL:
                next_step_id = step.condition_fn(instance.context) if step.condition_fn else step.next_step_id
                step_state.status = "completed"
                instance.current_step_id = next_step_id
                instance.context.current_step_id = next_step_id
                self._persist(instance)
                continue

            elif step.step_type == StepType.LOOP:
                step_state.execution_count += 1
                should_continue = step.loop_condition_fn(instance.context) if step.loop_condition_fn else False
                if should_continue and step.loop_step_id:
                    instance.current_step_id = step.loop_step_id
                    instance.context.current_step_id = step.loop_step_id
                else:
                    step_state.status = "completed"
                    instance.current_step_id = step.next_step_id
                    instance.context.current_step_id = step.next_step_id
                self._persist(instance)
                continue

            # Move to next step
            if step_state.status == "completed" and step.next_step_id:
                instance.current_step_id = step.next_step_id
                instance.context.current_step_id = step.next_step_id
                self._persist(instance)
            elif step_state.status == "completed" and not step.next_step_id:
                # Workflow complete
                instance.status = WorkflowStatus.COMPLETED
                instance.completed_at = datetime.utcnow()
                instance.final_output = instance.context.step_data
                self._persist(instance)
                yield EngineEvent(
                    event_type="complete",
                    instance_id=instance.id,
                    data=instance.final_output
                )
                return
            else:
                # Step didn't complete successfully
                return

    async def _execute_step(
        self,
        instance: WorkflowInstance,
        step: StepDefinition,
        step_state: StepState
    ) -> AsyncGenerator[EngineEvent, None]:
        """Execute an EXECUTE type step."""
        step_state.status = "running"
        step_state.started_at = datetime.utcnow()
        step_state.execution_count += 1
        self._persist(instance)

        yield EngineEvent(
            event_type="step_start",
            instance_id=instance.id,
            step_id=step.id,
            step_name=step.name
        )

        try:
            if not step.execute_fn:
                raise ValueError(f"Step {step.id} has no execute function")

            # Execute the step function
            output = await step.execute_fn(instance.context)

            if output.success:
                step_state.status = "completed"
                step_state.output = output
                step_state.completed_at = datetime.utcnow()

                # Store output data
                instance.context.step_data[step.id] = output.data

                yield EngineEvent(
                    event_type="step_complete",
                    instance_id=instance.id,
                    step_id=step.id,
                    step_name=step.name,
                    data={
                        "output": output.data,
                        "display_title": output.display_title,
                        "display_content": output.display_content,
                        "content_type": output.content_type
                    }
                )
            else:
                step_state.status = "failed"
                step_state.error = output.error
                instance.status = WorkflowStatus.FAILED
                self._persist(instance)

                yield EngineEvent(
                    event_type="error",
                    instance_id=instance.id,
                    step_id=step.id,
                    error=output.error
                )

        except Exception as e:
            logger.exception(f"Error executing step {step.id}")
            step_state.status = "failed"
            step_state.error = str(e)
            instance.status = WorkflowStatus.FAILED
            self._persist(instance)

            yield EngineEvent(
                event_type="error",
                instance_id=instance.id,
                step_id=step.id,
                error=str(e)
            )

        self._persist(instance)

    def _get_previous_step_id(self, instance: WorkflowInstance, current_step_id: str) -> Optional[str]:
        """Get the ID of the step that executed before the current one."""
        steps = instance.context.definition.steps
        for i, step in enumerate(steps):
            if step.id == current_step_id and i > 0:
                return steps[i - 1].id
        return None

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

        current_step = None
        if instance.current_step_id:
            step = instance.context.definition.get_step(instance.current_step_id)
            if step:
                current_step = {
                    "id": step.id,
                    "name": step.name,
                    "description": step.description,
                    "step_type": step.step_type.value,
                    "ui_component": step.ui_component
                }

        return {
            "id": instance.id,
            "workflow_id": instance.workflow_id,
            "status": instance.status.value,
            "current_step": current_step,
            "step_data": instance.context.step_data,
            "step_states": {
                step_id: {
                    "status": state.status,
                    "execution_count": state.execution_count,
                    "error": state.error
                }
                for step_id, state in instance.context.step_states.items()
            },
            "created_at": instance.created_at.isoformat(),
            "updated_at": instance.updated_at.isoformat(),
            "completed_at": instance.completed_at.isoformat() if instance.completed_at else None
        }


# Global engine instance
workflow_engine = WorkflowEngine()
