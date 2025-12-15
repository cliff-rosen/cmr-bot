"""
Workflow Templates

Pre-built workflow templates that users can instantiate.
"""

from .research import research_workflow
from .simple_search import simple_search_workflow
from .vendor_finder import vendor_finder_workflow


def register_all_workflows():
    """Register all built-in workflow templates."""
    from ..registry import workflow_registry

    workflow_registry.register(research_workflow)
    workflow_registry.register(simple_search_workflow)
    workflow_registry.register(vendor_finder_workflow)


__all__ = [
    "research_workflow",
    "simple_search_workflow",
    "vendor_finder_workflow",
    "register_all_workflows",
]
