<p align="center">
  <img src="docs/images/eleanor-logo.png" alt="Eleanor Logo" width="200"/>
</p>

<h1 align="center">Eleanor</h1>

<p align="center">
  <strong>Hunt. Collect. Analyze. Respond.</strong>
</p>

<p align="center">
  <em>The open-source DFIR platform that unifies your investigation workflow</em>
</p>

<p align="center">
  <a href="#features">Features</a> •
  <a href="#who-is-eleanor-for">Who It's For</a> •
  <a href="#quick-start">Quick Start</a> •
  <a href="#documentation">Documentation</a> •
  <a href="#contributing">Contributing</a>
</p>

<p align="center">
  <a href="https://github.com/Project-Eleanor/Eleanor/releases">
    <img src="https://img.shields.io/github/v/release/Project-Eleanor/Eleanor?include_prereleases&style=flat-square" alt="Release">
  </a>
  <a href="https://github.com/Project-Eleanor/Eleanor/blob/main/LICENSE">
    <img src="https://img.shields.io/github/license/Project-Eleanor/Eleanor?style=flat-square" alt="License">
  </a>
  <a href="https://github.com/Project-Eleanor/Eleanor/actions/workflows/ci.yml">
    <img src="https://img.shields.io/github/actions/workflow/status/Project-Eleanor/Eleanor/ci.yml?branch=main&style=flat-square&label=CI" alt="CI Status">
  </a>
  <a href="https://github.com/Project-Eleanor/Eleanor/issues">
    <img src="https://img.shields.io/github/issues/Project-Eleanor/Eleanor?style=flat-square" alt="Issues">
  </a>
  <a href="https://github.com/Project-Eleanor/Eleanor/pulls">
    <img src="https://img.shields.io/github/issues-pr/Project-Eleanor/Eleanor?style=flat-square" alt="Pull Requests">
  </a>
</p>

---

## What is Eleanor?

Eleanor is an open-source, self-hosted **Digital Forensics and Incident Response (DFIR)** platform that brings the entire investigation lifecycle into a single, unified interface. No more juggling a dozen browser tabs, copy-pasting IOCs between tools, or losing context during critical investigations.

> **Named after the unicorn 1967 Shelby GT500 from *Gone in 60 Seconds*** — Eleanor is the all-in-one DFIR solution the community has long sought.

### The Problem Eleanor Solves

Modern DFIR teams use 10+ separate tools: SIEM for detection, case management for tracking, endpoint agents for collection, forensic tools for analysis, threat intel platforms for enrichment, and SOAR for response. Each tool has its own interface, data format, and learning curve. Context-switching kills investigation velocity.

**Eleanor fixes this.** It integrates battle-tested open-source tools (IRIS, Velociraptor, OpenCTI, Shuffle, Timesketch) under a single Sentinel-style dashboard. One login, one interface, one unified workflow from detection to remediation.

### Philosophy

**Investigation-first, not alert-first.** Most security tools optimize for alert triage—Eleanor optimizes for deep investigation. Start with a hypothesis, hunt proactively, and follow the evidence wherever it leads. When you find something, you have the tools to respond immediately.

## Who is Eleanor For?

| Role | How Eleanor Helps |
|------|-------------------|
| **SOC Analysts** | Investigate alerts faster with unified entity profiles, automated enrichment, and one-click threat intel lookups. No more copying hashes between VirusTotal tabs. |
| **Threat Hunters** | Hunt across your environment with ES\|QL/KQL queries, save successful hunts as reusable playbooks, and build workbooks that capture institutional knowledge. |
| **Forensic Investigators** | Process disk images, memory dumps, and triage packages with 34+ built-in parsers. Build timelines, trace lateral movement, and generate court-ready reports. |
| **Incident Responders** | Coordinate response with case management, execute automated playbooks with approval gates, and contain threats without leaving the platform. |
| **MSSPs** | Serve multiple clients from one instance with full multi-tenancy, tenant isolation, and per-organization configurations. |

## What Makes Eleanor Unique?

1. **Unified Interface, Best-of-Breed Tools** — Eleanor doesn't reinvent proven tools. It wraps IRIS, Velociraptor, OpenCTI, and Shuffle in a cohesive UI so you get the power of each without the integration headaches.

2. **Self-Hosted & Privacy-Preserving** — Your investigation data never leaves your infrastructure. No cloud dependencies, no telemetry phoning home, no vendor lock-in. Critical for investigations involving sensitive data.

3. **Multi-Tenant by Design** — Built from day one for MSSPs and enterprise teams. Row-level security, scoped Elasticsearch indices, and per-tenant configurations. One instance, many clients.

4. **Investigation Workbooks** — Capture your team's investigative playbooks as reusable workbooks. New analysts can follow proven procedures; experienced hunters can share their techniques.

5. **OVA Deployment** — Download a pre-configured virtual appliance and be investigating in under 30 minutes. No Kubernetes expertise required (though we support that too).

## Features

### Core Capabilities

| Feature | Description |
|---------|-------------|
| **Threat Hunting** | ES|QL/KQL query interface with Monaco editor, saved queries, and workbooks |
| **Case Management** | Full lifecycle tracking with IRIS integration, assets, IOCs, and notes |
| **Evidence Processing** | 34+ parsers for EVTX, Registry, MFT, Browser artifacts, Memory, and more |
| **Entity Profiling** | Aggregated views of hosts, users, IPs with threat intelligence enrichment |
| **Timeline Analysis** | Interactive D3 timeline reconstruction with correlation markers |
| **Investigation Graphs** | Cytoscape-powered relationship visualization with path analysis |
| **Endpoint Collection** | Live response and artifact collection via Velociraptor |
| **Automated Response** | SOAR workflows via Shuffle with approval gates |
| **Forensic Reports** | Professional report generation with templates (PDF, DOCX, HTML) |

### v0.4.0 Highlights

- **Multi-tenancy** — Organization-level isolation with RLS and tenant-scoped indices
- **Visual Rule Builder** — Drag-drop correlation rules with 4 detection patterns
- **Response Playbooks** — Automated workflows with approval gates and SOAR integration
- **Real-time Dashboard** — Live SOC monitoring with WebSocket event streaming
- **MITRE ATT&CK Navigator** — Coverage analysis, gap identification, and layer export

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ELEANOR UNIFIED DASHBOARD                           │
│                            (Angular 17+ SPA)                                │
│  ┌──────────┬──────────┬──────────┬──────────┬──────────┬──────────────┐   │
│  │ Incidents│ Hunting  │ Entities │ Timeline │ Evidence │  Workbooks   │   │
│  │  Queue   │ Console  │ Profiles │   View   │ Browser  │  & Reports   │   │
│  └──────────┴──────────┴──────────┴──────────┴──────────┴──────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ELEANOR ORCHESTRATION API                           │
│                              (FastAPI + Celery)                             │
│  ┌─────────────┬─────────────┬─────────────┬─────────────┬──────────────┐  │
│  │   Search    │   Entity    │  Evidence   │  Workflow   │    Auth      │  │
│  │   Engine    │  Enrichment │  Parsing    │   Engine    │  (JWT/OIDC)  │  │
│  └─────────────┴─────────────┴─────────────┴─────────────┴──────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
          ┌───────────────────────────┼───────────────────────────┐
          ▼                           ▼                           ▼
┌─────────────────────┐   ┌─────────────────────┐   ┌─────────────────────┐
│    IRIS Adapter     │   │ Velociraptor Adapter│   │   OpenCTI Adapter   │
│  (Case Management)  │   │    (Collection)     │   │  (Threat Intel)     │
└─────────────────────┘   └─────────────────────┘   └─────────────────────┘
          │                           │                           │
          └───────────────────────────┼───────────────────────────┘
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           SHARED DATA LAYER                                 │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐             │
│  │  Elasticsearch  │  │   PostgreSQL    │  │     Redis       │             │
│  │  (Events/Search)│  │ (Config/Users)  │  │  (Cache/Queue)  │             │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Quick Start

### Prerequisites

- Docker Engine 24.0+ & Docker Compose v2
- 32GB+ RAM (64GB recommended for production)
- 500GB+ SSD storage

### Deploy with Docker Compose

```bash
# Clone the repository
git clone https://github.com/Project-Eleanor/Eleanor.git
cd Eleanor

# Copy environment template
cp .env.example .env
# Edit .env with your settings (change default passwords!)

# Start core services
docker compose up -d

# Start integrated tools
docker compose -f docker-compose.tools.yml up -d

# Check status
docker compose ps
```

### Deploy with Kubernetes

```bash
cd deploy/kubernetes

# Development environment
./deploy.sh development deploy

# Production environment (update secrets first!)
vim overlays/production/secrets.yaml
./deploy.sh production deploy
```

### Access the Platform

| Service | URL | Default Credentials |
|---------|-----|---------------------|
| Eleanor UI | http://localhost:4200 | admin / admin123 |
| Eleanor API | http://localhost:8000/docs | — |
| IRIS | https://localhost:8443 | administrator / iris_admin |
| Velociraptor | https://localhost:8889 | admin / admin |

## Documentation

| Document | Description |
|----------|-------------|
| [Quick Start Guide](docs/QUICKSTART.md) | Get up and running in minutes |
| [Architecture Overview](docs/ARCHITECTURE.md) | System design and components |
| [API Reference](docs/API_REFERENCE.md) | Complete API documentation |
| [Parser Development](docs/PARSER_DEVELOPMENT.md) | Creating custom evidence parsers |
| [Kubernetes Deployment](deploy/kubernetes/README.md) | Production K8s deployment |
| [Contributing Guide](CONTRIBUTING.md) | How to contribute to Eleanor |

## Integrated Components

Eleanor integrates these battle-tested open-source tools:

| Component | Role | Integration |
|-----------|------|-------------|
| [DFIR-IRIS](https://github.com/dfir-iris/iris-web) | Case Management | REST API |
| [Velociraptor](https://github.com/Velocidex/velociraptor) | Endpoint Collection | REST API |
| [OpenCTI](https://github.com/OpenCTI-Platform/opencti) | Threat Intelligence | GraphQL |
| [Shuffle](https://github.com/Shuffle/Shuffle) | SOAR Automation | REST API |
| [Timesketch](https://github.com/google/timesketch) | Timeline Analysis | REST API |
| [Dissect](https://github.com/fox-it/dissect) | Artifact Parsing | Native |

## Technology Stack

| Layer | Technologies |
|-------|-------------|
| **Frontend** | Angular 17, Material Design, Cytoscape.js, D3.js, Monaco Editor |
| **Backend** | Python 3.11, FastAPI, Celery, SQLAlchemy |
| **Database** | PostgreSQL 15, Elasticsearch 8.x, Redis 7 |
| **Infrastructure** | Docker, Kubernetes, Nginx |
| **Parsing** | Dissect, Volatility3, python-evtx |

## System Requirements

| Deployment | RAM | CPU | Storage | Use Case |
|------------|-----|-----|---------|----------|
| Development | 16GB | 4 cores | 100GB | Local testing |
| Small Lab | 32GB | 8 cores | 500GB | Small team |
| Production | 64GB | 16 cores | 1TB+ | Enterprise |
| Enterprise | 128GB+ | 32+ cores | Multi-TB | Large scale |

## Roadmap

See our [Project Roadmap](https://github.com/Project-Eleanor/Eleanor/projects/1) for planned features.

### Upcoming in v0.5.0

- [ ] AI-Assisted Investigation — LLM-powered query suggestions and anomaly explanations
- [ ] Evidence Chain of Custody — Cryptographic verification with blockchain anchoring
- [ ] Federated Search — Cross-instance threat hunting with privacy controls
- [ ] Mobile Forensics — iOS/Android artifact parsing and timeline integration
- [ ] Compliance Reporting — Automated audit reports for SOC2, HIPAA, PCI-DSS

## Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

### Ways to Contribute

- Report bugs and request features via [Issues](https://github.com/Project-Eleanor/Eleanor/issues)
- Submit pull requests for bug fixes and features
- Improve documentation
- Write evidence parsers
- Share detection rules and workbooks

### Development Setup

```bash
# Backend
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload

# Frontend
cd frontend
npm install
ng serve
```

## Security

If you discover a security vulnerability, please see our [Security Policy](SECURITY.md) for responsible disclosure guidelines.

## License

Eleanor is licensed under the [Apache License 2.0](LICENSE).

```
Copyright 2024-2026 Project Eleanor Contributors

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
```

## Acknowledgments

Eleanor stands on the shoulders of giants. Special thanks to:

- The [DFIR-IRIS](https://github.com/dfir-iris/iris-web) team
- The [Velociraptor](https://github.com/Velocidex/velociraptor) community
- The [OpenCTI](https://github.com/OpenCTI-Platform/opencti) project
- The [Dissect](https://github.com/fox-it/dissect) developers at Fox-IT
- All open-source DFIR tool maintainers

---

<p align="center">
  <sub>Built with dedication for the DFIR community</sub>
</p>
