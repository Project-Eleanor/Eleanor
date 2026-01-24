import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import {
  IntegrationStatus,
  IntegrationsStatusResponse,
  IntegrationConfigResponse,
  TestIntegrationResponse
} from '../../shared/models';

@Injectable({
  providedIn: 'root'
})
export class IntegrationService {
  private apiUrl = `${environment.apiUrl}/integrations`;

  constructor(private http: HttpClient) {}

  getStatus(): Observable<IntegrationsStatusResponse> {
    return this.http.get<IntegrationsStatusResponse>(`${this.apiUrl}/status`);
  }

  getIntegrationStatus(name: string): Observable<IntegrationStatus> {
    return this.http.get<IntegrationStatus>(`${this.apiUrl}/${name}/status`);
  }

  getConfig(name: string): Observable<IntegrationConfigResponse> {
    return this.http.get<IntegrationConfigResponse>(`${this.apiUrl}/${name}/config`);
  }

  test(name: string): Observable<TestIntegrationResponse> {
    return this.http.post<TestIntegrationResponse>(`${this.apiUrl}/${name}/test`, {});
  }

  reconnect(name: string): Observable<{ success: boolean; message: string; status?: string }> {
    return this.http.post<{ success: boolean; message: string; status?: string }>(
      `${this.apiUrl}/${name}/reconnect`,
      {}
    );
  }
}
