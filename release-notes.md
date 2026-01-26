# Eleanor v0.4.0

**Hunt. Collect. Analyze. Respond.** — Now with automated incident response!

This release transforms Eleanor from an investigation platform into a complete SOC toolkit with multi-tenancy, visual rule building, automated playbooks, real-time monitoring, and MITRE ATT&CK integration.

## Highlights

### 🏢 Multi-tenancy Support
- Organization-level data isolation with PostgreSQL Row-Level Security
- Per-tenant Elasticsearch indices (`eleanor-{tenant}-events-*`)
- Tenant-scoped API keys for external integrations
- Organization switcher in UI header

### 🔍 Visual Correlation Rule Builder
- Drag-and-drop rule creation with 4 correlation patterns:
  - **Sequence** — Ordered event chains (A → B → C within timeframe)
  - **Temporal Join** — Events sharing attributes within time window
  - **Aggregation** — Threshold-based alerts (>N events in X minutes)
  - **Spike Detection** — Anomaly detection vs baseline
- Live preview against historical data
- Sigma rule import support
- Rule testing sandbox

### ⚡ Response Playbook Engine
- Native playbook definitions with JSONB step storage
- Conditional branching and approval gates
- Automatic rule-to-playbook binding
- Shuffle SOAR integration for external actions
- Execution timeline with step-by-step audit trail

### 📊 Real-time SOC Dashboard
- WebSocket-powered live event streaming
- Alert feed with severity indicators
- Event ticker for high-priority activities
- Detection chart with hourly trends
- Stats panel with key metrics (EPS, active alerts, coverage)

### 🎯 MITRE ATT&CK Navigator Integration
- Full ATT&CK matrix visualization
- Detection coverage analysis with gap identification
- Incident/alert heatmap overlay
- Navigator layer import/export (.json)
- Technique badges throughout the UI

## What's Changed

### Backend
- Multi-tenant middleware with automatic context injection
- Playbook execution engine with Celery task orchestration
- Rule validation service with pattern-specific logic
- Dashboard stats aggregation service
- MITRE ATT&CK data service with caching

### Frontend
- Tenant administration interface
- Rule builder with Monaco editor integration
- Playbook editor with visual step designer
- SOC dashboard with real-time updates
- Enhanced MITRE component with Navigator features

### Infrastructure
- Kubernetes manifests with HPA auto-scaling
- GitHub Actions CI/CD pipeline
- Dependabot configuration for security updates

## Upgrade Notes

1. **Database Migration Required**
   ```bash
   alembic upgrade head
   ```
   New tables: `tenants`, `tenant_memberships`, `playbooks`, `playbook_executions`

2. **Elasticsearch Reindex** (Optional)
   For multi-tenancy, existing indices can be migrated to tenant-prefixed pattern

3. **Configuration**
   New environment variables:
   - `ENABLE_MULTI_TENANCY=true` (default: false for backward compatibility)
   - `DEFAULT_TENANT_SLUG=default`

## Docker Images

```bash
docker pull ghcr.io/project-eleanor/eleanor-backend:0.4.0
docker pull ghcr.io/project-eleanor/eleanor-frontend:0.4.0
```

## Contributors

Thanks to all contributors who made this release possible!

---

**Full Changelog**: https://github.com/Project-Eleanor/Eleanor/compare/v0.3.0...v0.4.0
