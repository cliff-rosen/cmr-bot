"""
Workflow Registry

Central registry for all available workflow graph templates.
"""

from typing import Dict, List, Optional
from schemas.workflow import WorkflowGraph


class WorkflowRegistry:
    """
    Registry for workflow graph definitions.

    Workflows are registered at startup and can be retrieved by ID.
    """

    _instance: Optional["WorkflowRegistry"] = None

    def __init__(self):
        self._workflows: Dict[str, WorkflowGraph] = {}

    @classmethod
    def get_instance(cls) -> "WorkflowRegistry":
        """Get the singleton registry instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def register(self, workflow: WorkflowGraph) -> None:
        """Register a workflow graph definition."""
        if workflow.id in self._workflows:
            raise ValueError(f"Workflow '{workflow.id}' is already registered")

        # Validate before registering
        errors = workflow.validate()
        if errors:
            raise ValueError(f"Invalid workflow '{workflow.id}': {errors}")

        self._workflows[workflow.id] = workflow

    def get(self, workflow_id: str) -> Optional[WorkflowGraph]:
        """Get a workflow graph by ID."""
        return self._workflows.get(workflow_id)

    def get_all(self) -> List[WorkflowGraph]:
        """Get all registered workflow graphs."""
        return list(self._workflows.values())

    def get_by_category(self, category: str) -> List[WorkflowGraph]:
        """Get all workflows in a category."""
        return [w for w in self._workflows.values() if w.category == category]

    def list_categories(self) -> List[str]:
        """Get all unique categories."""
        return list(set(w.category for w in self._workflows.values()))

    def to_dict(self, workflow_id: str) -> Optional[Dict]:
        """Get a workflow graph as a dict for API responses."""
        workflow = self.get(workflow_id)
        if not workflow:
            return None

        return {
            "id": workflow.id,
            "name": workflow.name,
            "description": workflow.description,
            "icon": workflow.icon,
            "category": workflow.category,
            "input_schema": workflow.input_schema,
            "output_schema": workflow.output_schema,
            "entry_node": workflow.entry_node,
            "nodes": {
                node_id: {
                    "id": node.id,
                    "name": node.name,
                    "description": node.description,
                    "node_type": node.node_type,
                    "ui_component": node.ui_component,
                    "checkpoint_config": {
                        "title": node.checkpoint_config.title,
                        "description": node.checkpoint_config.description,
                        "allowed_actions": [a.value for a in node.checkpoint_config.allowed_actions],
                        "editable_fields": node.checkpoint_config.editable_fields,
                    } if node.checkpoint_config else None
                }
                for node_id, node in workflow.nodes.items()
            },
            "edges": [
                {
                    "from_node": edge.from_node,
                    "to_node": edge.to_node,
                    "label": edge.label,
                    # Note: condition functions can't be serialized
                    "has_condition": edge.condition is not None
                }
                for edge in workflow.edges
            ]
        }

    def list_all_dict(self) -> List[Dict]:
        """Get all workflows as dicts for API responses."""
        return [
            {
                "id": w.id,
                "name": w.name,
                "description": w.description,
                "icon": w.icon,
                "category": w.category,
            }
            for w in self._workflows.values()
        ]


# Global registry instance
workflow_registry = WorkflowRegistry.get_instance()
