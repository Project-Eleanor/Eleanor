import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../../environments/environment';

const API_URL = `${environment.apiUrl}/rules/builder`;

// Types
export interface PatternDefinition {
  type: string;
  name: string;
  description: string;
  use_cases: string[];
  required_config: string[];
  example_config: Record<string, any>;
}

export interface PatternsResponse {
  patterns: PatternDefinition[];
}

export interface AvailableField {
  path: string;
  type: 'string' | 'number' | 'boolean' | 'ip' | 'date' | 'keyword';
  description?: string;
  sample_values?: any[];
}

export interface FieldsResponse {
  fields: AvailableField[];
  index_patterns: string[];
}

export interface FieldCondition {
  field: string;
  operator: string;
  value: any;
  negate?: boolean;
}

export interface EventDefinition {
  id: string;
  name: string;
  description?: string;
  conditions: FieldCondition[];
  raw_query?: string;
  indices?: string[];
}

export interface JoinField {
  field: string;
  alias?: string;
}

export interface ThresholdCondition {
  event_id: string;
  operator: string;
  count: number;
}

export interface SequenceConfig {
  order: string[];
  strict_order?: boolean;
}

export interface TemporalJoinConfig {
  max_span: string;
  require_all?: boolean;
}

export interface AggregationConfig {
  group_by: string[];
  having: ThresholdCondition[];
}

export interface SpikeConfig {
  field: string;
  baseline_window: string;
  spike_window: string;
  spike_threshold: number;
  min_baseline: number;
}

export interface RuleBuilderConfig {
  pattern_type: string;
  window: string;
  events: EventDefinition[];
  join_on: JoinField[];
  thresholds: ThresholdCondition[];
  sequence?: SequenceConfig;
  temporal_join?: TemporalJoinConfig;
  aggregation?: AggregationConfig;
  spike?: SpikeConfig;
  realtime?: boolean;
}

export interface ValidationError {
  field: string;
  message: string;
  severity: 'error' | 'warning' | 'info';
}

export interface ValidationResult {
  valid: boolean;
  errors: ValidationError[];
  warnings: ValidationError[];
  generated_config?: Record<string, any>;
}

export interface EventMatch {
  timestamp: string;
  event_id: string;
  entity_key?: string;
  document: Record<string, any>;
}

export interface CorrelationMatch {
  entity_key: string;
  event_counts: Record<string, number>;
  first_event_time: string;
  last_event_time: string;
  total_events: number;
  sample_events: EventMatch[];
}

export interface PreviewRequest {
  config: RuleBuilderConfig;
  time_range: string;
  limit: number;
}

export interface PreviewResult {
  total_matches: number;
  matches: CorrelationMatch[];
  events_scanned: number;
  duration_ms: number;
  time_range_start: string;
  time_range_end: string;
}

export interface TestRequest {
  config: RuleBuilderConfig;
  start_time: string;
  end_time: string;
}

export interface TestResult {
  total_matches: number;
  matches_by_hour: Record<string, number>;
  top_entities: Array<{ entity: string; count: number }>;
  sample_matches: CorrelationMatch[];
  estimated_alerts_per_day: number;
  duration_ms: number;
}

export interface SigmaImportRequest {
  sigma_yaml: string;
  convert_to_correlation?: boolean;
}

export interface SigmaImportResult {
  success: boolean;
  rule_name?: string;
  detection_rule?: Record<string, any>;
  correlation_config?: Record<string, any>;
  warnings: string[];
  errors: string[];
}

@Injectable({
  providedIn: 'root'
})
export class RuleBuilderService {
  constructor(private http: HttpClient) {}

  getPatterns(): Observable<PatternsResponse> {
    return this.http.get<PatternsResponse>(`${API_URL}/patterns`);
  }

  getFields(indexPattern?: string): Observable<FieldsResponse> {
    const params = indexPattern ? { index_pattern: indexPattern } : {};
    return this.http.get<FieldsResponse>(`${API_URL}/fields`, { params });
  }

  validate(config: RuleBuilderConfig): Observable<ValidationResult> {
    return this.http.post<ValidationResult>(`${API_URL}/validate`, config);
  }

  preview(request: PreviewRequest): Observable<PreviewResult> {
    return this.http.post<PreviewResult>(`${API_URL}/preview`, request);
  }

  test(request: TestRequest): Observable<TestResult> {
    return this.http.post<TestResult>(`${API_URL}/test`, request);
  }

  importSigma(request: SigmaImportRequest): Observable<SigmaImportResult> {
    return this.http.post<SigmaImportResult>(`${API_URL}/import/sigma`, request);
  }
}
