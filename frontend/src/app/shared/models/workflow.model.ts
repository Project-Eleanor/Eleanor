export type WorkflowStatus = 'active' | 'inactive' | 'draft';
export type ExecutionStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled' | 'awaiting_approval';

export interface Workflow {
  id: string;
  name: string;
  description: string | null;
  category: string;
  trigger_type: 'manual' | 'automated' | 'scheduled';
  status: WorkflowStatus;
  requires_approval: boolean;
  parameters: WorkflowParameter[];
  actions: WorkflowAction[];
  created_by: string;
  created_at: string;
  updated_at: string;
}

export interface WorkflowParameter {
  name: string;
  type: 'string' | 'number' | 'boolean' | 'select' | 'entity';
  required: boolean;
  default_value: unknown;
  options?: string[];
  description: string | null;
}

export interface WorkflowAction {
  id: string;
  name: string;
  type: string;
  config: Record<string, unknown>;
  order: number;
}

export interface WorkflowExecution {
  id: string;
  workflow_id: string;
  workflow_name: string;
  status: ExecutionStatus;
  parameters: Record<string, unknown>;
  started_at: string;
  completed_at: string | null;
  started_by: string;
  approved_by: string | null;
  results: ExecutionResult[];
  error: string | null;
}

export interface ExecutionResult {
  action_id: string;
  action_name: string;
  status: 'success' | 'failed' | 'skipped';
  output: Record<string, unknown>;
  error: string | null;
  executed_at: string;
}

export interface WorkflowTrigger {
  workflow_id: string;
  parameters: Record<string, unknown>;
}

export interface ApprovalRequest {
  id: string;
  execution_id: string;
  workflow_name: string;
  requested_by: string;
  requested_at: string;
  parameters: Record<string, unknown>;
  status: 'pending' | 'approved' | 'rejected';
}
