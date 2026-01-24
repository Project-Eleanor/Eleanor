export interface SearchQuery {
  query: string;
  index?: string;
  from?: number;
  size?: number;
  sort?: string;
  filters?: Record<string, unknown>;
}

export interface SearchResult {
  id: string;
  index: string;
  score: number;
  source: Record<string, unknown>;
  highlight?: Record<string, string[]>;
}

export interface SearchResponse {
  total: number;
  hits: SearchResult[];
  took: number;
  aggregations?: Record<string, unknown>;
}

export interface SavedQuery {
  id: string;
  name: string;
  description: string | null;
  query: string;
  query_type: 'esql' | 'kql' | 'lucene';
  is_public: boolean;
  created_by: string;
  created_at: string;
  updated_at: string;
  tags: string[];
}

export interface SavedQueryCreate {
  name: string;
  description?: string;
  query: string;
  query_type?: 'esql' | 'kql' | 'lucene';
  is_public?: boolean;
  tags?: string[];
}
