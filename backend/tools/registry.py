"""
Tool Registry for CMR Bot

Global registry of tools available to the primary agent.
Tools are capabilities the agent can invoke regardless of UI state.
"""

from typing import Dict, List, Any, Callable, Optional
from dataclasses import dataclass
from sqlalchemy.orm import Session


@dataclass
class ToolProgress:
    """Progress update from a streaming tool."""
    stage: str  # Current stage name (e.g., "creating_checklist", "searching")
    message: str  # Human-readable status message
    data: Optional[Dict[str, Any]] = None  # Optional structured data for UI
    progress: Optional[float] = None  # Optional 0-1 progress indicator


@dataclass
class ToolResult:
    """Result from a tool execution."""
    text: str  # Text result to send back to LLM
    data: Optional[Dict[str, Any]] = None  # Structured data for frontend/workspace
    workspace_payload: Optional[Dict[str, Any]] = None  # Payload to display in workspace panel


@dataclass
class ToolConfig:
    """Configuration for a tool the agent can use."""
    name: str  # Tool name (e.g., "web_search", "create_asset")
    description: str  # Description for the LLM
    input_schema: Dict[str, Any]  # JSON schema for tool parameters
    executor: Callable[[Dict[str, Any], Session, int, Dict[str, Any]], Any]
    # executor signature: (params, db, user_id, context) -> str | ToolResult | Generator[ToolProgress, None, ToolResult]
    category: str = "general"  # Tool category for organization
    streaming: bool = False  # If True, executor yields ToolProgress before returning ToolResult


class ToolRegistry:
    """Global registry of tools available to the primary agent."""

    def __init__(self):
        self._tools: Dict[str, ToolConfig] = {}

    def register(self, tool: ToolConfig):
        """Register a tool."""
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[ToolConfig]:
        """Get a tool by name."""
        return self._tools.get(name)

    def get_all(self) -> List[ToolConfig]:
        """Get all registered tools."""
        return list(self._tools.values())

    def get_by_category(self, category: str) -> List[ToolConfig]:
        """Get tools by category."""
        return [t for t in self._tools.values() if t.category == category]

    def to_anthropic_format(self) -> List[Dict[str, Any]]:
        """Convert all tools to Anthropic API format."""
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.input_schema
            }
            for tool in self._tools.values()
        ]


# Global registry instance
_tool_registry = ToolRegistry()


def register_tool(tool: ToolConfig):
    """Register a tool in the global registry."""
    _tool_registry.register(tool)


def get_tool(name: str) -> Optional[ToolConfig]:
    """Get a tool by name."""
    return _tool_registry.get(name)


def get_all_tools() -> List[ToolConfig]:
    """Get all registered tools."""
    return _tool_registry.get_all()


def get_tools_by_category(category: str) -> List[ToolConfig]:
    """Get tools by category."""
    return _tool_registry.get_by_category(category)


def get_tools_for_anthropic() -> List[Dict[str, Any]]:
    """Get all tools in Anthropic API format."""
    return _tool_registry.to_anthropic_format()
