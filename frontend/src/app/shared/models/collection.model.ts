export type EndpointStatus = 'online' | 'offline' | 'unknown';
export type CollectionStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';

export interface Endpoint {
  id: string;
  hostname: string;
  ip_address: string | null;
  os_type: string;
  os_version: string | null;
  agent_version: string | null;
  status: EndpointStatus;
  last_seen: string | null;
  labels: string[];
}

export interface EndpointListResponse {
  items: Endpoint[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface ArtifactDefinition {
  name: string;
  description: string;
  category: string;
  parameters: ArtifactParameter[];
}

export interface ArtifactParameter {
  name: string;
  type: string;
  description: string;
  required: boolean;
  default_value: unknown;
}

export interface Collection {
  id: string;
  name: string;
  description: string | null;
  artifact: string;
  parameters: Record<string, unknown>;
  targets: string[];
  status: CollectionStatus;
  started_at: string | null;
  completed_at: string | null;
  created_by: string;
  results_count: number;
}

export interface CollectionCreate {
  name: string;
  description?: string;
  artifact: string;
  parameters?: Record<string, unknown>;
  targets: string[];
}

export interface Hunt {
  id: string;
  name: string;
  description: string | null;
  artifact: string;
  parameters: Record<string, unknown>;
  status: CollectionStatus;
  started_at: string | null;
  completed_at: string | null;
  created_by: string;
  total_clients: number;
  completed_clients: number;
  results_count: number;
}

export interface HuntCreate {
  name: string;
  description?: string;
  artifact: string;
  parameters?: Record<string, unknown>;
  labels?: string[];
}
