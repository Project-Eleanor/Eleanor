import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import { IOC, EntityEnrichment } from '../../shared/models';

export interface EnrichmentResult {
  indicator: string;
  indicator_type: string;
  sources: EnrichmentSource[];
  summary: EnrichmentSummary;
}

export interface EnrichmentSource {
  name: string;
  data: Record<string, unknown>;
  enriched_at: string;
}

export interface EnrichmentSummary {
  risk_score: number | null;
  category: string | null;
  tags: string[];
  first_seen: string | null;
  last_seen: string | null;
  is_malicious: boolean;
}

@Injectable({
  providedIn: 'root'
})
export class EnrichmentService {
  private apiUrl = `${environment.apiUrl}/enrichment`;

  constructor(private http: HttpClient) {}

  enrich(indicator: string, indicatorType?: string): Observable<EnrichmentResult> {
    return this.http.post<EnrichmentResult>(`${this.apiUrl}/enrich`, {
      indicator,
      indicator_type: indicatorType
    });
  }

  enrichBatch(indicators: { value: string; type?: string }[]): Observable<EnrichmentResult[]> {
    return this.http.post<EnrichmentResult[]>(`${this.apiUrl}/enrich/batch`, { indicators });
  }

  getIOCs(params?: {
    indicator_type?: string;
    source?: string;
    min_confidence?: number;
    page?: number;
    page_size?: number;
  }): Observable<{ items: IOC[]; total: number }> {
    return this.http.get<{ items: IOC[]; total: number }>(`${this.apiUrl}/iocs`, { params: params as Record<string, string> });
  }

  searchThreatIntel(query: string): Observable<{
    indicators: IOC[];
    reports: ThreatReport[];
    actors: ThreatActor[];
  }> {
    return this.http.get<{
      indicators: IOC[];
      reports: ThreatReport[];
      actors: ThreatActor[];
    }>(`${this.apiUrl}/search`, { params: { query } });
  }
}

export interface ThreatReport {
  id: string;
  name: string;
  description: string;
  published: string;
  source: string;
  url: string | null;
  tags: string[];
}

export interface ThreatActor {
  id: string;
  name: string;
  aliases: string[];
  description: string;
  motivation: string | null;
  sophistication: string | null;
  first_seen: string | null;
  last_seen: string | null;
}
