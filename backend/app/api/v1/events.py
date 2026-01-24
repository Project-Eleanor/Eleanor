"""Events API endpoints for event ingestion."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.v1.auth import get_current_user
from app.config import get_settings
from app.database import get_elasticsearch
from app.models.user import User

router = APIRouter()
settings = get_settings()


class EventCreate(BaseModel):
    """Single event creation request."""

    timestamp: datetime = Field(alias="@timestamp")
    case_id: UUID | None = None
    event_type: str | None = None
    source_type: str | None = None
    severity: str | None = None
    host: dict | None = None
    user: dict | None = None
    process: dict | None = None
    file: dict | None = None
    network: dict | None = None
    registry: dict | None = None
    message: str | None = None
    raw: str | None = None
    tags: list[str] = []
    mitre: dict | None = None
    metadata: dict = {}

    class Config:
        populate_by_name = True


class BulkEventsCreate(BaseModel):
    """Bulk event creation request."""

    events: list[EventCreate]


class EventResponse(BaseModel):
    """Event response."""

    id: str
    index: str
    result: str


class BulkEventResponse(BaseModel):
    """Bulk event response."""

    indexed: int
    errors: int
    items: list[dict]


@router.post("", response_model=EventResponse, status_code=status.HTTP_201_CREATED)
async def create_event(
    event_data: EventCreate,
    current_user: Annotated[User, Depends(get_current_user)],
) -> EventResponse:
    """Ingest a single event."""
    es = await get_elasticsearch()

    # Prepare document
    doc = event_data.model_dump(by_alias=True, exclude_none=True)
    if event_data.case_id:
        doc["case_id"] = str(event_data.case_id)

    # Determine index name based on timestamp
    index_date = event_data.timestamp.strftime("%Y.%m.%d")
    index_name = f"{settings.elasticsearch_index_prefix}-events-{index_date}"

    response = await es.index(
        index=index_name,
        body=doc,
        refresh=True,
    )

    return EventResponse(
        id=response["_id"],
        index=response["_index"],
        result=response["result"],
    )


@router.post("/bulk", response_model=BulkEventResponse, status_code=status.HTTP_201_CREATED)
async def create_events_bulk(
    bulk_data: BulkEventsCreate,
    current_user: Annotated[User, Depends(get_current_user)],
) -> BulkEventResponse:
    """Bulk ingest events."""
    es = await get_elasticsearch()

    if not bulk_data.events:
        return BulkEventResponse(indexed=0, errors=0, items=[])

    # Prepare bulk request
    operations = []
    for event in bulk_data.events:
        doc = event.model_dump(by_alias=True, exclude_none=True)
        if event.case_id:
            doc["case_id"] = str(event.case_id)

        index_date = event.timestamp.strftime("%Y.%m.%d")
        index_name = f"{settings.elasticsearch_index_prefix}-events-{index_date}"

        operations.append({"index": {"_index": index_name}})
        operations.append(doc)

    response = await es.bulk(body=operations, refresh=True)

    indexed = 0
    errors = 0
    items = []

    for item in response.get("items", []):
        index_result = item.get("index", {})
        if index_result.get("status") in (200, 201):
            indexed += 1
        else:
            errors += 1
        items.append({
            "id": index_result.get("_id"),
            "index": index_result.get("_index"),
            "status": index_result.get("status"),
            "error": index_result.get("error"),
        })

    return BulkEventResponse(
        indexed=indexed,
        errors=errors,
        items=items,
    )


@router.get("/{event_id}")
async def get_event(
    event_id: str,
    index: str,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Get event by ID."""
    es = await get_elasticsearch()

    try:
        response = await es.get(index=index, id=event_id)
        return {
            "id": response["_id"],
            "index": response["_index"],
            **response["_source"],
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event not found: {e}",
        )
