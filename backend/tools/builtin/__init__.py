"""
Built-in tools for CMR Bot.

This package contains the standard tools available to the agent.
"""

from .search import register_search_tools
from .memory import register_memory_tools
from .research import register_research_tools
from .iterator import register_iterator_tools
from .map_reduce import register_map_reduce_tools
from .workflow_builder import register_workflow_builder_tools
from .smart_search import register_smart_search_tools
from .pubmed_search import register_pubmed_search_tools
from .arxiv_search import register_arxiv_search_tools
from .assets import register_asset_tools


def register_all_builtin_tools():
    """Register all built-in tools. Called at startup."""
    register_search_tools()
    register_memory_tools()
    register_research_tools()
    register_iterator_tools()
    register_map_reduce_tools()
    register_workflow_builder_tools()
    register_smart_search_tools()
    register_pubmed_search_tools()
    register_arxiv_search_tools()
    register_asset_tools()


__all__ = [
    'register_search_tools',
    'register_memory_tools',
    'register_research_tools',
    'register_iterator_tools',
    'register_map_reduce_tools',
    'register_workflow_builder_tools',
    'register_smart_search_tools',
    'register_pubmed_search_tools',
    'register_arxiv_search_tools',
    'register_asset_tools',
    'register_all_builtin_tools'
]
