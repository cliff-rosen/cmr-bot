"""
Built-in tools for CMR Bot.

This package contains the standard tools available to the agent.
"""

from .search import register_search_tools
from .memory import register_memory_tools
from .research import register_research_tools
from .research_workflow import register_research_workflow_tool
from .iterator import register_iterator_tools
from .map_reduce import register_map_reduce_tools
from .workflow_builder import register_workflow_builder_tools
from .smart_search import register_smart_search_tools
from .pubmed_search import register_pubmed_search_tools
from .pubmed_smart_search import register_pubmed_smart_search_tools
from .arxiv_search import register_arxiv_search_tools
from .assets import register_asset_tools
from .gmail import register_gmail_tools
from .agents import register_agent_tools
from .review_collector import register_review_collector_tools
from .entity_verification import register_entity_verification_tool
from .review_analyzer import register_review_analyzer_tool


def register_all_builtin_tools():
    """Register all built-in tools. Called at startup."""
    register_search_tools()
    register_memory_tools()
    register_research_tools()
    register_research_workflow_tool()
    register_iterator_tools()
    register_map_reduce_tools()
    register_workflow_builder_tools()
    register_smart_search_tools()
    register_pubmed_search_tools()
    register_pubmed_smart_search_tools()
    register_arxiv_search_tools()
    register_asset_tools()
    register_gmail_tools()
    register_agent_tools()
    register_review_collector_tools()
    register_entity_verification_tool()
    register_review_analyzer_tool()


__all__ = [
    'register_search_tools',
    'register_memory_tools',
    'register_research_tools',
    'register_research_workflow_tool',
    'register_iterator_tools',
    'register_map_reduce_tools',
    'register_workflow_builder_tools',
    'register_smart_search_tools',
    'register_pubmed_search_tools',
    'register_pubmed_smart_search_tools',
    'register_arxiv_search_tools',
    'register_asset_tools',
    'register_gmail_tools',
    'register_agent_tools',
    'register_review_collector_tools',
    'register_entity_verification_tool',
    'register_review_analyzer_tool',
    'register_all_builtin_tools'
]
