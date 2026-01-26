"""MITRE ATT&CK API endpoints.

Provides access to MITRE ATT&CK framework data, coverage analysis,
and Navigator layer import/export.
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.mitre_service import get_mitre_service

logger = logging.getLogger(__name__)

router = APIRouter()


# =============================================================================
# Schemas
# =============================================================================


class TacticResponse(BaseModel):
    """MITRE tactic response."""

    id: str
    name: str
    description: str
    external_id: str


class TechniqueBasic(BaseModel):
    """Basic technique info."""

    id: str
    name: str
    subtechniques: list[dict[str, str]] = Field(default_factory=list)


class MatrixColumn(BaseModel):
    """Matrix column (tactic with techniques)."""

    tactic: TacticResponse
    techniques: list[TechniqueBasic]


class MatrixResponse(BaseModel):
    """Full MITRE ATT&CK matrix response."""

    tactics: list[TacticResponse]
    matrix: list[MatrixColumn]
    technique_count: int
    subtechnique_count: int
    last_updated: str


class TechniqueDetail(BaseModel):
    """Detailed technique information."""

    id: str
    name: str
    description: str
    tactics: list[str]
    platforms: list[str]
    data_sources: list[str]
    detection: str
    is_subtechnique: bool
    parent_id: str | None
    subtechniques: list[str]
    url: str


class CoverageRule(BaseModel):
    """Rule providing coverage."""

    id: str
    name: str
    severity: str


class TechniqueCoverage(BaseModel):
    """Coverage for a single technique."""

    technique_id: str
    technique_name: str
    rule_count: int
    rules: list[CoverageRule]


class CoverageStatistics(BaseModel):
    """Coverage statistics."""

    total_techniques: int
    covered_techniques: int
    coverage_percent: float
    total_rules: int


class TacticCoverage(BaseModel):
    """Coverage for a single tactic."""

    tactic_id: str
    tactic_name: str
    total_techniques: int
    covered_techniques: int
    coverage_percent: float


class CoverageResponse(BaseModel):
    """Detection coverage response."""

    coverage_map: list[TechniqueCoverage]
    statistics: CoverageStatistics
    by_tactic: list[TacticCoverage]


class CoverageGap(BaseModel):
    """Coverage gap item."""

    technique_id: str
    technique_name: str
    tactics: list[str]
    platforms: list[str]
    data_sources: list[str]
    detection_guidance: str | None
    url: str


class HeatmapItem(BaseModel):
    """Heatmap data item."""

    technique_id: str
    technique_name: str
    count: int
    intensity: float
    tactics: list[str]


class HeatmapResponse(BaseModel):
    """Heatmap response."""

    heatmap: list[HeatmapItem]
    time_range: str
    total_alerts: int
    unique_techniques: int


class LayerExportRequest(BaseModel):
    """Layer export request."""

    layer_name: str = "Eleanor Detection Coverage"
    include_rules: bool = True


class LayerImportRequest(BaseModel):
    """Layer import request."""

    layer: dict[str, Any]


class ImportedTechnique(BaseModel):
    """Imported technique from layer."""

    technique_id: str
    technique_name: str
    score: int
    color: str | None
    comment: str | None
    enabled: bool


class LayerImportResponse(BaseModel):
    """Layer import response."""

    layer_name: str
    description: str
    technique_count: int
    techniques: list[ImportedTechnique]


class TechniqueSearch(BaseModel):
    """Technique search result."""

    id: str
    name: str
    tactics: list[str]
    is_subtechnique: bool


# =============================================================================
# Endpoints
# =============================================================================


@router.get("/matrix", response_model=MatrixResponse)
async def get_matrix() -> dict[str, Any]:
    """Get the full MITRE ATT&CK matrix.

    Returns tactics and techniques organized in matrix format.
    """
    service = await get_mitre_service()
    return await service.get_matrix()


@router.get("/techniques/{technique_id}", response_model=TechniqueDetail)
async def get_technique(technique_id: str) -> dict[str, Any]:
    """Get details for a specific technique.

    Args:
        technique_id: MITRE technique ID (e.g., T1059, T1059.001)
    """
    service = await get_mitre_service()
    technique = await service.get_technique(technique_id)
    if not technique:
        raise HTTPException(status_code=404, detail=f"Technique {technique_id} not found")
    return technique


@router.get("/techniques/search", response_model=list[TechniqueSearch])
async def search_techniques(
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(20, ge=1, le=100),
) -> list[dict[str, Any]]:
    """Search techniques by name or ID.

    Args:
        q: Search query (matches technique ID or name)
        limit: Maximum results to return
    """
    service = await get_mitre_service()
    return await service.search_techniques(q, limit)


@router.get("/coverage", response_model=CoverageResponse)
async def get_coverage(
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get detection coverage analysis.

    Returns which MITRE techniques are covered by detection rules.
    """
    service = await get_mitre_service()
    return await service.get_coverage(db)


@router.get("/coverage/gaps", response_model=list[CoverageGap])
async def get_coverage_gaps(
    priority: str = Query("high", regex="^(high|medium|low|all)$"),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    """Get detection coverage gaps.

    Returns techniques without detection coverage, prioritized by importance.

    Args:
        priority: Filter by gap priority
    """
    service = await get_mitre_service()
    return await service.get_coverage_gaps(db, priority)


@router.get("/heatmap", response_model=HeatmapResponse)
async def get_heatmap(
    time_range: str = Query("7d", regex="^(24h|7d|30d)$"),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get technique heatmap based on alerts/incidents.

    Returns technique activity levels over the specified time range.

    Args:
        time_range: Time range for analysis
    """
    service = await get_mitre_service()
    return await service.get_heatmap(db, time_range)


@router.get("/layers/export")
async def export_layer(
    layer_name: str = Query("Eleanor Detection Coverage"),
    include_rules: bool = Query(True),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Export detection coverage as ATT&CK Navigator layer.

    Returns a JSON file compatible with MITRE ATT&CK Navigator.

    Args:
        layer_name: Name for the exported layer
        include_rules: Include rule names in comments
    """
    service = await get_mitre_service()
    return await service.export_layer(db, layer_name, include_rules)


@router.post("/layers/import", response_model=LayerImportResponse)
async def import_layer(
    request: LayerImportRequest,
) -> dict[str, Any]:
    """Import ATT&CK Navigator layer.

    Parses a Navigator layer and returns technique mappings.

    Args:
        request: Layer data to import
    """
    service = await get_mitre_service()
    return await service.import_layer(request.layer)


@router.get("/tactics", response_model=list[TacticResponse])
async def get_tactics() -> list[dict[str, Any]]:
    """Get all MITRE ATT&CK tactics."""
    service = await get_mitre_service()
    matrix = await service.get_matrix()
    return matrix["tactics"]
