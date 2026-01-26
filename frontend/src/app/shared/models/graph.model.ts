/**
 * Graph data models for investigation visualizations.
 */

export type EntityType = 'host' | 'user' | 'ip' | 'process' | 'file' | 'domain';

export interface GraphNode {
  id: string;
  label: string;
  type: EntityType;
  event_count?: number;
  first_seen?: string;
  last_seen?: string;
  risk_score?: number;
}

export interface GraphEdge {
  source: string;
  target: string;
  relationship: string;
  weight?: number;
  timestamp?: string;
}

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
  metadata?: {
    case_id?: string;
    total_nodes?: number;
    total_edges?: number;
    truncated?: boolean;
    isolated?: boolean;
    subgraph?: boolean;
  };
}

export interface SavedGraph {
  id: string;
  name: string;
  description?: string;
  case_id: string;
  definition: GraphDefinition;
  config: GraphConfig;
  created_by?: string;
  created_at: string;
  updated_at: string;
}

export interface GraphDefinition {
  nodes: GraphNode[];
  edges: GraphEdge[];
  positions?: Record<string, { x: number; y: number }>;
  zoom?: number;
  pan?: { x: number; y: number };
}

export interface GraphConfig {
  layout?: string;
  showLabels?: boolean;
  nodeSize?: number;
  edgeWidth?: number;
  filters?: GraphFilters;
}

export interface GraphFilters {
  entityTypes?: EntityType[];
  minEventCount?: number;
  timeRange?: {
    start: string;
    end: string;
  };
}

export interface BuildGraphRequest {
  case_id: string;
  max_nodes?: number;
  entity_types?: EntityType[];
  time_start?: string;
  time_end?: string;
}

export interface ExpandNodeRequest {
  case_id: string;
  node_id: string;
  max_connections?: number;
}

export interface FindPathRequest {
  case_id: string;
  source_node: string;
  target_node: string;
  max_hops?: number;
}

export interface PathResult {
  found: boolean;
  path_nodes: string[];
  path_edges: GraphEdge[];
  hops: number;
}

export interface EntityRelationships {
  entity_id: string;
  entity_type: EntityType;
  entity_value: string;
  relationships: Record<string, RelatedEntity[]>;
  related_entities: GraphNode[];
}

export interface RelatedEntity {
  entity_id: string;
  entity_type: EntityType;
  entity_value: string;
  event_count: number;
}

// Cytoscape styling
export const NODE_COLORS: Record<EntityType, string> = {
  host: '#4CAF50',      // Green
  user: '#2196F3',      // Blue
  ip: '#FF9800',        // Orange
  process: '#9C27B0',   // Purple
  file: '#795548',      // Brown
  domain: '#00BCD4',    // Cyan
};

export const NODE_SHAPES: Record<EntityType, string> = {
  host: 'rectangle',
  user: 'ellipse',
  ip: 'diamond',
  process: 'hexagon',
  file: 'triangle',
  domain: 'round-rectangle',
};
