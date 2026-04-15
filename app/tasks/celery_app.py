"""
Celery application — task queue and beat scheduler.
"""
from celery import Celery
from celery.schedules import crontab

from app.config import settings

celery_app = Celery(
    "daca_ops",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "app.tasks.agent_tasks",
        "app.tasks.integration_tasks",
        "app.tasks.sla_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="America/New_York",
    enable_utc=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
)

celery_app.conf.beat_schedule = {
    # Poll Gmail inbox every 60 seconds
    "poll-gmail-inbox": {
        "task": "app.tasks.agent_tasks.run_intake_agent",
        "schedule": settings.gmail_poll_interval_seconds,
    },
    # Poll Typeform sheet every 10 minutes
    "poll-typeform-sheet": {
        "task": "app.tasks.integration_tasks.sync_typeform_responses",
        "schedule": settings.typeform_poll_interval_minutes * 60,
    },
    # SLA check every 15 minutes
    "check-sla-deadlines": {
        "task": "app.tasks.sla_tasks.run_sla_check",
        "schedule": settings.sla_check_interval_minutes * 60,
    },
    # Weekly Slack update: Tuesday at 10:00 AM ET
    "weekly-slack-update": {
        "task": "app.tasks.sla_tasks.send_weekly_status_update",
        "schedule": crontab(hour=10, minute=0, day_of_week="tuesday"),
    },
    # Sync Ops Manual: every Monday at 9:00 AM ET
    "sync-ops-manual": {
        "task": "app.tasks.integration_tasks.sync_ops_manual",
        "schedule": crontab(hour=9, minute=0, day_of_week="monday"),
    },
    # Monthly Webster report: 1st of each month at 8:00 AM ET
    "monthly-webster-report": {
        "task": "app.tasks.integration_tasks.generate_monthly_webster_report",
        "schedule": crontab(hour=8, minute=0, day_of_month="1"),
    },
}
