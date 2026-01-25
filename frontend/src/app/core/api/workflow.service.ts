import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import {
  Workflow,
  WorkflowExecution,
  WorkflowTrigger,
  ApprovalRequest,
  ExecutionStatus
} from '../../shared/models';

@Injectable({
  providedIn: 'root'
})
export class WorkflowService {
  private apiUrl = `${environment.apiUrl}/workflows`;

  constructor(private http: HttpClient) {}

  list(params?: { category?: string; status?: string }): Observable<Workflow[]> {
    let httpParams = new HttpParams();

    if (params) {
      if (params.category) httpParams = httpParams.set('category', params.category);
      if (params.status) httpParams = httpParams.set('status', params.status);
    }

    return this.http.get<Workflow[]>(this.apiUrl, { params: httpParams });
  }

  get(id: string): Observable<Workflow> {
    return this.http.get<Workflow>(`${this.apiUrl}/${id}`);
  }

  trigger(workflowId: string, parameters: Record<string, unknown>): Observable<WorkflowExecution> {
    return this.http.post<WorkflowExecution>(`${this.apiUrl}/trigger`, {
      workflow_id: workflowId,
      parameters
    });
  }

  getExecutions(params?: {
    workflow_id?: string;
    status?: ExecutionStatus;
    page?: number;
    page_size?: number;
  }): Observable<{ items: WorkflowExecution[]; total: number }> {
    let httpParams = new HttpParams();

    if (params) {
      if (params.workflow_id) httpParams = httpParams.set('workflow_id', params.workflow_id);
      if (params.status) httpParams = httpParams.set('status', params.status);
      if (params.page) httpParams = httpParams.set('page', params.page.toString());
      if (params.page_size) httpParams = httpParams.set('page_size', params.page_size.toString());
    }

    return this.http.get<{ items: WorkflowExecution[]; total: number }>(
      `${this.apiUrl}/executions`,
      { params: httpParams }
    );
  }

  getExecution(id: string): Observable<WorkflowExecution> {
    return this.http.get<WorkflowExecution>(`${this.apiUrl}/executions/${id}`);
  }

  cancelExecution(id: string): Observable<WorkflowExecution> {
    return this.http.post<WorkflowExecution>(`${this.apiUrl}/executions/${id}/cancel`, {});
  }

  getApprovals(): Observable<ApprovalRequest[]> {
    return this.http.get<ApprovalRequest[]>(`${this.apiUrl}/approvals`);
  }

  approve(approvalId: string): Observable<WorkflowExecution> {
    return this.http.post<WorkflowExecution>(`${this.apiUrl}/approvals/${approvalId}/approve`, {});
  }

  reject(approvalId: string, reason?: string): Observable<WorkflowExecution> {
    return this.http.post<WorkflowExecution>(`${this.apiUrl}/approvals/${approvalId}/deny`, { comment: reason });
  }
}
