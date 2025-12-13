"""
Table Operations Router

Endpoints for table manipulation including AI-computed columns.
"""

import asyncio
import json
import logging
import os
from typing import Any, Dict, List

import anthropic
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from routers.auth import get_current_user
from models import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/table", tags=["table"])


class ComputeColumnRequest(BaseModel):
    """Request to compute a new column for a table."""
    rows: List[Dict[str, Any]]
    prompt: str
    column_key: str
    column_type: str  # 'text', 'boolean', 'number'


async def compute_single_value(
    client: anthropic.AsyncAnthropic,
    row: Dict[str, Any],
    prompt: str,
    column_type: str,
    row_index: int
) -> Dict[str, Any]:
    """Compute a single cell value using the LLM."""
    # Substitute {field} placeholders with actual values
    filled_prompt = prompt
    for key, value in row.items():
        placeholder = "{" + key + "}"
        if placeholder in filled_prompt:
            filled_prompt = filled_prompt.replace(placeholder, str(value) if value is not None else "")

    # Add type-specific instruction
    if column_type == "boolean":
        system_instruction = "You must respond with ONLY 'Yes' or 'No'. No other text or explanation."
    elif column_type == "number":
        system_instruction = "You must respond with ONLY a number. No other text, units, or explanation."
    else:
        system_instruction = "Respond concisely with the requested information."

    try:
        response = await client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=200,
            temperature=0,
            system=system_instruction,
            messages=[{"role": "user", "content": filled_prompt}]
        )

        raw_value = response.content[0].text.strip()

        # Parse based on type
        if column_type == "boolean":
            value = raw_value.lower() in ["yes", "true", "1"]
        elif column_type == "number":
            try:
                # Try to extract number from response
                import re
                match = re.search(r'-?\d+\.?\d*', raw_value)
                value = float(match.group()) if match else None
            except:
                value = None
        else:
            value = raw_value

        return {"row_index": row_index, "value": value, "success": True}
    except Exception as e:
        logger.error(f"Error computing value for row {row_index}: {e}")
        return {"row_index": row_index, "value": None, "success": False, "error": str(e)}


@router.post("/compute-column")
async def compute_column(
    request: ComputeColumnRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Compute values for a new column by running a prompt on each row.

    Returns SSE stream with progress updates and row results.
    """
    async def generate():
        client = anthropic.AsyncAnthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))

        try:
            total = len(request.rows)
            completed = 0

            # Initial progress
            yield f"data: {json.dumps({'type': 'progress', 'completed': 0, 'total': total, 'message': 'Starting computation...'})}\n\n"

            # Process rows in batches for parallelism (limit concurrent requests)
            batch_size = 5

            for batch_start in range(0, total, batch_size):
                batch_end = min(batch_start + batch_size, total)
                batch_rows = request.rows[batch_start:batch_end]

                # Create tasks for this batch
                tasks = [
                    compute_single_value(
                        client,
                        row,
                        request.prompt,
                        request.column_type,
                        batch_start + i
                    )
                    for i, row in enumerate(batch_rows)
                ]

                # Run batch in parallel
                results = await asyncio.gather(*tasks)

                # Yield results
                for result in results:
                    completed += 1

                    # Yield row result
                    yield f"data: {json.dumps({'type': 'row_result', 'row_index': result['row_index'], 'value': result['value']})}\n\n"

                    # Yield progress update
                    yield f"data: {json.dumps({'type': 'progress', 'completed': completed, 'total': total, 'message': f'Processing {completed}/{total}...'})}\n\n"

            # Complete
            yield f"data: {json.dumps({'type': 'complete', 'message': f'Computed {total} values'})}\n\n"

        except Exception as e:
            logger.error(f"Column computation error: {e}", exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        finally:
            await client.close()

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )
