/**
 * Workbook data models for dashboard visualizations.
 */

export type TileType = 'query' | 'chart' | 'table' | 'markdown' | 'metric' | 'timeline';
export type ChartType = 'line' | 'bar' | 'pie' | 'area';

export interface TilePosition {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface TileConfig {
  query?: string;
  chart_type?: ChartType;
  x_field?: string;
  y_field?: string;
  interval?: string;
  group_by?: string;
  split_by?: string;
  limit?: number;
  columns?: string[];
  page_size?: number;
  sort?: { field: string; order: 'asc' | 'desc' };
  content?: string;  // For markdown tiles
  aggregation?: 'count' | 'cardinality' | 'sum' | 'avg';
  field?: string;
  timestamp_field?: string;
  refresh_interval?: number;  // seconds
}

export interface TileDefinition {
  id: string;
  type: TileType;
  title: string;
  position: TilePosition;
  config: TileConfig;
}

export interface WorkbookDefinition {
  tiles: TileDefinition[];
  layout: {
    columns: number;
    row_height: number;
  };
  variables: Record<string, string>;
}

export interface Workbook {
  id: string;
  name: string;
  description?: string;
  definition: WorkbookDefinition;
  is_public: boolean;
  created_by?: string;
  created_at: string;
  updated_at: string;
}

export interface WorkbookCreate {
  name: string;
  description?: string;
  definition?: WorkbookDefinition;
  is_public?: boolean;
}

export interface WorkbookUpdate {
  name?: string;
  description?: string;
  definition?: WorkbookDefinition;
  is_public?: boolean;
}

export interface WorkbookTemplate {
  name: string;
  description: string;
  tile_count: number;
}

export interface TileExecuteRequest {
  tile_type: TileType;
  config: TileConfig;
  variables?: Record<string, string>;
  case_id?: string;
}

export interface TileExecuteResponse {
  data: any;
  metadata: Record<string, any>;
}

export interface MetricData {
  value: number;
}

export interface ChartData {
  key: string;
  count: number;
  split?: { key: string; count: number }[];
}

export interface TableData {
  [key: string]: any;
}

export interface TimelineData {
  timestamp: string;
  count: number;
}
