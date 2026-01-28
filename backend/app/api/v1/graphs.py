"""Investigation graph API endpoints.

Provides endpoints for building, exploring, and saving investigation graphs
that visualize entity relationships within a case.
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
from app.models.graph import SavedGraph
from app.models.user import User
from app.services.graph_builder import GraphBuilder

logger = logging.getLogger(__name__)
router = APIRouter()


# Pydantic schemas
class GraphNode(BaseModel):
    """Graph node representation."""

    id: str = Field(..., description="Unique node ID (type:value)")
    label: str = Field(..., description="Display label")
    type: str = Field(..., description="Entity type: host, user, ip, process, file, domain")
    event_count: int | None = Field(None, description="Number of related events")
    first_seen: str | None = Field(None, description="First occurrence timestamp")
    last_seen: str | None = Field(None, description="Last occurrence timestamp")
    risk_score: int | None = Field(None, description="Risk score from threat intel (0-100)")


class GraphEdge(BaseModel):
    """Graph edge representation."""

    source: str = Field(..., description="Source node ID")
    target: str = Field(..., description="Target node ID")
    relationship: str = Field(..., description="Relationship type: executed, connected_to, logged_into, etc.")
    weight: int | None = Field(None, description="Edge weight (event count)")
    timestamp: str | None = Field(None, description="Most recent relationship timestamp")


class GraphData(BaseModel):
    """Full graph data structure."""

    nodes: list[GraphNode]
    edges: list[GraphEdge]
    metadata: dict | None = None


class BuildGraphRequest(BaseModel):
    """Request to build a graph from case events."""

    case_id: UUID = Field(..., description="Case UUID")
    max_nodes: int = Field(100, ge=10, le=500, description="Maximum nodes")
    entity_types: list[str] | None = Field(
        None,
        description="Filter to specific entity types: host, user, ip, process, file, domain",
    )
    time_start: datetime | None = Field(None, description="Start of time range")
    time_end: datetime | None = Field(None, description="End of time range")


class ExpandNodeRequest(BaseModel):
    """Request to expand a node's connections."""

    case_id: UUID = Field(..., description="Case UUID")
    node_id: str = Field(..., description="Node ID to expand (type:value)")
    max_connections: int = Field(20, ge=5, le=100, description="Max connections")


class FindPathRequest(BaseModel):
    """Request to find path between two nodes."""

    case_id: UUID = Field(..., description="Case UUID")
    source_node: str = Field(..., description="Source node ID")
    target_node: str = Field(..., description="Target node ID")
    max_hops: int = Field(5, ge=1, le=10, description="Maximum path length")


class SaveGraphRequest(BaseModel):
    """Request to save a graph configuration."""

    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    case_id: UUID
    definition: dict = Field(..., description="Graph definition (nodes, edges, positions)")
    config: dict | None = Field(None, description="Graph configuration (layout, filters)")


class SavedGraphResponse(BaseModel):
    """Saved graph response."""

    id: UUID
    name: str
    description: str | None
    case_id: UUID
    definition: dict
    config: dict
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SavedGraphListResponse(BaseModel):
    """List of saved graphs."""

    items: list[SavedGraphResponse]
    total: int


@router.post("/build", response_model=GraphData)
async def build_graph(
    request: BuildGraphRequest,
    current_user: Annotated[User, Depends(get_current_user)],
) -> GraphData:
    """Build an investigation graph from case events.

    Analyzes events in the case and extracts entity relationships
    to create a visual graph.
    """
    es = await get_elasticsearch()
    builder = GraphBuilder(es)

    time_range = None
    if request.time_start and request.time_end:
        time_range = (request.time_start, request.time_end)

    result = await builder.build_case_graph(
        case_id=str(request.case_id),
        max_nodes=request.max_nodes,
        entity_types=request.entity_types,
        time_range=time_range,
    )

    return GraphData(
        nodes=[GraphNode(**n) for n in result["nodes"]],
        edges=[GraphEdge(**e) for e in result["edges"]],
        metadata=result.get("metadata"),
    )


@router.post("/expand", response_model=GraphData)
async def expand_node(
    request: ExpandNodeRequest,
    current_user: Annotated[User, Depends(get_current_user)],
) -> GraphData:
    """Expand a node to show its connections.

    Returns additional nodes and edges to add to the existing graph.
    """
    es = await get_elasticsearch()
    builder = GraphBuilder(es)

    result = await builder.expand_node(
        case_id=str(request.case_id),
        node_id=request.node_id,
        max_connections=request.max_connections,
    )

    return GraphData(
        nodes=[GraphNode(**n) for n in result["nodes"]],
        edges=[GraphEdge(**e) for e in result["edges"]],
    )


@router.get("/entity-relationships")
async def get_entity_relationships(
    case_id: UUID,
    entity_type: str = Query(..., description="Entity type"),
    entity_value: str = Query(..., description="Entity value"),
    current_user: Annotated[User, Depends(get_current_user)] = None,
) -> dict:
    """Get all relationships for a specific entity."""
    es = await get_elasticsearch()
    builder = GraphBuilder(es)

    return await builder.get_entity_relationships(
        case_id=str(case_id),
        entity_type=entity_type,
        entity_value=entity_value,
    )


@router.post("/path")
async def find_path(
    request: FindPathRequest,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Find shortest path between two entities.

    Uses breadth-first search through entity relationships.
    """
    es = await get_elasticsearch()
    builder = GraphBuilder(es)

    result = await builder.find_path(
        case_id=str(request.case_id),
        source_node=request.source_node,
        target_node=request.target_node,
        max_hops=request.max_hops,
    )

    return result


@router.post("/saved", response_model=SavedGraphResponse)
async def save_graph(
    request: SaveGraphRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> SavedGraphResponse:
    """Save a graph configuration for later use."""
    graph = SavedGraph(
        name=request.name,
        description=request.description,
        case_id=request.case_id,
        definition=request.definition,
        config=request.config or {},
        created_by=current_user.id,
    )
    db.add(graph)
    await db.commit()
    await db.refresh(graph)

    logger.info(f"Saved graph '{request.name}' for case {request.case_id}")

    return SavedGraphResponse(
        id=graph.id,
        name=graph.name,
        description=graph.description,
        case_id=graph.case_id,
        definition=graph.definition,
        config=graph.config,
        created_by=graph.created_by,
        created_at=graph.created_at,
        updated_at=graph.updated_at,
    )


@router.get("/saved", response_model=SavedGraphListResponse)
async def list_saved_graphs(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    case_id: UUID | None = Query(None, description="Filter by case"),
) -> SavedGraphListResponse:
    """List saved graphs, optionally filtered by case."""
    query = select(SavedGraph)

    if case_id:
        query = query.where(SavedGraph.case_id == case_id)

    query = query.order_by(SavedGraph.updated_at.desc())

    result = await db.execute(query)
    graphs = result.scalars().all()

    return SavedGraphListResponse(
        items=[
            SavedGraphResponse(
                id=graph.id,
                name=graph.name,
                description=graph.description,
                case_id=graph.case_id,
                definition=graph.definition,
                config=graph.config,
                created_by=graph.created_by,
                created_at=graph.created_at,
                updated_at=graph.updated_at,
            )
            for graph in graphs
        ],
        total=len(graphs),
    )


@router.get("/saved/{graph_id}", response_model=SavedGraphResponse)
async def get_saved_graph(
    graph_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> SavedGraphResponse:
    """Get a saved graph by ID."""
    graph = await db.get(SavedGraph, graph_id)
    if not graph:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Graph {graph_id} not found",
        )

    return SavedGraphResponse(
        id=graph.id,
        name=graph.name,
        description=graph.description,
        case_id=graph.case_id,
        definition=graph.definition,
        config=graph.config,
        created_by=graph.created_by,
        created_at=graph.created_at,
        updated_at=graph.updated_at,
    )


@router.delete("/saved/{graph_id}")
async def delete_saved_graph(
    graph_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Delete a saved graph."""
    graph = await db.get(SavedGraph, graph_id)
    if not graph:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Graph {graph_id} not found",
        )

    await db.delete(graph)
    await db.commit()

    return {"status": "deleted", "id": str(graph_id)}
