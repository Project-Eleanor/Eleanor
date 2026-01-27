# Eleanor DFIR Platform - Quick Start Guide

Get started with Eleanor by following this end-to-end investigation workflow.

## Prerequisites

- Eleanor deployed and accessible
- Admin credentials
- (Optional) Velociraptor connected for endpoint collection
- (Optional) Test data or evidence to import

## 1. Login & Dashboard

### First Login

1. Navigate to `https://your-eleanor-instance`
2. Login with your credentials
3. Complete any first-run prompts

### Dashboard Overview

The main dashboard shows:
- **Active Cases**: Current investigations
- **Recent Alerts**: Detection engine findings
- **System Health**: Integration status
- **Quick Actions**: Common tasks

## 2. Create a Case

Every investigation starts with a case.

### Create New Case

1. Click **Cases** → **New Case**
2. Fill in case details:
   - **Title**: "Suspicious PowerShell Activity - WS001"
   - **Description**: Brief summary of the incident
   - **Severity**: Medium/High/Critical
   - **Assignee**: Select investigator
3. Click **Create Case**

### Add Case Tags

Add MITRE ATT&CK tags for correlation:
- Click **Add Tag**
- Search for techniques (e.g., T1059.001 - PowerShell)
- Tags enable correlation across cases

## 3. Collect Evidence

### From Velociraptor (Live Collection)

1. Go to **Collection** → **Endpoints**
2. Find target endpoint (search by hostname/IP)
3. Click endpoint → **Collect Artifact**
4. Select artifacts:
   - `Windows.KapeFiles.Targets` - Comprehensive triage
   - `Windows.EventLogs.Evtx` - Event logs
   - `Windows.System.Pslist` - Process list
5. Click **Collect** → link to case

### Upload Evidence Files

1. Go to **Evidence** → **Upload**
2. Drag files or click to browse:
   - Disk images (.E01, .dd, .vmdk)
   - Memory dumps (.raw, .dmp)
   - Log files (.evtx, .log)
   - Triage packages (.zip)
3. Select evidence type and case
4. Click **Upload**

### Parsing

Eleanor automatically parses uploaded evidence:
- Event logs → Timeline events
- Registry hives → Configuration data
- Browser artifacts → Web history
- Prefetch → Program execution

Monitor parsing at **Evidence** → **Processing Jobs**

## 4. Hunt for Threats

### ES|QL Query Console

1. Go to **Hunting** → **Console**
2. Write queries in ES|QL syntax:

```esql
// Find PowerShell execution
FROM eleanor-events-*
| WHERE process.name == "powershell.exe"
| WHERE @timestamp > NOW() - 7 days
| STATS count = COUNT(*) BY host.name, user.name
| SORT count DESC
```

```esql
// Detect encoded commands
FROM eleanor-events-*
| WHERE process.command_line LIKE "*-enc*" OR process.command_line LIKE "*-encoded*"
| KEEP @timestamp, host.name, user.name, process.command_line
| SORT @timestamp DESC
```

3. Click **Execute**
4. Review results
5. Save useful queries with **Save Query**

### Visual Query Builder

For complex queries without ES|QL:

1. Click **Query Builder** tab
2. Add conditions:
   - Event Type: Process Creation
   - Process Name: contains "powershell"
   - Time Range: Last 24 hours
3. Click **Execute**

### Saved Queries

Access pre-built detection queries:
- **Detection** → **Queries**
- Browse by category (Execution, Persistence, etc.)
- One-click execute

## 5. Investigate Entities

### Entity Profile

Click any entity (host, user, IP) to view:
- **Timeline**: All related events
- **Related Cases**: Previous investigations
- **Threat Intel**: Reputation data
- **Connections**: Network activity

### Entity Enrichment

1. Click entity (e.g., IP address)
2. View **Threat Intel** tab
3. See OpenCTI enrichment:
   - Risk score
   - Known indicators
   - Threat actor associations
   - MITRE ATT&CK mapping

## 6. Build Timeline

### Automatic Timeline

Eleanor automatically builds timelines from parsed evidence.

1. Go to **Timeline** in your case
2. View chronological events
3. Filter by:
   - Source type
   - Entity
   - Time range
   - Tags

### Manual Timeline Events

Add investigator notes to timeline:

1. Click **Add Event**
2. Enter:
   - Timestamp
   - Description
   - Category (e.g., Initial Access, Execution)
   - Related entities
3. Click **Save**

### Timesketch Integration

For advanced timeline analysis:
1. Click **Export to Timesketch**
2. Open in Timesketch for:
   - Multi-timeline correlation
   - Event tagging
   - Collaborative annotation

## 7. Visualize Investigation

### Investigation Graph

1. Go to **Graph** in your case
2. View entity relationships:
   - Hosts connected to IPs
   - Users on hosts
   - Files on systems
3. Click nodes to:
   - View details
   - Expand connections
   - Add to timeline

### MITRE ATT&CK Navigator

1. Go to **MITRE** → **Navigator**
2. View technique coverage:
   - Highlighted: Observed in this case
   - Heat map: Frequency across cases
3. Click technique for related events

## 8. Response Actions

### Isolate Compromised Host

1. Go to **Response** → **Endpoints**
2. Find compromised host
3. Click **Isolate**
4. Enter reason (required for audit)
5. Confirm action

Host isolation:
- Blocks all network except management
- Maintains Velociraptor connection
- Logged in case timeline

### Release Host

After remediation:
1. Go to **Response** → **Endpoints**
2. Find isolated host
3. Click **Release**
4. Document remediation performed

### Other Actions

- **Kill Process**: Terminate malicious process
- **Quarantine File**: Move file to quarantine
- **Block IP**: Add to firewall (via Shuffle)
- **Disable User**: Lock compromised account (via Shuffle)

## 9. Document Findings

### Case Notes

1. Open case → **Notes**
2. Click **Add Note**
3. Write findings with Markdown:
   ```markdown
   ## Initial Access

   PowerShell execution from phishing document detected on WS001.

   **IOCs:**
   - C2: 192.168.1.100
   - File hash: abc123...

   **MITRE:** T1566.001, T1059.001
   ```

### Add IOCs

1. Case → **IOCs**
2. Click **Add IOC**
3. Enter indicator:
   - Type: IP, Domain, Hash, etc.
   - Value: 192.168.1.100
   - TLP: Amber
   - Tags: C2, Cobalt Strike

IOCs are:
- Synced to IRIS case
- Checked against OpenCTI
- Available for hunting

## 10. Generate Reports

### Quick Report

1. Case → **Reports** → **Generate**
2. Select template:
   - Executive Summary
   - Technical Report
   - IOC Report
3. Choose format (PDF, DOCX, HTML)
4. Click **Generate**

### Report Contents

Auto-generated sections:
- Case summary
- Timeline highlights
- IOC list
- MITRE ATT&CK mapping
- Evidence inventory
- Response actions taken

## 11. Close Case

### Case Resolution

1. Case → **Status** → **Close Case**
2. Select resolution:
   - True Positive - Confirmed
   - True Positive - Contained
   - False Positive
   - Benign Activity
3. Add closing notes
4. Click **Close**

### Post-Incident

After closing:
- Case archived for reference
- IOCs remain in threat intel
- Detection rules updated
- Lessons learned documented

## Next Steps

- [Configure Detection Rules](detection-rules.md)
- [Set Up Playbooks](playbooks.md)
- [Integration Guide](integrations.md)
- [Advanced Hunting](hunting-guide.md)
