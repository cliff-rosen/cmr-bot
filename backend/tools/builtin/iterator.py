"""
Iterator tool for CMR Bot.

Processes each item in a list with an operation (LLM prompt or tool call).
Supports parallel execution for efficiency.
"""

import asyncio
import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, Dict, Generator, List, Optional, Tuple

import anthropic
from sqlalchemy.orm import Session

from models import Asset, AssetType
from tools.registry import ToolConfig, ToolResult, ToolProgress, register_tool, get_tool

logger = logging.getLogger(__name__)

# Configuration
ITERATOR_MODEL = "claude-sonnet-4-20250514"
ITERATOR_MAX_TOKENS = 1024
DEFAULT_MAX_CONCURRENCY = 5


@dataclass
class IteratorOperation:
    """Defines the operation to perform on each item."""
    type: str  # 'llm' or 'tool'
    prompt: Optional[str] = None  # For LLM operations
    tool_name: Optional[str] = None  # For tool operations
    tool_params_template: Optional[Dict[str, Any]] = None  # For tool operations


@dataclass
class ItemResult:
    """Result of processing a single item."""
    item: str
    result: str
    success: bool
    error: Optional[str] = None


def _substitute_item(template: Any, item: str) -> Any:
    """Recursively substitute {item} placeholder in a template."""
    if isinstance(template, str):
        return template.replace("{item}", item)
    elif isinstance(template, dict):
        return {k: _substitute_item(v, item) for k, v in template.items()}
    elif isinstance(template, list):
        return [_substitute_item(v, item) for v in template]
    else:
        return template


def _process_item_llm(item: str, prompt: str) -> ItemResult:
    """Process a single item using LLM."""
    try:
        client = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))

        # Substitute {item} in the prompt
        full_prompt = prompt.replace("{item}", item)

        response = client.messages.create(
            model=ITERATOR_MODEL,
            max_tokens=ITERATOR_MAX_TOKENS,
            messages=[{"role": "user", "content": full_prompt}]
        )

        result_text = response.content[0].text if response.content else ""
        return ItemResult(item=item, result=result_text, success=True)

    except Exception as e:
        logger.error(f"LLM processing error for item '{item}': {e}")
        return ItemResult(item=item, result="", success=False, error=str(e))


def _process_item_tool(
    item: str,
    tool_name: str,
    params_template: Dict[str, Any],
    db: Session,
    user_id: int
) -> ItemResult:
    """Process a single item using a tool."""
    try:
        tool_config = get_tool(tool_name)
        if not tool_config:
            return ItemResult(
                item=item,
                result="",
                success=False,
                error=f"Tool '{tool_name}' not found"
            )

        # Substitute {item} in the params template
        params = _substitute_item(params_template, item)

        # Execute the tool synchronously
        context = {}
        result = tool_config.executor(params, db, user_id, context)

        if isinstance(result, ToolResult):
            return ItemResult(item=item, result=result.text, success=True)
        elif isinstance(result, str):
            return ItemResult(item=item, result=result, success=True)
        else:
            return ItemResult(item=item, result=str(result), success=True)

    except Exception as e:
        logger.error(f"Tool processing error for item '{item}': {e}")
        return ItemResult(item=item, result="", success=False, error=str(e))


def _load_items_from_asset(db: Session, user_id: int, asset_id: int) -> List[str]:
    """Load items from a LIST asset."""
    asset = db.query(Asset).filter(
        Asset.asset_id == asset_id,
        Asset.user_id == user_id
    ).first()

    if not asset:
        raise ValueError(f"Asset {asset_id} not found")

    if asset.asset_type != AssetType.LIST:
        raise ValueError(f"Asset {asset_id} is not a LIST type (got {asset.asset_type})")

    if not asset.content:
        raise ValueError(f"Asset {asset_id} has no content")

    try:
        items = json.loads(asset.content)
        if not isinstance(items, list):
            raise ValueError(f"Asset {asset_id} content is not a JSON array")
        return [str(item) for item in items]
    except json.JSONDecodeError as e:
        raise ValueError(f"Asset {asset_id} content is not valid JSON: {e}")


def execute_iterate(
    params: Dict[str, Any],
    db: Session,
    user_id: int,
    context: Dict[str, Any]
) -> Generator[ToolProgress, None, ToolResult]:
    """
    Execute the iterate operation on a list of items.

    This is a streaming tool that yields progress updates as items are processed.
    """
    # Get cancellation token if available
    cancellation_token = context.get("cancellation_token")

    # Extract parameters
    items = params.get("items", [])
    asset_id = params.get("asset_id")
    operation = params.get("operation", {})
    max_concurrency = params.get("max_concurrency", DEFAULT_MAX_CONCURRENCY)

    # Load items from asset if asset_id is provided
    if asset_id:
        try:
            items = _load_items_from_asset(db, user_id, asset_id)
        except ValueError as e:
            return ToolResult(text=f"Error loading items from asset: {e}")

    if not items:
        return ToolResult(text="No items to process")

    # Parse operation
    op_type = operation.get("type", "llm")
    op_prompt = operation.get("prompt")
    op_tool_name = operation.get("tool_name")
    op_tool_params = operation.get("tool_params_template", {})

    # Validate operation
    if op_type == "llm" and not op_prompt:
        return ToolResult(text="LLM operation requires a 'prompt' field")
    if op_type == "tool" and not op_tool_name:
        return ToolResult(text="Tool operation requires a 'tool_name' field")

    total = len(items)
    completed = 0
    # Pre-allocate results list to maintain order
    results: List[Optional[ItemResult]] = [None] * total

    # Send starting event with full items list for UI rendering
    yield ToolProgress(
        stage="starting",
        message=f"Processing {total} items",
        data={
            "total": total,
            "max_concurrency": max_concurrency,
            "items": items  # Full list for UI to render
        },
        progress=0.0
    )

    # Process items in parallel
    def process_item_with_index(index: int, item: str) -> Tuple[int, ItemResult]:
        if op_type == "llm":
            return index, _process_item_llm(item, op_prompt)
        else:
            return index, _process_item_tool(item, op_tool_name, op_tool_params, db, user_id)

    # Use ThreadPoolExecutor for parallel processing
    from concurrent.futures import as_completed

    with ThreadPoolExecutor(max_workers=max_concurrency) as executor:
        # Submit all tasks with their indices
        futures = {
            executor.submit(process_item_with_index, idx, item): idx
            for idx, item in enumerate(items)
        }

        # Process completed tasks as they finish (in completion order)
        for future in as_completed(futures):
            # Check for cancellation
            if cancellation_token and cancellation_token.is_cancelled:
                logger.info("Iterator cancelled")
                executor.shutdown(wait=False, cancel_futures=True)
                yield ToolProgress(
                    stage="cancelled",
                    message=f"Cancelled after processing {completed}/{total} items",
                    data={"completed": completed, "total": total}
                )
                # Collect completed results
                final_results = [r for r in results if r is not None]
                return ToolResult(
                    text=f"Iterator cancelled after processing {completed}/{total} items",
                    data={
                        "partial": True,
                        "results": [{"item": r.item, "result": r.result, "success": r.success, "error": r.error} for r in final_results]
                    }
                )

            try:
                index, result = future.result(timeout=60)  # 60 second timeout per item
                results[index] = result
                completed += 1

                # Send per-item completion event for live UI update
                yield ToolProgress(
                    stage="item_complete",
                    message=f"Completed: {result.item[:50]}..." if len(result.item) > 50 else f"Completed: {result.item}",
                    data={
                        "index": index,
                        "item": result.item,
                        "result": result.result[:500] if result.result else "",  # Truncate for progress
                        "success": result.success,
                        "error": result.error,
                        "completed": completed,
                        "total": total
                    },
                    progress=completed / total
                )
            except Exception as e:
                logger.error(f"Error processing item: {e}")
                idx = futures[future]
                error_result = ItemResult(item=items[idx], result="", success=False, error=str(e))
                results[idx] = error_result
                completed += 1

                yield ToolProgress(
                    stage="item_complete",
                    message=f"Failed: {items[idx][:50]}..." if len(items[idx]) > 50 else f"Failed: {items[idx]}",
                    data={
                        "index": idx,
                        "item": items[idx],
                        "result": "",
                        "success": False,
                        "error": str(e),
                        "completed": completed,
                        "total": total
                    },
                    progress=completed / total
                )

    # Format final results (filter out any None values, though there shouldn't be any)
    final_results = [r for r in results if r is not None]
    successful = sum(1 for r in final_results if r.success)
    failed = len(final_results) - successful

    # Build output text
    output_lines = [f"Processed {total} items ({successful} successful, {failed} failed):\n"]
    for r in final_results:
        if r.success:
            output_lines.append(f"- **{r.item}**: {r.result}")
        else:
            output_lines.append(f"- **{r.item}**: [ERROR] {r.error}")

    return ToolResult(
        text="\n".join(output_lines),
        data={
            "total": total,
            "successful": successful,
            "failed": failed,
            "results": [
                {
                    "item": r.item,
                    "result": r.result,
                    "success": r.success,
                    "error": r.error
                }
                for r in final_results
            ]
        }
    )


ITERATE_TOOL = ToolConfig(
    name="iterate",
    description="Process each item in a list with an operation (LLM prompt or tool call). Use this to apply the same operation to multiple items in parallel. Items can be provided directly or loaded from a LIST asset.",
    input_schema={
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of items to process. Either provide this or asset_id."
            },
            "asset_id": {
                "type": "integer",
                "description": "ID of a LIST asset to load items from. Either provide this or items."
            },
            "operation": {
                "type": "object",
                "description": "The operation to perform on each item",
                "properties": {
                    "type": {
                        "type": "string",
                        "enum": ["llm", "tool"],
                        "description": "Type of operation: 'llm' for LLM prompt, 'tool' for tool call"
                    },
                    "prompt": {
                        "type": "string",
                        "description": "For LLM operations: the prompt to use. Use {item} as placeholder for the current item."
                    },
                    "tool_name": {
                        "type": "string",
                        "description": "For tool operations: the name of the tool to call"
                    },
                    "tool_params_template": {
                        "type": "object",
                        "description": "For tool operations: parameters template with {item} placeholders"
                    }
                },
                "required": ["type"]
            },
            "max_concurrency": {
                "type": "integer",
                "description": "Maximum number of items to process in parallel (default: 5)",
                "default": 5
            }
        },
        "required": ["operation"]
    },
    executor=execute_iterate,
    category="processing",
    streaming=True
)


def register_iterator_tools():
    """Register all iterator tools."""
    register_tool(ITERATE_TOOL)
    logger.info("Registered iterator tool")
