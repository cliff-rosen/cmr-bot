"""
Chat Payloads Package

This package contains the payload configuration registry for the chat system.
Page-specific payload configurations can be registered to provide rich interactions.
"""

from .registry import (
    PayloadConfig,
    PageConfig,
    ClientAction,
    ToolConfig,
    ToolResult,
    get_page_payloads,
    get_page_context_builder,
    get_page_client_actions,
    get_page_tools,
    has_page_payloads,
    register_page
)

__all__ = [
    'PayloadConfig',
    'PageConfig',
    'ClientAction',
    'ToolConfig',
    'ToolResult',
    'get_page_payloads',
    'get_page_context_builder',
    'get_page_client_actions',
    'get_page_tools',
    'has_page_payloads',
    'register_page'
]
