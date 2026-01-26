"""Celery tasks for IOC enrichment.

Handles asynchronous enrichment of indicators of compromise (IOCs)
using threat intelligence sources like OpenCTI.
"""

import logging
from typing import Any
from uuid import UUID

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    name="eleanor.enrich_iocs",
    max_retries=3,
    default_retry_delay=30,
    queue="enrichment",
)
def enrich_iocs(
    self,
    iocs: list[dict[str, str]],
    case_id: str | None = None,
    update_elasticsearch: bool = True,
) -> dict[str, Any]:
    """Enrich a list of IOCs with threat intelligence.

    Args:
        iocs: List of IOC dicts with 'type' and 'value' keys
        case_id: Optional case UUID to associate enrichments
        update_elasticsearch: Whether to update ES documents with enrichment

    Returns:
        Dict with enrichment results
    """
    import asyncio

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(
            _enrich_iocs_async(iocs, case_id, update_elasticsearch)
        )
        return result
    finally:
        loop.close()


async def _enrich_iocs_async(
    iocs: list[dict[str, str]],
    case_id: str | None,
    update_elasticsearch: bool,
) -> dict[str, Any]:
    """Async implementation of IOC enrichment."""
    from app.config import get_settings

    settings = get_settings()
    results = {
        "total": len(iocs),
        "enriched": 0,
        "malicious": 0,
        "suspicious": 0,
        "clean": 0,
        "errors": 0,
        "details": [],
    }

    # Check if OpenCTI is enabled
    if not settings.opencti_enabled:
        logger.warning("OpenCTI not enabled, skipping enrichment")
        return results

    try:
        from app.adapters.opencti.adapter import OpenCTIAdapter

        adapter = OpenCTIAdapter()
        await adapter.initialize()

        for ioc in iocs:
            ioc_type = ioc.get("type", "")
            ioc_value = ioc.get("value", "")

            if not ioc_type or not ioc_value:
                continue

            try:
                # Query OpenCTI for the IOC
                enrichment = await adapter.lookup_indicator(ioc_type, ioc_value)

                if enrichment:
                    results["enriched"] += 1

                    # Categorize by score
                    score = enrichment.get("score", 0)
                    if score >= 70:
                        results["malicious"] += 1
                    elif score >= 40:
                        results["suspicious"] += 1
                    else:
                        results["clean"] += 1

                    results["details"].append({
                        "ioc": ioc,
                        "enrichment": enrichment,
                    })

            except Exception as e:
                logger.warning(f"Failed to enrich IOC {ioc_value}: {e}")
                results["errors"] += 1

        await adapter.shutdown()

    except ImportError:
        logger.error("OpenCTI adapter not available")
    except Exception as e:
        logger.exception(f"Enrichment failed: {e}")
        results["errors"] = len(iocs)

    return results


@shared_task(
    name="eleanor.enrich_entity",
    max_retries=3,
    default_retry_delay=30,
    queue="enrichment",
)
def enrich_entity(
    entity_type: str,
    entity_value: str,
    case_id: str | None = None,
) -> dict[str, Any]:
    """Enrich a single entity with contextual information.

    Args:
        entity_type: Type of entity (host, user, ip, domain, hash)
        entity_value: Value of the entity
        case_id: Optional case UUID

    Returns:
        Dict with enrichment data
    """
    import asyncio

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(
            _enrich_entity_async(entity_type, entity_value, case_id)
        )
        return result
    finally:
        loop.close()


async def _enrich_entity_async(
    entity_type: str,
    entity_value: str,
    case_id: str | None,
) -> dict[str, Any]:
    """Async implementation of entity enrichment."""
    from app.config import get_settings
    from elasticsearch import AsyncElasticsearch

    settings = get_settings()
    es = AsyncElasticsearch(
        hosts=[settings.elasticsearch_url],
        verify_certs=False,
    )

    try:
        enrichment = {
            "entity_type": entity_type,
            "entity_value": entity_value,
            "first_seen": None,
            "last_seen": None,
            "event_count": 0,
            "related_entities": [],
            "threat_intel": None,
        }

        # Build search query based on entity type
        field_map = {
            "host": "host.name",
            "user": "user.name",
            "ip": ["source.ip", "destination.ip"],
            "domain": "url.domain",
            "hash": ["file.hash.sha256", "file.hash.sha1", "file.hash.md5"],
        }

        fields = field_map.get(entity_type, entity_type)
        if isinstance(fields, str):
            fields = [fields]

        # Query Elasticsearch for entity occurrences
        should_clauses = [
            {"term": {field: entity_value}} for field in fields
        ]

        index_pattern = f"{settings.elasticsearch_index_prefix}-events-*"
        if case_id:
            index_pattern = f"{settings.elasticsearch_index_prefix}-events-{case_id}"

        result = await es.search(
            index=index_pattern,
            query={"bool": {"should": should_clauses, "minimum_should_match": 1}},
            aggs={
                "first_seen": {"min": {"field": "@timestamp"}},
                "last_seen": {"max": {"field": "@timestamp"}},
                "related_hosts": {"terms": {"field": "host.name", "size": 10}},
                "related_users": {"terms": {"field": "user.name", "size": 10}},
                "related_ips": {"terms": {"field": "source.ip", "size": 10}},
            },
            size=0,
        )

        aggs = result.get("aggregations", {})
        enrichment["event_count"] = result["hits"]["total"]["value"]
        enrichment["first_seen"] = aggs.get("first_seen", {}).get("value_as_string")
        enrichment["last_seen"] = aggs.get("last_seen", {}).get("value_as_string")

        # Collect related entities
        for key in ["related_hosts", "related_users", "related_ips"]:
            buckets = aggs.get(key, {}).get("buckets", [])
            for bucket in buckets:
                if bucket["key"] != entity_value:
                    enrichment["related_entities"].append({
                        "type": key.replace("related_", "").rstrip("s"),
                        "value": bucket["key"],
                        "count": bucket["doc_count"],
                    })

        # Try threat intelligence enrichment
        if entity_type in ("ip", "domain", "hash"):
            ioc_type_map = {
                "ip": "ipv4" if "." in entity_value else "ipv6",
                "domain": "domain",
                "hash": _detect_hash_type(entity_value),
            }
            ioc_type = ioc_type_map.get(entity_type)
            if ioc_type:
                ti_result = await _enrich_iocs_async(
                    [{"type": ioc_type, "value": entity_value}],
                    case_id,
                    False,
                )
                if ti_result["details"]:
                    enrichment["threat_intel"] = ti_result["details"][0].get("enrichment")

        return enrichment

    finally:
        await es.close()


def _detect_hash_type(value: str) -> str:
    """Detect hash type from value length."""
    length = len(value)
    if length == 32:
        return "md5"
    elif length == 40:
        return "sha1"
    elif length == 64:
        return "sha256"
    return "hash"


@shared_task(
    name="eleanor.batch_enrich_events",
    max_retries=2,
    queue="enrichment",
)
def batch_enrich_events(
    case_id: str,
    index_name: str | None = None,
) -> dict[str, Any]:
    """Extract and enrich all IOCs from case events.

    Args:
        case_id: Case UUID
        index_name: Optional specific index name

    Returns:
        Dict with batch enrichment results
    """
    import asyncio

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(
            _batch_enrich_events_async(case_id, index_name)
        )
        return result
    finally:
        loop.close()


async def _batch_enrich_events_async(
    case_id: str,
    index_name: str | None,
) -> dict[str, Any]:
    """Async implementation of batch event enrichment."""
    from app.config import get_settings
    from elasticsearch import AsyncElasticsearch

    settings = get_settings()
    es = AsyncElasticsearch(
        hosts=[settings.elasticsearch_url],
        verify_certs=False,
    )

    try:
        if not index_name:
            index_name = f"{settings.elasticsearch_index_prefix}-events-{case_id}"

        # Extract unique IOCs from events
        iocs = []

        # Get unique IPs
        ip_result = await es.search(
            index=index_name,
            aggs={
                "source_ips": {"terms": {"field": "source.ip", "size": 100}},
                "dest_ips": {"terms": {"field": "destination.ip", "size": 100}},
            },
            size=0,
        )

        for bucket in ip_result["aggregations"].get("source_ips", {}).get("buckets", []):
            iocs.append({"type": "ipv4", "value": bucket["key"]})
        for bucket in ip_result["aggregations"].get("dest_ips", {}).get("buckets", []):
            iocs.append({"type": "ipv4", "value": bucket["key"]})

        # Get unique domains
        domain_result = await es.search(
            index=index_name,
            aggs={
                "domains": {"terms": {"field": "url.domain", "size": 100}},
            },
            size=0,
        )

        for bucket in domain_result["aggregations"].get("domains", {}).get("buckets", []):
            iocs.append({"type": "domain", "value": bucket["key"]})

        # Get unique file hashes
        hash_result = await es.search(
            index=index_name,
            aggs={
                "sha256": {"terms": {"field": "file.hash.sha256", "size": 100}},
                "sha1": {"terms": {"field": "file.hash.sha1", "size": 100}},
                "md5": {"terms": {"field": "file.hash.md5", "size": 100}},
            },
            size=0,
        )

        for bucket in hash_result["aggregations"].get("sha256", {}).get("buckets", []):
            iocs.append({"type": "sha256", "value": bucket["key"]})
        for bucket in hash_result["aggregations"].get("sha1", {}).get("buckets", []):
            iocs.append({"type": "sha1", "value": bucket["key"]})
        for bucket in hash_result["aggregations"].get("md5", {}).get("buckets", []):
            iocs.append({"type": "md5", "value": bucket["key"]})

        # Deduplicate
        seen = set()
        unique_iocs = []
        for ioc in iocs:
            key = f"{ioc['type']}:{ioc['value']}"
            if key not in seen:
                seen.add(key)
                unique_iocs.append(ioc)

        logger.info(f"Extracted {len(unique_iocs)} unique IOCs from case {case_id}")

        # Enrich IOCs
        enrichment_result = await _enrich_iocs_async(unique_iocs, case_id, True)

        return {
            "case_id": case_id,
            "iocs_extracted": len(unique_iocs),
            "enrichment": enrichment_result,
        }

    finally:
        await es.close()
