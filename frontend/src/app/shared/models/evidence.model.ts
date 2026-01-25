export type EvidenceType = 'disk_image' | 'memory' | 'logs' | 'triage' | 'pcap' | 'artifact' | 'document' | 'malware' | 'other';
export type EvidenceStatus = 'pending' | 'uploading' | 'processing' | 'ready' | 'failed' | 'quarantined';

export interface Evidence {
  id: string;
  case_id: string;
  filename: string;
  original_filename: string | null;
  file_size: number | null;
  md5: string | null;
  sha1: string | null;
  sha256: string | null;
  mime_type: string | null;
  evidence_type: EvidenceType;
  status: EvidenceStatus;
  description: string | null;
  source_host: string | null;
  collected_at: string | null;
  collected_by: string | null;
  uploaded_by: string | null;
  uploader_name: string | null;
  uploaded_at: string;
  metadata: Record<string, unknown>;
}

export interface CustodyEvent {
  id: string;
  evidence_id: string;
  action: string;
  actor_id: string | null;
  actor_name: string | null;
  ip_address: string | null;
  user_agent: string | null;
  details: Record<string, unknown>;
  created_at: string;
}

export interface EvidenceCreate {
  case_id: string;
  evidence_type?: EvidenceType;
  source_host?: string;
  collected_at?: string;
  collected_by?: string;
  description?: string;
  metadata?: Record<string, unknown>;
}

export interface EvidenceUpdate {
  evidence_type?: EvidenceType;
  status?: EvidenceStatus;
  description?: string;
  source_host?: string;
  collected_at?: string;
  collected_by?: string;
  metadata?: Record<string, unknown>;
}

export interface EvidenceListResponse {
  items: Evidence[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}
