"""Workbook API endpoints.

Provides endpoints for creating, managing, and executing workbook tiles
for investigation dashboards.
"""

import logging
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import get_current_user
from app.database import get_db, get_elasticsearch
from app.models.user import User
from app.models.workbook import Workbook

logger = logging.getLogger(__name__)
router = APIRouter()


# Pydantic schemas
class TileDefinition(BaseModel):
    """Definition for a workbook tile."""

    id: str = Field(..., description="Unique tile ID within workbook")
    type: str = Field(..., description="Tile type: query, chart, table, markdown, metric, timeline")
    title: str = Field(..., description="Tile title")
    position: dict = Field(
        ...,
        description="Position and size: {x, y, width, height}",
    )
    config: dict = Field(default_factory=dict, description="Tile-specific configuration")


class WorkbookDefinition(BaseModel):
    """Full workbook definition."""

    tiles: list[TileDefinition] = Field(default_factory=list)
    layout: dict = Field(
        default_factory=dict,
        description="Layout configuration (grid columns, row height)",
    )
    variables: dict = Field(
        default_factory=dict,
        description="Workbook-level variables for tiles",
    )


class WorkbookCreate(BaseModel):
    """Request to create a workbook."""

    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    definition: WorkbookDefinition = Field(default_factory=WorkbookDefinition)
    is_public: bool = True


class WorkbookUpdate(BaseModel):
    """Request to update a workbook."""

    name: str | None = None
    description: str | None = None
    definition: WorkbookDefinition | None = None
    is_public: bool | None = None


class WorkbookResponse(BaseModel):
    """Workbook response."""

    id: UUID
    name: str
    description: str | None
    definition: dict
    is_public: bool
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class WorkbookListResponse(BaseModel):
    """Paginated workbook list."""

    items: list[WorkbookResponse]
    total: int
    page: int
    page_size: int
    pages: int


class TileExecuteRequest(BaseModel):
    """Request to execute a tile query."""

    tile_type: str = Field(..., description="Tile type")
    config: dict = Field(..., description="Tile configuration")
    variables: dict = Field(default_factory=dict, description="Variable substitutions")
    case_id: UUID | None = Field(None, description="Case context for queries")


class TileExecuteResponse(BaseModel):
    """Response from tile execution."""

    data: list[dict] | dict | str = Field(..., description="Tile data")
    metadata: dict = Field(default_factory=dict)


# Workbook templates
WORKBOOK_TEMPLATES = [
    {
        "name": "Case Overview",
        "description": "Summary dashboard for case investigations",
        "definition": {
            "tiles": [
                {
                    "id": "events-count",
                    "type": "metric",
                    "title": "Total Events",
                    "position": {"x": 0, "y": 0, "width": 3, "height": 2},
                    "config": {
                        "query": "*",
                        "aggregation": "count",
                    },
                },
                {
                    "id": "hosts-count",
                    "type": "metric",
                    "title": "Unique Hosts",
                    "position": {"x": 3, "y": 0, "width": 3, "height": 2},
                    "config": {
                        "query": "*",
                        "aggregation": "cardinality",
                        "field": "host.name",
                    },
                },
                {
                    "id": "users-count",
                    "type": "metric",
                    "title": "Unique Users",
                    "position": {"x": 6, "y": 0, "width": 3, "height": 2},
                    "config": {
                        "query": "*",
                        "aggregation": "cardinality",
                        "field": "user.name",
                    },
                },
                {
                    "id": "alerts-count",
                    "type": "metric",
                    "title": "Alerts",
                    "position": {"x": 9, "y": 0, "width": 3, "height": 2},
                    "config": {
                        "query": "event.kind:alert",
                        "aggregation": "count",
                    },
                },
                {
                    "id": "events-timeline",
                    "type": "chart",
                    "title": "Events Over Time",
                    "position": {"x": 0, "y": 2, "width": 8, "height": 4},
                    "config": {
                        "chart_type": "line",
                        "query": "*",
                        "x_field": "@timestamp",
                        "interval": "1h",
                    },
                },
                {
                    "id": "top-hosts",
                    "type": "chart",
                    "title": "Top Hosts",
                    "position": {"x": 8, "y": 2, "width": 4, "height": 4},
                    "config": {
                        "chart_type": "bar",
                        "query": "*",
                        "group_by": "host.name",
                        "limit": 10,
                    },
                },
                {
                    "id": "recent-events",
                    "type": "table",
                    "title": "Recent Events",
                    "position": {"x": 0, "y": 6, "width": 12, "height": 4},
                    "config": {
                        "query": "*",
                        "columns": [
                            "@timestamp",
                            "host.name",
                            "user.name",
                            "event.action",
                            "message",
                        ],
                        "page_size": 10,
                        "sort": {"field": "@timestamp", "order": "desc"},
                    },
                },
            ],
            "layout": {
                "columns": 12,
                "row_height": 60,
            },
        },
    },
    {
        "name": "Authentication Analysis",
        "description": "Focus on authentication events and anomalies",
        "definition": {
            "tiles": [
                {
                    "id": "auth-success",
                    "type": "metric",
                    "title": "Successful Logins",
                    "position": {"x": 0, "y": 0, "width": 4, "height": 2},
                    "config": {
                        "query": "event.category:authentication AND event.outcome:success",
                        "aggregation": "count",
                    },
                },
                {
                    "id": "auth-failure",
                    "type": "metric",
                    "title": "Failed Logins",
                    "position": {"x": 4, "y": 0, "width": 4, "height": 2},
                    "config": {
                        "query": "event.category:authentication AND event.outcome:failure",
                        "aggregation": "count",
                    },
                },
                {
                    "id": "unique-users",
                    "type": "metric",
                    "title": "Unique Users",
                    "position": {"x": 8, "y": 0, "width": 4, "height": 2},
                    "config": {
                        "query": "event.category:authentication",
                        "aggregation": "cardinality",
                        "field": "user.name",
                    },
                },
                {
                    "id": "auth-timeline",
                    "type": "chart",
                    "title": "Authentication Events",
                    "position": {"x": 0, "y": 2, "width": 12, "height": 4},
                    "config": {
                        "chart_type": "bar",
                        "query": "event.category:authentication",
                        "x_field": "@timestamp",
                        "interval": "1h",
                        "split_by": "event.outcome",
                    },
                },
                {
                    "id": "failed-users",
                    "type": "table",
                    "title": "Users with Failed Logins",
                    "position": {"x": 0, "y": 6, "width": 6, "height": 4},
                    "config": {
                        "query": "event.category:authentication AND event.outcome:failure",
                        "columns": ["user.name", "source.ip", "count"],
                        "group_by": ["user.name", "source.ip"],
                        "sort": {"field": "count", "order": "desc"},
                    },
                },
                {
                    "id": "login-sources",
                    "type": "chart",
                    "title": "Login Sources",
                    "position": {"x": 6, "y": 6, "width": 6, "height": 4},
                    "config": {
                        "chart_type": "pie",
                        "query": "event.category:authentication",
                        "group_by": "source.ip",
                        "limit": 10,
                    },
                },
            ],
            "layout": {
                "columns": 12,
                "row_height": 60,
            },
        },
    },
]


@router.get("", response_model=WorkbookListResponse)
async def list_workbooks(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    is_public: bool | None = Query(None),
) -> WorkbookListResponse:
    """List workbooks with pagination."""
    query = select(Workbook)

    if is_public is not None:
        query = query.where(Workbook.is_public == is_public)

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query) or 0

    # Get page
    query = query.order_by(Workbook.updated_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    workbooks = result.scalars().all()

    pages = (total + page_size - 1) // page_size

    return WorkbookListResponse(
        items=[
            WorkbookResponse(
                id=w.id,
                name=w.name,
                description=w.description,
                definition=w.definition,
                is_public=w.is_public,
                created_by=w.created_by,
                created_at=w.created_at,
                updated_at=w.updated_at,
            )
            for w in workbooks
        ],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.post("", response_model=WorkbookResponse)
async def create_workbook(
    request: WorkbookCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> WorkbookResponse:
    """Create a new workbook."""
    workbook = Workbook(
        name=request.name,
        description=request.description,
        definition=request.definition.model_dump(),
        is_public=request.is_public,
        created_by=current_user.id,
    )
    db.add(workbook)
    await db.commit()
    await db.refresh(workbook)

    logger.info(f"Created workbook '{request.name}'")

    return WorkbookResponse(
        id=workbook.id,
        name=workbook.name,
        description=workbook.description,
        definition=workbook.definition,
        is_public=workbook.is_public,
        created_by=workbook.created_by,
        created_at=workbook.created_at,
        updated_at=workbook.updated_at,
    )


@router.get("/templates")
async def list_templates(
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[dict]:
    """List built-in workbook templates."""
    return [
        {
            "name": t["name"],
            "description": t["description"],
            "tile_count": len(t["definition"]["tiles"]),
        }
        for t in WORKBOOK_TEMPLATES
    ]


@router.post("/templates/{template_name}", response_model=WorkbookResponse)
async def create_from_template(
    template_name: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    name: str = Query(..., description="Name for the new workbook"),
) -> WorkbookResponse:
    """Create a workbook from a template."""
    # Find template
    template = next(
        (t for t in WORKBOOK_TEMPLATES if t["name"].lower() == template_name.lower()),
        None,
    )
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template '{template_name}' not found",
        )

    workbook = Workbook(
        name=name,
        description=template["description"],
        definition=template["definition"],
        is_public=True,
        created_by=current_user.id,
    )
    db.add(workbook)
    await db.commit()
    await db.refresh(workbook)

    return WorkbookResponse(
        id=workbook.id,
        name=workbook.name,
        description=workbook.description,
        definition=workbook.definition,
        is_public=workbook.is_public,
        created_by=workbook.created_by,
        created_at=workbook.created_at,
        updated_at=workbook.updated_at,
    )


@router.get("/{workbook_id}", response_model=WorkbookResponse)
async def get_workbook(
    workbook_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> WorkbookResponse:
    """Get a workbook by ID."""
    workbook = await db.get(Workbook, workbook_id)
    if not workbook:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workbook {workbook_id} not found",
        )

    return WorkbookResponse(
        id=workbook.id,
        name=workbook.name,
        description=workbook.description,
        definition=workbook.definition,
        is_public=workbook.is_public,
        created_by=workbook.created_by,
        created_at=workbook.created_at,
        updated_at=workbook.updated_at,
    )


@router.patch("/{workbook_id}", response_model=WorkbookResponse)
async def update_workbook(
    workbook_id: UUID,
    request: WorkbookUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> WorkbookResponse:
    """Update a workbook."""
    workbook = await db.get(Workbook, workbook_id)
    if not workbook:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workbook {workbook_id} not found",
        )

    if request.name is not None:
        workbook.name = request.name
    if request.description is not None:
        workbook.description = request.description
    if request.definition is not None:
        workbook.definition = request.definition.model_dump()
    if request.is_public is not None:
        workbook.is_public = request.is_public

    await db.commit()
    await db.refresh(workbook)

    return WorkbookResponse(
        id=workbook.id,
        name=workbook.name,
        description=workbook.description,
        definition=workbook.definition,
        is_public=workbook.is_public,
        created_by=workbook.created_by,
        created_at=workbook.created_at,
        updated_at=workbook.updated_at,
    )


@router.delete("/{workbook_id}")
async def delete_workbook(
    workbook_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Delete a workbook."""
    workbook = await db.get(Workbook, workbook_id)
    if not workbook:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workbook {workbook_id} not found",
        )

    await db.delete(workbook)
    await db.commit()

    return {"status": "deleted", "id": str(workbook_id)}


@router.post("/{workbook_id}/clone", response_model=WorkbookResponse)
async def clone_workbook(
    workbook_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    name: str = Query(..., description="Name for the cloned workbook"),
) -> WorkbookResponse:
    """Clone an existing workbook."""
    original = await db.get(Workbook, workbook_id)
    if not original:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workbook {workbook_id} not found",
        )

    clone = Workbook(
        name=name,
        description=f"Clone of {original.name}",
        definition=original.definition,
        is_public=original.is_public,
        created_by=current_user.id,
    )
    db.add(clone)
    await db.commit()
    await db.refresh(clone)

    return WorkbookResponse(
        id=clone.id,
        name=clone.name,
        description=clone.description,
        definition=clone.definition,
        is_public=clone.is_public,
        created_by=clone.created_by,
        created_at=clone.created_at,
        updated_at=clone.updated_at,
    )


@router.post("/execute-tile", response_model=TileExecuteResponse)
async def execute_tile(
    request: TileExecuteRequest,
    current_user: Annotated[User, Depends(get_current_user)],
) -> TileExecuteResponse:
    """Execute a workbook tile query and return results."""
    from app.config import get_settings

    settings = get_settings()
    es = await get_elasticsearch()

    config = request.config
    tile_type = request.tile_type

    # Determine index
    index_pattern = f"{settings.elasticsearch_index_prefix}-events-*"
    if request.case_id:
        index_pattern = f"{settings.elasticsearch_index_prefix}-events-{request.case_id}"

    # Substitute variables
    query_str = config.get("query", "*")
    for var_name, var_value in request.variables.items():
        query_str = query_str.replace(f"${{{var_name}}}", str(var_value))

    try:
        if tile_type == "metric":
            return await _execute_metric_tile(es, index_pattern, query_str, config)
        elif tile_type == "chart":
            return await _execute_chart_tile(es, index_pattern, query_str, config)
        elif tile_type == "table":
            return await _execute_table_tile(es, index_pattern, query_str, config)
        elif tile_type == "markdown":
            return TileExecuteResponse(
                data=config.get("content", ""),
                metadata={"type": "markdown"},
            )
        elif tile_type == "timeline":
            return await _execute_timeline_tile(es, index_pattern, query_str, config)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown tile type: {tile_type}",
            )
    except Exception as e:
        logger.error(f"Tile execution failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Tile execution failed: {str(e)}",
        )


async def _execute_metric_tile(es, index: str, query: str, config: dict) -> TileExecuteResponse:
    """Execute a metric tile query."""
    aggregation = config.get("aggregation", "count")
    field = config.get("field")

    aggs = {}
    if aggregation == "count":
        # Just count documents
        result = await es.count(index=index, query={"query_string": {"query": query}})
        return TileExecuteResponse(
            data={"value": result["count"]},
            metadata={"aggregation": "count"},
        )
    elif aggregation == "cardinality" and field:
        aggs["metric"] = {"cardinality": {"field": field}}
    elif aggregation == "sum" and field:
        aggs["metric"] = {"sum": {"field": field}}
    elif aggregation == "avg" and field:
        aggs["metric"] = {"avg": {"field": field}}

    result = await es.search(
        index=index,
        query={"query_string": {"query": query}},
        aggs=aggs,
        size=0,
    )

    value = result["aggregations"]["metric"]["value"] if aggs else result["hits"]["total"]["value"]

    return TileExecuteResponse(
        data={"value": value},
        metadata={"aggregation": aggregation, "field": field},
    )


async def _execute_chart_tile(es, index: str, query: str, config: dict) -> TileExecuteResponse:
    """Execute a chart tile query."""
    chart_type = config.get("chart_type", "line")
    x_field = config.get("x_field", "@timestamp")
    interval = config.get("interval", "1h")
    group_by = config.get("group_by")
    split_by = config.get("split_by")
    limit = config.get("limit", 10)

    aggs: dict = {}

    if chart_type in ("line", "bar") and x_field == "@timestamp":
        # Time-based histogram
        aggs["buckets"] = {
            "date_histogram": {
                "field": "@timestamp",
                "fixed_interval": interval,
            }
        }
        if split_by:
            aggs["buckets"]["aggs"] = {"split": {"terms": {"field": split_by, "size": 10}}}
    elif group_by:
        # Terms aggregation
        aggs["buckets"] = {"terms": {"field": group_by, "size": limit}}

    result = await es.search(
        index=index,
        query={"query_string": {"query": query}},
        aggs=aggs,
        size=0,
    )

    # Format data for chart
    buckets = result.get("aggregations", {}).get("buckets", {}).get("buckets", [])
    data = []

    for bucket in buckets:
        item = {
            "key": bucket.get("key_as_string") or bucket.get("key"),
            "count": bucket.get("doc_count"),
        }
        if "split" in bucket:
            item["split"] = [
                {"key": s["key"], "count": s["doc_count"]} for s in bucket["split"]["buckets"]
            ]
        data.append(item)

    return TileExecuteResponse(
        data=data,
        metadata={"chart_type": chart_type, "x_field": x_field},
    )


async def _execute_table_tile(es, index: str, query: str, config: dict) -> TileExecuteResponse:
    """Execute a table tile query."""
    columns = config.get("columns", ["@timestamp", "message"])
    page_size = config.get("page_size", 10)
    sort_config = config.get("sort", {"field": "@timestamp", "order": "desc"})
    group_by = config.get("group_by")

    # Build source filter
    source_fields = columns.copy()
    if "_source" not in source_fields:
        pass  # Keep as is

    if group_by:
        # Aggregated table
        aggs: dict = {"table": {"composite": {"sources": []}}}
        for field in group_by:
            aggs["table"]["composite"]["sources"].append(
                {field.replace(".", "_"): {"terms": {"field": field}}}
            )
        aggs["table"]["composite"]["size"] = page_size

        result = await es.search(
            index=index,
            query={"query_string": {"query": query}},
            aggs=aggs,
            size=0,
        )

        buckets = result["aggregations"]["table"]["buckets"]
        data = [{**b["key"], "count": b["doc_count"]} for b in buckets]
    else:
        # Regular search
        sort = [{sort_config["field"]: sort_config["order"]}]

        result = await es.search(
            index=index,
            query={"query_string": {"query": query}},
            _source=source_fields,
            sort=sort,
            size=page_size,
        )

        data = [hit["_source"] for hit in result["hits"]["hits"]]

    return TileExecuteResponse(
        data=data,
        metadata={"columns": columns, "total": result["hits"]["total"]["value"]},
    )


async def _execute_timeline_tile(es, index: str, query: str, config: dict) -> TileExecuteResponse:
    """Execute a timeline tile query."""
    timestamp_field = config.get("timestamp_field", "@timestamp")
    interval = config.get("interval", "1h")

    aggs = {
        "timeline": {
            "date_histogram": {
                "field": timestamp_field,
                "fixed_interval": interval,
            }
        }
    }

    result = await es.search(
        index=index,
        query={"query_string": {"query": query}},
        aggs=aggs,
        size=0,
    )

    buckets = result["aggregations"]["timeline"]["buckets"]
    data = [{"timestamp": b["key_as_string"], "count": b["doc_count"]} for b in buckets]

    return TileExecuteResponse(
        data=data,
        metadata={"timestamp_field": timestamp_field, "interval": interval},
    )
