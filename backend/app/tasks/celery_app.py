"""Celery application factory for Eleanor.

Configures Celery with Redis as broker and backend, with multiple queues
for different priority levels and task types.
"""

import logging

from celery import Celery

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Create Celery application
celery_app = Celery(
    "eleanor",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "app.tasks.parsing",
        "app.tasks.enrichment",
        "app.tasks.indexing",
    ],
)

# Celery configuration
celery_app.conf.update(
    # Task settings
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # Task execution settings
    task_time_limit=7200,  # 2 hours hard limit
    task_soft_time_limit=7000,  # Soft limit for cleanup
    task_acks_late=True,  # Acknowledge after task completes
    task_reject_on_worker_lost=True,  # Re-queue if worker dies
    # Result settings
    result_expires=86400,  # Results expire after 24 hours
    result_extended=True,  # Include additional result metadata
    # Retry settings
    task_default_retry_delay=60,  # 1 minute between retries
    task_max_retries=3,
    # Routing
    task_default_queue="default",
    task_queues={
        "high": {
            "exchange": "high",
            "routing_key": "high",
        },
        "default": {
            "exchange": "default",
            "routing_key": "default",
        },
        "low": {
            "exchange": "low",
            "routing_key": "low",
        },
        "enrichment": {
            "exchange": "enrichment",
            "routing_key": "enrichment",
        },
    },
    # Task routes
    task_routes={
        "app.tasks.parsing.*": {"queue": "default"},
        "app.tasks.enrichment.*": {"queue": "enrichment"},
        "app.tasks.indexing.*": {"queue": "default"},
    },
    # Worker settings
    worker_prefetch_multiplier=1,  # Fair task distribution
    worker_concurrency=4,  # Concurrent tasks per worker
    # Logging
    worker_hijack_root_logger=False,
    worker_log_format="[%(asctime)s: %(levelname)s/%(processName)s] %(message)s",
    worker_task_log_format="[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s",
)


# Task state change signals for monitoring
@celery_app.task(bind=True, name="eleanor.health_check")
def health_check(self):
    """Simple health check task to verify Celery is working."""
    return {"status": "ok", "worker": self.request.hostname}


def get_celery_app() -> Celery:
    """Get the configured Celery application instance."""
    return celery_app
