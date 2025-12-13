"""
Agent Management Tools

Tools for the main chat agent to create, manage, and monitor autonomous background agents.
"""

import logging
from typing import Any, Dict, List
from sqlalchemy.orm import Session

from tools.registry import ToolConfig, ToolResult, register_tool
from models import AgentLifecycle, AgentStatus

logger = logging.getLogger(__name__)


def execute_list_agents(
    params: Dict[str, Any],
    db: Session,
    user_id: int,
    context: Dict[str, Any]
) -> ToolResult:
    """List all autonomous agents."""
    from services.autonomous_agent_service import AutonomousAgentService

    include_completed = params.get("include_completed", True)

    service = AutonomousAgentService(db, user_id)
    agents = service.list_agents(include_completed=include_completed)

    if not agents:
        return ToolResult(
            text="No autonomous agents found.",
            data={"agents": [], "count": 0}
        )

    formatted = f"**Found {len(agents)} autonomous agents:**\n\n"
    agent_list = []

    for agent in agents:
        status_icon = {
            "active": "🟢",
            "paused": "🟡",
            "completed": "⚪",
            "failed": "🔴"
        }.get(agent.status.value, "⚪")

        formatted += f"{status_icon} **{agent.name}** (ID: {agent.agent_id})\n"
        formatted += f"   Lifecycle: {agent.lifecycle.value} | Status: {agent.status.value}\n"
        formatted += f"   Runs: {agent.total_runs} | Assets: {agent.total_assets_created}\n"
        if agent.description:
            formatted += f"   {agent.description[:100]}\n"
        formatted += "\n"

        agent_list.append({
            "agent_id": agent.agent_id,
            "name": agent.name,
            "description": agent.description,
            "lifecycle": agent.lifecycle.value,
            "status": agent.status.value,
            "total_runs": agent.total_runs,
            "total_assets_created": agent.total_assets_created,
            "tools": agent.tools or []
        })

    return ToolResult(text=formatted, data={"agents": agent_list, "count": len(agents)})


def execute_get_agent(
    params: Dict[str, Any],
    db: Session,
    user_id: int,
    context: Dict[str, Any]
) -> ToolResult:
    """Get details of a specific agent."""
    from services.autonomous_agent_service import AutonomousAgentService

    agent_id = params.get("agent_id")
    agent_name = params.get("name")

    if not agent_id and not agent_name:
        return ToolResult(text="Error: Must provide either agent_id or name")

    service = AutonomousAgentService(db, user_id)

    agent = None
    if agent_id:
        agent = service.get_agent(agent_id)
    elif agent_name:
        # Search by name
        agents = service.list_agents()
        for a in agents:
            if a.name.lower() == agent_name.lower():
                agent = a
                break
        if not agent:
            for a in agents:
                if agent_name.lower() in a.name.lower():
                    agent = a
                    break

    if not agent:
        return ToolResult(
            text=f"Agent not found: {agent_id or agent_name}",
            data={"success": False, "error": "not_found"}
        )

    # Get recent runs
    runs = service.get_agent_runs(agent.agent_id, limit=5)

    formatted = f"**{agent.name}** (ID: {agent.agent_id})\n\n"
    formatted += f"**Status:** {agent.status.value}\n"
    formatted += f"**Lifecycle:** {agent.lifecycle.value}\n"
    if agent.description:
        formatted += f"**Description:** {agent.description}\n"
    formatted += f"**Tools:** {', '.join(agent.tools) if agent.tools else 'None'}\n"
    formatted += f"**Total Runs:** {agent.total_runs}\n"
    formatted += f"**Assets Created:** {agent.total_assets_created}\n"

    if agent.next_run_at:
        formatted += f"**Next Run:** {agent.next_run_at}\n"

    formatted += f"\n**Instructions:**\n```\n{agent.instructions[:500]}{'...' if len(agent.instructions) > 500 else ''}\n```\n"

    if runs:
        formatted += f"\n**Recent Runs:**\n"
        for run in runs[:5]:
            status_icon = {"completed": "✅", "running": "🔄", "failed": "❌", "pending": "⏳"}.get(run.status.value, "•")
            formatted += f"- {status_icon} Run #{run.run_id}: {run.status.value}"
            if run.result_summary:
                formatted += f" - {run.result_summary[:50]}..."
            formatted += "\n"

    return ToolResult(
        text=formatted,
        data={
            "success": True,
            "agent": {
                "agent_id": agent.agent_id,
                "name": agent.name,
                "description": agent.description,
                "lifecycle": agent.lifecycle.value,
                "status": agent.status.value,
                "instructions": agent.instructions,
                "tools": agent.tools or [],
                "total_runs": agent.total_runs,
                "total_assets_created": agent.total_assets_created,
                "next_run_at": str(agent.next_run_at) if agent.next_run_at else None
            },
            "recent_runs": [
                {"run_id": r.run_id, "status": r.status.value, "result_summary": r.result_summary}
                for r in runs
            ]
        }
    )


def execute_create_agent(
    params: Dict[str, Any],
    db: Session,
    user_id: int,
    context: Dict[str, Any]
) -> ToolResult:
    """Propose creating a new autonomous agent (returns a payload for user approval)."""
    import json

    name = params.get("name")
    instructions = params.get("instructions")
    lifecycle = params.get("lifecycle", "one_shot")
    description = params.get("description")
    tools = params.get("tools", [])
    monitor_interval = params.get("monitor_interval_minutes")

    if not name:
        return ToolResult(text="Error: Agent name is required")
    if not instructions:
        return ToolResult(text="Error: Agent instructions are required")

    try:
        AgentLifecycle(lifecycle)
    except ValueError:
        return ToolResult(text=f"Error: Invalid lifecycle '{lifecycle}'. Must be one of: one_shot, scheduled, monitor")

    # Build the payload for frontend approval
    payload = {
        "type": "agent_create",
        "title": f"Create Agent: {name}",
        "content": description or f"New {lifecycle} agent",
        "agent_data": {
            "name": name,
            "description": description,
            "instructions": instructions,
            "lifecycle": lifecycle,
            "tools": tools,
            "monitor_interval_minutes": monitor_interval
        }
    }

    # Format explanation for the chat
    formatted = f"I've prepared a proposal to create a new agent:\n\n"
    formatted += f"**Name:** {name}\n"
    formatted += f"**Lifecycle:** {lifecycle}\n"
    if description:
        formatted += f"**Description:** {description}\n"
    if tools:
        formatted += f"**Tools:** {', '.join(tools)}\n"
    formatted += f"\nPlease review the details in the workspace panel and click **Create Agent** to confirm."

    # Include the payload block for the frontend to parse
    formatted += f"\n\n```payload\n{json.dumps(payload, indent=2)}\n```"

    return ToolResult(
        text=formatted,
        data={
            "proposal": True,
            "payload_type": "agent_create",
            "agent_data": payload["agent_data"]
        }
    )


def execute_trigger_agent_run(
    params: Dict[str, Any],
    db: Session,
    user_id: int,
    context: Dict[str, Any]
) -> ToolResult:
    """Trigger an immediate run of an agent."""
    from services.autonomous_agent_service import AutonomousAgentService

    agent_id = params.get("agent_id")
    if not agent_id:
        return ToolResult(text="Error: agent_id is required")

    service = AutonomousAgentService(db, user_id)

    agent = service.get_agent(agent_id)
    if not agent:
        return ToolResult(text=f"Agent not found: {agent_id}", data={"success": False})

    run = service.queue_run(agent_id)
    if not run:
        return ToolResult(
            text=f"Could not queue run for agent '{agent.name}'. Agent may not be active.",
            data={"success": False}
        )

    return ToolResult(
        text=f"**Run Queued!**\n\nAgent '{agent.name}' run #{run.run_id} has been queued and will execute shortly.",
        data={
            "success": True,
            "run_id": run.run_id,
            "agent_id": agent_id,
            "agent_name": agent.name,
            "status": run.status.value
        }
    )


def execute_pause_agent(
    params: Dict[str, Any],
    db: Session,
    user_id: int,
    context: Dict[str, Any]
) -> ToolResult:
    """Pause an active agent."""
    from services.autonomous_agent_service import AutonomousAgentService

    agent_id = params.get("agent_id")
    if not agent_id:
        return ToolResult(text="Error: agent_id is required")

    service = AutonomousAgentService(db, user_id)

    agent = service.pause_agent(agent_id)
    if not agent:
        return ToolResult(text=f"Could not pause agent {agent_id}. Agent may not exist or is not active.")

    return ToolResult(
        text=f"**Agent Paused**\n\nAgent '{agent.name}' has been paused. Use `resume_agent` to reactivate it.",
        data={"success": True, "agent_id": agent_id, "name": agent.name, "status": "paused"}
    )


def execute_resume_agent(
    params: Dict[str, Any],
    db: Session,
    user_id: int,
    context: Dict[str, Any]
) -> ToolResult:
    """Resume a paused agent."""
    from services.autonomous_agent_service import AutonomousAgentService

    agent_id = params.get("agent_id")
    if not agent_id:
        return ToolResult(text="Error: agent_id is required")

    service = AutonomousAgentService(db, user_id)

    agent = service.resume_agent(agent_id)
    if not agent:
        return ToolResult(text=f"Could not resume agent {agent_id}. Agent may not exist or is not paused.")

    return ToolResult(
        text=f"**Agent Resumed**\n\nAgent '{agent.name}' is now active.",
        data={"success": True, "agent_id": agent_id, "name": agent.name, "status": "active"}
    )


def execute_update_agent(
    params: Dict[str, Any],
    db: Session,
    user_id: int,
    context: Dict[str, Any]
) -> ToolResult:
    """Propose updating an agent's configuration (returns a payload for user approval)."""
    import json
    from services.autonomous_agent_service import AutonomousAgentService

    agent_id = params.get("agent_id")
    if not agent_id:
        return ToolResult(text="Error: agent_id is required")

    service = AutonomousAgentService(db, user_id)

    # Get current agent to show full state after update
    agent = service.get_agent(agent_id)
    if not agent:
        return ToolResult(text=f"Agent not found: {agent_id}", data={"success": False})

    # Build the updated agent data (merge current with updates)
    agent_data = {
        "agent_id": agent_id,
        "name": params.get("name", agent.name),
        "description": params.get("description", agent.description),
        "instructions": params.get("instructions", agent.instructions),
        "lifecycle": agent.lifecycle.value,  # Can't change lifecycle
        "tools": params.get("tools", agent.tools or []),
        "monitor_interval_minutes": params.get("monitor_interval_minutes", agent.monitor_interval_minutes)
    }

    # Track what's being changed
    changes = []
    if "name" in params and params["name"] != agent.name:
        changes.append("name")
    if "description" in params and params["description"] != agent.description:
        changes.append("description")
    if "instructions" in params and params["instructions"] != agent.instructions:
        changes.append("instructions")
    if "tools" in params and params["tools"] != (agent.tools or []):
        changes.append("tools")
    if "monitor_interval_minutes" in params and params["monitor_interval_minutes"] != agent.monitor_interval_minutes:
        changes.append("monitor_interval_minutes")

    if not changes:
        return ToolResult(text="No changes detected - the provided values match the current agent configuration.")

    # Build the payload for frontend approval
    payload = {
        "type": "agent_update",
        "title": f"Update Agent: {agent_data['name']}",
        "content": f"Updating: {', '.join(changes)}",
        "agent_data": agent_data
    }

    # Format explanation for the chat
    formatted = f"I've prepared an update proposal for agent **{agent.name}** (ID: {agent_id}):\n\n"
    formatted += f"**Changes:** {', '.join(changes)}\n"
    formatted += f"\nPlease review the details in the workspace panel and click **Update Agent** to confirm."

    # Include the payload block for the frontend to parse
    formatted += f"\n\n```payload\n{json.dumps(payload, indent=2)}\n```"

    return ToolResult(
        text=formatted,
        data={
            "proposal": True,
            "payload_type": "agent_update",
            "agent_id": agent_id,
            "changes": changes,
            "agent_data": agent_data
        }
    )


def execute_delete_agent(
    params: Dict[str, Any],
    db: Session,
    user_id: int,
    context: Dict[str, Any]
) -> ToolResult:
    """Delete an agent."""
    from services.autonomous_agent_service import AutonomousAgentService

    agent_id = params.get("agent_id")
    if not agent_id:
        return ToolResult(text="Error: agent_id is required")

    service = AutonomousAgentService(db, user_id)

    # Get agent name before deletion
    agent = service.get_agent(agent_id)
    if not agent:
        return ToolResult(text=f"Agent not found: {agent_id}", data={"success": False})

    agent_name = agent.name

    if not service.delete_agent(agent_id):
        return ToolResult(text=f"Failed to delete agent {agent_id}")

    return ToolResult(
        text=f"**Agent Deleted**\n\nAgent '{agent_name}' (ID: {agent_id}) has been deleted.",
        data={"success": True, "agent_id": agent_id, "name": agent_name}
    )


def execute_get_agent_runs(
    params: Dict[str, Any],
    db: Session,
    user_id: int,
    context: Dict[str, Any]
) -> ToolResult:
    """Get recent runs for an agent."""
    from services.autonomous_agent_service import AutonomousAgentService

    agent_id = params.get("agent_id")
    limit = params.get("limit", 10)

    if not agent_id:
        return ToolResult(text="Error: agent_id is required")

    service = AutonomousAgentService(db, user_id)

    agent = service.get_agent(agent_id)
    if not agent:
        return ToolResult(text=f"Agent not found: {agent_id}", data={"success": False})

    runs = service.get_agent_runs(agent_id, limit=limit)

    if not runs:
        return ToolResult(
            text=f"No runs found for agent '{agent.name}'.",
            data={"success": True, "runs": [], "count": 0}
        )

    formatted = f"**Runs for '{agent.name}'** ({len(runs)} shown)\n\n"
    run_list = []

    for run in runs:
        status_icon = {"completed": "✅", "running": "🔄", "failed": "❌", "pending": "⏳"}.get(run.status.value, "•")
        formatted += f"{status_icon} **Run #{run.run_id}** - {run.status.value}\n"
        if run.started_at:
            formatted += f"   Started: {run.started_at}\n"
        if run.result_summary:
            formatted += f"   Result: {run.result_summary[:100]}...\n"
        if run.error:
            formatted += f"   Error: {run.error[:100]}...\n"
        formatted += "\n"

        run_list.append({
            "run_id": run.run_id,
            "status": run.status.value,
            "started_at": str(run.started_at) if run.started_at else None,
            "completed_at": str(run.completed_at) if run.completed_at else None,
            "result_summary": run.result_summary,
            "error": run.error,
            "assets_created": run.assets_created
        })

    return ToolResult(text=formatted, data={"success": True, "runs": run_list, "count": len(runs)})


# Tool configurations
LIST_AGENTS_TOOL = ToolConfig(
    name="list_agents",
    description="List all autonomous background agents. Shows agent names, status, lifecycle type, and run counts.",
    input_schema={
        "type": "object",
        "properties": {
            "include_completed": {
                "type": "boolean",
                "default": True,
                "description": "Include completed one-shot agents"
            }
        }
    },
    executor=execute_list_agents,
    category="agents"
)

GET_AGENT_TOOL = ToolConfig(
    name="get_agent",
    description="Get detailed information about a specific autonomous agent including its instructions, tools, and recent runs.",
    input_schema={
        "type": "object",
        "properties": {
            "agent_id": {
                "type": "integer",
                "description": "The agent's ID"
            },
            "name": {
                "type": "string",
                "description": "The agent's name (alternative to agent_id)"
            }
        }
    },
    executor=execute_get_agent,
    category="agents"
)

CREATE_AGENT_TOOL = ToolConfig(
    name="create_agent",
    description="""Propose creating a new autonomous background agent. This will show a preview for the user to review and approve before the agent is actually created.

Lifecycle types:
- one_shot: Runs once when triggered manually
- scheduled: Runs on a schedule (not yet implemented)
- monitor: Runs periodically at a set interval

The agent will have access to the specified tools and follow the given instructions.""",
    input_schema={
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Name for the agent"
            },
            "instructions": {
                "type": "string",
                "description": "Detailed instructions for what the agent should do"
            },
            "lifecycle": {
                "type": "string",
                "enum": ["one_shot", "scheduled", "monitor"],
                "default": "one_shot",
                "description": "Agent lifecycle type"
            },
            "description": {
                "type": "string",
                "description": "Brief description of the agent's purpose"
            },
            "tools": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of tool names the agent can use (e.g., ['web_search', 'fetch_webpage'])"
            },
            "monitor_interval_minutes": {
                "type": "integer",
                "description": "For monitor agents, how often to run (in minutes)"
            }
        },
        "required": ["name", "instructions"]
    },
    executor=execute_create_agent,
    category="agents"
)

TRIGGER_AGENT_RUN_TOOL = ToolConfig(
    name="trigger_agent_run",
    description="Trigger an immediate run of an autonomous agent. The run will be queued and executed by the worker.",
    input_schema={
        "type": "object",
        "properties": {
            "agent_id": {
                "type": "integer",
                "description": "The agent's ID"
            }
        },
        "required": ["agent_id"]
    },
    executor=execute_trigger_agent_run,
    category="agents"
)

PAUSE_AGENT_TOOL = ToolConfig(
    name="pause_agent",
    description="Pause an active agent. Paused agents won't run automatically but can still be triggered manually.",
    input_schema={
        "type": "object",
        "properties": {
            "agent_id": {
                "type": "integer",
                "description": "The agent's ID"
            }
        },
        "required": ["agent_id"]
    },
    executor=execute_pause_agent,
    category="agents"
)

RESUME_AGENT_TOOL = ToolConfig(
    name="resume_agent",
    description="Resume a paused agent, making it active again.",
    input_schema={
        "type": "object",
        "properties": {
            "agent_id": {
                "type": "integer",
                "description": "The agent's ID"
            }
        },
        "required": ["agent_id"]
    },
    executor=execute_resume_agent,
    category="agents"
)

UPDATE_AGENT_TOOL = ToolConfig(
    name="update_agent",
    description="Propose updating an agent's configuration. This will show a preview for the user to review and approve before changes are applied. You can update name, description, instructions, tools, or monitor interval.",
    input_schema={
        "type": "object",
        "properties": {
            "agent_id": {
                "type": "integer",
                "description": "The agent's ID"
            },
            "name": {
                "type": "string",
                "description": "New name for the agent"
            },
            "description": {
                "type": "string",
                "description": "New description"
            },
            "instructions": {
                "type": "string",
                "description": "New instructions"
            },
            "tools": {
                "type": "array",
                "items": {"type": "string"},
                "description": "New list of tools"
            },
            "monitor_interval_minutes": {
                "type": "integer",
                "description": "New monitor interval (for monitor agents)"
            }
        },
        "required": ["agent_id"]
    },
    executor=execute_update_agent,
    category="agents"
)

DELETE_AGENT_TOOL = ToolConfig(
    name="delete_agent",
    description="Delete an autonomous agent and all its run history.",
    input_schema={
        "type": "object",
        "properties": {
            "agent_id": {
                "type": "integer",
                "description": "The agent's ID"
            }
        },
        "required": ["agent_id"]
    },
    executor=execute_delete_agent,
    category="agents"
)

GET_AGENT_RUNS_TOOL = ToolConfig(
    name="get_agent_runs",
    description="Get the run history for an agent, including status and results.",
    input_schema={
        "type": "object",
        "properties": {
            "agent_id": {
                "type": "integer",
                "description": "The agent's ID"
            },
            "limit": {
                "type": "integer",
                "default": 10,
                "description": "Maximum number of runs to return"
            }
        },
        "required": ["agent_id"]
    },
    executor=execute_get_agent_runs,
    category="agents"
)


def register_agent_tools():
    """Register all agent management tools."""
    register_tool(LIST_AGENTS_TOOL)
    register_tool(GET_AGENT_TOOL)
    register_tool(CREATE_AGENT_TOOL)
    register_tool(TRIGGER_AGENT_RUN_TOOL)
    register_tool(PAUSE_AGENT_TOOL)
    register_tool(RESUME_AGENT_TOOL)
    register_tool(UPDATE_AGENT_TOOL)
    register_tool(DELETE_AGENT_TOOL)
    register_tool(GET_AGENT_RUNS_TOOL)
    logger.info("Registered 9 agent management tools")
