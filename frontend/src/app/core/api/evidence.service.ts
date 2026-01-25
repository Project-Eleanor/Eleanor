import { Injectable } from '@angular/core';
import { HttpClient, HttpParams, HttpEvent } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import {
  Evidence,
  EvidenceCreate,
  EvidenceUpdate,
  EvidenceListResponse,
  EvidenceType,
  CustodyEvent
} from '../../shared/models';

@Injectable({
  providedIn: 'root'
})
export class EvidenceService {
  private apiUrl = `${environment.apiUrl}/evidence`;

  constructor(private http: HttpClient) {}

  list(params?: {
    case_id?: string;
    evidence_type?: EvidenceType;
    page?: number;
    page_size?: number;
    search?: string;
  }): Observable<EvidenceListResponse> {
    let httpParams = new HttpParams();

    if (params) {
      if (params.case_id) httpParams = httpParams.set('case_id', params.case_id);
      if (params.evidence_type) httpParams = httpParams.set('evidence_type', params.evidence_type);
      if (params.page) httpParams = httpParams.set('page', params.page.toString());
      if (params.page_size) httpParams = httpParams.set('page_size', params.page_size.toString());
      if (params.search) httpParams = httpParams.set('search', params.search);
    }

    return this.http.get<EvidenceListResponse>(this.apiUrl, { params: httpParams });
  }

  get(id: string): Observable<Evidence> {
    return this.http.get<Evidence>(`${this.apiUrl}/${id}`);
  }

  upload(caseId: string, file: File, metadata?: Partial<EvidenceCreate>): Observable<HttpEvent<Evidence>> {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('case_id', caseId);

    if (metadata) {
      Object.entries(metadata).forEach(([key, value]) => {
        if (value !== undefined) {
          formData.append(key, typeof value === 'object' ? JSON.stringify(value) : String(value));
        }
      });
    }

    return this.http.post<Evidence>(`${this.apiUrl}/upload`, formData, {
      reportProgress: true,
      observe: 'events'
    });
  }

  update(id: string, data: EvidenceUpdate): Observable<Evidence> {
    return this.http.patch<Evidence>(`${this.apiUrl}/${id}`, data);
  }

  delete(id: string): Observable<void> {
    return this.http.delete<void>(`${this.apiUrl}/${id}`);
  }

  download(id: string): Observable<Blob> {
    return this.http.get(`${this.apiUrl}/${id}/download`, {
      responseType: 'blob'
    });
  }

  verify(id: string): Observable<{ integrity_valid: boolean; stored_hashes: Record<string, string>; computed_hashes: Record<string, string> }> {
    return this.http.post<{ integrity_valid: boolean; stored_hashes: Record<string, string>; computed_hashes: Record<string, string> }>(
      `${this.apiUrl}/${id}/verify`,
      {}
    );
  }

  getCustodyChain(id: string): Observable<CustodyEvent[]> {
    return this.http.get<CustodyEvent[]>(`${this.apiUrl}/${id}/custody`);
  }
}
