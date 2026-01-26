# Eleanor

**Hunt. Collect. Analyze. Respond.**

Eleanor is an open-source, self-hosted Digital Forensics and Incident Response platform that provides a unified Sentinel-style interface for the complete investigation lifecycle. Rather than building everything from scratch, Eleanor integrates best-of-breed open-source tools under a single dashboard, eliminating context-switching during investigations.

**Named after the unicorn 1967 Shelby GT500 from Gone in 60 Seconds** - the all-in-one DFIR solution the community has long sought.

**Philosophy:** Investigation-first, not alert-first. Deep forensic investigation from hunt through response.

---

## Version & Status

| | |
|--|--|
| **Version** | 0.1.0-prealpha |
| **Status** | Phase 3 Complete - Frontend & Parsing Pipeline Ready |
| **Server** | vm-eleanor (10.150.150.50) |

---

## Features

- **Case Management**: Full lifecycle case tracking via IRIS integration
- **Threat Hunting**: ES|QL query interface with saved queries and workbooks
- **Evidence Browser**: Chain of custody tracking with file hashing
- **Entity Profiles**: Aggregated views of hosts, users, and IPs with OpenCTI enrichment
- **Timeline Visualization**: Interactive timeline reconstruction via Timesketch
- **Endpoint Collection**: Live response and artifact collection via Velociraptor
- **SOAR Integration**: Automated response workflows via Shuffle
- **Flexible Authentication**: OIDC, LDAP/AD, and local accounts

---

## Current Deployment

### Running Services

| Service | Port | URL | Credentials |
|---------|------|-----|-------------|
| **Eleanor API** | 8000 | http://vm-eleanor:8000 | admin / admin123 |
| **IRIS** | 8443 | https://vm-eleanor:8443 | administrator / iris_admin_password |
| **Velociraptor** | 8889 | https://vm-eleanor:8889 | eleanor / eleanor |
| **OpenCTI** | 8080 | http://vm-eleanor:8080 | admin@eleanor.local / opencti_admin_password |
| **Shuffle** | 3001 | http://vm-eleanor:3001 | admin / shuffle_admin_password |
| **Timesketch** | 5000 | http://vm-eleanor:5000 | eleanor / eleanor |
| **Elasticsearch** | 9200 | http://vm-eleanor:9200 | - |
| **PostgreSQL** | 5432 | Internal | - |
| **Redis** | 6379 | Internal | - |

### Container Summary (23 containers)

| Stack | Containers | Status |
|-------|------------|--------|
| Eleanor Core | 5 (postgres, elasticsearch, redis, celery-worker, celery-beat) | All healthy |
| IRIS | 5 (app, worker, nginx, db, rabbitmq) | Running |
| Velociraptor | 1 | Running |
| OpenCTI | 4 (platform, worker, rabbitmq, minio) | Running |
| Shuffle | 3 (backend, frontend, orborus) | Running |
| Timesketch | 5 (web, worker, nginx, postgres, redis) | Running |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ELEANOR UNIFIED DASHBOARD                           │
│                        (Angular + React Components)                         │
│                                                                             │
│  ┌──────────┬──────────┬──────────┬──────────┬──────────┬──────────────┐   │
│  │ Incidents│ Hunting  │ Entities │ Timeline │ Evidence │  Response    │   │
│  │  Queue   │ Console  │  Pages   │   View   │ Browser  │  Actions     │   │
│  └──────────┴──────────┴──────────┴──────────┴──────────┴──────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ELEANOR ORCHESTRATION API                           │
│                              (FastAPI) ✅ DONE                              │
│                                                                             │
│  ┌─────────────┬─────────────┬─────────────┬─────────────┬──────────────┐  │
│  │   Search    │   Entity    │  Workflow   │  Dashboard  │    Auth      │  │
│  │   Engine    │  Enrichment │   Trigger   │   State     │   Layer      │  │
│  │  (ES|QL)    │  (OpenCTI)  │  (Shuffle)  │ (Workbooks) │(OIDC/LDAP)   │  │
│  └─────────────┴─────────────┴─────────────┴─────────────┴──────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
          ┌───────────────────────────┼───────────────────────────┐
          ▼                           ▼                           ▼
┌─────────────────────┐   ┌─────────────────────┐   ┌─────────────────────┐
│    IRIS Adapter     │   │ Velociraptor Adapter│   │  Timesketch Adapter │
│  (Case Management)  │   │    (Collection)     │   │  (Timeline Engine)  │
│  - Cases            │   │  - Endpoints        │   │  - Sketches         │
│  - Assets           │   │  - Hunts            │   │  - Events           │
│  - IOCs             │   │  - Artifacts        │   │  - Annotations      │
│  - Notes            │   │  - Live Response    │   │  - Saved Views      │
└─────────────────────┘   └─────────────────────┘   └─────────────────────┘
          │                           │                           │
          ▼                           ▼                           ▼
┌─────────────────────┐   ┌─────────────────────┐   ┌─────────────────────┐
│  Shuffle Adapter    │   │  OpenCTI Adapter    │   │   Dissect Workers   │
│  (SOAR Engine)      │   │  (Threat Intel)     │   │  (Artifact Parsing) │
│  - Workflows        │   │  - Enrichment       │   │  - Registry         │
│  - Approvals        │   │  - Risk Scores      │   │  - Event Logs       │
│  - Integrations     │   │  - Threat Actors    │   │  - Browser Data     │
│  - Notifications    │   │  - Campaigns        │   │  - Custom Parsers   │
└─────────────────────┘   └─────────────────────┘   └─────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        SHARED DATA LAYER                                    │
│  ┌─────────────────────┐              ┌─────────────────────┐              │
│  │   Elasticsearch     │              │      Redis          │              │
│  │  - All event data   │              │  - Job queues       │              │
│  │  - Parsed artifacts │              │  - Session cache    │              │
│  │  - Timesketch data  │              │  - Enrichment cache │              │
│  └─────────────────────┘              └─────────────────────┘              │
│  ┌─────────────────────┐              ┌─────────────────────┐              │
│  │   PostgreSQL        │              │   File Storage      │              │
│  │  - Eleanor config   │              │  - Evidence files   │              │
│  │  - User preferences │              │  - Parsed output    │              │
│  │  - Workbooks/Saved  │              │  - Artifact cache   │              │
│  └─────────────────────┘              └─────────────────────┘              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Integrated Components

| Component | Role | Integration Method |
|-----------|------|-------------------|
| **Elasticsearch** | Central data store for all events | Direct |
| **Velociraptor** | Endpoint visibility, collection, response | REST API adapter |
| **IRIS** | Case management backend | REST API adapter |
| **Timesketch** | Timeline analysis engine | REST API + shared ES |
| **Shuffle** | SOAR / workflow automation | REST API adapter |
| **OpenCTI** | Threat intelligence enrichment | GraphQL API adapter |

---

## Implementation Plan

### Phase 1: Backend Foundation ✅ COMPLETE
- FastAPI application with 30+ API endpoints
- PostgreSQL for config/users/workbooks
- Elasticsearch for events/search
- JWT authentication (SAM working, OIDC/LDAP configured)
- Case/Evidence/Entity/Search APIs

### Phase 2: Tool Integrations ✅ COMPLETE
- Docker Compose deployment for all tools
- Adapter base classes implemented
- All 5 tool adapters created:
  - Velociraptor (Collection)
  - IRIS (Case Management)
  - OpenCTI (Threat Intelligence)
  - Shuffle (SOAR)
  - Timesketch (Timeline Analysis)
- API endpoints for integrations, enrichment, collection, workflows

### Phase 3: Frontend & Parsing Pipeline ✅ COMPLETE
- Angular 17 project with 14 feature modules
- Core layout with Sentinel-style dark theme
- Hunting Console with Monaco ES|QL/KQL editor
- Cytoscape investigation graphs
- D3 timeline visualization
- Workbooks system with 6 tile types
- Async parsing pipeline:
  - Celery workers for distributed processing
  - 34 evidence parsers (EVTX, Registry, Browser, MFT, Memory, etc.)
  - Dissect & Volatility3 integration
- Detection engine with correlation rules

### Phase 4: OVA Distribution ✅ COMPLETE
- Pre-configured Ubuntu 22.04 OVA
- All components as Docker containers
- Web-based setup wizard
- Auto-provisioning of integrations
- Backup/restore scripts

### Phase 5: Testing & Polish (IN PROGRESS)
- Basic API smoke tests
- Parser unit tests
- End-to-end workflow validation

---

## Project Structure

```
eleanor/
├── backend/
│   └── app/
│       ├── adapters/           # Tool integration adapters
│       │   ├── base.py         # Abstract adapter interfaces
│       │   ├── registry.py     # Adapter discovery & management
│       │   ├── velociraptor/   # Velociraptor adapter
│       │   ├── iris/           # IRIS adapter
│       │   ├── opencti/        # OpenCTI adapter
│       │   ├── shuffle/        # Shuffle adapter
│       │   └── timesketch/     # Timesketch adapter
│       ├── api/v1/             # API endpoints
│       │   ├── integrations.py # Integration status
│       │   ├── enrichment.py   # Entity enrichment
│       │   ├── collection.py   # Velociraptor collection
│       │   └── workflows.py    # Shuffle workflows
│       ├── config.py           # Application settings
│       └── main.py             # FastAPI application
├── docker/
│   ├── iris/                   # IRIS deployment
│   ├── velociraptor/           # Velociraptor deployment
│   └── timesketch/             # Timesketch deployment
├── config/
│   ├── timesketch/             # Timesketch config
│   └── velociraptor/           # Velociraptor config
├── docker-compose.yml          # Core services
├── docker-compose.tools.yml    # Integrated tools
└── .env.example                # Environment template
```

---

## Quick Start

### Prerequisites
- Docker & Docker Compose
- 32GB+ RAM recommended
- 500GB+ storage

### Deployment

```bash
# Clone the repository
git clone https://github.com/YOUR_ORG/eleanor.git
cd eleanor

# Copy and configure environment
cp .env.example .env
# Edit .env with your settings

# Start core services
docker compose up -d

# Start integrated tools
docker compose -f docker-compose.tools.yml up -d

# Start individual tool stacks
docker compose -f docker/iris/docker-compose.iris.yml up -d
docker compose -f docker/velociraptor/docker-compose.velociraptor.yml up -d
docker compose -f docker/timesketch/docker-compose.timesketch.yml up -d
```

### Create Users

```bash
# Timesketch
docker exec eleanor-timesketch-web tsctl create-user admin --password admin

# Velociraptor
docker exec eleanor-velociraptor velociraptor \
  --config /velociraptor/config/server.config.yaml \
  user add admin admin --role administrator
```

---

## Resource Requirements

| Deployment | RAM | CPU | Storage | Endpoints |
|------------|-----|-----|---------|-----------|
| Minimum | 32GB | 8 cores | 500GB SSD | Small lab |
| Recommended | 64GB | 16 cores | 1TB SSD | 100s of endpoints |
| Enterprise | 128GB+ | 32+ cores | Multi-TB | 1000s of endpoints |

---

## API Documentation

Once running, access the API documentation at:
- Swagger UI: http://vm-eleanor:8000/docs
- ReDoc: http://vm-eleanor:8000/redoc

---

## Technology Stack

| Component | Technology |
|-----------|------------|
| Frontend | Angular 17+ with React visualization components |
| Backend | Python FastAPI |
| Database | PostgreSQL (structured data) + Elasticsearch (events) |
| Auth | OIDC, LDAP/AD, Local (SAM) |
| Container | Docker & Docker Compose |

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

## License

Apache License 2.0 - see [LICENSE](LICENSE) for details.

---

## Acknowledgments

Eleanor integrates the following open-source projects:
- [DFIR-IRIS](https://github.com/dfir-iris/iris-web) - Case Management
- [Velociraptor](https://github.com/Velocidex/velociraptor) - Endpoint Collection
- [OpenCTI](https://github.com/OpenCTI-Platform/opencti) - Threat Intelligence
- [Shuffle](https://github.com/Shuffle/Shuffle) - SOAR Automation
- [Timesketch](https://github.com/google/timesketch) - Timeline Analysis
