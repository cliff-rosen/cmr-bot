"""
Autonomous Agent Service

Manages autonomous background agents - creation, execution, and lifecycle.
"""

import json
import logging
import os
from datetime import datetime, timedelta, date
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from models import (
    AutonomousAgent, AgentRun, AgentRunEvent, Asset, AssetType,
    AgentLifecycle, AgentStatus, AgentRunStatus, AgentRunEventType
)
from services.agent_loop import (
    run_agent_loop_sync, CancellationToken,
    AgentEvent, AgentThinking, AgentMessage, AgentToolStart, AgentToolProgress,
    AgentToolComplete, AgentComplete, AgentCancelled, AgentError
)
from tools import get_tool

logger = logging.getLogger(__name__)


class AutonomousAgentService:
    """Service for managing autonomous background agents."""

    def __init__(self, db: Session, user_id: int):
        self.db = db
        self.user_id = user_id

    # =========================================================================
    # Agent CRUD
    # =========================================================================

    def create_agent(
        self,
        name: str,
        instructions: str,
        lifecycle: AgentLifecycle,
        description: Optional[str] = None,
        tools: Optional[List[str]] = None,
        schedule: Optional[str] = None,
        monitor_interval_minutes: Optional[int] = None
    ) -> AutonomousAgent:
        """Create a new autonomous agent."""
        agent = AutonomousAgent(
            user_id=self.user_id,
            name=name,
            description=description,
            lifecycle=lifecycle,
            instructions=instructions,
            tools=tools or [],
            schedule=schedule,
            monitor_interval_minutes=monitor_interval_minutes,
            status=AgentStatus.ACTIVE
        )

        # Set initial next_run_at for scheduled/monitor agents
        if lifecycle == AgentLifecycle.ONE_SHOT:
            agent.next_run_at = datetime.utcnow()  # Run immediately
        elif lifecycle == AgentLifecycle.MONITOR and monitor_interval_minutes:
            agent.next_run_at = datetime.utcnow()  # First check immediately
        # For scheduled, we'd parse cron - simplified for now
        elif lifecycle == AgentLifecycle.SCHEDULED:
            agent.next_run_at = datetime.utcnow()  # Run immediately for POC

        self.db.add(agent)
        self.db.commit()
        self.db.refresh(agent)

        logger.info(f"Created agent {agent.agent_id}: {name} ({lifecycle.value})")

        # Queue initial run
        self.queue_run(agent.agent_id)

        return agent

    def get_agent(self, agent_id: int) -> Optional[AutonomousAgent]:
        """Get an agent by ID."""
        return self.db.query(AutonomousAgent).filter(
            AutonomousAgent.agent_id == agent_id,
            AutonomousAgent.user_id == self.user_id
        ).first()

    def list_agents(self, include_completed: bool = True) -> List[AutonomousAgent]:
        """List all agents for the user."""
        query = self.db.query(AutonomousAgent).filter(
            AutonomousAgent.user_id == self.user_id
        )
        if not include_completed:
            query = query.filter(AutonomousAgent.status != AgentStatus.COMPLETED)
        return query.order_by(AutonomousAgent.created_at.desc()).all()

    def update_agent(
        self,
        agent_id: int,
        **kwargs
    ) -> Optional[AutonomousAgent]:
        """Update an agent's properties."""
        agent = self.get_agent(agent_id)
        if not agent:
            return None

        for key, value in kwargs.items():
            if hasattr(agent, key):
                setattr(agent, key, value)

        self.db.commit()
        self.db.refresh(agent)
        return agent

    def delete_agent(self, agent_id: int) -> bool:
        """Delete an agent and its runs."""
        agent = self.get_agent(agent_id)
        if not agent:
            return False

        self.db.delete(agent)
        self.db.commit()
        logger.info(f"Deleted agent {agent_id}")
        return True

    def pause_agent(self, agent_id: int) -> Optional[AutonomousAgent]:
        """Pause an agent."""
        return self.update_agent(agent_id, status=AgentStatus.PAUSED)

    def resume_agent(self, agent_id: int) -> Optional[AutonomousAgent]:
        """Resume a paused agent."""
        agent = self.get_agent(agent_id)
        if not agent or agent.status != AgentStatus.PAUSED:
            return None

        agent.status = AgentStatus.ACTIVE
        agent.next_run_at = datetime.utcnow()  # Schedule immediate run
        self.db.commit()
        self.db.refresh(agent)

        # Queue a run
        self.queue_run(agent_id)
        return agent

    # =========================================================================
    # Run Management
    # =========================================================================

    def queue_run(self, agent_id: int) -> Optional[AgentRun]:
        """Queue a new run for an agent."""
        agent = self.get_agent(agent_id)
        if not agent or agent.status != AgentStatus.ACTIVE:
            return None

        run = AgentRun(
            agent_id=agent_id,
            status=AgentRunStatus.PENDING
        )
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)

        logger.info(f"Queued run {run.run_id} for agent {agent_id}")

        # In production, we'd send to SQS here
        # For now, we'll poll the database in the worker
        self._send_to_queue(run.run_id)

        return run

    def _send_to_queue(self, run_id: int):
        """Send a run to the task queue (SQS in production)."""
        queue_url = os.environ.get('TASK_QUEUE_URL')
        if queue_url:
            import boto3
            sqs = boto3.client('sqs')
            sqs.send_message(
                QueueUrl=queue_url,
                MessageBody=json.dumps({"run_id": run_id})
            )
            logger.info(f"Sent run {run_id} to SQS")
        else:
            # Local dev - worker will poll database
            logger.debug(f"No SQS queue configured, run {run_id} will be picked up by DB polling")

    def get_pending_runs(self) -> List[AgentRun]:
        """Get all pending runs (for worker polling in dev)."""
        return self.db.query(AgentRun).filter(
            AgentRun.status == AgentRunStatus.PENDING
        ).order_by(AgentRun.created_at.asc()).all()

    def get_run(self, run_id: int) -> Optional[AgentRun]:
        """Get a run by ID."""
        return self.db.query(AgentRun).filter(AgentRun.run_id == run_id).first()

    def get_agent_runs(self, agent_id: int, limit: int = 10) -> List[AgentRun]:
        """Get recent runs for an agent."""
        return self.db.query(AgentRun).filter(
            AgentRun.agent_id == agent_id
        ).order_by(AgentRun.created_at.desc()).limit(limit).all()

    # =========================================================================
    # Event Logging
    # =========================================================================

    def log_event(
        self,
        run_id: int,
        event_type: AgentRunEventType,
        message: str,
        data: Optional[Dict[str, Any]] = None
    ) -> AgentRunEvent:
        """Log a telemetry event for a run."""
        event = AgentRunEvent(
            run_id=run_id,
            event_type=event_type,
            message=message,
            data=data
        )
        self.db.add(event)
        self.db.commit()
        return event

    def get_run_events(self, run_id: int, limit: int = 100) -> List[AgentRunEvent]:
        """Get events for a run, ordered by creation time."""
        return self.db.query(AgentRunEvent).filter(
            AgentRunEvent.run_id == run_id
        ).order_by(AgentRunEvent.created_at.asc()).limit(limit).all()

    def _create_event_handler(self, run_id: int):
        """Create an event callback for the agent loop that logs to DB."""
        def handle_event(event: AgentEvent):
            event_type_name = type(event).__name__
            logger.debug(f"[Run {run_id}] Received event: {event_type_name}")

            try:
                if isinstance(event, AgentThinking):
                    logger.info(f"[Run {run_id}] THINKING: {event.message}")
                    self.log_event(
                        run_id,
                        AgentRunEventType.THINKING,
                        event.message
                    )
                elif isinstance(event, AgentMessage):
                    # Log the actual LLM response - truncate if very long
                    text_preview = event.text[:500] if len(event.text) > 500 else event.text
                    logger.info(f"[Run {run_id}] MESSAGE (iter {event.iteration}): {text_preview[:200]}...")
                    self.log_event(
                        run_id,
                        AgentRunEventType.MESSAGE,
                        f"[Iteration {event.iteration}] {event.text[:1000] if len(event.text) > 1000 else event.text}",
                        {"iteration": event.iteration, "full_text": event.text[:2000]}
                    )
                elif isinstance(event, AgentToolStart):
                    logger.info(f"[Run {run_id}] TOOL_START: {event.tool_name}")
                    self.log_event(
                        run_id,
                        AgentRunEventType.TOOL_START,
                        f"Starting tool: {event.tool_name}",
                        {"tool_name": event.tool_name, "input": event.tool_input}
                    )
                elif isinstance(event, AgentToolProgress):
                    logger.info(f"[Run {run_id}] TOOL_PROGRESS: {event.tool_name} - {event.progress.stage}: {event.progress.message}")
                    self.log_event(
                        run_id,
                        AgentRunEventType.TOOL_PROGRESS,
                        f"{event.tool_name}: {event.progress.message}",
                        {
                            "tool_name": event.tool_name,
                            "stage": event.progress.stage,
                            "progress": event.progress.progress,
                            "data": event.progress.data
                        }
                    )
                elif isinstance(event, AgentToolComplete):
                    # Truncate large results for storage
                    result_preview = str(event.result_text)[:500] if event.result_text else None
                    self.log_event(
                        run_id,
                        AgentRunEventType.TOOL_COMPLETE,
                        f"Completed tool: {event.tool_name}",
                        {"tool_name": event.tool_name, "result_preview": result_preview}
                    )
                elif isinstance(event, AgentComplete):
                    self.log_event(
                        run_id,
                        AgentRunEventType.STATUS,
                        "Agent completed successfully",
                        {"tool_count": len(event.tool_calls)}
                    )
                elif isinstance(event, AgentCancelled):
                    self.log_event(
                        run_id,
                        AgentRunEventType.WARNING,
                        "Agent was cancelled",
                        {"tool_count": len(event.tool_calls)}
                    )
                elif isinstance(event, AgentError):
                    self.log_event(
                        run_id,
                        AgentRunEventType.ERROR,
                        f"Agent error: {event.error}",
                        {"error": event.error}
                    )
            except Exception as e:
                # Don't let logging errors stop execution
                logger.error(f"Failed to log event: {e}")

        return handle_event

    # =========================================================================
    # Run Execution (called by worker)
    # =========================================================================

    def execute_run(self, run_id: int, cancellation_token: Optional[CancellationToken] = None) -> AgentRun:
        """Execute an agent run. Called by the worker process."""
        run = self.get_run(run_id)
        if not run:
            raise ValueError(f"Run {run_id} not found")

        agent = self.db.query(AutonomousAgent).filter(
            AutonomousAgent.agent_id == run.agent_id
        ).first()
        if not agent:
            raise ValueError(f"Agent {run.agent_id} not found")

        # Mark as running
        run.status = AgentRunStatus.RUNNING
        run.started_at = datetime.utcnow()
        self.db.commit()

        logger.info(f"Executing run {run_id} for agent {agent.agent_id} ({agent.name})")

        # Log run start event
        self.log_event(
            run_id,
            AgentRunEventType.STATUS,
            f"Run started for agent: {agent.name}",
            {"agent_id": agent.agent_id, "lifecycle": agent.lifecycle.value}
        )

        # Create event handler for logging during execution
        event_handler = self._create_event_handler(run_id)

        try:
            # Debug: Log all registered tools in the system
            from tools import get_all_tools
            all_registered = [t.name for t in get_all_tools()]
            logger.info(f"All registered tools in system: {all_registered}")

            # Build tool configs
            tool_configs = {}
            for tool_name in (agent.tools or []):
                config = get_tool(tool_name)
                if config:
                    tool_configs[tool_name] = config
                else:
                    logger.warning(f"Tool '{tool_name}' not found in registry")

            # Log what tools are available
            configured_tools = list(tool_configs.keys())
            logger.info(f"Agent {agent.agent_id} requested tools: {agent.tools}, configured: {configured_tools}")

            self.log_event(
                run_id,
                AgentRunEventType.STATUS,
                f"Tools configured: {configured_tools if configured_tools else 'None'} (from {len(all_registered)} registered)",
                {
                    "requested_tools": agent.tools or [],
                    "available_tools": configured_tools,
                    "missing_tools": [t for t in (agent.tools or []) if t not in tool_configs],
                    "all_registered_tools": all_registered
                }
            )

            # Build system prompt
            current_date = date.today().strftime("%Y-%m-%d")
            system_prompt = f"""You are an autonomous agent executing a specific task.

            **IMPORTANT - Current Date: {current_date}** (Use this date for all time-relative references.)

            ## Your Task
            {agent.instructions}

            ## Rules
            1. Complete the task thoroughly
            2. Use the available tools as needed
            3. Create assets for any significant outputs (reports, data, summaries)
            4. Be concise in your final response - summarize what you accomplished

            ## Creating Assets
            When you produce something valuable (a report, research summary, data), save it as an asset
            so the user can access it later. Use descriptive names.
            """

            messages = [{"role": "user", "content": "Execute your task now."}]

            # Run the agent loop with event logging
            result_text, tool_calls, error = run_agent_loop_sync(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                max_iterations=15,
                system_prompt=system_prompt,
                messages=messages,
                tools=tool_configs,
                db=self.db,
                user_id=agent.user_id,
                context={"agent_id": agent.agent_id, "run_id": run_id},
                cancellation_token=cancellation_token,
                temperature=0.7,
                on_event=event_handler
            )

            # Update run with results
            run.result_summary = result_text[:1000] if result_text else None
            run.tool_calls = tool_calls
            run.completed_at = datetime.utcnow()

            if error:
                run.status = AgentRunStatus.FAILED
                run.error = error
            else:
                run.status = AgentRunStatus.COMPLETED

                # Automatically save the agent's output as an asset
                if result_text and result_text.strip():
                    from datetime import date
                    try:
                        asset_name = f"{agent.name} - {date.today().strftime('%Y-%m-%d')} (Run #{run_id})"
                        asset = Asset(
                            user_id=agent.user_id,
                            name=asset_name,
                            asset_type=AssetType.DOCUMENT,
                            content=result_text,
                            description=f"Automatic output from agent '{agent.name}'",
                            created_by_agent_id=agent.agent_id,
                            agent_run_id=run_id
                        )
                        self.db.add(asset)
                        self.db.flush()  # Test if insert works
                        run.assets_created = (run.assets_created or 0) + 1
                        agent.total_assets_created = (agent.total_assets_created or 0) + 1

                        self.log_event(
                            run_id,
                            AgentRunEventType.STATUS,
                            f"Saved output as asset: {asset_name}",
                            {"asset_name": asset_name, "content_length": len(result_text)}
                        )
                    except Exception as asset_error:
                        logger.warning(f"Failed to save asset (may need DB migration): {asset_error}")
                        self.db.rollback()
                        self.log_event(
                            run_id,
                            AgentRunEventType.WARNING,
                            f"Could not save output as asset: {str(asset_error)[:200]}",
                            {"error": str(asset_error)}
                        )

            # Update agent stats
            agent.total_runs += 1
            agent.last_run_at = datetime.utcnow()

            # Handle lifecycle-specific logic
            if agent.lifecycle == AgentLifecycle.ONE_SHOT:
                agent.status = AgentStatus.COMPLETED
                agent.next_run_at = None
            elif agent.lifecycle == AgentLifecycle.MONITOR:
                # Schedule next check
                if agent.monitor_interval_minutes:
                    agent.next_run_at = datetime.utcnow() + timedelta(minutes=agent.monitor_interval_minutes)
                    # Queue next run (in production, a scheduler would do this)
                    self._schedule_next_run(agent)
            elif agent.lifecycle == AgentLifecycle.SCHEDULED:
                # Parse cron and schedule next - simplified for POC
                agent.next_run_at = datetime.utcnow() + timedelta(hours=24)
                self._schedule_next_run(agent)

            self.db.commit()
            logger.info(f"Run {run_id} completed with status {run.status.value}")

        except Exception as e:
            logger.error(f"Run {run_id} failed with error: {e}", exc_info=True)
            run.status = AgentRunStatus.FAILED
            run.error = str(e)
            run.completed_at = datetime.utcnow()
            self.db.commit()

            # Log the exception event
            self.log_event(
                run_id,
                AgentRunEventType.ERROR,
                f"Run failed with exception: {str(e)}",
                {"error": str(e), "error_type": type(e).__name__}
            )

        return run

    def _schedule_next_run(self, agent: AutonomousAgent):
        """Schedule the next run for a recurring agent."""
        # In production, this would create a scheduled SQS message or use EventBridge
        # For POC, we'll rely on the worker polling for due agents
        logger.debug(f"Agent {agent.agent_id} next run scheduled for {agent.next_run_at}")

    # =========================================================================
    # Asset Creation (for agents to use)
    # =========================================================================

    def create_asset(
        self,
        agent_id: int,
        run_id: int,
        name: str,
        content: str,
        asset_type: AssetType = AssetType.DOCUMENT,
        description: Optional[str] = None
    ) -> Asset:
        """Create an asset from an agent run."""
        agent = self.db.query(AutonomousAgent).filter(
            AutonomousAgent.agent_id == agent_id
        ).first()
        if not agent:
            raise ValueError(f"Agent {agent_id} not found")

        asset = Asset(
            user_id=agent.user_id,
            name=name,
            asset_type=asset_type,
            content=content,
            description=description,
            created_by_agent_id=agent_id,
            agent_run_id=run_id
        )
        self.db.add(asset)

        # Update run's asset count
        run = self.get_run(run_id)
        if run:
            run.assets_created = (run.assets_created or 0) + 1

        # Update agent's total asset count
        agent.total_assets_created = (agent.total_assets_created or 0) + 1

        self.db.commit()
        self.db.refresh(asset)

        logger.info(f"Agent {agent_id} created asset {asset.asset_id}: {name}")
        return asset
