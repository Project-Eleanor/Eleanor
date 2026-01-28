"""Entity enrichment endpoints.

Provides threat intelligence enrichment for indicators like IPs, domains,
hashes, and other observables using connected threat intel platforms.
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.adapters import IndicatorType, get_registry
from app.api.v1.auth import get_current_user
from app.models.user import User

router = APIRouter()


# =============================================================================
# Request/Response Models
# =============================================================================


class EnrichmentRequest(BaseModel):
    """Request to enrich a single indicator."""

    value: str = Field(..., description="The indicator value to enrich")
    indicator_type: str = Field(
        ...,
        description="Type of indicator: ipv4, ipv6, domain, url, email, md5, sha1, sha256, filename",
    )


class BulkEnrichmentRequest(BaseModel):
    """Request to enrich multiple indicators."""

    indicators: list[EnrichmentRequest] = Field(
        ...,
        max_length=100,
        description="List of indicators to enrich (max 100)",
    )


class ThreatActorInfo(BaseModel):
    """Threat actor summary."""

    external_id: str
    name: str
    aliases: list[str] = []
    description: str | None = None
    motivation: str | None = None
    sophistication: str | None = None
    country: str | None = None


class CampaignInfo(BaseModel):
    """Campaign summary."""

    external_id: str
    name: str
    description: str | None = None
    first_seen: str | None = None
    last_seen: str | None = None


class EnrichmentResult(BaseModel):
    """Result of indicator enrichment."""

    value: str
    indicator_type: str
    risk_score: int = Field(..., ge=0, le=100)
    verdict: str  # malicious, suspicious, clean, unknown
    first_seen: str | None = None
    last_seen: str | None = None
    sources: list[str] = []
    tags: list[str] = []
    description: str | None = None
    threat_actors: list[ThreatActorInfo] = []
    campaigns: list[CampaignInfo] = []
    related_indicators: list[dict[str, Any]] = []
    raw_data: dict[str, Any] = {}


class EnrichmentResponse(BaseModel):
    """Response for enrichment request."""

    success: bool
    result: EnrichmentResult | None = None
    error: str | None = None
    source: str = "opencti"


class BulkEnrichmentResponse(BaseModel):
    """Response for bulk enrichment request."""

    success: bool
    results: list[EnrichmentResponse]
    summary: dict[str, int]  # Count by verdict


# =============================================================================
# Helper Functions
# =============================================================================


def parse_indicator_type(type_str: str) -> IndicatorType:
    """Parse indicator type string to enum."""
    type_map = {
        "ipv4": IndicatorType.IPV4,
        "ip": IndicatorType.IPV4,
        "ipv6": IndicatorType.IPV6,
        "domain": IndicatorType.DOMAIN,
        "url": IndicatorType.URL,
        "email": IndicatorType.EMAIL,
        "md5": IndicatorType.FILE_HASH_MD5,
        "sha1": IndicatorType.FILE_HASH_SHA1,
        "sha256": IndicatorType.FILE_HASH_SHA256,
        "hash": IndicatorType.FILE_HASH_SHA256,
        "filename": IndicatorType.FILE_NAME,
        "file": IndicatorType.FILE_NAME,
        "registry": IndicatorType.REGISTRY_KEY,
        "useragent": IndicatorType.USER_AGENT,
        "cve": IndicatorType.CVE,
    }

    normalized = type_str.lower().replace("-", "").replace("_", "")
    if normalized not in type_map:
        raise ValueError(f"Unknown indicator type: {type_str}")

    return type_map[normalized]


# =============================================================================
# Endpoints
# =============================================================================


@router.post("/indicator", response_model=EnrichmentResponse)
async def enrich_indicator(
    request: EnrichmentRequest,
    current_user: User = Depends(get_current_user),
) -> EnrichmentResponse:
    """Enrich a single indicator with threat intelligence.

    Returns risk score, verdict, related threat actors, campaigns,
    and other context from connected threat intel platforms.
    """
    registry = get_registry()
    ti_adapter = registry.get_threat_intel()

    if not ti_adapter:
        return EnrichmentResponse(
            success=False,
            error="No threat intelligence adapter configured",
        )

    try:
        indicator_type = parse_indicator_type(request.indicator_type)
    except ValueError as e:
        return EnrichmentResponse(
            success=False,
            error=str(e),
        )

    try:
        result = await ti_adapter.enrich_indicator(request.value, indicator_type)

        # Convert to response format
        threat_actors = [
            ThreatActorInfo(
                external_id=threat_actor.external_id,
                name=threat_actor.name,
                aliases=threat_actor.aliases,
                description=threat_actor.description,
                motivation=threat_actor.motivation,
                sophistication=threat_actor.sophistication,
                country=threat_actor.country,
            )
            for threat_actor in result.threat_actors
        ]

        campaigns = [
            CampaignInfo(
                external_id=campaign.external_id,
                name=campaign.name,
                description=campaign.description,
                first_seen=campaign.first_seen.isoformat() if campaign.first_seen else None,
                last_seen=campaign.last_seen.isoformat() if campaign.last_seen else None,
            )
            for campaign in result.campaigns
        ]

        related = [
            {
                "value": related_indicator.value,
                "type": related_indicator.indicator_type.value,
                "score": related_indicator.score,
            }
            for related_indicator in result.related_indicators[:10]  # Limit related
        ]

        return EnrichmentResponse(
            success=True,
            result=EnrichmentResult(
                value=request.value,
                indicator_type=request.indicator_type,
                risk_score=result.risk_score,
                verdict=result.verdict,
                first_seen=result.indicator.first_seen.isoformat()
                if result.indicator.first_seen
                else None,
                last_seen=result.indicator.last_seen.isoformat()
                if result.indicator.last_seen
                else None,
                sources=result.indicator.sources,
                tags=result.indicator.tags,
                description=result.indicator.description,
                threat_actors=threat_actors,
                campaigns=campaigns,
                related_indicators=related,
                raw_data=result.raw_data,
            ),
        )

    except Exception as e:
        return EnrichmentResponse(
            success=False,
            error=str(e),
        )


@router.post("/bulk", response_model=BulkEnrichmentResponse)
async def bulk_enrich_indicators(
    request: BulkEnrichmentRequest,
    current_user: User = Depends(get_current_user),
) -> BulkEnrichmentResponse:
    """Enrich multiple indicators in bulk.

    Limited to 100 indicators per request for performance.
    """
    registry = get_registry()
    ti_adapter = registry.get_threat_intel()

    if not ti_adapter:
        return BulkEnrichmentResponse(
            success=False,
            results=[],
            summary={},
        )

    # Process each indicator
    results = []
    summary: dict[str, int] = {
        "malicious": 0,
        "suspicious": 0,
        "clean": 0,
        "unknown": 0,
        "error": 0,
    }

    for indicator in request.indicators:
        response = await enrich_indicator(
            EnrichmentRequest(
                value=indicator.value,
                indicator_type=indicator.indicator_type,
            ),
            current_user,
        )
        results.append(response)

        if response.success and response.result:
            verdict = response.result.verdict
            summary[verdict] = summary.get(verdict, 0) + 1
        else:
            summary["error"] += 1

    return BulkEnrichmentResponse(
        success=True,
        results=results,
        summary=summary,
    )


@router.get("/threat-actor/{name}")
async def get_threat_actor(
    name: str,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Get detailed threat actor profile."""
    registry = get_registry()
    ti_adapter = registry.get_threat_intel()

    if not ti_adapter:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No threat intelligence adapter configured",
        )

    actor = await ti_adapter.get_threat_actor(name)
    if not actor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Threat actor not found: {name}",
        )

    return {
        "external_id": actor.external_id,
        "name": actor.name,
        "aliases": actor.aliases,
        "description": actor.description,
        "motivation": actor.motivation,
        "sophistication": actor.sophistication,
        "country": actor.country,
        "first_seen": actor.first_seen.isoformat() if actor.first_seen else None,
        "last_seen": actor.last_seen.isoformat() if actor.last_seen else None,
        "ttps": actor.ttps,
        "associated_campaigns": actor.associated_campaigns,
        "metadata": actor.metadata,
    }


@router.get("/threat-actors/search")
async def search_threat_actors(
    q: str = Query(..., min_length=2, description="Search query"),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """Search threat actors by name or alias."""
    registry = get_registry()
    ti_adapter = registry.get_threat_intel()

    if not ti_adapter:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No threat intelligence adapter configured",
        )

    actors = await ti_adapter.search_threat_actors(q, limit)

    return [
        {
            "external_id": a.external_id,
            "name": a.name,
            "aliases": a.aliases,
            "description": a.description,
            "motivation": a.motivation,
        }
        for a in actors
    ]


@router.get("/campaign/{name}")
async def get_campaign(
    name: str,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Get detailed campaign information."""
    registry = get_registry()
    ti_adapter = registry.get_threat_intel()

    if not ti_adapter:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No threat intelligence adapter configured",
        )

    campaign = await ti_adapter.get_campaign(name)
    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Campaign not found: {name}",
        )

    return {
        "external_id": campaign.external_id,
        "name": campaign.name,
        "description": campaign.description,
        "first_seen": campaign.first_seen.isoformat() if campaign.first_seen else None,
        "last_seen": campaign.last_seen.isoformat() if campaign.last_seen else None,
        "threat_actor": campaign.threat_actor,
        "targets": campaign.targets,
        "malware": campaign.malware,
        "metadata": campaign.metadata,
    }


@router.get("/campaigns/search")
async def search_campaigns(
    q: str = Query(..., min_length=2, description="Search query"),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """Search campaigns by name."""
    registry = get_registry()
    ti_adapter = registry.get_threat_intel()

    if not ti_adapter:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No threat intelligence adapter configured",
        )

    campaigns = await ti_adapter.search_campaigns(q, limit)

    return [
        {
            "external_id": c.external_id,
            "name": c.name,
            "description": c.description,
            "first_seen": c.first_seen.isoformat() if c.first_seen else None,
            "last_seen": c.last_seen.isoformat() if c.last_seen else None,
        }
        for c in campaigns
    ]


@router.get("/related/{indicator_type}/{value}")
async def get_related_indicators(
    indicator_type: str,
    value: str,
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """Get indicators related to the given indicator."""
    registry = get_registry()
    ti_adapter = registry.get_threat_intel()

    if not ti_adapter:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No threat intelligence adapter configured",
        )

    try:
        ioc_type = parse_indicator_type(indicator_type)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    related = await ti_adapter.get_related_indicators(value, ioc_type, limit)

    return [
        {
            "value": r.value,
            "type": r.indicator_type.value,
            "score": r.score,
            "sources": r.sources,
            "tags": r.tags,
        }
        for r in related
    ]
