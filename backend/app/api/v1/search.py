"""Search API endpoints for hunting and queries."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import get_current_user
from app.config import get_settings
from app.database import get_db, get_elasticsearch
from app.models.user import User
from app.models.workbook import SavedQuery

router = APIRouter()
settings = get_settings()


class SearchRequest(BaseModel):
    """Search query request."""

    query: str
    indices: list[str] | None = None
    from_: int = 0
    size: int = 100
    sort: list[dict] | None = None
    aggs: dict | None = None


class SearchResponse(BaseModel):
    """Search query response."""

    took: int
    total: int
    hits: list[dict]
    aggregations: dict | None = None


class ESQLRequest(BaseModel):
    """ES|QL query request."""

    query: str


class SavedQueryCreate(BaseModel):
    """Saved query creation request."""

    name: str
    description: str | None = None
    query: str
    indices: list[str] = []
    category: str | None = None
    mitre_techniques: list[str] = []
    is_public: bool = False


class SavedQueryResponse(BaseModel):
    """Saved query response."""

    id: UUID
    name: str
    description: str | None
    query: str
    indices: list[str]
    category: str | None
    mitre_techniques: list[str]
    is_public: bool
    created_by: UUID | None

    class Config:
        from_attributes = True


@router.post("/query", response_model=SearchResponse)
async def search_events(
    request: SearchRequest,
    current_user: Annotated[User, Depends(get_current_user)],
) -> SearchResponse:
    """Execute search query against events."""
    es = await get_elasticsearch()

    # Default to all event indices if not specified
    indices = request.indices or [f"{settings.elasticsearch_index_prefix}-events-*"]

    body = {
        "query": {"query_string": {"query": request.query}},
        "from": request.from_,
        "size": request.size,
    }

    if request.sort:
        body["sort"] = request.sort
    else:
        body["sort"] = [{"@timestamp": {"order": "desc"}}]

    if request.aggs:
        body["aggs"] = request.aggs

    try:
        response = await es.search(
            index=",".join(indices),
            body=body,
        )

        hits = [
            {"id": hit["_id"], "index": hit["_index"], **hit["_source"]}
            for hit in response["hits"]["hits"]
        ]

        return SearchResponse(
            took=response["took"],
            total=response["hits"]["total"]["value"],
            hits=hits,
            aggregations=response.get("aggregations"),
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Search error: {e}",
        )


@router.post("/esql")
async def execute_esql(
    request: ESQLRequest,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Execute ES|QL query."""
    es = await get_elasticsearch()

    try:
        response = await es.esql.query(body={"query": request.query})
        return response
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"ES|QL error: {e}",
        )


@router.get("/indices")
async def list_indices(
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[dict]:
    """List available Elasticsearch indices."""
    es = await get_elasticsearch()

    try:
        response = await es.cat.indices(
            index=f"{settings.elasticsearch_index_prefix}-*",
            format="json",
        )
        return [
            {
                "index": idx["index"],
                "docs_count": idx.get("docs.count", "0"),
                "store_size": idx.get("store.size", "0"),
                "health": idx.get("health"),
            }
            for idx in response
        ]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list indices: {e}",
        )


@router.get("/schema/{index}")
async def get_index_schema(
    index: str,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Get field mappings for an index."""
    es = await get_elasticsearch()

    try:
        response = await es.indices.get_mapping(index=index)
        # Return the mappings for the first matching index
        for idx_name, idx_data in response.items():
            return {
                "index": idx_name,
                "mappings": idx_data.get("mappings", {}),
            }
        return {"index": index, "mappings": {}}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Index not found: {e}",
        )


@router.get("/saved", response_model=list[SavedQueryResponse])
async def list_saved_queries(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    category: str | None = Query(None),
) -> list[SavedQueryResponse]:
    """List saved queries."""
    query = select(SavedQuery).where(
        (SavedQuery.is_public == True) | (SavedQuery.created_by == current_user.id)  # noqa: E712
    )

    if category:
        query = query.where(SavedQuery.category == category)

    query = query.order_by(SavedQuery.name)

    result = await db.execute(query)
    queries = result.scalars().all()

    return [
        SavedQueryResponse(
            id=q.id,
            name=q.name,
            description=q.description,
            query=q.query,
            indices=q.indices,
            category=q.category,
            mitre_techniques=q.mitre_techniques,
            is_public=q.is_public,
            created_by=q.created_by,
        )
        for q in queries
    ]


@router.post("/saved", response_model=SavedQueryResponse, status_code=status.HTTP_201_CREATED)
async def create_saved_query(
    query_data: SavedQueryCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> SavedQueryResponse:
    """Save a query."""
    saved_query = SavedQuery(
        name=query_data.name,
        description=query_data.description,
        query=query_data.query,
        indices=query_data.indices,
        category=query_data.category,
        mitre_techniques=query_data.mitre_techniques,
        is_public=query_data.is_public,
        created_by=current_user.id,
    )

    db.add(saved_query)
    await db.commit()
    await db.refresh(saved_query)

    return SavedQueryResponse(
        id=saved_query.id,
        name=saved_query.name,
        description=saved_query.description,
        query=saved_query.query,
        indices=saved_query.indices,
        category=saved_query.category,
        mitre_techniques=saved_query.mitre_techniques,
        is_public=saved_query.is_public,
        created_by=saved_query.created_by,
    )


@router.delete("/saved/{query_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_saved_query(
    query_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    """Delete a saved query."""
    query = select(SavedQuery).where(SavedQuery.id == query_id)
    result = await db.execute(query)
    saved_query = result.scalar_one_or_none()

    if not saved_query:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Saved query not found",
        )

    if saved_query.created_by != current_user.id and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this query",
        )

    await db.delete(saved_query)
    await db.commit()
