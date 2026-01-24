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

  kql(query: string, index?: string): Observable<SearchResponse> {
    return this.http.post<SearchResponse>(`${this.apiUrl}/kql`, {
      query,
      index
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
}
