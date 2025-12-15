"""
Asset Tools

Tools for retrieving and searching user assets.
Allows the agent to access asset contents, with chunking support for large assets.
"""

import logging
import re
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from tools.registry import ToolConfig, ToolResult, register_tool

logger = logging.getLogger(__name__)

# Thresholds
MAX_CONTENT_DIRECT = 8000  # Return full content if under this size
CHUNK_SIZE = 2000  # Size of chunks for search results
SEARCH_CONTEXT_CHARS = 200  # Characters of context around search matches


def execute_list_assets(
    params: Dict[str, Any],
    db: Session,
    user_id: int,
    context: Dict[str, Any]
) -> ToolResult:
    """List available assets for the user."""
    from services.asset_service import AssetService
    from models import AssetType

    asset_type_filter = params.get("asset_type")
    in_context_only = params.get("in_context_only", False)

    service = AssetService(db, user_id)

    # Convert string to AssetType enum if provided
    asset_type = None
    if asset_type_filter:
        try:
            asset_type = AssetType(asset_type_filter)
        except ValueError:
            pass

    assets = service.list_assets(
        asset_type=asset_type,
        in_context_only=in_context_only,
        limit=50
    )

    if not assets:
        return ToolResult(
            text="No assets found.",
            data={"assets": [], "count": 0}
        )

    # Format asset list
    formatted = f"**Found {len(assets)} assets:**\n\n"
    asset_list = []

    for asset in assets:
        content_size = len(asset.content) if asset.content else 0
        size_note = f" ({content_size:,} chars)" if content_size > 0 else ""
        context_marker = " [IN CONTEXT]" if asset.is_in_context else ""

        formatted += f"- **{asset.name}** (ID: {asset.asset_id}, type: {asset.asset_type.value}){size_note}{context_marker}\n"
        if asset.description:
            formatted += f"  {asset.description[:100]}{'...' if len(asset.description) > 100 else ''}\n"

        asset_list.append({
            "asset_id": asset.asset_id,
            "name": asset.name,
            "type": asset.asset_type.value,
            "description": asset.description,
            "content_size": content_size,
            "is_in_context": asset.is_in_context,
            "has_summary": bool(asset.context_summary)
        })

    return ToolResult(
        text=formatted,
        data={"assets": asset_list, "count": len(assets)}
    )


def execute_get_asset(
    params: Dict[str, Any],
    db: Session,
    user_id: int,
    context: Dict[str, Any]
) -> ToolResult:
    """Get asset content by ID or name."""
    from services.asset_service import AssetService

    asset_id = params.get("asset_id")
    asset_name = params.get("name")
    include_content = params.get("include_content", True)
    offset = params.get("offset", 0)
    limit = params.get("limit", MAX_CONTENT_DIRECT)

    if not asset_id and not asset_name:
        return ToolResult(text="Error: Must provide either asset_id or name")

    service = AssetService(db, user_id)

    # Find asset
    asset = None
    if asset_id:
        asset = service.get_asset(asset_id)
    elif asset_name:
        # Search by name
        assets = service.list_assets(limit=100)
        for a in assets:
            if a.name.lower() == asset_name.lower():
                asset = a
                break
        # Fuzzy match if exact not found
        if not asset:
            for a in assets:
                if asset_name.lower() in a.name.lower():
                    asset = a
                    break

    if not asset:
        return ToolResult(
            text=f"Asset not found: {asset_id or asset_name}",
            data={"success": False, "error": "not_found"}
        )

    content_size = len(asset.content) if asset.content else 0

    # Build response
    formatted = f"**{asset.name}**\n"
    formatted += f"- Type: {asset.asset_type.value}\n"
    formatted += f"- ID: {asset.asset_id}\n"
    if asset.description:
        formatted += f"- Description: {asset.description}\n"
    if asset.tags:
        formatted += f"- Tags: {', '.join(asset.tags)}\n"
    formatted += f"- Content size: {content_size:,} characters\n"
    formatted += f"- In context: {asset.is_in_context}\n"

    result_data = {
        "success": True,
        "asset_id": asset.asset_id,
        "name": asset.name,
        "type": asset.asset_type.value,
        "description": asset.description,
        "content_size": content_size,
        "is_in_context": asset.is_in_context
    }

    if include_content and asset.content:
        if content_size <= MAX_CONTENT_DIRECT:
            # Return full content
            formatted += f"\n**Content:**\n```\n{asset.content}\n```"
            result_data["content"] = asset.content
            result_data["is_complete"] = True
        else:
            # Return chunk with pagination info
            chunk = asset.content[offset:offset + limit]
            remaining = content_size - (offset + len(chunk))

            formatted += f"\n**Content (showing {offset:,}-{offset + len(chunk):,} of {content_size:,}):**\n"
            formatted += f"```\n{chunk}\n```"

            if remaining > 0:
                formatted += f"\n*{remaining:,} more characters available. Use offset={offset + limit} to continue.*"

            result_data["content"] = chunk
            result_data["offset"] = offset
            result_data["is_complete"] = False
            result_data["remaining"] = remaining
            result_data["next_offset"] = offset + limit if remaining > 0 else None
    elif asset.context_summary:
        formatted += f"\n**Summary:**\n{asset.context_summary}"
        result_data["summary"] = asset.context_summary

    return ToolResult(text=formatted, data=result_data)


def execute_search_asset(
    params: Dict[str, Any],
    db: Session,
    user_id: int,
    context: Dict[str, Any]
) -> ToolResult:
    """Search within asset content."""
    from services.asset_service import AssetService

    asset_id = params.get("asset_id")
    asset_name = params.get("name")
    query = params.get("query", "")
    case_sensitive = params.get("case_sensitive", False)
    max_matches = params.get("max_matches", 10)

    if not asset_id and not asset_name:
        return ToolResult(text="Error: Must provide either asset_id or name")
    if not query:
        return ToolResult(text="Error: Must provide search query")

    service = AssetService(db, user_id)

    # Find asset
    asset = None
    if asset_id:
        asset = service.get_asset(asset_id)
    elif asset_name:
        assets = service.list_assets(limit=100)
        for a in assets:
            if a.name.lower() == asset_name.lower() or asset_name.lower() in a.name.lower():
                asset = a
                break

    if not asset:
        return ToolResult(
            text=f"Asset not found: {asset_id or asset_name}",
            data={"success": False, "error": "not_found"}
        )

    if not asset.content:
        return ToolResult(
            text=f"Asset '{asset.name}' has no searchable content.",
            data={"success": False, "error": "no_content"}
        )

    # Perform search
    content = asset.content
    search_content = content if case_sensitive else content.lower()
    search_query = query if case_sensitive else query.lower()

    matches = []
    start = 0
    while len(matches) < max_matches:
        pos = search_content.find(search_query, start)
        if pos == -1:
            break

        # Extract context around match
        context_start = max(0, pos - SEARCH_CONTEXT_CHARS)
        context_end = min(len(content), pos + len(query) + SEARCH_CONTEXT_CHARS)

        # Adjust to word boundaries if possible
        if context_start > 0:
            space_pos = content.rfind(' ', context_start - 50, context_start)
            if space_pos > 0:
                context_start = space_pos + 1
        if context_end < len(content):
            space_pos = content.find(' ', context_end, context_end + 50)
            if space_pos > 0:
                context_end = space_pos

        snippet = content[context_start:context_end]
        prefix = "..." if context_start > 0 else ""
        suffix = "..." if context_end < len(content) else ""

        matches.append({
            "position": pos,
            "snippet": f"{prefix}{snippet}{suffix}",
            "line_number": content[:pos].count('\n') + 1
        })

        start = pos + len(query)

    if not matches:
        return ToolResult(
            text=f"No matches found for '{query}' in asset '{asset.name}'.",
            data={"success": True, "matches": [], "total_matches": 0}
        )

    # Format results
    formatted = f"**Search results for '{query}' in '{asset.name}':**\n"
    formatted += f"Found {len(matches)} match{'es' if len(matches) != 1 else ''}\n\n"

    for i, match in enumerate(matches, 1):
        formatted += f"**Match {i}** (position {match['position']:,}, line {match['line_number']}):\n"
        formatted += f"```\n{match['snippet']}\n```\n\n"

    return ToolResult(
        text=formatted,
        data={
            "success": True,
            "asset_id": asset.asset_id,
            "asset_name": asset.name,
            "query": query,
            "matches": matches,
            "total_matches": len(matches)
        }
    )


def execute_save_asset(
    params: Dict[str, Any],
    db: Session,
    user_id: int,
    context: Dict[str, Any]
) -> ToolResult:
    """Save content as a new asset."""
    from services.asset_service import AssetService
    from models import AssetType

    name = params.get("name")
    content = params.get("content")
    asset_type = params.get("asset_type", "document")
    description = params.get("description")

    if not name:
        return ToolResult(text="Error: Must provide asset name")
    if not content:
        return ToolResult(text="Error: Must provide content to save")

    # Validate asset type
    try:
        asset_type_enum = AssetType(asset_type)
    except ValueError:
        return ToolResult(text=f"Error: Invalid asset type '{asset_type}'. Valid types: file, document, data, code, link, list")

    service = AssetService(db, user_id)

    # Get agent context if running in agent
    agent_id = context.get("agent_id")
    run_id = context.get("run_id")

    asset = service.create_asset(
        name=name,
        asset_type=asset_type_enum,
        content=content,
        description=description,
        created_by_agent_id=agent_id,
        agent_run_id=run_id
    )

    return ToolResult(
        text=f"Asset saved successfully!\n- Name: {asset.name}\n- ID: {asset.asset_id}\n- Type: {asset.asset_type.value}\n- Size: {len(content):,} characters",
        data={
            "success": True,
            "asset_id": asset.asset_id,
            "name": asset.name,
            "type": asset.asset_type.value,
            "content_size": len(content)
        }
    )


SAVE_ASSET_TOOL = ToolConfig(
    name="save_asset",
    description="""Save content as a user asset.

Use this to save important outputs like:
- Research reports or summaries
- Collected data
- Generated code
- Lists of items

The asset will be available to the user in their asset library.""",
    input_schema={
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Name for the asset (descriptive, e.g., 'AI News Summary - Dec 2024')"
            },
            "content": {
                "type": "string",
                "description": "The content to save"
            },
            "asset_type": {
                "type": "string",
                "enum": ["document", "data", "code", "list"],
                "default": "document",
                "description": "Type of asset"
            },
            "description": {
                "type": "string",
                "description": "Optional description of the asset"
            }
        },
        "required": ["name", "content"]
    },
    output_schema={
        "type": "object",
        "properties": {
            "success": {"type": "boolean", "description": "Whether the save operation succeeded"},
            "asset_id": {"type": "integer", "description": "ID of the created asset"},
            "name": {"type": "string", "description": "Name of the saved asset"},
            "type": {"type": "string", "description": "Asset type (document, data, code, list)"},
            "content_size": {"type": "integer", "description": "Size of saved content in characters"}
        },
        "required": ["success", "asset_id", "name", "type", "content_size"]
    },
    executor=execute_save_asset,
    category="assets"
)


# Tool configurations
LIST_ASSETS_TOOL = ToolConfig(
    name="list_assets",
    description="List available user assets. Use this to see what assets exist before retrieving them.",
    input_schema={
        "type": "object",
        "properties": {
            "asset_type": {
                "type": "string",
                "enum": ["file", "document", "data", "code", "link", "list"],
                "description": "Filter by asset type"
            },
            "in_context_only": {
                "type": "boolean",
                "default": False,
                "description": "Only show assets currently in context"
            }
        }
    },
    output_schema={
        "type": "object",
        "properties": {
            "assets": {
                "type": "array",
                "description": "List of available assets",
                "items": {
                    "type": "object",
                    "properties": {
                        "asset_id": {"type": "integer", "description": "Unique asset ID"},
                        "name": {"type": "string", "description": "Asset name"},
                        "type": {"type": "string", "description": "Asset type"},
                        "description": {"type": ["string", "null"], "description": "Asset description"},
                        "content_size": {"type": "integer", "description": "Content size in characters"},
                        "is_in_context": {"type": "boolean", "description": "Whether asset is in current context"},
                        "has_summary": {"type": "boolean", "description": "Whether asset has a summary"}
                    },
                    "required": ["asset_id", "name", "type", "content_size", "is_in_context"]
                }
            },
            "count": {"type": "integer", "description": "Total number of assets returned"}
        },
        "required": ["assets", "count"]
    },
    executor=execute_list_assets,
    category="assets"
)

GET_ASSET_TOOL = ToolConfig(
    name="get_asset",
    description="""Retrieve asset content by ID or name.

For small assets (<8000 chars): returns full content.
For large assets: returns a chunk with pagination. Use offset parameter to get more.

Use this to read the actual content of an asset.""",
    input_schema={
        "type": "object",
        "properties": {
            "asset_id": {
                "type": "integer",
                "description": "Asset ID to retrieve"
            },
            "name": {
                "type": "string",
                "description": "Asset name to search for (exact or partial match)"
            },
            "include_content": {
                "type": "boolean",
                "default": True,
                "description": "Whether to include content (set false for metadata only)"
            },
            "offset": {
                "type": "integer",
                "default": 0,
                "description": "Character offset for large assets (pagination)"
            },
            "limit": {
                "type": "integer",
                "default": 8000,
                "description": "Max characters to return per request"
            }
        }
    },
    output_schema={
        "type": "object",
        "properties": {
            "success": {"type": "boolean", "description": "Whether the retrieval succeeded"},
            "asset_id": {"type": "integer", "description": "Asset ID"},
            "name": {"type": "string", "description": "Asset name"},
            "type": {"type": "string", "description": "Asset type"},
            "description": {"type": ["string", "null"], "description": "Asset description"},
            "content_size": {"type": "integer", "description": "Total content size in characters"},
            "is_in_context": {"type": "boolean", "description": "Whether asset is in current context"},
            "content": {"type": "string", "description": "Asset content (full or chunk)"},
            "is_complete": {"type": "boolean", "description": "Whether full content was returned"},
            "offset": {"type": "integer", "description": "Current offset for paginated content"},
            "remaining": {"type": "integer", "description": "Remaining characters not yet returned"},
            "next_offset": {"type": ["integer", "null"], "description": "Offset to use for next chunk"},
            "summary": {"type": "string", "description": "Asset summary if available"},
            "error": {"type": "string", "description": "Error code if retrieval failed"}
        },
        "required": ["success"]
    },
    executor=execute_get_asset,
    category="assets"
)

SEARCH_ASSET_TOOL = ToolConfig(
    name="search_asset",
    description="""Search within an asset's content.

Returns matching snippets with surrounding context. Use this for large assets
when you need to find specific information without reading the entire content.""",
    input_schema={
        "type": "object",
        "properties": {
            "asset_id": {
                "type": "integer",
                "description": "Asset ID to search"
            },
            "name": {
                "type": "string",
                "description": "Asset name to search (exact or partial match)"
            },
            "query": {
                "type": "string",
                "description": "Text to search for"
            },
            "case_sensitive": {
                "type": "boolean",
                "default": False,
                "description": "Whether search is case-sensitive"
            },
            "max_matches": {
                "type": "integer",
                "default": 10,
                "description": "Maximum number of matches to return"
            }
        },
        "required": ["query"]
    },
    output_schema={
        "type": "object",
        "properties": {
            "success": {"type": "boolean", "description": "Whether search succeeded"},
            "asset_id": {"type": "integer", "description": "ID of searched asset"},
            "asset_name": {"type": "string", "description": "Name of searched asset"},
            "query": {"type": "string", "description": "The search query"},
            "matches": {
                "type": "array",
                "description": "List of matching snippets",
                "items": {
                    "type": "object",
                    "properties": {
                        "position": {"type": "integer", "description": "Character position of match"},
                        "snippet": {"type": "string", "description": "Text snippet with surrounding context"},
                        "line_number": {"type": "integer", "description": "Line number of match"}
                    },
                    "required": ["position", "snippet", "line_number"]
                }
            },
            "total_matches": {"type": "integer", "description": "Total number of matches found"},
            "error": {"type": "string", "description": "Error code if search failed"}
        },
        "required": ["success"]
    },
    executor=execute_search_asset,
    category="assets"
)


def register_asset_tools():
    """Register all asset tools."""
    register_tool(SAVE_ASSET_TOOL)
    register_tool(LIST_ASSETS_TOOL)
    register_tool(GET_ASSET_TOOL)
    register_tool(SEARCH_ASSET_TOOL)
    logger.info("Registered 4 asset tools")
