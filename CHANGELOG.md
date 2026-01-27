# Changelog

All notable changes to Eleanor will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0-alpha] - 2026-01-27

### Added

#### Core Platform
- **Unified Dashboard Shell** - Sentinel-style interface for complete DFIR workflow
- **ES|QL Hunting Console** - Elasticsearch query interface with 7 search endpoints
- **Case Management** - Full case lifecycle with IRIS integration
- **Evidence Management** - Chain of custody tracking with integrity verification
- **Multi-tenancy** - Complete tenant isolation with RBAC

#### Integrations (5 Adapters)
- **Velociraptor** - Endpoint collection, hunts, host isolation, file quarantine, process termination
- **DFIR-IRIS** - Bi-directional case sync, assets, IOCs, notes
- **OpenCTI** - Threat intelligence enrichment, indicator lookup, bulk enrichment
- **Shuffle SOAR** - Workflow execution, approvals, automated response actions
- **Timesketch** - Timeline analysis, sketches, event search, tagging

#### Cloud Storage Adapters
- **Local Filesystem** - Default storage with hash verification
- **AWS S3** - Full S3 support with multipart uploads and presigned URLs
- **Azure Blob Storage** - Azure Blob with managed identity support
- **Google Cloud Storage** - GCS with workload identity support

#### Microsoft Security Integrations
- **Microsoft Defender for Endpoint** - Device inventory, alerts, response actions (isolate, scan, collect)
- **Microsoft Sentinel** - Incident management, KQL queries, watchlists, hunting queries

#### Response Actions
- Host isolation/release via Velociraptor
- Process termination
- File quarantine
- Antivirus scan triggering
- Investigation package collection

#### Detection & Analytics
- MITRE ATT&CK Navigator with 9 endpoints including heatmaps
- Visual correlation rule builder
- SOC real-time dashboard with WebSocket support
- Playbook automation (11 endpoints)
- Workflow engine (12 endpoints)

#### Frontend Features
- Angular 20 with PrimeNG components
- Workbooks (editor/viewer)
- Investigation graphs (7 endpoints)
- Real-time notifications
- Mobile-responsive design

#### Deployment Options
- **Docker Compose** - Full stack with 24 containers
- **Kubernetes** - Production-ready with PDBs, HPAs, Ingress
- **OVA Appliance** - VMware/VirtualBox with setup wizard

#### Kubernetes Cloud Overlays
- **AWS EKS** - GP3/EFS storage, ALB ingress, IRSA, External Secrets
- **Azure AKS** - Premium SSD/Files, App Gateway, Workload Identity, Key Vault
- **GCP GKE** - PD-SSD/Filestore, GCE ingress, Workload Identity, Secret Manager

#### API
- 185 REST endpoints across 25 categories
- OpenAPI/Swagger documentation
- Rate limiting middleware
- Comprehensive audit logging

#### Security
- JWT authentication with configurable expiration
- RBAC with granular permissions
- Audit middleware for compliance
- Chain of custody for evidence integrity

### Infrastructure
- PostgreSQL 16 for persistent storage
- Elasticsearch 8.12 for event indexing
- Redis 7 for caching and task queues
- Celery workers for background processing

### Documentation
- Quick start guide
- Docker installation guide
- Kubernetes installation guide
- OVA installation guide
- Adapter configuration guide
- API documentation

## [0.4.0] - 2026-01-26

### Added
- Initial Timesketch adapter
- Initial Shuffle SOAR adapter
- Kubernetes PodDisruptionBudgets
- Kubernetes HorizontalPodAutoscalers

## [0.3.0] - 2026-01-25

### Added
- OpenCTI threat intelligence adapter
- Bulk enrichment endpoints
- MITRE ATT&CK mapping

## [0.2.0] - 2026-01-24

### Added
- DFIR-IRIS case management adapter
- Evidence upload and parsing pipeline
- Celery task queue for background processing

## [0.1.0] - 2026-01-23

### Added
- Initial project structure
- FastAPI backend with async support
- Angular frontend scaffold
- Velociraptor integration
- Docker Compose deployment
- Basic authentication

---

[1.0.0-alpha]: https://github.com/Project-Eleanor/Eleanor/releases/tag/v1.0.0-alpha
[0.4.0]: https://github.com/Project-Eleanor/Eleanor/releases/tag/v0.4.0
[0.3.0]: https://github.com/Project-Eleanor/Eleanor/releases/tag/v0.3.0
[0.2.0]: https://github.com/Project-Eleanor/Eleanor/releases/tag/v0.2.0
[0.1.0]: https://github.com/Project-Eleanor/Eleanor/releases/tag/v0.1.0
