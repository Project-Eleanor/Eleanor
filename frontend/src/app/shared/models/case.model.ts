export type Severity = 'critical' | 'high' | 'medium' | 'low' | 'info';
export type Priority = 'P1' | 'P2' | 'P3' | 'P4' | 'P5';
export type CaseStatus = 'open' | 'in_progress' | 'pending' | 'closed';

export interface Case {
  id: string;
  case_number: string;
  title: string;
  description: string | null;
  severity: Severity;
  priority: Priority;
  status: CaseStatus;
  assignee_id: string | null;
  assignee_name: string | null;
  created_by: string | null;
  created_by_name: string | null;
  created_at: string;
  updated_at: string;
  closed_at: string | null;
  tags: string[];
  mitre_tactics: string[];
  mitre_techniques: string[];
  metadata: Record<string, unknown>;
  evidence_count: number;
}

export interface CaseCreate {
  title: string;
  description?: string;
  severity?: Severity;
  priority?: Priority;
  assignee_id?: string;
  tags?: string[];
  mitre_tactics?: string[];
  mitre_techniques?: string[];
  metadata?: Record<string, unknown>;
}

export interface CaseUpdate {
  title?: string;
  description?: string;
  severity?: Severity;
  priority?: Priority;
  status?: CaseStatus;
  assignee_id?: string;
  tags?: string[];
  mitre_tactics?: string[];
  mitre_techniques?: string[];
  metadata?: Record<string, unknown>;
}

export interface CaseListResponse {
  items: Case[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface TimelineEvent {
  id: string;
  timestamp: string;
  title: string;
  description: string | null;
  category: string | null;
  source: string | null;
  entities: Record<string, unknown>;
  evidence_id: string | null;
  created_by: string | null;
  tags: string[];
}

export interface TimelineEventCreate {
  timestamp: string;
  title: string;
  description?: string;
  category?: string;
  source?: string;
  entities?: Record<string, unknown>;
  evidence_id?: string;
  tags?: string[];
}
