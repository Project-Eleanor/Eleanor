"""API v1 router."""

from fastapi import APIRouter

from app.api.v1 import (
    admin,
    alerts,
    analytics,
    auth,
    cases,
    collection,
    connectors,
    enrichment,
    entities,
    events,
    evidence,
    graphs,
    integrations,
    mitre,
    notifications,
    parsing,
    playbooks,
    rbac,
    realtime,
    rule_builder,
    search,
    tenants,
    workbooks,
    workflows,
    ws,
)

router = APIRouter()

# Core endpoints
router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
router.include_router(rbac.router, prefix="/rbac", tags=["RBAC"])
router.include_router(notifications.router, prefix="/notifications", tags=["Notifications"])
router.include_router(cases.router, prefix="/cases", tags=["Cases"])
router.include_router(evidence.router, prefix="/evidence", tags=["Evidence"])
router.include_router(events.router, prefix="/events", tags=["Events"])
router.include_router(search.router, prefix="/search", tags=["Search"])
router.include_router(entities.router, prefix="/entities", tags=["Entities"])
router.include_router(admin.router, prefix="/admin", tags=["Admin"])
router.include_router(tenants.router, prefix="/admin/tenants", tags=["Tenants"])

# Parsing endpoints
router.include_router(parsing.router, prefix="/parsing", tags=["Parsing"])

# Graph endpoints
router.include_router(graphs.router, prefix="/graphs", tags=["Investigation Graphs"])

# Workbook endpoints
router.include_router(workbooks.router, prefix="/workbooks", tags=["Workbooks"])

# Analytics and connectors
router.include_router(analytics.router, prefix="/analytics", tags=["Analytics"])
router.include_router(rule_builder.router, prefix="/rules/builder", tags=["Rule Builder"])
router.include_router(alerts.router, prefix="/alerts", tags=["Alerts"])
router.include_router(connectors.router, prefix="/connectors", tags=["Data Connectors"])

# Integration endpoints
router.include_router(integrations.router, prefix="/integrations", tags=["Integrations"])
router.include_router(enrichment.router, prefix="/enrichment", tags=["Enrichment"])
router.include_router(collection.router, prefix="/collection", tags=["Collection"])
router.include_router(workflows.router, prefix="/workflows", tags=["Workflows"])
router.include_router(playbooks.router, prefix="/playbooks", tags=["Playbooks"])
router.include_router(realtime.router, prefix="/realtime", tags=["Real-time Dashboard"])

# MITRE ATT&CK endpoints
router.include_router(mitre.router, prefix="/mitre", tags=["MITRE ATT&CK"])

# WebSocket endpoint
router.include_router(ws.router, tags=["WebSocket"])
