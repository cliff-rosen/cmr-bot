"""
Built-in tools for CMR Bot.

This package contains the standard tools available to the agent.
"""

from .search import register_search_tools
from .memory import register_memory_tools
from .research import register_research_tools
from .iterator import register_iterator_tools
from .map_reduce import register_map_reduce_tools


def register_all_builtin_tools():
    """Register all built-in tools. Called at startup."""
    register_search_tools()
    register_memory_tools()
    register_research_tools()
    register_iterator_tools()
    register_map_reduce_tools()


__all__ = [
    'register_search_tools',
    'register_memory_tools',
    'register_research_tools',
    'register_iterator_tools',
    'register_map_reduce_tools',
    'register_all_builtin_tools'
]
