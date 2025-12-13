"""
Agent Worker Process

Simple worker that polls for pending agent runs and executes them.
In production, this would listen to SQS instead of polling the database.

Usage:
    python worker.py
"""

import logging
import os
import signal
import sys
import time
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from config import setup_logging
from database import SessionLocal, init_db
from models import AutonomousAgent, AgentRun, AgentRunStatus, AgentStatus
from services.autonomous_agent_service import AutonomousAgentService
from services.agent_loop import CancellationToken
from tools import register_all_builtin_tools

# Setup logging
logger, _ = setup_logging()
logger = logging.getLogger(__name__)

# Configuration
POLL_INTERVAL_SECONDS = int(os.environ.get('WORKER_POLL_INTERVAL', 5))
USE_SQS = bool(os.environ.get('TASK_QUEUE_URL'))

# Global cancellation token for graceful shutdown
shutdown_requested = False
current_cancellation_token: Optional[CancellationToken] = None


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    global shutdown_requested, current_cancellation_token
    logger.info(f"Received signal {signum}, initiating graceful shutdown...")
    shutdown_requested = True
    if current_cancellation_token:
        current_cancellation_token.cancel()


def get_db() -> Session:
    """Get a database session."""
    return SessionLocal()


def check_due_agents(db: Session):
    """Check for scheduled/monitor agents that are due to run and queue them."""
    now = datetime.utcnow()

    due_agents = db.query(AutonomousAgent).filter(
        AutonomousAgent.status == AgentStatus.ACTIVE,
        AutonomousAgent.next_run_at <= now
    ).all()

    for agent in due_agents:
        # Check if there's already a pending/running run
        existing_run = db.query(AgentRun).filter(
            AgentRun.agent_id == agent.agent_id,
            AgentRun.status.in_([AgentRunStatus.PENDING, AgentRunStatus.RUNNING])
        ).first()

        if existing_run:
            logger.debug(f"Agent {agent.agent_id} already has a pending/running run")
            continue

        # Queue a new run
        service = AutonomousAgentService(db, agent.user_id)
        run = service.queue_run(agent.agent_id)
        if run:
            logger.info(f"Queued run for due agent {agent.agent_id} ({agent.name})")


def process_pending_runs(db: Session):
    """Process all pending runs."""
    global current_cancellation_token

    pending_runs = db.query(AgentRun).filter(
        AgentRun.status == AgentRunStatus.PENDING
    ).order_by(AgentRun.created_at.asc()).all()

    for run in pending_runs:
        if shutdown_requested:
            logger.info("Shutdown requested, stopping run processing")
            break

        agent = db.query(AutonomousAgent).filter(
            AutonomousAgent.agent_id == run.agent_id
        ).first()

        if not agent:
            logger.warning(f"Run {run.run_id} has no associated agent, marking as failed")
            run.status = AgentRunStatus.FAILED
            run.error = "Agent not found"
            db.commit()
            continue

        logger.info(f"Processing run {run.run_id} for agent {agent.agent_id} ({agent.name})")

        # Create cancellation token for this run
        current_cancellation_token = CancellationToken()

        try:
            service = AutonomousAgentService(db, agent.user_id)
            service.execute_run(run.run_id, cancellation_token=current_cancellation_token)
            logger.info(f"Run {run.run_id} completed with status {run.status.value}")
        except Exception as e:
            logger.error(f"Error executing run {run.run_id}: {e}", exc_info=True)
            # The service should have already marked the run as failed
        finally:
            current_cancellation_token = None


def poll_sqs():
    """Poll SQS for messages and process them."""
    import boto3
    import json

    queue_url = os.environ['TASK_QUEUE_URL']
    sqs = boto3.client('sqs')

    while not shutdown_requested:
        try:
            response = sqs.receive_message(
                QueueUrl=queue_url,
                MaxNumberOfMessages=1,
                WaitTimeSeconds=20  # Long polling
            )

            messages = response.get('Messages', [])
            for message in messages:
                if shutdown_requested:
                    break

                body = json.loads(message['Body'])
                run_id = body.get('run_id')

                if run_id:
                    db = get_db()
                    try:
                        run = db.query(AgentRun).filter(AgentRun.run_id == run_id).first()
                        if run:
                            agent = db.query(AutonomousAgent).filter(
                                AutonomousAgent.agent_id == run.agent_id
                            ).first()
                            if agent:
                                logger.info(f"Processing SQS message for run {run_id}")
                                service = AutonomousAgentService(db, agent.user_id)
                                service.execute_run(run_id)
                    finally:
                        db.close()

                # Delete the message after processing
                sqs.delete_message(
                    QueueUrl=queue_url,
                    ReceiptHandle=message['ReceiptHandle']
                )

        except Exception as e:
            logger.error(f"Error polling SQS: {e}", exc_info=True)
            time.sleep(5)


def poll_database():
    """Poll the database for pending runs."""
    logger.info("Starting database polling mode")

    while not shutdown_requested:
        db = get_db()
        try:
            # Check for due scheduled/monitor agents
            check_due_agents(db)

            # Process pending runs
            process_pending_runs(db)

        except Exception as e:
            logger.error(f"Error in poll cycle: {e}", exc_info=True)
        finally:
            db.close()

        # Wait before next poll
        for _ in range(POLL_INTERVAL_SECONDS):
            if shutdown_requested:
                break
            time.sleep(1)


def main():
    """Main worker entry point."""
    logger.info("=" * 60)
    logger.info("Agent Worker Starting")
    logger.info("=" * 60)

    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Initialize database
    init_db()
    logger.info("Database initialized")

    # Register tools
    register_all_builtin_tools()
    logger.info("Tools registered")

    # Choose polling method
    if USE_SQS:
        logger.info(f"Using SQS queue: {os.environ['TASK_QUEUE_URL']}")
        poll_sqs()
    else:
        logger.info(f"Using database polling (interval: {POLL_INTERVAL_SECONDS}s)")
        poll_database()

    logger.info("Worker shutdown complete")


if __name__ == "__main__":
    main()
