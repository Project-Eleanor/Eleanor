"""Search API endpoints for hunting and queries."""

import re
from collections.abc import Callable
from typing import Annotated, Any
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


# =============================================================================
# PATTERN: Compiled Regex Dispatch Table
# Pre-compiled regex patterns with associated handler functions for efficient
# KQL expression parsing. This replaces the sequential if-else regex matching
# with a single-pass dispatch table lookup.
# =============================================================================

# Field pattern common to all operators (word characters with optional dots)
_FIELD_PATTERN = r"(\w+(?:\.\w+)*)"

# Handler type: takes regex match and returns ES query dict
ComparisonHandler = Callable[[re.Match[str]], dict[str, Any]]


def _make_match_handler() -> tuple[re.Pattern[str], ComparisonHandler]:
    """Handler for 'contains' operator -> ES match query."""
    pattern = re.compile(rf"{_FIELD_PATTERN}\s+contains\s+[\"'](.+?)[\"']", re.IGNORECASE)

    def handler(match: re.Match[str]) -> dict[str, Any]:
        field, value = match.groups()
        return {"match": {field: value}}

    return pattern, handler


def _make_prefix_handler() -> tuple[re.Pattern[str], ComparisonHandler]:
    """Handler for 'startswith' operator -> ES prefix query."""
    pattern = re.compile(rf"{_FIELD_PATTERN}\s+startswith\s+[\"'](.+?)[\"']", re.IGNORECASE)

    def handler(match: re.Match[str]) -> dict[str, Any]:
        field, value = match.groups()
        return {"prefix": {field: value}}

    return pattern, handler


def _make_endswith_handler() -> tuple[re.Pattern[str], ComparisonHandler]:
    """Handler for 'endswith' operator -> ES wildcard query."""
    pattern = re.compile(rf"{_FIELD_PATTERN}\s+endswith\s+[\"'](.+?)[\"']", re.IGNORECASE)

    def handler(match: re.Match[str]) -> dict[str, Any]:
        field, value = match.groups()
        return {"wildcard": {field: f"*{value}"}}

    return pattern, handler


def _make_in_handler() -> tuple[re.Pattern[str], ComparisonHandler]:
    """Handler for 'in' operator -> ES terms query."""
    pattern = re.compile(rf"{_FIELD_PATTERN}\s+in\s*\(([^)]+)\)", re.IGNORECASE)

    def handler(match: re.Match[str]) -> dict[str, Any]:
        field = match.group(1)
        values_str = match.group(2)
        values = [v.strip().strip("\"'") for v in values_str.split(",")]
        return {"terms": {field: values}}

    return pattern, handler


def _make_has_handler() -> tuple[re.Pattern[str], ComparisonHandler]:
    """Handler for 'has' operator -> ES match with AND operator."""
    pattern = re.compile(rf"{_FIELD_PATTERN}\s+has\s+[\"'](.+?)[\"']", re.IGNORECASE)

    def handler(match: re.Match[str]) -> dict[str, Any]:
        field, value = match.groups()
        return {"match": {field: {"query": value, "operator": "and"}}}

    return pattern, handler


def _make_neq_handler() -> tuple[re.Pattern[str], ComparisonHandler]:
    """Handler for '!=' operator -> ES must_not term query."""
    pattern = re.compile(rf"{_FIELD_PATTERN}\s*!=\s*[\"'](.+?)[\"']")

    def handler(match: re.Match[str]) -> dict[str, Any]:
        field, value = match.groups()
        return {"bool": {"must_not": [{"term": {field: value}}]}}

    return pattern, handler


def _make_eq_handler() -> tuple[re.Pattern[str], ComparisonHandler]:
    """Handler for '==' operator -> ES term query."""
    pattern = re.compile(rf"{_FIELD_PATTERN}\s*==\s*[\"'](.+?)[\"']")

    def handler(match: re.Match[str]) -> dict[str, Any]:
        field, value = match.groups()
        return {"term": {field: value}}

    return pattern, handler


def _make_gte_handler() -> tuple[re.Pattern[str], ComparisonHandler]:
    """Handler for '>=' operator -> ES range gte query."""
    pattern = re.compile(rf"{_FIELD_PATTERN}\s*>=\s*(\d+)")

    def handler(match: re.Match[str]) -> dict[str, Any]:
        field, value = match.groups()
        return {"range": {field: {"gte": int(value)}}}

    return pattern, handler


def _make_lte_handler() -> tuple[re.Pattern[str], ComparisonHandler]:
    """Handler for '<=' operator -> ES range lte query."""
    pattern = re.compile(rf"{_FIELD_PATTERN}\s*<=\s*(\d+)")

    def handler(match: re.Match[str]) -> dict[str, Any]:
        field, value = match.groups()
        return {"range": {field: {"lte": int(value)}}}

    return pattern, handler


def _make_gt_handler() -> tuple[re.Pattern[str], ComparisonHandler]:
    """Handler for '>' operator -> ES range gt query."""
    pattern = re.compile(rf"{_FIELD_PATTERN}\s*>\s*(\d+)")

    def handler(match: re.Match[str]) -> dict[str, Any]:
        field, value = match.groups()
        return {"range": {field: {"gt": int(value)}}}

    return pattern, handler


def _make_lt_handler() -> tuple[re.Pattern[str], ComparisonHandler]:
    """Handler for '<' operator -> ES range lt query."""
    pattern = re.compile(rf"{_FIELD_PATTERN}\s*<\s*(\d+)")

    def handler(match: re.Match[str]) -> dict[str, Any]:
        field, value = match.groups()
        return {"range": {field: {"lt": int(value)}}}

    return pattern, handler


def _make_simple_eq_num_handler() -> tuple[re.Pattern[str], ComparisonHandler]:
    """Handler for '=' with numeric value -> ES term query with int."""
    pattern = re.compile(rf"{_FIELD_PATTERN}\s*=\s*(\d+)")

    def handler(match: re.Match[str]) -> dict[str, Any]:
        field, value = match.groups()
        return {"term": {field: int(value)}}

    return pattern, handler


def _make_simple_eq_str_handler() -> tuple[re.Pattern[str], ComparisonHandler]:
    """Handler for '=' with quoted string -> ES term query."""
    pattern = re.compile(rf"{_FIELD_PATTERN}\s*=\s*[\"'](.+?)[\"']")

    def handler(match: re.Match[str]) -> dict[str, Any]:
        field, value = match.groups()
        return {"term": {field: value}}

    return pattern, handler


# Build the dispatch table at module load time
# Order matters: more specific patterns should come first
_COMPARISON_DISPATCH_TABLE: list[tuple[re.Pattern[str], ComparisonHandler]] = [
    _make_match_handler(),  # contains
    _make_prefix_handler(),  # startswith
    _make_endswith_handler(),  # endswith
    _make_in_handler(),  # in
    _make_has_handler(),  # has
    _make_neq_handler(),  # !=
    _make_eq_handler(),  # ==
    _make_gte_handler(),  # >=
    _make_lte_handler(),  # <=
    _make_gt_handler(),  # >
    _make_lt_handler(),  # <
    _make_simple_eq_num_handler(),  # = (numeric)
    _make_simple_eq_str_handler(),  # = (string)
]


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


class KQLRequest(BaseModel):
    """KQL (Kusto Query Language) request."""

    query: str
    indices: list[str] | None = None
    from_: int = 0
    size: int = 100


def kql_to_elasticsearch(kql: str) -> dict[str, Any]:
    """Convert KQL syntax to Elasticsearch query DSL.

    Supports:
    - field == "value" → term query
    - field contains "value" → match query
    - field startswith "value" → prefix query
    - field != "value" → must_not term
    - field > value, field < value → range query
    - field >= value, field <= value → range query
    - expr1 and expr2 → bool must
    - expr1 or expr2 → bool should
    - not expr → bool must_not
    - field in ("val1", "val2") → terms query
    - * (wildcard) → match_all
    """
    kql = kql.strip()

    if not kql or kql == "*":
        return {"match_all": {}}

    # Remove table name prefix if present (e.g., "SecurityEvent | where ...")
    if "|" in kql:
        parts = kql.split("|")
        # Take everything after the first pipe for filtering
        kql = "|".join(parts[1:]).strip()
        if kql.lower().startswith("where "):
            kql = kql[6:].strip()

    return _parse_kql_expression(kql)


def _parse_kql_expression(expr: str) -> dict[str, Any]:
    """Parse a KQL expression into ES query DSL.

    PATTERN: Recursive Descent Parser
    This parser uses recursive descent with operator precedence handling.

    ## Operator Precedence (lowest to highest)
    1. OR  - Boolean disjunction, parsed first (lowest precedence)
    2. AND - Boolean conjunction
    3. NOT - Boolean negation (prefix operator)
    4. Comparison operators (==, !=, <, >, <=, >=, contains, etc.)

    ## Parenthesis Handling
    The depth counter tracks nested parentheses to ensure operators
    inside parentheses are not split at the current recursion level.
    When depth > 0, we're inside a nested expression.

    ## Quote Handling
    Strings in single or double quotes are preserved as literals.
    The in_quote flag prevents splitting on operators within strings.

    Args:
        expr: KQL expression string to parse

    Returns:
        Elasticsearch query DSL dictionary
    """
    expr = expr.strip()

    if not expr:
        return {"match_all": {}}

    # Handle parentheses - unwrap if entire expression is wrapped
    # Uses depth tracking to verify the outer parens match
    if expr.startswith("(") and expr.endswith(")"):
        # Check if entire expression is wrapped in parens
        depth = 0
        all_wrapped = True
        for i, c in enumerate(expr):
            if c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
            # If depth hits 0 before the end, parens don't wrap the whole expr
            if depth == 0 and i < len(expr) - 1:
                all_wrapped = False
                break
        if all_wrapped:
            expr = expr[1:-1].strip()

    # Handle OR (lowest precedence)
    or_parts = _split_by_operator(expr, " or ")
    if len(or_parts) > 1:
        clauses = [_parse_kql_expression(p) for p in or_parts]
        return {"bool": {"should": clauses, "minimum_should_match": 1}}

    # Handle AND
    and_parts = _split_by_operator(expr, " and ")
    if len(and_parts) > 1:
        clauses = [_parse_kql_expression(p) for p in and_parts]
        return {"bool": {"must": clauses}}

    # Handle NOT
    if expr.lower().startswith("not "):
        inner = expr[4:].strip()
        return {"bool": {"must_not": [_parse_kql_expression(inner)]}}

    # Handle comparison operators
    return _parse_comparison(expr)


def _split_by_operator(expr: str, op: str) -> list[str]:
    """Split expression by operator, respecting parentheses and quotes.

    State Machine for parsing:
    - depth: Tracks parenthesis nesting level (0 = top level)
    - in_quote: Whether currently inside a quoted string
    - quote_char: The quote character that opened the current string (' or ")

    The parser only splits on the operator when:
    1. Not inside a quoted string (in_quote == False)
    2. At the top level of nesting (depth == 0)
    3. The remaining text starts with the operator (case-insensitive)

    Escape sequences: Backslash-escaped quotes (\\" or \\') do not toggle
    the in_quote state.

    Args:
        expr: Expression string to split
        op: Operator string to split on (e.g., " and ", " or ")

    Returns:
        List of expression parts, with the operator removed
    """
    parts = []
    depth = 0  # Parenthesis depth counter
    in_quote = False  # Currently inside a quoted string
    quote_char = None  # The quote character that opened current string
    current = []  # Characters of current part being accumulated
    i = 0
    op_lower = op.lower()

    while i < len(expr):
        c = expr[i]

        # Handle quote state transitions (skip escaped quotes)
        if c in ('"', "'") and (i == 0 or expr[i - 1] != "\\"):
            if not in_quote:
                in_quote = True
                quote_char = c
            elif c == quote_char:
                in_quote = False
                quote_char = None

        # Only track depth and check for operators outside of quotes
        if not in_quote:
            if c == "(":
                depth += 1
            elif c == ")":
                depth -= 1

            # At top level, check if we hit the operator
            if depth == 0:
                remaining = expr[i:].lower()
                if remaining.startswith(op_lower):
                    parts.append("".join(current).strip())
                    current = []
                    i += len(op)
                    continue

        current.append(c)
        i += 1

    if current:
        parts.append("".join(current).strip())

    return parts


def _parse_comparison(expr: str) -> dict[str, Any]:
    """Parse a single comparison expression using compiled regex dispatch table.

    PATTERN: Dispatch Table Pattern
    Uses pre-compiled regex patterns with associated handlers for O(n) matching
    where n is the number of operators. This is more efficient than the previous
    sequential if-else chain and easier to extend with new operators.

    The dispatch table is defined at module load time, so regex compilation
    happens once, not on every call.

    Args:
        expr: Comparison expression to parse (e.g., "field == 'value'")

    Returns:
        Elasticsearch query DSL dictionary
    """
    expr = expr.strip()

    # Try each pattern in the dispatch table
    for pattern, handler in _COMPARISON_DISPATCH_TABLE:
        match = pattern.match(expr)
        if match:
            return handler(match)

    # Fallback: treat as query string for free-text search
    return {"query_string": {"query": expr}}


@router.post("/kql", response_model=SearchResponse)
async def execute_kql(
    request: KQLRequest,
    current_user: Annotated[User, Depends(get_current_user)],
) -> SearchResponse:
    """Execute KQL (Kusto Query Language) query.

    Translates KQL syntax to Elasticsearch query DSL.
    Supports: where, ==, !=, contains, startswith, and, or, not, in, range operators
    """
    es = await get_elasticsearch()
    indices = request.indices or [f"{settings.elasticsearch_index_prefix}-events-*"]

    try:
        es_query = kql_to_elasticsearch(request.query)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"KQL parse error: {e}",
        )

    body = {
        "query": es_query,
        "from": request.from_,
        "size": request.size,
        "sort": [{"@timestamp": {"order": "desc"}}],
    }

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
