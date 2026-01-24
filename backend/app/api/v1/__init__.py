"""API v1 router."""

from fastapi import APIRouter

from app.api.v1 import (
    admin,
    auth,
    cases,
    collection,
    enrichment,
    entities,
    events,
    evidence,
    integrations,
    search,
    workflows,
)

router = APIRouter()

# Core endpoints
router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
router.include_router(cases.router, prefix="/cases", tags=["Cases"])
router.include_router(evidence.router, prefix="/evidence", tags=["Evidence"])
router.include_router(events.router, prefix="/events", tags=["Events"])
router.include_router(search.router, prefix="/search", tags=["Search"])
router.include_router(entities.router, prefix="/entities", tags=["Entities"])
router.include_router(admin.router, prefix="/admin", tags=["Admin"])

# Integration endpoints
router.include_router(integrations.router, prefix="/integrations", tags=["Integrations"])
router.include_router(enrichment.router, prefix="/enrichment", tags=["Enrichment"])
router.include_router(collection.router, prefix="/collection", tags=["Collection"])
router.include_router(workflows.router, prefix="/workflows", tags=["Workflows"])
