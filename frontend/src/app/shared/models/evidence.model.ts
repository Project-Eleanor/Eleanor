export type EvidenceType = 'file' | 'image' | 'log' | 'memory' | 'network' | 'registry' | 'artifact' | 'other';
export type EvidenceStatus = 'pending' | 'processing' | 'analyzed' | 'archived';

export interface Evidence {
  id: string;
  case_id: string;
  filename: string;
  original_filename: string;
  file_path: string;
  file_size: number;
  file_hash_md5: string | null;
  file_hash_sha256: string | null;
  mime_type: string | null;
  evidence_type: EvidenceType;
  status: EvidenceStatus;
  description: string | null;
  source: string | null;
  collected_at: string | null;
  collected_by: string | null;
  chain_of_custody: CustodyEntry[];
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface CustodyEntry {
  timestamp: string;
  action: string;
  user: string;
  notes: string | null;
}

export interface EvidenceCreate {
  case_id: string;
  filename: string;
  evidence_type?: EvidenceType;
  description?: string;
  source?: string;
  collected_at?: string;
  metadata?: Record<string, unknown>;
}

export interface EvidenceListResponse {
  items: Evidence[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}
