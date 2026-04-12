"""
Celery Beat schedule configuration.
Defines periodic tasks for Trail's background workers.
"""
from celery.schedules import crontab

beat_schedule = {
    # Daily snapshots at 23:59
    "daily-snapshots": {
        "task": "src.tasks.workers.snapshot_worker.create_daily_snapshots",
        "schedule": crontab(hour=23, minute=59),
    },
    # Notion AI Agent poller — every minute
    "notion-poller": {
        "task": "src.services.notion_agent.agent.poll_notion_commands",
        "schedule": 60.0,  # Every 60 seconds
    },
    # Notion AI Agent responder — every 30 seconds
    "notion-responder": {
        "task": "src.services.notion_agent.responder.process_notion_commands",
        "schedule": 30.0,  # Every 30 seconds
    },
    # Escalation engine — daily at 09:00
    "check-stale-projects": {
        "task": "src.services.escalation.engine.check_stale_projects",
        "schedule": crontab(hour=9, minute=0),
    },
}
