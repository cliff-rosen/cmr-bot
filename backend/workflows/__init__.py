"""
Workflow Engine Package

Provides a graph-based workflow execution engine.
Workflows are defined as directed graphs with nodes (execute/checkpoint) and edges (transitions).
Loops and conditionals are represented as edges with conditions.
"""

from schemas.workflow import (
    # Core types
    CheckpointAction,
    StepOutput,
    CheckpointConfig,
    WorkflowStatus,
    StepState,
    WorkflowContext,
    WorkflowInstance,
    # Graph types
    StepNode,
    Edge,
    WorkflowGraph,
    # Backwards compatibility alias
    WorkflowDefinition,
)
from .registry import workflow_registry, WorkflowRegistry
from .engine import workflow_engine, WorkflowEngine, EngineEvent

__all__ = [
    # Core types
    "CheckpointAction",
    "StepOutput",
    "CheckpointConfig",
    "WorkflowStatus",
    "StepState",
    "WorkflowContext",
    "WorkflowInstance",
    # Graph types
    "StepNode",
    "Edge",
    "WorkflowGraph",
    # Backwards compatibility
    "WorkflowDefinition",
    # Registry
    "workflow_registry",
    "WorkflowRegistry",
    # Engine
    "workflow_engine",
    "WorkflowEngine",
    "EngineEvent",
]
