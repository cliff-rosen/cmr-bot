"""
MapReduce tool for CMR Bot.

Processes a list of items with a map operation (in parallel),
then combines all results with a reduce operation.
"""

import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any, Dict, Generator, List, Optional, Tuple

import anthropic
from sqlalchemy.orm import Session

from models import Asset, AssetType
from tools.registry import ToolConfig, ToolResult, ToolProgress, register_tool, get_tool

logger = logging.getLogger(__name__)

# Configuration
MAP_REDUCE_MODEL = "claude-sonnet-4-20250514"
MAP_MAX_TOKENS = 1024
REDUCE_MAX_TOKENS = 4096
DEFAULT_MAX_CONCURRENCY = 5


@dataclass
class MapResult:
    """Result of processing a single item in the map phase."""
    item: str
    result: str
    success: bool
    error: Optional[str] = None


def _substitute_placeholder(template: Any, placeholder: str, value: str) -> Any:
    """Recursively substitute a placeholder in a template."""
    if isinstance(template, str):
        return template.replace(placeholder, value)
    elif isinstance(template, dict):
        return {k: _substitute_placeholder(v, placeholder, value) for k, v in template.items()}
    elif isinstance(template, list):
        return [_substitute_placeholder(v, placeholder, value) for v in template]
    else:
        return template


def _map_item_llm(item: str, prompt: str) -> MapResult:
    """Process a single item using LLM in the map phase."""
    try:
        client = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
        full_prompt = prompt.replace("{item}", item)

        response = client.messages.create(
            model=MAP_REDUCE_MODEL,
            max_tokens=MAP_MAX_TOKENS,
            messages=[{"role": "user", "content": full_prompt}]
        )

        result_text = response.content[0].text if response.content else ""
        return MapResult(item=item, result=result_text, success=True)

    except Exception as e:
        logger.error(f"Map LLM error for item '{item}': {e}")
        return MapResult(item=item, result="", success=False, error=str(e))


def _map_item_tool(
    item: str,
    tool_name: str,
    params_template: Dict[str, Any],
    db: Session,
    user_id: int
) -> MapResult:
    """Process a single item using a tool in the map phase."""
    try:
        tool_config = get_tool(tool_name)
        if not tool_config:
            return MapResult(
                item=item,
                result="",
                success=False,
                error=f"Tool '{tool_name}' not found"
            )

        params = _substitute_placeholder(params_template, "{item}", item)
        context = {}
        result = tool_config.executor(params, db, user_id, context)

        if isinstance(result, ToolResult):
            return MapResult(item=item, result=result.text, success=True)
        elif isinstance(result, str):
            return MapResult(item=item, result=result, success=True)
        else:
            return MapResult(item=item, result=str(result), success=True)

    except Exception as e:
        logger.error(f"Map tool error for item '{item}': {e}")
        return MapResult(item=item, result="", success=False, error=str(e))


def _reduce_llm(results: List[Dict[str, Any]], prompt: str) -> Tuple[str, bool, Optional[str]]:
    """Reduce all mapped results using LLM."""
    try:
        client = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))

        # Format results for the prompt
        results_json = json.dumps(results, indent=2)
        full_prompt = prompt.replace("{results}", results_json)

        response = client.messages.create(
            model=MAP_REDUCE_MODEL,
            max_tokens=REDUCE_MAX_TOKENS,
            messages=[{"role": "user", "content": full_prompt}]
        )

        result_text = response.content[0].text if response.content else ""
        return result_text, True, None

    except Exception as e:
        logger.error(f"Reduce LLM error: {e}")
        return "", False, str(e)


def _reduce_tool(
    results: List[Dict[str, Any]],
    tool_name: str,
    params_template: Dict[str, Any],
    db: Session,
    user_id: int
) -> Tuple[str, bool, Optional[str]]:
    """Reduce all mapped results using a tool."""
    try:
        tool_config = get_tool(tool_name)
        if not tool_config:
            return "", False, f"Tool '{tool_name}' not found"

        # Substitute {results} with JSON string of results
        results_json = json.dumps(results)
        params = _substitute_placeholder(params_template, "{results}", results_json)

        context = {}
        result = tool_config.executor(params, db, user_id, context)

        if isinstance(result, ToolResult):
            return result.text, True, None
        elif isinstance(result, str):
            return result, True, None
        else:
            return str(result), True, None

    except Exception as e:
        logger.error(f"Reduce tool error: {e}")
        return "", False, str(e)


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


def execute_map_reduce(
    params: Dict[str, Any],
    db: Session,
    user_id: int,
    context: Dict[str, Any]
) -> Generator[ToolProgress, None, ToolResult]:
    """
    Execute MapReduce: map operation on each item, then reduce all results.

    This is a streaming tool that yields progress updates during processing.
    """
    cancellation_token = context.get("cancellation_token")

    # Extract parameters
    items = params.get("items", [])
    asset_id = params.get("asset_id")
    map_operation = params.get("map_operation", {})
    reduce_operation = params.get("reduce_operation", {})
    max_concurrency = params.get("max_concurrency", DEFAULT_MAX_CONCURRENCY)

    # Load items from asset if provided
    if asset_id:
        try:
            items = _load_items_from_asset(db, user_id, asset_id)
        except ValueError as e:
            return ToolResult(text=f"Error loading items from asset: {e}")

    if not items:
        return ToolResult(text="No items to process")

    # Parse map operation
    map_type = map_operation.get("type", "llm")
    map_prompt = map_operation.get("prompt")
    map_tool_name = map_operation.get("tool_name")
    map_tool_params = map_operation.get("tool_params_template", {})

    # Parse reduce operation
    reduce_type = reduce_operation.get("type", "llm")
    reduce_prompt = reduce_operation.get("prompt")
    reduce_tool_name = reduce_operation.get("tool_name")
    reduce_tool_params = reduce_operation.get("tool_params_template", {})

    # Validate operations
    if map_type == "llm" and not map_prompt:
        return ToolResult(text="Map operation with type 'llm' requires a 'prompt' field")
    if map_type == "tool" and not map_tool_name:
        return ToolResult(text="Map operation with type 'tool' requires a 'tool_name' field")
    if reduce_type == "llm" and not reduce_prompt:
        return ToolResult(text="Reduce operation with type 'llm' requires a 'prompt' field")
    if reduce_type == "tool" and not reduce_tool_name:
        return ToolResult(text="Reduce operation with type 'tool' requires a 'tool_name' field")

    total = len(items)
    completed = 0
    map_results: List[Optional[MapResult]] = [None] * total

    # === MAP PHASE ===
    yield ToolProgress(
        stage="map_starting",
        message=f"Map phase: Processing {total} items",
        data={
            "phase": "map",
            "total": total,
            "max_concurrency": max_concurrency,
            "items": items
        },
        progress=0.0
    )

    def process_map_item(index: int, item: str) -> Tuple[int, MapResult]:
        if map_type == "llm":
            return index, _map_item_llm(item, map_prompt)
        else:
            return index, _map_item_tool(item, map_tool_name, map_tool_params, db, user_id)

    with ThreadPoolExecutor(max_workers=max_concurrency) as executor:
        futures = {
            executor.submit(process_map_item, idx, item): idx
            for idx, item in enumerate(items)
        }

        for future in as_completed(futures):
            # Check for cancellation
            if cancellation_token and cancellation_token.is_cancelled:
                logger.info("MapReduce cancelled during map phase")
                executor.shutdown(wait=False, cancel_futures=True)
                yield ToolProgress(
                    stage="cancelled",
                    message=f"Cancelled during map phase ({completed}/{total} items)",
                    data={"phase": "map", "completed": completed, "total": total}
                )
                return ToolResult(
                    text=f"MapReduce cancelled during map phase after processing {completed}/{total} items",
                    data={"partial": True, "phase": "map"}
                )

            try:
                index, result = future.result(timeout=60)
                map_results[index] = result
                completed += 1

                yield ToolProgress(
                    stage="map_item_complete",
                    message=f"Mapped: {result.item[:50]}..." if len(result.item) > 50 else f"Mapped: {result.item}",
                    data={
                        "phase": "map",
                        "index": index,
                        "item": result.item,
                        "result": result.result[:300] if result.result else "",
                        "success": result.success,
                        "error": result.error,
                        "completed": completed,
                        "total": total
                    },
                    progress=(completed / total) * 0.8  # Map is 80% of progress
                )
            except Exception as e:
                logger.error(f"Map error: {e}")
                idx = futures[future]
                error_result = MapResult(item=items[idx], result="", success=False, error=str(e))
                map_results[idx] = error_result
                completed += 1

                yield ToolProgress(
                    stage="map_item_complete",
                    message=f"Map failed: {items[idx][:50]}...",
                    data={
                        "phase": "map",
                        "index": idx,
                        "item": items[idx],
                        "success": False,
                        "error": str(e),
                        "completed": completed,
                        "total": total
                    },
                    progress=(completed / total) * 0.8
                )

    # Collect map results
    final_map_results = [r for r in map_results if r is not None]
    successful_maps = sum(1 for r in final_map_results if r.success)
    failed_maps = len(final_map_results) - successful_maps

    # === REDUCE PHASE ===
    yield ToolProgress(
        stage="reduce_starting",
        message=f"Reduce phase: Combining {successful_maps} results",
        data={
            "phase": "reduce",
            "map_successful": successful_maps,
            "map_failed": failed_maps
        },
        progress=0.85
    )

    # Check for cancellation before reduce
    if cancellation_token and cancellation_token.is_cancelled:
        logger.info("MapReduce cancelled before reduce phase")
        return ToolResult(
            text=f"MapReduce cancelled before reduce phase (mapped {successful_maps}/{total} items)",
            data={
                "partial": True,
                "phase": "reduce",
                "map_results": [
                    {"item": r.item, "result": r.result, "success": r.success, "error": r.error}
                    for r in final_map_results
                ]
            }
        )

    # Prepare results for reduce (only successful ones)
    results_for_reduce = [
        {"item": r.item, "result": r.result}
        for r in final_map_results
        if r.success
    ]

    if not results_for_reduce:
        return ToolResult(
            text="MapReduce failed: No successful map results to reduce",
            data={
                "map_total": total,
                "map_successful": 0,
                "map_failed": failed_maps,
                "reduce_success": False
            }
        )

    # Execute reduce
    if reduce_type == "llm":
        reduce_result, reduce_success, reduce_error = _reduce_llm(results_for_reduce, reduce_prompt)
    else:
        reduce_result, reduce_success, reduce_error = _reduce_tool(
            results_for_reduce, reduce_tool_name, reduce_tool_params, db, user_id
        )

    yield ToolProgress(
        stage="reduce_complete",
        message="Reduce complete" if reduce_success else f"Reduce failed: {reduce_error}",
        data={
            "phase": "reduce",
            "success": reduce_success,
            "error": reduce_error
        },
        progress=1.0
    )

    if not reduce_success:
        return ToolResult(
            text=f"MapReduce reduce phase failed: {reduce_error}",
            data={
                "map_total": total,
                "map_successful": successful_maps,
                "map_failed": failed_maps,
                "reduce_success": False,
                "reduce_error": reduce_error,
                "map_results": [
                    {"item": r.item, "result": r.result, "success": r.success}
                    for r in final_map_results
                ]
            }
        )

    # Success!
    return ToolResult(
        text=reduce_result,
        data={
            "map_total": total,
            "map_successful": successful_maps,
            "map_failed": failed_maps,
            "reduce_success": True,
            "map_results": [
                {"item": r.item, "result": r.result, "success": r.success, "error": r.error}
                for r in final_map_results
            ],
            "reduced_result": reduce_result
        }
    )


MAP_REDUCE_TOOL = ToolConfig(
    name="map_reduce",
    description="Process a list with a map operation on each item (in parallel), then reduce all results into a single output. Use for tasks like: summarizing multiple documents, aggregating data, combining analyses. Map processes each item independently, reduce combines all results.",
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
            "map_operation": {
                "type": "object",
                "description": "Operation to apply to each item in parallel",
                "properties": {
                    "type": {
                        "type": "string",
                        "enum": ["llm", "tool"],
                        "description": "Type of operation: 'llm' for LLM prompt, 'tool' for tool call"
                    },
                    "prompt": {
                        "type": "string",
                        "description": "For LLM: prompt with {item} placeholder for current item"
                    },
                    "tool_name": {
                        "type": "string",
                        "description": "For tool: name of the tool to call"
                    },
                    "tool_params_template": {
                        "type": "object",
                        "description": "For tool: parameters template with {item} placeholders"
                    }
                },
                "required": ["type"]
            },
            "reduce_operation": {
                "type": "object",
                "description": "Operation to combine all map results into final output",
                "properties": {
                    "type": {
                        "type": "string",
                        "enum": ["llm", "tool"],
                        "description": "Type of operation: 'llm' for LLM prompt, 'tool' for tool call"
                    },
                    "prompt": {
                        "type": "string",
                        "description": "For LLM: prompt with {results} placeholder for JSON array of map results"
                    },
                    "tool_name": {
                        "type": "string",
                        "description": "For tool: name of the tool to call"
                    },
                    "tool_params_template": {
                        "type": "object",
                        "description": "For tool: parameters template with {results} placeholder"
                    }
                },
                "required": ["type"]
            },
            "max_concurrency": {
                "type": "integer",
                "description": "Maximum parallel map operations (default: 5)",
                "default": 5
            }
        },
        "required": ["map_operation", "reduce_operation"]
    },
    executor=execute_map_reduce,
    category="processing",
    streaming=True
)


def register_map_reduce_tools():
    """Register the map_reduce tool."""
    register_tool(MAP_REDUCE_TOOL)
    logger.info("Registered map_reduce tool")
