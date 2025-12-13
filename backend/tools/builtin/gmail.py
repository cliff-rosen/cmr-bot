"""
Gmail Tool

Allows the agent to interact with the user's Gmail account.
Requires the user to have connected their Google account via OAuth.
"""

import logging
from typing import Any, Dict

from sqlalchemy.orm import Session

from services.gmail_service import GmailService, GmailServiceError, NotConnectedError
from tools.registry import ToolConfig, ToolResult, register_tool

logger = logging.getLogger(__name__)


def execute_gmail_search(
    params: Dict[str, Any],
    db: Session,
    user_id: int,
    context: Dict[str, Any]
) -> ToolResult:
    """
    Search Gmail for messages matching a query.
    """
    query = params.get("query", "")
    max_results = min(params.get("max_results", 10), 50)

    if not query:
        return ToolResult(
            text="Error: No search query provided",
            data={"success": False, "error": "No query provided"}
        )

    try:
        service = GmailService(db, user_id)
        messages = service.search_messages(query=query, max_results=max_results)

        if not messages:
            return ToolResult(
                text=f"No emails found matching: {query}",
                data={"success": True, "query": query, "count": 0, "messages": []}
            )

        # Format results
        formatted = f"**Found {len(messages)} emails matching '{query}':**\n\n"
        message_data = []

        for i, msg in enumerate(messages, 1):
            formatted += f"**{i}. {msg.subject}**\n"
            formatted += f"   From: {msg.sender}\n"
            formatted += f"   Date: {msg.date}\n"
            formatted += f"   Preview: {msg.snippet[:100]}...\n\n"

            message_data.append({
                "id": msg.id,
                "thread_id": msg.thread_id,
                "subject": msg.subject,
                "sender": msg.sender,
                "date": msg.date,
                "snippet": msg.snippet,
                "labels": msg.labels
            })

        return ToolResult(
            text=formatted,
            data={
                "success": True,
                "query": query,
                "count": len(messages),
                "messages": message_data
            }
        )

    except NotConnectedError as e:
        return ToolResult(
            text=f"Gmail not connected: {str(e)}",
            data={"success": False, "error": "not_connected", "message": str(e)}
        )
    except GmailServiceError as e:
        logger.error(f"Gmail search error: {e}")
        return ToolResult(
            text=f"Gmail search failed: {str(e)}",
            data={"success": False, "error": str(e)}
        )


def execute_gmail_read(
    params: Dict[str, Any],
    db: Session,
    user_id: int,
    context: Dict[str, Any]
) -> ToolResult:
    """
    Read a specific email by ID.
    """
    message_id = params.get("message_id", "")

    if not message_id:
        return ToolResult(
            text="Error: No message_id provided",
            data={"success": False, "error": "No message_id provided"}
        )

    try:
        service = GmailService(db, user_id)
        msg = service.get_message(message_id, include_body=True)

        formatted = f"**{msg.subject}**\n\n"
        formatted += f"**From:** {msg.sender}\n"
        formatted += f"**To:** {msg.recipient}\n"
        formatted += f"**Date:** {msg.date}\n"
        formatted += f"**Labels:** {', '.join(msg.labels)}\n\n"
        formatted += "---\n\n"
        formatted += msg.body or "(no body)"

        return ToolResult(
            text=formatted,
            data={
                "success": True,
                "message": {
                    "id": msg.id,
                    "thread_id": msg.thread_id,
                    "subject": msg.subject,
                    "sender": msg.sender,
                    "recipient": msg.recipient,
                    "date": msg.date,
                    "body": msg.body,
                    "labels": msg.labels
                }
            }
        )

    except NotConnectedError as e:
        return ToolResult(
            text=f"Gmail not connected: {str(e)}",
            data={"success": False, "error": "not_connected", "message": str(e)}
        )
    except GmailServiceError as e:
        logger.error(f"Gmail read error: {e}")
        return ToolResult(
            text=f"Failed to read email: {str(e)}",
            data={"success": False, "error": str(e)}
        )


def execute_gmail_send(
    params: Dict[str, Any],
    db: Session,
    user_id: int,
    context: Dict[str, Any]
) -> ToolResult:
    """
    Send an email.
    """
    to = params.get("to", "")
    subject = params.get("subject", "")
    body = params.get("body", "")

    if not to:
        return ToolResult(
            text="Error: No recipient (to) provided",
            data={"success": False, "error": "No recipient provided"}
        )
    if not subject:
        return ToolResult(
            text="Error: No subject provided",
            data={"success": False, "error": "No subject provided"}
        )
    if not body:
        return ToolResult(
            text="Error: No body provided",
            data={"success": False, "error": "No body provided"}
        )

    try:
        service = GmailService(db, user_id)
        result = service.send_message(to=to, subject=subject, body=body)

        return ToolResult(
            text=f"Email sent successfully to {to}",
            data={
                "success": True,
                "message_id": result.get("id"),
                "thread_id": result.get("threadId")
            }
        )

    except NotConnectedError as e:
        return ToolResult(
            text=f"Gmail not connected: {str(e)}",
            data={"success": False, "error": "not_connected", "message": str(e)}
        )
    except GmailServiceError as e:
        logger.error(f"Gmail send error: {e}")
        return ToolResult(
            text=f"Failed to send email: {str(e)}",
            data={"success": False, "error": str(e)}
        )


# Tool configurations
GMAIL_SEARCH_TOOL = ToolConfig(
    name="gmail_search",
    description="""Search the user's Gmail inbox for emails.

Use this when the user asks to:
- Find emails from a specific person
- Search for emails about a topic
- Look up recent emails or messages
- Check for emails with specific keywords

Requires the user to have connected their Google account.
Uses Gmail search syntax (same as Gmail search box).""",
    input_schema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Gmail search query. Examples: 'from:john@example.com', 'subject:meeting', 'is:unread', 'after:2024/01/01 before:2024/02/01', 'has:attachment'"
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of emails to return (default: 10, max: 50)",
                "default": 10
            }
        },
        "required": ["query"]
    },
    executor=execute_gmail_search,
    category="integrations"
)


GMAIL_READ_TOOL = ToolConfig(
    name="gmail_read",
    description="""Read a specific email by its message ID.

Use this after searching for emails to read the full content of a specific message.
The message_id comes from gmail_search results.

Requires the user to have connected their Google account.""",
    input_schema={
        "type": "object",
        "properties": {
            "message_id": {
                "type": "string",
                "description": "The Gmail message ID (from gmail_search results)"
            }
        },
        "required": ["message_id"]
    },
    executor=execute_gmail_read,
    category="integrations"
)


GMAIL_SEND_TOOL = ToolConfig(
    name="gmail_send",
    description="""Send an email from the user's Gmail account.

Use this when the user asks to:
- Send an email
- Reply to someone
- Compose and send a message

IMPORTANT: Always confirm with the user before sending emails.
Requires the user to have connected their Google account.""",
    input_schema={
        "type": "object",
        "properties": {
            "to": {
                "type": "string",
                "description": "Recipient email address"
            },
            "subject": {
                "type": "string",
                "description": "Email subject line"
            },
            "body": {
                "type": "string",
                "description": "Email body (plain text)"
            }
        },
        "required": ["to", "subject", "body"]
    },
    executor=execute_gmail_send,
    category="integrations"
)


def register_gmail_tools():
    """Register all Gmail tools."""
    register_tool(GMAIL_SEARCH_TOOL)
    register_tool(GMAIL_READ_TOOL)
    register_tool(GMAIL_SEND_TOOL)
    logger.info("Registered Gmail tools")
