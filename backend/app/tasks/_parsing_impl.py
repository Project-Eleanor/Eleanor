"""Implementation details for parsing tasks.

Separates the async implementation from the Celery task definitions
to allow proper async/await usage with database operations.
"""

import logging
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.models.evidence import Evidence
from app.models.parsing_job import ParsingJob
from app.parsers.registry import get_parser, load_builtin_parsers

logger = logging.getLogger(__name__)
settings = get_settings()

# Create a separate engine for Celery tasks
_task_engine = None
_task_session_maker = None


def get_task_session_maker() -> async_sessionmaker:
    """Get session maker for task execution."""
    global _task_engine, _task_session_maker

    if _task_session_maker is None:
        _task_engine = create_async_engine(
            settings.database_url,
            echo=False,
            pool_size=5,
            max_overflow=10,
        )
        _task_session_maker = async_sessionmaker(
            _task_engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    return _task_session_maker


async def get_elasticsearch_client():
    """Get Elasticsearch client for indexing."""
    from elasticsearch import AsyncElasticsearch

    return AsyncElasticsearch(
        hosts=[settings.elasticsearch_url],
        verify_certs=False,
    )


async def run_parsing_job(
    job_id: str,
    evidence_id: str,
    case_id: str,
    parser_hint: str | None,
    config: dict,
    task: Any,
) -> dict[str, Any]:
    """Execute the parsing job.

    Args:
        job_id: UUID of the ParsingJob
        evidence_id: UUID of the Evidence
        case_id: UUID of the Case
        parser_hint: Optional parser hint
        config: Parser configuration
        task: Celery task instance for progress updates

    Returns:
        Dict with results summary
    """
    # Ensure parsers are loaded
    load_builtin_parsers()

    session_maker = get_task_session_maker()
    es = await get_elasticsearch_client()

    try:
        async with session_maker() as session:
            # Get the job and evidence records
            job = await session.get(ParsingJob, UUID(job_id))
            if not job:
                raise ValueError(f"ParsingJob {job_id} not found")

            evidence = await session.get(Evidence, UUID(evidence_id))
            if not evidence:
                raise ValueError(f"Evidence {evidence_id} not found")

            # Mark job as running
            job.mark_running()
            await session.commit()

            # Get file path
            file_path = Path(evidence.file_path) if evidence.file_path else None
            if not file_path or not file_path.exists():
                raise FileNotFoundError(f"Evidence file not found: {evidence.file_path}")

            # Find appropriate parser
            with open(file_path, "rb") as f:
                content = f.read(4096)  # Read first 4KB for detection

            parser = get_parser(
                file_path=file_path,
                content=content,
                hint=parser_hint,
            )

            if not parser:
                raise ValueError(f"No parser found for evidence: {evidence.filename}")

            job.parser_type = parser.name
            await session.commit()

            logger.info(f"Parsing evidence {evidence.filename} with parser {parser.name}")

            # Parse and index events
            events_parsed = 0
            events_indexed = 0
            events_failed = 0
            batch = []
            batch_size = 500

            index_name = f"{settings.elasticsearch_index_prefix}-events-{case_id}"

            for event in parser.parse(file_path, source_name=evidence.filename):
                events_parsed += 1

                try:
                    # Convert to dict and add metadata
                    doc = event.to_dict()
                    doc["case_id"] = str(case_id)
                    doc["evidence_id"] = str(evidence_id)

                    batch.append(
                        {
                            "_index": index_name,
                            "_source": doc,
                        }
                    )

                    # Bulk index when batch is full
                    if len(batch) >= batch_size:
                        indexed = await _bulk_index(es, batch)
                        events_indexed += indexed
                        events_failed += len(batch) - indexed
                        batch = []

                        # Update progress
                        progress = min(int((events_parsed / max(events_parsed, 1000)) * 100), 99)
                        job.update_progress(events_parsed, events_indexed, progress)
                        await session.commit()

                        # Update Celery task state
                        task.update_state(
                            state="PROGRESS",
                            meta={
                                "events_parsed": events_parsed,
                                "events_indexed": events_indexed,
                                "progress": progress,
                            },
                        )

                except Exception as e:
                    logger.warning(f"Failed to process event: {e}")
                    events_failed += 1

            # Index remaining batch
            if batch:
                indexed = await _bulk_index(es, batch)
                events_indexed += indexed
                events_failed += len(batch) - indexed

            # Build results summary
            results_summary = {
                "parser": parser.name,
                "category": parser.category.value,
                "total_events": events_parsed,
                "indexed_events": events_indexed,
                "failed_events": events_failed,
                "index_name": index_name,
            }

            # Mark job as completed
            job.mark_completed(events_parsed, events_indexed, results_summary)
            await session.commit()

            logger.info(
                f"Completed parsing job {job_id}: "
                f"{events_parsed} parsed, {events_indexed} indexed"
            )

            return results_summary

    finally:
        await es.close()


async def _bulk_index(es, batch: list[dict]) -> int:
    """Bulk index documents to Elasticsearch.

    Args:
        es: Elasticsearch client
        batch: List of documents to index

    Returns:
        Number of successfully indexed documents
    """
    from elasticsearch.helpers import async_bulk

    try:
        success, failed = await async_bulk(
            es,
            batch,
            raise_on_error=False,
            raise_on_exception=False,
        )
        return success
    except Exception as e:
        logger.error(f"Bulk indexing failed: {e}")
        return 0


async def mark_job_failed(
    job_id: str, error_message: str, error_details: dict | None = None
) -> None:
    """Mark a parsing job as failed."""
    session_maker = get_task_session_maker()

    async with session_maker() as session:
        job = await session.get(ParsingJob, UUID(job_id))
        if job:
            job.mark_failed(error_message, error_details)
            await session.commit()


async def mark_job_cancelled(job_id: str) -> None:
    """Mark a parsing job as cancelled."""
    session_maker = get_task_session_maker()

    async with session_maker() as session:
        job = await session.get(ParsingJob, UUID(job_id))
        if job:
            job.mark_cancelled()
            await session.commit()
