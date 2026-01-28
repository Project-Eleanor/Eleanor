"""Celery tasks for parsing evidence files.

Handles the asynchronous parsing of evidence files using the parser framework,
with progress tracking and error handling.
"""

import logging
from typing import Any

from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    name="eleanor.parse_evidence",
    max_retries=3,
    default_retry_delay=60,
    soft_time_limit=7000,
    time_limit=7200,
)
def parse_evidence(
    self,
    job_id: str,
    evidence_id: str,
    case_id: str,
    parser_hint: str | None = None,
    config: dict | None = None,
) -> dict[str, Any]:
    """Parse an evidence file and index results to Elasticsearch.

    Args:
        job_id: UUID of the ParsingJob record
        evidence_id: UUID of the Evidence record
        case_id: UUID of the Case record
        parser_hint: Optional hint for parser selection
        config: Optional parser configuration

    Returns:
        Dict with parsing results summary
    """
    import asyncio

    from app.tasks._parsing_impl import run_parsing_job

    try:
        # Run the async parsing implementation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                run_parsing_job(
                    job_id=job_id,
                    evidence_id=evidence_id,
                    case_id=case_id,
                    parser_hint=parser_hint,
                    config=config or {},
                    task=self,
                )
            )
            return result
        finally:
            loop.close()

    except SoftTimeLimitExceeded:
        logger.error(f"Parsing job {job_id} exceeded time limit")
        # Update job status
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            from app.tasks._parsing_impl import mark_job_failed
            loop.run_until_complete(
                mark_job_failed(job_id, "Task exceeded time limit (2 hours)")
            )
        finally:
            loop.close()
        raise

    except Exception as e:
        logger.exception(f"Parsing job {job_id} failed: {e}")
        # Update job status
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            from app.tasks._parsing_impl import mark_job_failed
            loop.run_until_complete(
                mark_job_failed(job_id, str(e), {"exception_type": type(e).__name__})
            )
        finally:
            loop.close()
        raise self.retry(exc=e)


@shared_task(
    bind=True,
    name="eleanor.batch_parse_evidence",
    max_retries=1,
)
def batch_parse_evidence(
    self,
    job_ids: list[str],
) -> dict[str, Any]:
    """Submit multiple parsing jobs as a batch.

    Args:
        job_ids: List of ParsingJob UUIDs to process

    Returns:
        Dict with batch status
    """
    from celery import group

    tasks = []
    for job_id in job_ids:
        # Each job will be processed individually
        tasks.append(parse_evidence.s(job_id=job_id))

    # Execute as a group
    job = group(tasks)
    result = job.apply_async()

    return {
        "batch_id": result.id,
        "job_count": len(job_ids),
        "status": "submitted",
    }


@shared_task(name="eleanor.cancel_parsing_job")
def cancel_parsing_job(job_id: str, celery_task_id: str | None = None) -> dict[str, Any]:
    """Cancel a running parsing job.

    Args:
        job_id: UUID of the ParsingJob record
        celery_task_id: Optional Celery task ID to revoke

    Returns:
        Dict with cancellation status
    """
    import asyncio

    from app.tasks.celery_app import celery_app

    # Revoke the Celery task if we have the ID
    if celery_task_id:
        celery_app.control.revoke(celery_task_id, terminate=True)

    # Update job status
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        from app.tasks._parsing_impl import mark_job_cancelled
        loop.run_until_complete(mark_job_cancelled(job_id))
    finally:
        loop.close()

    return {
        "job_id": job_id,
        "status": "cancelled",
    }
