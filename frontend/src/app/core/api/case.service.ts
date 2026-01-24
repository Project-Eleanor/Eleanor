import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import {
  Case,
  CaseCreate,
  CaseUpdate,
  CaseListResponse,
  CaseStatus,
  Severity,
  TimelineEvent,
  TimelineEventCreate
} from '../../shared/models';

@Injectable({
  providedIn: 'root'
})
export class CaseService {
  private apiUrl = `${environment.apiUrl}/cases`;

  constructor(private http: HttpClient) {}

  list(params?: {
    page?: number;
    page_size?: number;
    status?: CaseStatus;
    severity?: Severity;
    assignee_id?: string;
    search?: string;
  }): Observable<CaseListResponse> {
    let httpParams = new HttpParams();

    if (params) {
      if (params.page) httpParams = httpParams.set('page', params.page.toString());
      if (params.page_size) httpParams = httpParams.set('page_size', params.page_size.toString());
      if (params.status) httpParams = httpParams.set('status', params.status);
      if (params.severity) httpParams = httpParams.set('severity', params.severity);
      if (params.assignee_id) httpParams = httpParams.set('assignee_id', params.assignee_id);
      if (params.search) httpParams = httpParams.set('search', params.search);
    }

    return this.http.get<CaseListResponse>(this.apiUrl, { params: httpParams });
  }

  get(id: string): Observable<Case> {
    return this.http.get<Case>(`${this.apiUrl}/${id}`);
  }

  create(data: CaseCreate): Observable<Case> {
    return this.http.post<Case>(this.apiUrl, data);
  }

  update(id: string, data: CaseUpdate): Observable<Case> {
    return this.http.patch<Case>(`${this.apiUrl}/${id}`, data);
  }

  delete(id: string): Observable<void> {
    return this.http.delete<void>(`${this.apiUrl}/${id}`);
  }

  getTimeline(caseId: string): Observable<TimelineEvent[]> {
    return this.http.get<TimelineEvent[]>(`${this.apiUrl}/${caseId}/timeline`);
  }

  addTimelineEvent(caseId: string, event: TimelineEventCreate): Observable<TimelineEvent> {
    return this.http.post<TimelineEvent>(`${this.apiUrl}/${caseId}/timeline`, event);
  }
}
