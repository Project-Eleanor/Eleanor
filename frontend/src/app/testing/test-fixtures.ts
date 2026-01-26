/**
 * Test fixtures providing mock data for unit tests.
 * These fixtures match the Eleanor API response schemas.
 */
import {
  Case,
  CaseListResponse,
  CaseStatus,
  Severity,
  Priority,
  TimelineEvent,
} from '../shared/models/case.model';
import {
  GraphData,
  GraphNode,
  GraphEdge,
  SavedGraph,
  GraphDefinition,
  GraphConfig,
} from '../shared/models/graph.model';
import {
  SearchResponse,
  SearchResult,
  SavedQuery,
} from '../shared/models/search.model';
import {
  Workbook,
  WorkbookDefinition,
  TileDefinition,
} from '../shared/models/workbook.model';
import {
  Entity,
  EntityType,
  EntityEvent,
} from '../shared/models/entity.model';

// ============================================================================
// Case Fixtures
// ============================================================================

export const mockCase: Case = {
  id: 'case-001',
  case_number: 'ELEANOR-2025-0001',
  title: 'Test Investigation Case',
  description: 'A sample case for testing purposes',
  severity: 'high',
  priority: 'P2',
  status: 'in_progress',
  assignee_id: 'user-001',
  assignee_name: 'Test User',
  created_by: 'admin-001',
  created_by_name: 'Admin User',
  created_at: '2025-01-15T10:00:00Z',
  updated_at: '2025-01-20T15:30:00Z',
  closed_at: null,
  tags: ['malware', 'incident-response'],
  mitre_tactics: ['TA0001', 'TA0003'],
  mitre_techniques: ['T1059', 'T1105'],
  metadata: {},
  evidence_count: 5,
};

export const mockCaseList: CaseListResponse = {
  items: [
    mockCase,
    {
      ...mockCase,
      id: 'case-002',
      case_number: 'ELEANOR-2025-0002',
      title: 'Secondary Test Case',
      status: 'open',
      severity: 'medium',
    },
    {
      ...mockCase,
      id: 'case-003',
      case_number: 'ELEANOR-2025-0003',
      title: 'Closed Investigation',
      status: 'closed',
      severity: 'low',
      closed_at: '2025-01-18T12:00:00Z',
    },
  ],
  total: 3,
  page: 1,
  page_size: 20,
  pages: 1,
};

export const mockTimelineEvent: TimelineEvent = {
  id: 'event-001',
  timestamp: '2025-01-15T10:30:00Z',
  title: 'Initial Detection',
  description: 'Suspicious process execution detected',
  category: 'detection',
  source: 'EDR',
  entities: { process: 'powershell.exe', user: 'testuser' },
  evidence_id: 'evidence-001',
  created_by: 'system',
  tags: ['automated'],
};

// ============================================================================
// Graph Fixtures
// ============================================================================

export const mockGraphNodes: GraphNode[] = [
  {
    id: 'node-host-1',
    label: 'WORKSTATION-01',
    type: 'host',
    event_count: 150,
    first_seen: '2025-01-10T08:00:00Z',
    last_seen: '2025-01-20T16:00:00Z',
    risk_score: 75,
  },
  {
    id: 'node-user-1',
    label: 'john.doe',
    type: 'user',
    event_count: 80,
    first_seen: '2025-01-10T08:15:00Z',
    last_seen: '2025-01-20T15:45:00Z',
  },
  {
    id: 'node-ip-1',
    label: '192.168.1.100',
    type: 'ip',
    event_count: 45,
    first_seen: '2025-01-12T09:00:00Z',
    last_seen: '2025-01-19T11:30:00Z',
  },
  {
    id: 'node-process-1',
    label: 'powershell.exe',
    type: 'process',
    event_count: 25,
    risk_score: 85,
  },
  {
    id: 'node-file-1',
    label: 'malware.exe',
    type: 'file',
    event_count: 5,
    risk_score: 95,
  },
];

export const mockGraphEdges: GraphEdge[] = [
  {
    source: 'node-user-1',
    target: 'node-host-1',
    relationship: 'logged_into',
    weight: 10,
    timestamp: '2025-01-15T08:00:00Z',
  },
  {
    source: 'node-host-1',
    target: 'node-ip-1',
    relationship: 'connected_to',
    weight: 5,
  },
  {
    source: 'node-host-1',
    target: 'node-process-1',
    relationship: 'executed',
    weight: 8,
  },
  {
    source: 'node-process-1',
    target: 'node-file-1',
    relationship: 'wrote',
    weight: 1,
  },
];

export const mockGraphData: GraphData = {
  nodes: mockGraphNodes,
  edges: mockGraphEdges,
  metadata: {
    case_id: 'case-001',
    total_nodes: 5,
    total_edges: 4,
    truncated: false,
  },
};

export const mockSavedGraph: SavedGraph = {
  id: 'graph-001',
  name: 'Investigation Overview',
  description: 'Main attack chain visualization',
  case_id: 'case-001',
  definition: {
    nodes: mockGraphNodes,
    edges: mockGraphEdges,
    positions: {
      'node-host-1': { x: 100, y: 100 },
      'node-user-1': { x: 200, y: 50 },
      'node-ip-1': { x: 200, y: 150 },
      'node-process-1': { x: 300, y: 100 },
      'node-file-1': { x: 400, y: 100 },
    },
    zoom: 1.0,
    pan: { x: 0, y: 0 },
  },
  config: {
    layout: 'dagre',
    showLabels: true,
    nodeSize: 30,
    edgeWidth: 2,
  },
  created_by: 'user-001',
  created_at: '2025-01-16T10:00:00Z',
  updated_at: '2025-01-18T14:30:00Z',
};

// ============================================================================
// Search Fixtures
// ============================================================================

export const mockSearchResult: SearchResult = {
  id: 'doc-001',
  index: 'eleanor-events-2025.01',
  score: 1.5,
  source: {
    '@timestamp': '2025-01-15T10:30:00Z',
    'event.category': 'process',
    'event.type': 'start',
    'process.name': 'powershell.exe',
    'process.command_line': 'powershell.exe -enc SGVsbG8gV29ybGQ=',
    'host.name': 'WORKSTATION-01',
    'user.name': 'john.doe',
  },
  highlight: {
    'process.name': ['<em>powershell</em>.exe'],
  },
};

export const mockSearchResponse: SearchResponse = {
  total: 100,
  hits: [
    mockSearchResult,
    {
      ...mockSearchResult,
      id: 'doc-002',
      source: {
        '@timestamp': '2025-01-15T10:31:00Z',
        'event.category': 'network',
        'event.type': 'connection',
        'destination.ip': '192.168.1.100',
        'source.ip': '10.0.0.50',
        'host.name': 'WORKSTATION-01',
      },
    },
  ],
  took: 15,
  aggregations: {
    event_types: {
      buckets: [
        { key: 'process', doc_count: 50 },
        { key: 'network', doc_count: 30 },
        { key: 'file', doc_count: 20 },
      ],
    },
  },
};

export const mockSavedQuery: SavedQuery = {
  id: 'query-001',
  name: 'PowerShell Execution',
  description: 'Find all PowerShell process executions',
  query: 'process.name:powershell.exe',
  query_type: 'kql',
  is_public: true,
  created_by: 'user-001',
  created_at: '2025-01-10T09:00:00Z',
  updated_at: '2025-01-10T09:00:00Z',
  tags: ['hunting', 'powershell'],
};

// ============================================================================
// Workbook Fixtures
// ============================================================================

export const mockTile: TileDefinition = {
  id: 'tile-001',
  type: 'table',
  title: 'Recent Events',
  position: { x: 0, y: 0, width: 6, height: 4 },
  config: {
    query: 'FROM eleanor-events-* | LIMIT 100',
    columns: ['@timestamp', 'event.category', 'host.name', 'user.name'],
    page_size: 20,
  },
};

export const mockWorkbookDefinition: WorkbookDefinition = {
  tiles: [
    mockTile,
    {
      id: 'tile-002',
      type: 'metric',
      title: 'Total Events',
      position: { x: 6, y: 0, width: 3, height: 2 },
      config: {
        query: 'FROM eleanor-events-* | STATS COUNT(*)',
        aggregation: 'count',
      },
    },
    {
      id: 'tile-003',
      type: 'chart',
      title: 'Events by Type',
      position: { x: 0, y: 4, width: 6, height: 4 },
      config: {
        query: 'FROM eleanor-events-* | STATS COUNT(*) BY event.category',
        chart_type: 'bar',
        x_field: 'event.category',
        y_field: 'count',
      },
    },
  ],
  layout: {
    columns: 12,
    row_height: 80,
  },
  variables: {
    case_id: 'case-001',
  },
};

export const mockWorkbook: Workbook = {
  id: 'wb-001',
  name: 'Investigation Dashboard',
  description: 'Main investigation workbook',
  definition: mockWorkbookDefinition,
  is_public: false,
  created_by: 'user-001',
  created_at: '2025-01-12T10:00:00Z',
  updated_at: '2025-01-18T16:00:00Z',
};

export const mockWorkbookList = {
  items: [
    mockWorkbook,
    {
      ...mockWorkbook,
      id: 'wb-002',
      name: 'Threat Hunting Workbook',
      is_public: true,
    },
  ],
  total: 2,
  page: 1,
  page_size: 20,
  pages: 1,
};

// ============================================================================
// Entity Fixtures
// ============================================================================

export const mockEntity: Entity = {
  id: 'entity-001',
  entity_type: 'host',
  value: 'WORKSTATION-01',
  first_seen: '2025-01-01T00:00:00Z',
  last_seen: '2025-01-20T16:00:00Z',
  attributes: {
    os: 'Windows 10',
    domain: 'CORP',
  },
  enrichment: null,
  related_cases: ['case-001', 'case-002'],
  risk_score: 75,
  tags: ['critical-asset', 'executive'],
};

export const mockEntityEvent: EntityEvent = {
  id: 'entity-event-001',
  timestamp: '2025-01-15T10:30:00Z',
  event_type: 'process_start',
  message: 'Process powershell.exe started',
  case_id: 'case-001',
};

// ============================================================================
// Factory Functions
// ============================================================================

/**
 * Create a case with custom overrides.
 */
export function createMockCase(overrides: Partial<Case> = {}): Case {
  return { ...mockCase, ...overrides };
}

/**
 * Create a graph node with custom overrides.
 */
export function createMockGraphNode(overrides: Partial<GraphNode> = {}): GraphNode {
  return { ...mockGraphNodes[0], ...overrides };
}

/**
 * Create a search result with custom source data.
 */
export function createMockSearchResult(source: Record<string, unknown>): SearchResult {
  return {
    id: `doc-${Date.now()}`,
    index: 'eleanor-events-2025.01',
    score: 1.0,
    source,
  };
}

/**
 * Create a workbook with custom tiles.
 */
export function createMockWorkbook(tiles: TileDefinition[]): Workbook {
  return {
    ...mockWorkbook,
    id: `wb-${Date.now()}`,
    definition: {
      ...mockWorkbookDefinition,
      tiles,
    },
  };
}

/**
 * Create an entity with custom type and value.
 */
export function createMockEntity(type: EntityType, value: string): Entity {
  return {
    ...mockEntity,
    id: `entity-${Date.now()}`,
    entity_type: type,
    value,
  };
}
