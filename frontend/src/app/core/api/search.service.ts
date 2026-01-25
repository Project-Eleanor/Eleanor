import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import {
  SearchQuery,
  SearchResponse,
  SavedQuery,
  SavedQueryCreate
} from '../../shared/models';

@Injectable({
  providedIn: 'root'
})
export class SearchService {
  private apiUrl = `${environment.apiUrl}/search`;

  constructor(private http: HttpClient) {}

  query(searchQuery: SearchQuery): Observable<SearchResponse> {
    return this.http.post<SearchResponse>(`${this.apiUrl}/query`, searchQuery);
  }

  esql(query: string, params?: { from?: number; size?: number }): Observable<SearchResponse> {
    return this.http.post<SearchResponse>(`${this.apiUrl}/esql`, {
      query,
      ...params
    });
  }

  kql(query: string, params?: { indices?: string[]; from_?: number; size?: number }): Observable<SearchResponse> {
    return this.http.post<SearchResponse>(`${this.apiUrl}/kql`, {
      query,
      ...params
    });
  }

  getSavedQueries(): Observable<SavedQuery[]> {
    return this.http.get<SavedQuery[]>(`${this.apiUrl}/saved`);
  }

  getSavedQuery(id: string): Observable<SavedQuery> {
    return this.http.get<SavedQuery>(`${this.apiUrl}/saved/${id}`);
  }

  createSavedQuery(query: SavedQueryCreate): Observable<SavedQuery> {
    return this.http.post<SavedQuery>(`${this.apiUrl}/saved`, query);
  }

  updateSavedQuery(id: string, query: Partial<SavedQueryCreate>): Observable<SavedQuery> {
    return this.http.patch<SavedQuery>(`${this.apiUrl}/saved/${id}`, query);
  }

  deleteSavedQuery(id: string): Observable<void> {
    return this.http.delete<void>(`${this.apiUrl}/saved/${id}`);
  }

  /**
   * List available Elasticsearch indices.
   */
  getIndices(): Observable<IndexInfo[]> {
    return this.http.get<IndexInfo[]>(`${this.apiUrl}/indices`);
  }

  /**
   * Get field mappings for an index.
   */
  getSchema(index: string): Observable<IndexSchema> {
    return this.http.get<IndexSchema>(`${this.apiUrl}/schema/${encodeURIComponent(index)}`);
  }
}

export interface IndexInfo {
  index: string;
  docs_count: string;
  store_size: string;
  health: string;
}

export interface IndexSchema {
  index: string;
  mappings: Record<string, unknown>;
}
