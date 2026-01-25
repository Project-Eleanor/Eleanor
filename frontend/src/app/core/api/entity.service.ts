import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import {
  Entity,
  EntityType,
  EntityProfile,
  EntityEvent,
  HostProfile,
  UserProfile,
  IPProfile
} from '../../shared/models';

@Injectable({
  providedIn: 'root'
})
export class EntityService {
  private apiUrl = `${environment.apiUrl}/entities`;

  constructor(private http: HttpClient) {}

  search(params: {
    query?: string;
    entity_type?: EntityType;
    page?: number;
    page_size?: number;
  }): Observable<{ items: Entity[]; total: number }> {
    let httpParams = new HttpParams();

    if (params.query) httpParams = httpParams.set('query', params.query);
    if (params.entity_type) httpParams = httpParams.set('entity_type', params.entity_type);
    if (params.page) httpParams = httpParams.set('page', params.page.toString());
    if (params.page_size) httpParams = httpParams.set('page_size', params.page_size.toString());

    return this.http.get<{ items: Entity[]; total: number }>(this.apiUrl, { params: httpParams });
  }

  get(type: EntityType, value: string): Observable<Entity> {
    return this.http.get<Entity>(`${this.apiUrl}/${type}/${encodeURIComponent(value)}`);
  }

  getHostProfile(hostname: string): Observable<HostProfile> {
    return this.http.get<HostProfile>(`${this.apiUrl}/hosts/${encodeURIComponent(hostname)}`);
  }

  getUserProfile(username: string): Observable<UserProfile> {
    return this.http.get<UserProfile>(`${this.apiUrl}/users/${encodeURIComponent(username)}`);
  }

  getIPProfile(ip: string): Observable<IPProfile> {
    return this.http.get<IPProfile>(`${this.apiUrl}/ips/${encodeURIComponent(ip)}`);
  }

  /**
   * Get events for an entity.
   */
  getEntityEvents(entityType: EntityType, identifier: string, params?: { from?: number; size?: number }): Observable<EntityEvent[]> {
    let httpParams = new HttpParams();
    if (params?.from !== undefined) httpParams = httpParams.set('from', params.from.toString());
    if (params?.size !== undefined) httpParams = httpParams.set('size', params.size.toString());

    return this.http.get<EntityEvent[]>(
      `${this.apiUrl}/${entityType}/${encodeURIComponent(identifier)}/events`,
      { params: httpParams }
    );
  }

  enrich(type: EntityType, value: string): Observable<Entity> {
    return this.http.post<Entity>(`${this.apiUrl}/${type}/${encodeURIComponent(value)}/enrich`, {});
  }

  getRelatedCases(type: EntityType, value: string): Observable<{ case_id: string; case_number: string; title: string }[]> {
    return this.http.get<{ case_id: string; case_number: string; title: string }[]>(
      `${this.apiUrl}/${type}/${encodeURIComponent(value)}/cases`
    );
  }
}
