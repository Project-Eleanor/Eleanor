import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';

export interface ResponseAction {
  id: string;
  action_type: string;
  status: string;
  client_id: string;
  hostname?: string;
  target_details: Record<string, unknown>;
  reason?: string;
  job_id?: string;
  case_id?: string;
  user_id: string;
  created_at: string;
  started_at?: string;
  completed_at?: string;
  error_message?: string;
}

export interface IsolationStatus {
  client_id: string;
  is_isolated: boolean;
  last_action?: string;
  last_action_at?: string;
  last_action_by?: string;
}

export interface IsolateRequest {
  client_id: string;
  hostname?: string;
  reason: string;
  case_id?: string;
}

export interface ReleaseRequest {
  client_id: string;
  reason: string;
  case_id?: string;
}

export interface QuarantineFileRequest {
  client_id: string;
  file_path: string;
  reason: string;
  case_id?: string;
}

export interface KillProcessRequest {
  client_id: string;
  pid: number;
  reason: string;
  case_id?: string;
}

export interface ResponseActionResult {
  success: boolean;
  action_id: string;
  client_id: string;
  action_type: string;
  message: string;
  job_id?: string;
}

export interface Endpoint {
  client_id: string;
  hostname: string;
  os?: string;
  os_version?: string;
  ip_addresses: string[];
  last_seen?: string;
  online: boolean;
  labels: Record<string, string>;
}

@Injectable({ providedIn: 'root' })
export class ResponseService {
  private apiUrl = `${environment.apiUrl}/response`;
  private collectionUrl = `${environment.apiUrl}/collection`;

  constructor(private http: HttpClient) {}

  // ==========================================================================
  // Host Isolation
  // ==========================================================================

  isolateHost(request: IsolateRequest): Observable<ResponseActionResult> {
    return this.http.post<ResponseActionResult>(`${this.apiUrl}/isolate`, request);
  }

  releaseHost(request: ReleaseRequest): Observable<ResponseActionResult> {
    return this.http.post<ResponseActionResult>(`${this.apiUrl}/release`, request);
  }

  getIsolationStatus(clientId: string): Observable<IsolationStatus> {
    return this.http.get<IsolationStatus>(`${this.apiUrl}/status/${clientId}`);
  }

  // ==========================================================================
  // File Quarantine
  // ==========================================================================

  quarantineFile(request: QuarantineFileRequest): Observable<ResponseActionResult> {
    return this.http.post<ResponseActionResult>(`${this.apiUrl}/quarantine-file`, request);
  }

  // ==========================================================================
  // Process Termination
  // ==========================================================================

  killProcess(request: KillProcessRequest): Observable<ResponseActionResult> {
    return this.http.post<ResponseActionResult>(`${this.apiUrl}/kill-process`, request);
  }

  // ==========================================================================
  // Action History
  // ==========================================================================

  getActions(params?: {
    action_type?: string;
    status?: string;
    client_id?: string;
    limit?: number;
    offset?: number;
  }): Observable<ResponseAction[]> {
    let httpParams = new HttpParams();

    if (params) {
      if (params.action_type) httpParams = httpParams.set('action_type', params.action_type);
      if (params.status) httpParams = httpParams.set('status', params.status);
      if (params.client_id) httpParams = httpParams.set('client_id', params.client_id);
      if (params.limit) httpParams = httpParams.set('limit', params.limit.toString());
      if (params.offset) httpParams = httpParams.set('offset', params.offset.toString());
    }

    return this.http.get<ResponseAction[]>(`${this.apiUrl}/actions`, { params: httpParams });
  }

  getAction(actionId: string): Observable<ResponseAction> {
    return this.http.get<ResponseAction>(`${this.apiUrl}/actions/${actionId}`);
  }

  getClientActions(clientId: string, limit = 50): Observable<ResponseAction[]> {
    return this.http.get<ResponseAction[]>(`${this.apiUrl}/actions/client/${clientId}`, {
      params: { limit: limit.toString() }
    });
  }

  getCaseActions(caseId: string, limit = 100): Observable<ResponseAction[]> {
    return this.http.get<ResponseAction[]>(`${this.apiUrl}/actions/case/${caseId}`, {
      params: { limit: limit.toString() }
    });
  }

  // ==========================================================================
  // Endpoints (from collection API)
  // ==========================================================================

  getEndpoints(params?: {
    search?: string;
    online_only?: boolean;
    limit?: number;
    offset?: number;
  }): Observable<Endpoint[]> {
    let httpParams = new HttpParams();

    if (params) {
      if (params.search) httpParams = httpParams.set('search', params.search);
      if (params.online_only) httpParams = httpParams.set('online_only', 'true');
      if (params.limit) httpParams = httpParams.set('limit', params.limit.toString());
      if (params.offset) httpParams = httpParams.set('offset', params.offset.toString());
    }

    return this.http.get<Endpoint[]>(`${this.collectionUrl}/endpoints`, { params: httpParams });
  }

  getEndpoint(clientId: string): Observable<Endpoint> {
    return this.http.get<Endpoint>(`${this.collectionUrl}/endpoints/${clientId}`);
  }

  searchEndpoints(query: string): Observable<Endpoint[]> {
    return this.http.get<Endpoint[]>(`${this.collectionUrl}/endpoints/search/${query}`);
  }
}
