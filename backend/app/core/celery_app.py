"""Celery app factory."""
from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from .config import settings

celery_app = Celery(
    "sourcer",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "app.tasks.pipeline",
        "app.tasks.deep_scan",
        "app.tasks.score_now",
        "app.tasks.outreach",
        "app.tasks.poll_inbox",
        "app.tasks.reply_pipeline",
        "app.tasks.workflow",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=60 * 30,
    task_soft_time_limit=60 * 25,
    worker_prefetch_multiplier=1,
    # Periodic tasks — requires running `celery -A app.core.celery_app beat`
    beat_schedule={
        "poll-linkedin-inbox-every-30min": {
            "task": "sourcer.poll_linkedin_inbox",
            "schedule": crontab(minute="*/30"),  # every 30 minutes
        },
    },
)
