import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';

export type RuleSeverity = 'informational' | 'low' | 'medium' | 'high' | 'critical';
export type RuleStatus = 'enabled' | 'disabled' | 'testing';
export type RuleType = 'scheduled' | 'realtime' | 'threshold' | 'correlation';

export interface DetectionRule {
  id: string;
  name: string;
  description: string | null;
  rule_type: RuleType;
  severity: RuleSeverity;
  status: RuleStatus;
  query: string;
  query_language: string;
  indices: string[];
  schedule_interval: number | null;
  lookback_period: number | null;
  threshold_count: number | null;
  threshold_field: string | null;
  mitre_tactics: string[];
  mitre_techniques: string[];
  tags: string[];
  category: string | null;
  data_sources: string[];
  auto_create_incident: boolean;
  playbook_id: string | null;
  references: string[];
  custom_fields: Record<string, unknown>;
  created_by: string | null;
  created_at: string;
  updated_at: string;
  last_run_at: string | null;
  hit_count: number;
  false_positive_count: number;
}

export interface RuleCreate {
  name: string;
  description?: string;
  rule_type?: RuleType;
  severity?: RuleSeverity;
  query: string;
  query_language?: string;
  indices?: string[];
  schedule_interval?: number;
  lookback_period?: number;
  threshold_count?: number;
  threshold_field?: string;
  mitre_tactics?: string[];
  mitre_techniques?: string[];
  tags?: string[];
  category?: string;
  data_sources?: string[];
  auto_create_incident?: boolean;
  playbook_id?: string;
  references?: string[];
  custom_fields?: Record<string, unknown>;
}

export interface RuleListResponse {
  items: DetectionRule[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface RuleExecution {
  id: string;
  rule_id: string;
  started_at: string;
  completed_at: string | null;
  duration_ms: number | null;
  status: string;
  hits_count: number;
  events_scanned: number;
  error_message: string | null;
  incidents_created: number;
}

export interface AnalyticsStats {
  total_rules: number;
  by_status: Record<string, number>;
  by_severity: Record<string, number>;
  total_hits: number;
}

@Injectable({
  providedIn: 'root'
})
export class AnalyticsService {
  private apiUrl = `${environment.apiUrl}/analytics`;

  constructor(private http: HttpClient) {}

  listRules(params?: {
    status?: RuleStatus;
    severity?: RuleSeverity;
    rule_type?: RuleType;
    category?: string;
    search?: string;
    page?: number;
    page_size?: number;
  }): Observable<RuleListResponse> {
    let httpParams = new HttpParams();

    if (params) {
      if (params.status) httpParams = httpParams.set('status', params.status);
      if (params.severity) httpParams = httpParams.set('severity', params.severity);
      if (params.rule_type) httpParams = httpParams.set('rule_type', params.rule_type);
      if (params.category) httpParams = httpParams.set('category', params.category);
      if (params.search) httpParams = httpParams.set('search', params.search);
      if (params.page) httpParams = httpParams.set('page', params.page.toString());
      if (params.page_size) httpParams = httpParams.set('page_size', params.page_size.toString());
    }

    return this.http.get<RuleListResponse>(`${this.apiUrl}/rules`, { params: httpParams });
  }

  getRule(id: string): Observable<DetectionRule> {
    return this.http.get<DetectionRule>(`${this.apiUrl}/rules/${id}`);
  }

  createRule(rule: RuleCreate): Observable<DetectionRule> {
    return this.http.post<DetectionRule>(`${this.apiUrl}/rules`, rule);
  }

  updateRule(id: string, updates: Partial<RuleCreate>): Observable<DetectionRule> {
    return this.http.patch<DetectionRule>(`${this.apiUrl}/rules/${id}`, updates);
  }

  deleteRule(id: string): Observable<void> {
    return this.http.delete<void>(`${this.apiUrl}/rules/${id}`);
  }

  enableRule(id: string): Observable<DetectionRule> {
    return this.http.post<DetectionRule>(`${this.apiUrl}/rules/${id}/enable`, {});
  }

  disableRule(id: string): Observable<DetectionRule> {
    return this.http.post<DetectionRule>(`${this.apiUrl}/rules/${id}/disable`, {});
  }

  runRule(id: string): Observable<RuleExecution> {
    return this.http.post<RuleExecution>(`${this.apiUrl}/rules/${id}/run`, {});
  }

  getRuleExecutions(ruleId: string, limit?: number): Observable<RuleExecution[]> {
    let params = new HttpParams();
    if (limit) params = params.set('limit', limit.toString());

    return this.http.get<RuleExecution[]>(`${this.apiUrl}/rules/${ruleId}/executions`, { params });
  }

  getStats(): Observable<AnalyticsStats> {
    return this.http.get<AnalyticsStats>(`${this.apiUrl}/stats`);
  }
}
