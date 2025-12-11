"""
Memory tools for CMR Bot primary agent.

These tools allow the agent to manage user memories:
- Save important information for future reference
- Search for relevant memories
- Delete outdated or incorrect memories
"""

import logging
from typing import Dict, Any
from sqlalchemy.orm import Session

from .registry import ToolConfig, ToolResult, register_tool
from services.memory_service import MemoryService
from models import MemoryType

logger = logging.getLogger(__name__)


# =============================================================================
# Save Memory Tool
# =============================================================================

def execute_save_memory(
    params: Dict[str, Any],
    db: Session,
    user_id: int,
    context: Dict[str, Any]
) -> ToolResult:
    """Save a memory for the user."""
    content = params.get("content", "").strip()
    memory_type = params.get("memory_type", "fact")
    category = params.get("category")
    is_pinned = params.get("is_pinned", False)

    if not content:
        return ToolResult(text="Error: No content provided for memory")

    # Convert string to enum
    try:
        mem_type = MemoryType(memory_type)
    except ValueError:
        return ToolResult(text=f"Error: Invalid memory_type '{memory_type}'. Valid types: fact, preference, entity, project, working")

    try:
        service = MemoryService(db, user_id)

        # Get conversation_id from context if available
        conversation_id = context.get("conversation_id")

        memory = service.create_memory(
            content=content,
            memory_type=mem_type,
            category=category,
            source_conversation_id=conversation_id,
            is_pinned=is_pinned
        )

        return ToolResult(
            text=f"Saved memory: \"{content}\" (type: {memory_type}, id: {memory.memory_id})",
            data={
                "type": "memory_saved",
                "memory_id": memory.memory_id,
                "memory_type": memory_type,
                "content": content
            }
        )

    except Exception as e:
        logger.error(f"Error saving memory: {e}", exc_info=True)
        return ToolResult(text=f"Error saving memory: {str(e)}")


SAVE_MEMORY_TOOL = ToolConfig(
    name="save_memory",
    description="""Save important information about the user for future conversations.

    Use this tool to remember:
    - Facts about the user (name, job, location, preferences)
    - Projects they're working on
    - People and entities they mention frequently
    - Their preferences and how they like things done

    Memory types:
    - fact: Factual information about the user
    - preference: User preferences and how they like things
    - entity: People, companies, projects, or things they reference
    - project: Active projects or ongoing work
    - working: Temporary notes for the current session only

    Always save memories when the user shares important personal information, preferences, or context that would be useful in future conversations.""",
    input_schema={
        "type": "object",
        "properties": {
            "content": {
                "type": "string",
                "description": "The information to remember. Be concise but include key details."
            },
            "memory_type": {
                "type": "string",
                "enum": ["fact", "preference", "entity", "project", "working"],
                "description": "Type of memory. Use 'fact' for user info, 'preference' for how they like things, 'entity' for people/things they mention, 'project' for ongoing work, 'working' for temporary session notes.",
                "default": "fact"
            },
            "category": {
                "type": "string",
                "description": "Optional category like 'work', 'personal', 'health', etc."
            },
            "is_pinned": {
                "type": "boolean",
                "description": "If true, this memory will always be included in context. Use sparingly for critical information.",
                "default": False
            }
        },
        "required": ["content"]
    },
    executor=execute_save_memory,
    category="memory"
)


# =============================================================================
# Search Memory Tool
# =============================================================================

def execute_search_memory(
    params: Dict[str, Any],
    db: Session,
    user_id: int,
    context: Dict[str, Any]
) -> ToolResult:
    """Search user's memories."""
    query = params.get("query", "").strip()
    limit = params.get("limit", 5)
    memory_type = params.get("memory_type")

    if not query:
        return ToolResult(text="Error: No search query provided")

    try:
        service = MemoryService(db, user_id)

        # Convert memory_type if provided
        mem_type = None
        if memory_type:
            try:
                mem_type = MemoryType(memory_type)
            except ValueError:
                pass  # Ignore invalid type, search all

        results = service.search_memories(query, limit=limit, memory_type=mem_type)

        if not results:
            return ToolResult(
                text=f"No memories found matching: {query}",
                data={"type": "memory_search", "query": query, "results": []}
            )

        formatted = f"Found {len(results)} relevant memories:\n\n"
        result_data = []
        for memory, score in results:
            formatted += f"- [{memory.memory_type.value}] {memory.content} (relevance: {score:.2f})\n"
            result_data.append({
                "memory_id": memory.memory_id,
                "content": memory.content,
                "memory_type": memory.memory_type.value,
                "score": score
            })

        return ToolResult(
            text=formatted,
            data={"type": "memory_search", "query": query, "results": result_data}
        )

    except Exception as e:
        logger.error(f"Error searching memories: {e}", exc_info=True)
        return ToolResult(text=f"Error searching memories: {str(e)}")


SEARCH_MEMORY_TOOL = ToolConfig(
    name="search_memory",
    description="""Search through saved memories using semantic search.

    Use this to recall information about the user that might be relevant to the current conversation. The search uses AI embeddings to find semantically similar memories, not just keyword matching.""",
    input_schema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "What to search for. Can be a question or topic."
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of results to return (default: 5)",
                "default": 5
            },
            "memory_type": {
                "type": "string",
                "enum": ["fact", "preference", "entity", "project"],
                "description": "Optional: filter to specific memory type"
            }
        },
        "required": ["query"]
    },
    executor=execute_search_memory,
    category="memory"
)


# =============================================================================
# Delete Memory Tool
# =============================================================================

def execute_delete_memory(
    params: Dict[str, Any],
    db: Session,
    user_id: int,
    context: Dict[str, Any]
) -> ToolResult:
    """Delete a memory."""
    memory_id = params.get("memory_id")
    content_match = params.get("content_match")

    if not memory_id and not content_match:
        return ToolResult(text="Error: Provide either memory_id or content_match to delete")

    try:
        service = MemoryService(db, user_id)

        if memory_id:
            success = service.delete_memory(memory_id)
            if success:
                return ToolResult(
                    text=f"Deleted memory {memory_id}",
                    data={"type": "memory_deleted", "memory_id": memory_id}
                )
            else:
                return ToolResult(text=f"Memory {memory_id} not found")

        if content_match:
            count = service.delete_by_content(content_match)
            return ToolResult(
                text=f"Deleted {count} memories matching '{content_match}'",
                data={"type": "memories_deleted", "count": count, "match": content_match}
            )

    except Exception as e:
        logger.error(f"Error deleting memory: {e}", exc_info=True)
        return ToolResult(text=f"Error deleting memory: {str(e)}")


DELETE_MEMORY_TOOL = ToolConfig(
    name="delete_memory",
    description="""Delete incorrect or outdated memories.

    Use this when:
    - The user tells you something you remembered is wrong
    - Information is no longer relevant
    - The user asks you to forget something

    You can delete by specific ID (from search results) or by matching content.""",
    input_schema={
        "type": "object",
        "properties": {
            "memory_id": {
                "type": "integer",
                "description": "Specific memory ID to delete (from search results)"
            },
            "content_match": {
                "type": "string",
                "description": "Delete all memories containing this text"
            }
        }
    },
    executor=execute_delete_memory,
    category="memory"
)


# =============================================================================
# List Recent Memories Tool
# =============================================================================

def execute_list_memories(
    params: Dict[str, Any],
    db: Session,
    user_id: int,
    context: Dict[str, Any]
) -> ToolResult:
    """List recent memories."""
    memory_type = params.get("memory_type")
    category = params.get("category")
    limit = params.get("limit", 10)

    try:
        service = MemoryService(db, user_id)

        # Convert memory_type if provided
        mem_type = None
        if memory_type:
            try:
                mem_type = MemoryType(memory_type)
            except ValueError:
                return ToolResult(text=f"Invalid memory_type: {memory_type}")

        memories = service.list_memories(
            memory_type=mem_type,
            category=category,
            limit=limit
        )

        if not memories:
            return ToolResult(
                text="No memories found",
                data={"type": "memory_list", "memories": []}
            )

        formatted = f"Found {len(memories)} memories:\n\n"
        result_data = []
        for m in memories:
            pin_marker = "📌 " if m.is_pinned else ""
            formatted += f"- {pin_marker}[{m.memory_type.value}] {m.content} (id: {m.memory_id})\n"
            result_data.append({
                "memory_id": m.memory_id,
                "content": m.content,
                "memory_type": m.memory_type.value,
                "category": m.category,
                "is_pinned": m.is_pinned
            })

        return ToolResult(
            text=formatted,
            data={"type": "memory_list", "memories": result_data}
        )

    except Exception as e:
        logger.error(f"Error listing memories: {e}", exc_info=True)
        return ToolResult(text=f"Error listing memories: {str(e)}")


LIST_MEMORIES_TOOL = ToolConfig(
    name="list_memories",
    description="""List recent memories, optionally filtered by type or category.

    Use this to see what you know about the user or to find specific memories to update/delete.""",
    input_schema={
        "type": "object",
        "properties": {
            "memory_type": {
                "type": "string",
                "enum": ["fact", "preference", "entity", "project", "working"],
                "description": "Filter to specific memory type"
            },
            "category": {
                "type": "string",
                "description": "Filter to specific category (e.g., 'work', 'personal')"
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of memories to return (default: 10)",
                "default": 10
            }
        }
    },
    executor=execute_list_memories,
    category="memory"
)


# =============================================================================
# Tool Registration
# =============================================================================

def register_memory_tools():
    """Register all memory tools. Called at startup."""
    register_tool(SAVE_MEMORY_TOOL)
    register_tool(SEARCH_MEMORY_TOOL)
    register_tool(DELETE_MEMORY_TOOL)
    register_tool(LIST_MEMORIES_TOOL)
    logger.info("Registered 4 memory tools")
