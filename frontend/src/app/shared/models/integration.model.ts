export type IntegrationStatusType = 'connected' | 'disconnected' | 'error' | 'configuring';

export interface IntegrationStatus {
  name: string;
  description: string;
  status: IntegrationStatusType;
  enabled: boolean;
  version: string | null;
  message: string | null;
  last_check: string | null;
  details: Record<string, unknown>;
}

export interface IntegrationsStatusResponse {
  integrations: IntegrationStatus[];
  summary: Record<string, number>;
}

export interface IntegrationConfigResponse {
  name: string;
  config: Record<string, unknown>;
}

export interface TestIntegrationResponse {
  success: boolean;
  message: string;
  status: string;
  version?: string;
  details?: Record<string, unknown>;
}
