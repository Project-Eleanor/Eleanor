# Eleanor API Reference

This document provides a comprehensive reference for the Eleanor REST API v1.

## Base URL

All API endpoints are prefixed with:
```
/api/v1
```

## Authentication

Eleanor uses JWT (JSON Web Tokens) for authentication.

### Login
```http
POST /api/v1/auth/login
Content-Type: application/x-www-form-urlencoded

username=<username>&password=<password>
```

**Response:**
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

### Using the Token

Include the token in the `Authorization` header for all subsequent requests:
```http
Authorization: Bearer <access_token>
```

---

## Endpoints by Category

### Authentication (`/auth`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/auth/login` | Authenticate user and get JWT token |
| GET | `/auth/me` | Get current user information |
| POST | `/auth/logout` | Invalidate current token |
| POST | `/auth/refresh` | Refresh JWT token |
| GET | `/auth/setup/status` | Check if initial setup is complete |
| POST | `/auth/setup` | Complete initial setup (create admin user) |

---

### Cases (`/cases`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/cases` | List cases with filtering and pagination |
| POST | `/cases` | Create a new case |
| GET | `/cases/{case_id}` | Get case details |
| PATCH | `/cases/{case_id}` | Update case |
| DELETE | `/cases/{case_id}` | Delete case |
| GET | `/cases/{case_id}/timeline` | Get case timeline events |
| POST | `/cases/{case_id}/timeline` | Add timeline event |

#### Create Case

```bash
curl -X POST http://localhost:8000/api/v1/cases \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Incident Investigation 2026-001",
    "description": "Potential lateral movement detected",
    "severity": "high",
    "status": "open"
  }'
```

**Response:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "Incident Investigation 2026-001",
  "description": "Potential lateral movement detected",
  "severity": "high",
  "status": "open",
  "created_by": "analyst@example.com",
  "created_at": "2026-01-26T10:30:00Z"
}
```

---

### Evidence (`/evidence`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/evidence` | List evidence with filtering |
| POST | `/evidence/upload` | Upload new evidence file |
| GET | `/evidence/{evidence_id}` | Get evidence details |
| PATCH | `/evidence/{evidence_id}` | Update evidence metadata |
| DELETE | `/evidence/{evidence_id}` | Delete evidence |
| GET | `/evidence/{evidence_id}/download` | Download evidence file |
| GET | `/evidence/{evidence_id}/custody` | Get chain of custody |
| POST | `/evidence/{evidence_id}/verify` | Verify evidence integrity |

#### Upload Evidence

```bash
curl -X POST http://localhost:8000/api/v1/evidence/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@/path/to/Security.evtx" \
  -F "case_id=550e8400-e29b-41d4-a716-446655440000" \
  -F "description=Windows Security Event Log"
```

---

### Parsing (`/parsing`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/parsing/submit` | Submit evidence for parsing |
| GET | `/parsing/jobs/{job_id}` | Get parsing job status |
| GET | `/parsing/jobs` | List parsing jobs |
| POST | `/parsing/jobs/{job_id}/cancel` | Cancel parsing job |
| GET | `/parsing/parsers` | List available parsers |
| POST | `/parsing/batch-submit` | Submit multiple files for parsing |

#### Submit for Parsing

```bash
curl -X POST http://localhost:8000/api/v1/parsing/submit \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "evidence_id": "550e8400-e29b-41d4-a716-446655440000",
    "parser_hint": "windows_evtx"
  }'
```

**Response:**
```json
{
  "job_id": "123e4567-e89b-12d3-a456-426614174000",
  "status": "pending",
  "evidence_id": "550e8400-e29b-41d4-a716-446655440000",
  "parser_name": "windows_evtx",
  "created_at": "2026-01-26T10:35:00Z"
}
```

---

### Search (`/search`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/search/query` | Execute Elasticsearch query |
| POST | `/search/kql` | Execute KQL query |
| POST | `/search/esql` | Execute ES|QL query |
| GET | `/search/indices` | List available indices |
| GET | `/search/schema/{index}` | Get index schema/mapping |
| GET | `/search/saved` | List saved queries |
| POST | `/search/saved` | Save a query |
| DELETE | `/search/saved/{query_id}` | Delete saved query |

#### KQL Query

```bash
curl -X POST http://localhost:8000/api/v1/search/kql \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "process.name:powershell.exe AND event.action:process_created",
    "index": "eleanor-events-*",
    "from": 0,
    "size": 100,
    "time_range": {
      "start": "2026-01-25T00:00:00Z",
      "end": "2026-01-26T23:59:59Z"
    }
  }'
```

---

### Events (`/events`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/events` | Index a single event |
| POST | `/events/bulk` | Bulk index events |
| GET | `/events/{event_id}` | Get event by ID |

---

### Entities (`/entities`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/entities/hosts/{hostname}` | Get host entity profile |
| GET | `/entities/users/{username}` | Get user entity profile |
| GET | `/entities/ips/{ip_address}` | Get IP entity profile |
| GET | `/entities/{entity_type}/{identifier}/events` | Get events for entity |

#### Get Host Profile

```bash
curl http://localhost:8000/api/v1/entities/hosts/WORKSTATION-01 \
  -H "Authorization: Bearer $TOKEN"
```

**Response:**
```json
{
  "identifier": "WORKSTATION-01",
  "entity_type": "host",
  "first_seen": "2026-01-15T08:00:00Z",
  "last_seen": "2026-01-26T10:30:00Z",
  "event_count": 15847,
  "related_users": ["admin", "analyst"],
  "related_ips": ["192.168.1.100"],
  "risk_score": 45
}
```

---

### Investigation Graphs (`/graphs`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/graphs/build` | Build investigation graph |
| POST | `/graphs/expand` | Expand graph node |
| GET | `/graphs/entity-relationships` | Get entity relationships |
| POST | `/graphs/path` | Find path between entities |
| POST | `/graphs/saved` | Save graph |
| GET | `/graphs/saved` | List saved graphs |
| GET | `/graphs/saved/{graph_id}` | Get saved graph |
| DELETE | `/graphs/saved/{graph_id}` | Delete saved graph |

#### Build Graph

```bash
curl -X POST http://localhost:8000/api/v1/graphs/build \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "case_id": "550e8400-e29b-41d4-a716-446655440000",
    "seed_entities": [
      {"type": "host", "value": "WORKSTATION-01"}
    ],
    "depth": 2
  }'
```

---

### Workbooks (`/workbooks`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/workbooks` | List workbooks |
| POST | `/workbooks` | Create workbook |
| GET | `/workbooks/templates` | List workbook templates |
| POST | `/workbooks/templates/{template_name}` | Create from template |
| GET | `/workbooks/{workbook_id}` | Get workbook |
| PATCH | `/workbooks/{workbook_id}` | Update workbook |
| DELETE | `/workbooks/{workbook_id}` | Delete workbook |
| POST | `/workbooks/{workbook_id}/clone` | Clone workbook |
| POST | `/workbooks/execute-tile` | Execute workbook tile query |

---

### Analytics (`/analytics`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/analytics/rules` | List detection rules |
| POST | `/analytics/rules` | Create detection rule |
| GET | `/analytics/rules/{rule_id}` | Get rule details |
| PATCH | `/analytics/rules/{rule_id}` | Update rule |
| DELETE | `/analytics/rules/{rule_id}` | Delete rule |
| POST | `/analytics/rules/{rule_id}/enable` | Enable rule |
| POST | `/analytics/rules/{rule_id}/disable` | Disable rule |
| GET | `/analytics/rules/{rule_id}/executions` | Get rule execution history |
| POST | `/analytics/rules/{rule_id}/run` | Manually run rule |
| POST | `/analytics/rules/{rule_id}/run-correlation` | Run correlation rule |
| POST | `/analytics/correlation/test` | Test correlation rule |
| GET | `/analytics/realtime/status` | Get realtime processor status |
| GET | `/analytics/realtime/streams` | Get event stream status |
| GET | `/analytics/correlation/templates` | List correlation templates |
| POST | `/analytics/correlation/templates/{template_name}/create` | Create rule from template |
| GET | `/analytics/stats` | Get analytics statistics |

---

### Alerts (`/alerts`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/alerts/` | List alerts |
| GET | `/alerts/{alert_id}` | Get alert details |
| GET | `/alerts/{alert_id}/events` | Get alert events |
| POST | `/alerts/{alert_id}/acknowledge` | Acknowledge alert |
| POST | `/alerts/{alert_id}/close` | Close alert |
| POST | `/alerts/{alert_id}/assign-case` | Assign alert to case |
| POST | `/alerts/bulk` | Bulk alert operations |
| DELETE | `/alerts/{alert_id}` | Delete alert |
| GET | `/alerts/stats/summary` | Get alert statistics |

---

### Data Connectors (`/connectors`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/connectors` | List connectors |
| POST | `/connectors` | Create connector |
| GET | `/connectors/{connector_id}` | Get connector details |
| PATCH | `/connectors/{connector_id}` | Update connector |
| DELETE | `/connectors/{connector_id}` | Delete connector |
| POST | `/connectors/{connector_id}/enable` | Enable connector |
| POST | `/connectors/{connector_id}/disable` | Disable connector |
| POST | `/connectors/{connector_id}/test` | Test connector connectivity |
| GET | `/connectors/{connector_id}/events` | Get connector events |
| GET | `/connectors/stats/overview` | Get connector statistics |

#### Connector Types

- `syslog` - Syslog receiver (TCP/UDP)
- `windows_event` - Windows Event collection via WinRM
- `cloud_trail` - AWS CloudTrail logs
- `azure_ad` - Azure AD audit logs
- `office_365` - Microsoft 365 logs
- `aws_s3` - AWS S3 bucket ingestion
- `beats` - Elastic Beats input
- `kafka` - Kafka consumer
- `webhook` - HTTP webhook receiver
- `api_polling` - API polling connector
- `file_upload` - Manual file upload
- `custom` - Custom connector

---

### Integrations (`/integrations`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/integrations/status` | Get all integrations status |
| GET | `/integrations/{integration_name}/status` | Get integration status |
| GET | `/integrations/{integration_name}/config` | Get integration config |
| POST | `/integrations/{integration_name}/test` | Test integration |
| POST | `/integrations/{integration_name}/reconnect` | Reconnect integration |

#### Available Integrations

- `velociraptor` - Endpoint collection and response
- `iris` - DFIR-IRIS case management
- `opencti` - Threat intelligence
- `shuffle` - SOAR workflow automation
- `timesketch` - Timeline analysis

---

### Enrichment (`/enrichment`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/enrichment/indicator` | Enrich single indicator |
| POST | `/enrichment/bulk` | Bulk enrich indicators |
| GET | `/enrichment/threat-actor/{name}` | Get threat actor info |
| GET | `/enrichment/threat-actors/search` | Search threat actors |
| GET | `/enrichment/campaign/{name}` | Get campaign info |
| GET | `/enrichment/campaigns/search` | Search campaigns |
| GET | `/enrichment/related/{indicator_type}/{value}` | Get related indicators |

#### Enrich Indicator

```bash
curl -X POST http://localhost:8000/api/v1/enrichment/indicator \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "indicator_type": "ip",
    "value": "203.0.113.50"
  }'
```

---

### Collection (`/collection`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/collection/endpoints` | List endpoints |
| GET | `/collection/endpoints/{client_id}` | Get endpoint details |
| GET | `/collection/endpoints/search/{query}` | Search endpoints |
| GET | `/collection/artifacts` | List available artifacts |
| POST | `/collection/collect` | Start collection job |
| GET | `/collection/jobs/{job_id}` | Get collection job status |
| GET | `/collection/jobs/{job_id}/results` | Get collection results |
| GET | `/collection/hunts` | List hunts |
| POST | `/collection/hunts` | Create hunt |
| POST | `/collection/hunts/{hunt_id}/start` | Start hunt |
| POST | `/collection/hunts/{hunt_id}/stop` | Stop hunt |
| GET | `/collection/hunts/{hunt_id}/results` | Get hunt results |
| POST | `/collection/response/isolate` | Isolate endpoint |
| POST | `/collection/response/unisolate` | Unisolate endpoint |
| POST | `/collection/response/quarantine-file` | Quarantine file |
| POST | `/collection/response/kill-process` | Kill process |

---

### Workflows (`/workflows`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/workflows/` | List workflows |
| GET | `/workflows/{workflow_id}` | Get workflow details |
| POST | `/workflows/trigger` | Trigger workflow |
| GET | `/workflows/executions` | List executions |
| GET | `/workflows/executions/{execution_id}` | Get execution details |
| POST | `/workflows/executions/{execution_id}/cancel` | Cancel execution |
| GET | `/workflows/approvals` | List pending approvals |
| POST | `/workflows/approvals/{approval_id}/approve` | Approve action |
| POST | `/workflows/approvals/{approval_id}/deny` | Deny action |
| POST | `/workflows/actions/isolate-host` | Quick action: Isolate host |
| POST | `/workflows/actions/block-ip` | Quick action: Block IP |
| POST | `/workflows/actions/disable-user` | Quick action: Disable user |

---

### RBAC (`/rbac`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/rbac/permissions` | List all permissions |
| GET | `/rbac/roles` | List all roles |
| GET | `/rbac/roles/{role_id}` | Get role details |
| POST | `/rbac/roles` | Create role |
| PATCH | `/rbac/roles/{role_id}` | Update role |
| DELETE | `/rbac/roles/{role_id}` | Delete role |
| GET | `/rbac/users/{user_id}/permissions` | Get user permissions |
| GET | `/rbac/users/me/permissions` | Get current user permissions |
| PUT | `/rbac/users/{user_id}/roles` | Assign roles to user |

---

### Admin (`/admin`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/admin/users` | List users |
| POST | `/admin/users` | Create user |
| PATCH | `/admin/users/{user_id}` | Update user |
| DELETE | `/admin/users/{user_id}` | Delete user |
| GET | `/admin/audit` | Get audit log |
| GET | `/admin/config` | Get system configuration |
| GET | `/admin/updates/check` | Check for updates |
| POST | `/admin/updates/apply` | Apply updates |
| GET | `/admin/health` | Get system health status |

---

### Notifications (`/notifications`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/notifications` | List notifications |
| GET | `/notifications/unread-count` | Get unread count |
| GET | `/notifications/{notification_id}` | Get notification |
| POST | `/notifications/{notification_id}/read` | Mark as read |
| POST | `/notifications/mark-read` | Mark multiple as read |
| POST | `/notifications/mark-all-read` | Mark all as read |
| DELETE | `/notifications/{notification_id}` | Delete notification |
| GET | `/notifications/preferences` | Get preferences |
| PATCH | `/notifications/preferences` | Update preferences |
| POST | `/notifications` | Create notification (admin) |

---

### WebSocket (`/ws`)

| Endpoint | Description |
|----------|-------------|
| `/ws/events` | Real-time event stream |
| `/ws/alerts` | Real-time alert notifications |
| `/ws/stats` | WebSocket connection statistics |

#### WebSocket Connection

```javascript
const ws = new WebSocket('ws://localhost:8000/api/v1/ws/events?token=' + accessToken);

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Event received:', data);
};
```

---

## Common Response Formats

### Pagination

List endpoints support pagination:

```json
{
  "items": [...],
  "total": 150,
  "page": 1,
  "page_size": 50,
  "total_pages": 3
}
```

**Query Parameters:**
- `page` - Page number (default: 1)
- `page_size` - Items per page (default: 50, max: 200)

### Error Response

```json
{
  "detail": "Error message describing what went wrong"
}
```

**HTTP Status Codes:**
- `400` - Bad Request (validation error)
- `401` - Unauthorized (missing/invalid token)
- `403` - Forbidden (insufficient permissions)
- `404` - Not Found
- `422` - Unprocessable Entity (validation failed)
- `500` - Internal Server Error

---

## Rate Limiting

API requests are rate limited per user:
- Default: 100 requests per minute
- Search endpoints: 30 requests per minute
- Bulk operations: 10 requests per minute

Rate limit headers:
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1706270400
```

---

## SDK Examples

### Python

```python
import httpx

class EleanorClient:
    def __init__(self, base_url: str, token: str):
        self.base_url = base_url
        self.headers = {"Authorization": f"Bearer {token}"}

    def list_cases(self, page: int = 1) -> dict:
        response = httpx.get(
            f"{self.base_url}/api/v1/cases",
            headers=self.headers,
            params={"page": page}
        )
        response.raise_for_status()
        return response.json()

    def search_kql(self, query: str, index: str = "eleanor-events-*") -> dict:
        response = httpx.post(
            f"{self.base_url}/api/v1/search/kql",
            headers=self.headers,
            json={"query": query, "index": index}
        )
        response.raise_for_status()
        return response.json()

# Usage
client = EleanorClient("http://localhost:8000", "your-token")
cases = client.list_cases()
results = client.search_kql("process.name:powershell.exe")
```

### curl

```bash
# Login
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -d "username=admin&password=secret" | jq -r '.access_token')

# List cases
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v1/cases

# Search events
curl -X POST http://localhost:8000/api/v1/search/kql \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "event.action:process_created", "size": 10}'
```
