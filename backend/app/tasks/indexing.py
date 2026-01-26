"""Celery tasks for Elasticsearch indexing operations.

Handles batch indexing, re-indexing, and index management operations.
"""

import logging
from typing import Any
from uuid import UUID

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    name="eleanor.batch_index_events",
    max_retries=3,
    default_retry_delay=60,
)
def batch_index_events(
    self,
    events: list[dict[str, Any]],
    index_name: str,
    case_id: str | None = None,
) -> dict[str, Any]:
    """Batch index events to Elasticsearch.

    Args:
        events: List of event documents to index
        index_name: Target index name
        case_id: Optional case UUID to add to events

    Returns:
        Dict with indexing results
    """
    import asyncio

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(
            _batch_index_async(events, index_name, case_id)
        )
        return result
    finally:
        loop.close()


async def _batch_index_async(
    events: list[dict[str, Any]],
    index_name: str,
    case_id: str | None,
) -> dict[str, Any]:
    """Async implementation of batch indexing."""
    from elasticsearch import AsyncElasticsearch
    from elasticsearch.helpers import async_bulk

    from app.config import get_settings

    settings = get_settings()
    es = AsyncElasticsearch(
        hosts=[settings.elasticsearch_url],
        verify_certs=False,
    )

    try:
        # Prepare bulk actions
        actions = []
        for event in events:
            if case_id:
                event["case_id"] = case_id
            actions.append({
                "_index": index_name,
                "_source": event,
            })

        # Execute bulk indexing
        success, errors = await async_bulk(
            es,
            actions,
            raise_on_error=False,
            raise_on_exception=False,
        )

        return {
            "index_name": index_name,
            "total": len(events),
            "success": success,
            "errors": len(errors) if isinstance(errors, list) else 0,
        }

    finally:
        await es.close()


@shared_task(
    name="eleanor.reindex_case_events",
    max_retries=2,
)
def reindex_case_events(
    case_id: str,
    source_index: str | None = None,
    dest_index: str | None = None,
    query: dict | None = None,
) -> dict[str, Any]:
    """Reindex events for a case with optional filtering.

    Args:
        case_id: Case UUID
        source_index: Source index (defaults to case events index)
        dest_index: Destination index (defaults to new case events index)
        query: Optional filter query

    Returns:
        Dict with reindex results
    """
    import asyncio

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(
            _reindex_async(case_id, source_index, dest_index, query)
        )
        return result
    finally:
        loop.close()


async def _reindex_async(
    case_id: str,
    source_index: str | None,
    dest_index: str | None,
    query: dict | None,
) -> dict[str, Any]:
    """Async implementation of reindexing."""
    from elasticsearch import AsyncElasticsearch

    from app.config import get_settings

    settings = get_settings()
    es = AsyncElasticsearch(
        hosts=[settings.elasticsearch_url],
        verify_certs=False,
    )

    try:
        prefix = settings.elasticsearch_index_prefix

        if not source_index:
            source_index = f"{prefix}-events-{case_id}"
        if not dest_index:
            dest_index = f"{prefix}-events-{case_id}-reindexed"

        # Build reindex body
        body = {
            "source": {"index": source_index},
            "dest": {"index": dest_index},
        }

        if query:
            body["source"]["query"] = query

        # Execute reindex
        result = await es.reindex(body=body, wait_for_completion=True)

        return {
            "case_id": case_id,
            "source_index": source_index,
            "dest_index": dest_index,
            "total": result.get("total", 0),
            "created": result.get("created", 0),
            "updated": result.get("updated", 0),
            "failures": result.get("failures", []),
        }

    finally:
        await es.close()


@shared_task(name="eleanor.delete_case_events")
def delete_case_events(
    case_id: str,
    index_name: str | None = None,
) -> dict[str, Any]:
    """Delete all events for a case.

    Args:
        case_id: Case UUID
        index_name: Optional specific index name

    Returns:
        Dict with deletion results
    """
    import asyncio

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(
            _delete_events_async(case_id, index_name)
        )
        return result
    finally:
        loop.close()


async def _delete_events_async(
    case_id: str,
    index_name: str | None,
) -> dict[str, Any]:
    """Async implementation of event deletion."""
    from elasticsearch import AsyncElasticsearch

    from app.config import get_settings

    settings = get_settings()
    es = AsyncElasticsearch(
        hosts=[settings.elasticsearch_url],
        verify_certs=False,
    )

    try:
        if not index_name:
            index_name = f"{settings.elasticsearch_index_prefix}-events-{case_id}"

        # Check if index exists
        exists = await es.indices.exists(index=index_name)

        if not exists:
            return {
                "case_id": case_id,
                "index_name": index_name,
                "deleted": 0,
                "message": "Index does not exist",
            }

        # Delete the index
        await es.indices.delete(index=index_name)

        return {
            "case_id": case_id,
            "index_name": index_name,
            "deleted": True,
            "message": "Index deleted successfully",
        }

    finally:
        await es.close()


@shared_task(name="eleanor.create_case_index")
def create_case_index(
    case_id: str,
) -> dict[str, Any]:
    """Create Elasticsearch index for a case.

    Args:
        case_id: Case UUID

    Returns:
        Dict with creation results
    """
    import asyncio

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(_create_index_async(case_id))
        return result
    finally:
        loop.close()


async def _create_index_async(case_id: str) -> dict[str, Any]:
    """Async implementation of index creation."""
    from elasticsearch import AsyncElasticsearch

    from app.config import get_settings

    settings = get_settings()
    es = AsyncElasticsearch(
        hosts=[settings.elasticsearch_url],
        verify_certs=False,
    )

    try:
        index_name = f"{settings.elasticsearch_index_prefix}-events-{case_id}"

        # Check if index exists
        exists = await es.indices.exists(index=index_name)

        if exists:
            return {
                "case_id": case_id,
                "index_name": index_name,
                "created": False,
                "message": "Index already exists",
            }

        # Create index with ECS-compatible mappings
        mappings = {
            "properties": {
                "@timestamp": {"type": "date"},
                "case_id": {"type": "keyword"},
                "evidence_id": {"type": "keyword"},
                "message": {"type": "text"},
                "event": {
                    "properties": {
                        "kind": {"type": "keyword"},
                        "category": {"type": "keyword"},
                        "type": {"type": "keyword"},
                        "action": {"type": "keyword"},
                        "outcome": {"type": "keyword"},
                        "severity": {"type": "integer"},
                    }
                },
                "host": {
                    "properties": {
                        "name": {"type": "keyword"},
                        "ip": {"type": "ip"},
                        "mac": {"type": "keyword"},
                        "os": {
                            "properties": {
                                "name": {"type": "keyword"},
                                "version": {"type": "keyword"},
                            }
                        },
                    }
                },
                "user": {
                    "properties": {
                        "name": {"type": "keyword"},
                        "domain": {"type": "keyword"},
                        "id": {"type": "keyword"},
                    }
                },
                "process": {
                    "properties": {
                        "name": {"type": "keyword"},
                        "pid": {"type": "integer"},
                        "command_line": {"type": "text"},
                        "executable": {"type": "keyword"},
                        "parent": {
                            "properties": {
                                "pid": {"type": "integer"},
                            }
                        },
                    }
                },
                "file": {
                    "properties": {
                        "name": {"type": "keyword"},
                        "path": {"type": "keyword"},
                        "hash": {
                            "properties": {
                                "sha256": {"type": "keyword"},
                                "sha1": {"type": "keyword"},
                                "md5": {"type": "keyword"},
                            }
                        },
                    }
                },
                "source": {
                    "properties": {
                        "ip": {"type": "ip"},
                        "port": {"type": "integer"},
                    }
                },
                "destination": {
                    "properties": {
                        "ip": {"type": "ip"},
                        "port": {"type": "integer"},
                    }
                },
                "network": {
                    "properties": {
                        "protocol": {"type": "keyword"},
                        "direction": {"type": "keyword"},
                    }
                },
                "url": {
                    "properties": {
                        "full": {"type": "keyword"},
                        "domain": {"type": "keyword"},
                    }
                },
                "labels": {"type": "object"},
                "tags": {"type": "keyword"},
                "_raw": {"type": "text", "index": False},
                "_source": {
                    "properties": {
                        "type": {"type": "keyword"},
                        "file": {"type": "keyword"},
                        "line": {"type": "integer"},
                    }
                },
            }
        }

        await es.indices.create(
            index=index_name,
            mappings=mappings,
            settings={
                "number_of_shards": 1,
                "number_of_replicas": 0,
            },
        )

        return {
            "case_id": case_id,
            "index_name": index_name,
            "created": True,
            "message": "Index created successfully",
        }

    finally:
        await es.close()


@shared_task(name="eleanor.get_index_stats")
def get_index_stats(
    case_id: str | None = None,
    index_pattern: str | None = None,
) -> dict[str, Any]:
    """Get Elasticsearch index statistics.

    Args:
        case_id: Optional case UUID to get specific index stats
        index_pattern: Optional index pattern for broader stats

    Returns:
        Dict with index statistics
    """
    import asyncio

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(
            _get_stats_async(case_id, index_pattern)
        )
        return result
    finally:
        loop.close()


async def _get_stats_async(
    case_id: str | None,
    index_pattern: str | None,
) -> dict[str, Any]:
    """Async implementation of stats retrieval."""
    from elasticsearch import AsyncElasticsearch

    from app.config import get_settings

    settings = get_settings()
    es = AsyncElasticsearch(
        hosts=[settings.elasticsearch_url],
        verify_certs=False,
    )

    try:
        if case_id:
            pattern = f"{settings.elasticsearch_index_prefix}-events-{case_id}"
        elif index_pattern:
            pattern = index_pattern
        else:
            pattern = f"{settings.elasticsearch_index_prefix}-events-*"

        # Get index stats
        stats = await es.indices.stats(index=pattern)

        indices = stats.get("indices", {})
        total_docs = 0
        total_size = 0
        index_list = []

        for idx_name, idx_stats in indices.items():
            primaries = idx_stats.get("primaries", {})
            docs = primaries.get("docs", {})
            store = primaries.get("store", {})

            doc_count = docs.get("count", 0)
            size_bytes = store.get("size_in_bytes", 0)

            total_docs += doc_count
            total_size += size_bytes

            index_list.append({
                "name": idx_name,
                "doc_count": doc_count,
                "size_bytes": size_bytes,
                "size_human": _format_bytes(size_bytes),
            })

        return {
            "pattern": pattern,
            "index_count": len(indices),
            "total_docs": total_docs,
            "total_size_bytes": total_size,
            "total_size_human": _format_bytes(total_size),
            "indices": sorted(index_list, key=lambda x: x["doc_count"], reverse=True),
        }

    finally:
        await es.close()


def _format_bytes(size: int) -> str:
    """Format bytes to human-readable string."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} PB"
