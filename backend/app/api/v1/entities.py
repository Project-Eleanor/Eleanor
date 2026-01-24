"""Entities API endpoints for host, user, and IP profiles."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from app.api.v1.auth import get_current_user
from app.config import get_settings
from app.database import get_elasticsearch
from app.models.user import User

router = APIRouter()
settings = get_settings()


class EntityProfile(BaseModel):
    """Entity profile response."""

    entity_type: str
    identifier: str
    first_seen: str | None
    last_seen: str | None
    event_count: int
    related_cases: list[str]
    summary: dict


class EntityEvent(BaseModel):
    """Event associated with an entity."""

    id: str
    timestamp: str
    event_type: str | None
    message: str | None
    case_id: str | None


@router.get("/hosts/{hostname}", response_model=EntityProfile)
async def get_host_profile(
    hostname: str,
    current_user: Annotated[User, Depends(get_current_user)],
) -> EntityProfile:
    """Get host profile aggregated from events."""
    es = await get_elasticsearch()

    try:
        response = await es.search(
            index=f"{settings.elasticsearch_index_prefix}-events-*",
            body={
                "size": 0,
                "query": {
                    "bool": {
                        "should": [
                            {"term": {"host.name": hostname}},
                            {"term": {"host.hostname": hostname}},
                        ],
                        "minimum_should_match": 1,
                    }
                },
                "aggs": {
                    "first_seen": {"min": {"field": "@timestamp"}},
                    "last_seen": {"max": {"field": "@timestamp"}},
                    "cases": {"terms": {"field": "case_id", "size": 100}},
                    "event_types": {"terms": {"field": "event_type", "size": 20}},
                    "users": {"terms": {"field": "user.name", "size": 20}},
                    "processes": {"terms": {"field": "process.name", "size": 20}},
                },
            },
        )

        aggs = response.get("aggregations", {})
        total = response["hits"]["total"]["value"]

        return EntityProfile(
            entity_type="host",
            identifier=hostname,
            first_seen=aggs.get("first_seen", {}).get("value_as_string"),
            last_seen=aggs.get("last_seen", {}).get("value_as_string"),
            event_count=total,
            related_cases=[
                bucket["key"]
                for bucket in aggs.get("cases", {}).get("buckets", [])
            ],
            summary={
                "event_types": {
                    bucket["key"]: bucket["doc_count"]
                    for bucket in aggs.get("event_types", {}).get("buckets", [])
                },
                "users": [
                    bucket["key"]
                    for bucket in aggs.get("users", {}).get("buckets", [])
                ],
                "top_processes": [
                    bucket["key"]
                    for bucket in aggs.get("processes", {}).get("buckets", [])
                ],
            },
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get host profile: {e}",
        )


@router.get("/users/{username}", response_model=EntityProfile)
async def get_user_profile(
    username: str,
    current_user: Annotated[User, Depends(get_current_user)],
) -> EntityProfile:
    """Get user profile aggregated from events."""
    es = await get_elasticsearch()

    try:
        response = await es.search(
            index=f"{settings.elasticsearch_index_prefix}-events-*",
            body={
                "size": 0,
                "query": {"term": {"user.name": username}},
                "aggs": {
                    "first_seen": {"min": {"field": "@timestamp"}},
                    "last_seen": {"max": {"field": "@timestamp"}},
                    "cases": {"terms": {"field": "case_id", "size": 100}},
                    "event_types": {"terms": {"field": "event_type", "size": 20}},
                    "hosts": {"terms": {"field": "host.name", "size": 20}},
                    "processes": {"terms": {"field": "process.name", "size": 20}},
                },
            },
        )

        aggs = response.get("aggregations", {})
        total = response["hits"]["total"]["value"]

        return EntityProfile(
            entity_type="user",
            identifier=username,
            first_seen=aggs.get("first_seen", {}).get("value_as_string"),
            last_seen=aggs.get("last_seen", {}).get("value_as_string"),
            event_count=total,
            related_cases=[
                bucket["key"]
                for bucket in aggs.get("cases", {}).get("buckets", [])
            ],
            summary={
                "event_types": {
                    bucket["key"]: bucket["doc_count"]
                    for bucket in aggs.get("event_types", {}).get("buckets", [])
                },
                "hosts": [
                    bucket["key"]
                    for bucket in aggs.get("hosts", {}).get("buckets", [])
                ],
                "top_processes": [
                    bucket["key"]
                    for bucket in aggs.get("processes", {}).get("buckets", [])
                ],
            },
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get user profile: {e}",
        )


@router.get("/ips/{ip_address}", response_model=EntityProfile)
async def get_ip_profile(
    ip_address: str,
    current_user: Annotated[User, Depends(get_current_user)],
) -> EntityProfile:
    """Get IP address profile aggregated from events."""
    es = await get_elasticsearch()

    try:
        response = await es.search(
            index=f"{settings.elasticsearch_index_prefix}-events-*",
            body={
                "size": 0,
                "query": {
                    "bool": {
                        "should": [
                            {"term": {"host.ip": ip_address}},
                            {"term": {"network.source_ip": ip_address}},
                            {"term": {"network.destination_ip": ip_address}},
                        ],
                        "minimum_should_match": 1,
                    }
                },
                "aggs": {
                    "first_seen": {"min": {"field": "@timestamp"}},
                    "last_seen": {"max": {"field": "@timestamp"}},
                    "cases": {"terms": {"field": "case_id", "size": 100}},
                    "event_types": {"terms": {"field": "event_type", "size": 20}},
                    "hosts": {"terms": {"field": "host.name", "size": 20}},
                    "ports": {"terms": {"field": "network.destination_port", "size": 20}},
                },
            },
        )

        aggs = response.get("aggregations", {})
        total = response["hits"]["total"]["value"]

        return EntityProfile(
            entity_type="ip",
            identifier=ip_address,
            first_seen=aggs.get("first_seen", {}).get("value_as_string"),
            last_seen=aggs.get("last_seen", {}).get("value_as_string"),
            event_count=total,
            related_cases=[
                bucket["key"]
                for bucket in aggs.get("cases", {}).get("buckets", [])
            ],
            summary={
                "event_types": {
                    bucket["key"]: bucket["doc_count"]
                    for bucket in aggs.get("event_types", {}).get("buckets", [])
                },
                "hosts": [
                    bucket["key"]
                    for bucket in aggs.get("hosts", {}).get("buckets", [])
                ],
                "ports": [
                    bucket["key"]
                    for bucket in aggs.get("ports", {}).get("buckets", [])
                ],
            },
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get IP profile: {e}",
        )


@router.get("/{entity_type}/{identifier}/events", response_model=list[EntityEvent])
async def get_entity_events(
    entity_type: str,
    identifier: str,
    current_user: Annotated[User, Depends(get_current_user)],
    from_: int = Query(0, alias="from"),
    size: int = Query(100, le=1000),
) -> list[EntityEvent]:
    """Get events for a specific entity."""
    es = await get_elasticsearch()

    # Build query based on entity type
    if entity_type == "host":
        query = {
            "bool": {
                "should": [
                    {"term": {"host.name": identifier}},
                    {"term": {"host.hostname": identifier}},
                ],
                "minimum_should_match": 1,
            }
        }
    elif entity_type == "user":
        query = {"term": {"user.name": identifier}}
    elif entity_type == "ip":
        query = {
            "bool": {
                "should": [
                    {"term": {"host.ip": identifier}},
                    {"term": {"network.source_ip": identifier}},
                    {"term": {"network.destination_ip": identifier}},
                ],
                "minimum_should_match": 1,
            }
        }
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown entity type: {entity_type}",
        )

    try:
        response = await es.search(
            index=f"{settings.elasticsearch_index_prefix}-events-*",
            body={
                "query": query,
                "sort": [{"@timestamp": {"order": "desc"}}],
                "from": from_,
                "size": size,
            },
        )

        events = []
        for hit in response["hits"]["hits"]:
            source = hit["_source"]
            events.append(
                EntityEvent(
                    id=hit["_id"],
                    timestamp=source.get("@timestamp", ""),
                    event_type=source.get("event_type"),
                    message=source.get("message"),
                    case_id=source.get("case_id"),
                )
            )

        return events

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get entity events: {e}",
        )
