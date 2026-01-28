import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';

export type ConnectorType =
  | 'syslog'
  | 'windows_event'
  | 'cloud_trail'
  | 'azure_ad'
  | 'office_365'
  | 'aws_s3'
  | 'beats'
  | 'kafka'
  | 'webhook'
  | 'api_polling'
  | 'file_upload'
  | 'custom'
  // Phase 4 connector types
  | 'gcp_cloud_logging'
  | 'aws_security_hub'
  | 'azure_event_hub'
  | 'fluentd'
  | 'wef'
  | 'okta'
  | 'crowdstrike_fdr'
  | 'splunk_hec';

export type ConnectorStatus = 'enabled' | 'disabled' | 'error' | 'configuring';
export type ConnectorHealth = 'healthy' | 'degraded' | 'unhealthy' | 'unknown';

export interface DataConnector {
  id: string;
  name: string;
  description: string | null;
  connector_type: ConnectorType;
  status: ConnectorStatus;
  health: ConnectorHealth;
  config: Record<string, unknown>;
  target_index: string | null;
  data_type: string | null;
  parser_config: Record<string, unknown>;
  include_filters: Record<string, unknown>;
  exclude_filters: Record<string, unknown>;
  polling_interval: number | null;
  events_received: number;
  events_processed: number;
  events_failed: number;
  bytes_received: number;
  last_event_at: string | null;
  last_error_at: string | null;
  last_error_message: string | null;
  last_health_check_at: string | null;
  tags: Record<string, string>;
  created_by: string | null;
  created_at: string;
  updated_at: string;
}

export interface ConnectorCreate {
  name: string;
  description?: string;
  connector_type: ConnectorType;
  config?: Record<string, unknown>;
  target_index?: string;
  data_type?: string;
  parser_config?: Record<string, unknown>;
  include_filters?: Record<string, unknown>;
  exclude_filters?: Record<string, unknown>;
  polling_interval?: number;
  tags?: Record<string, string>;
}

export interface ConnectorListResponse {
  items: DataConnector[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface ConnectorEvent {
  id: string;
  connector_id: string;
  event_type: string;
  message: string | null;
  details: Record<string, unknown>;
  created_at: string;
}

export interface TestResult {
  success: boolean;
  message: string;
  latency_ms: number | null;
  details: Record<string, unknown>;
}

export interface ConnectorsStats {
  total_connectors: number;
  by_status: Record<string, number>;
  by_health: Record<string, number>;
  by_type: Record<string, number>;
  total_events_received: number;
  total_events_processed: number;
  total_events_failed: number;
  total_bytes_received: number;
}

@Injectable({
  providedIn: 'root'
})
export class ConnectorsService {
  private apiUrl = `${environment.apiUrl}/connectors`;

  constructor(private http: HttpClient) {}

  list(params?: {
    type?: ConnectorType;
    status?: ConnectorStatus;
    health?: ConnectorHealth;
    search?: string;
    page?: number;
    page_size?: number;
  }): Observable<ConnectorListResponse> {
    let httpParams = new HttpParams();

    if (params) {
      if (params.type) httpParams = httpParams.set('type', params.type);
      if (params.status) httpParams = httpParams.set('status', params.status);
      if (params.health) httpParams = httpParams.set('health', params.health);
      if (params.search) httpParams = httpParams.set('search', params.search);
      if (params.page) httpParams = httpParams.set('page', params.page.toString());
      if (params.page_size) httpParams = httpParams.set('page_size', params.page_size.toString());
    }

    return this.http.get<ConnectorListResponse>(this.apiUrl, { params: httpParams });
  }

  get(id: string): Observable<DataConnector> {
    return this.http.get<DataConnector>(`${this.apiUrl}/${id}`);
  }

  create(connector: ConnectorCreate): Observable<DataConnector> {
    return this.http.post<DataConnector>(this.apiUrl, connector);
  }

  update(id: string, updates: Partial<ConnectorCreate>): Observable<DataConnector> {
    return this.http.patch<DataConnector>(`${this.apiUrl}/${id}`, updates);
  }

  delete(id: string): Observable<void> {
    return this.http.delete<void>(`${this.apiUrl}/${id}`);
  }

  enable(id: string): Observable<DataConnector> {
    return this.http.post<DataConnector>(`${this.apiUrl}/${id}/enable`, {});
  }

  disable(id: string): Observable<DataConnector> {
    return this.http.post<DataConnector>(`${this.apiUrl}/${id}/disable`, {});
  }

  test(id: string): Observable<TestResult> {
    return this.http.post<TestResult>(`${this.apiUrl}/${id}/test`, {});
  }

  getEvents(id: string, limit?: number): Observable<ConnectorEvent[]> {
    let params = new HttpParams();
    if (limit) params = params.set('limit', limit.toString());

    return this.http.get<ConnectorEvent[]>(`${this.apiUrl}/${id}/events`, { params });
  }

  getStats(): Observable<ConnectorsStats> {
    return this.http.get<ConnectorsStats>(`${this.apiUrl}/stats/overview`);
  }
}
