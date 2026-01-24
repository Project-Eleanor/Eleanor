import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import {
  Endpoint,
  EndpointListResponse,
  ArtifactDefinition,
  Collection,
  CollectionCreate,
  Hunt,
  HuntCreate,
  CollectionStatus
} from '../../shared/models';

@Injectable({
  providedIn: 'root'
})
export class CollectionService {
  private apiUrl = `${environment.apiUrl}/collection`;

  constructor(private http: HttpClient) {}

  // Endpoints
  getEndpoints(params?: {
    status?: string;
    search?: string;
    labels?: string[];
    page?: number;
    page_size?: number;
  }): Observable<EndpointListResponse> {
    let httpParams = new HttpParams();

    if (params) {
      if (params.status) httpParams = httpParams.set('status', params.status);
      if (params.search) httpParams = httpParams.set('search', params.search);
      if (params.labels) httpParams = httpParams.set('labels', params.labels.join(','));
      if (params.page) httpParams = httpParams.set('page', params.page.toString());
      if (params.page_size) httpParams = httpParams.set('page_size', params.page_size.toString());
    }

    return this.http.get<EndpointListResponse>(`${this.apiUrl}/endpoints`, { params: httpParams });
  }

  getEndpoint(id: string): Observable<Endpoint> {
    return this.http.get<Endpoint>(`${this.apiUrl}/endpoints/${id}`);
  }

  // Artifacts
  getArtifacts(category?: string): Observable<ArtifactDefinition[]> {
    let httpParams = new HttpParams();
    if (category) httpParams = httpParams.set('category', category);

    return this.http.get<ArtifactDefinition[]>(`${this.apiUrl}/artifacts`, { params: httpParams });
  }

  getArtifact(name: string): Observable<ArtifactDefinition> {
    return this.http.get<ArtifactDefinition>(`${this.apiUrl}/artifacts/${name}`);
  }

  // Collections
  getCollections(params?: {
    status?: CollectionStatus;
    page?: number;
    page_size?: number;
  }): Observable<{ items: Collection[]; total: number }> {
    let httpParams = new HttpParams();

    if (params) {
      if (params.status) httpParams = httpParams.set('status', params.status);
      if (params.page) httpParams = httpParams.set('page', params.page.toString());
      if (params.page_size) httpParams = httpParams.set('page_size', params.page_size.toString());
    }

    return this.http.get<{ items: Collection[]; total: number }>(
      `${this.apiUrl}/collections`,
      { params: httpParams }
    );
  }

  createCollection(data: CollectionCreate): Observable<Collection> {
    return this.http.post<Collection>(`${this.apiUrl}/collections`, data);
  }

  getCollection(id: string): Observable<Collection> {
    return this.http.get<Collection>(`${this.apiUrl}/collections/${id}`);
  }

  cancelCollection(id: string): Observable<Collection> {
    return this.http.post<Collection>(`${this.apiUrl}/collections/${id}/cancel`, {});
  }

  getCollectionResults(id: string): Observable<Record<string, unknown>[]> {
    return this.http.get<Record<string, unknown>[]>(`${this.apiUrl}/collections/${id}/results`);
  }

  // Hunts
  getHunts(params?: {
    status?: CollectionStatus;
    page?: number;
    page_size?: number;
  }): Observable<{ items: Hunt[]; total: number }> {
    let httpParams = new HttpParams();

    if (params) {
      if (params.status) httpParams = httpParams.set('status', params.status);
      if (params.page) httpParams = httpParams.set('page', params.page.toString());
      if (params.page_size) httpParams = httpParams.set('page_size', params.page_size.toString());
    }

    return this.http.get<{ items: Hunt[]; total: number }>(`${this.apiUrl}/hunts`, { params: httpParams });
  }

  createHunt(data: HuntCreate): Observable<Hunt> {
    return this.http.post<Hunt>(`${this.apiUrl}/hunts`, data);
  }

  getHunt(id: string): Observable<Hunt> {
    return this.http.get<Hunt>(`${this.apiUrl}/hunts/${id}`);
  }

  cancelHunt(id: string): Observable<Hunt> {
    return this.http.post<Hunt>(`${this.apiUrl}/hunts/${id}/cancel`, {});
  }

  getHuntResults(id: string): Observable<Record<string, unknown>[]> {
    return this.http.get<Record<string, unknown>[]>(`${this.apiUrl}/hunts/${id}/results`);
  }
}
