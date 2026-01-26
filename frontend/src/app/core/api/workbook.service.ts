import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import {
  Workbook,
  WorkbookCreate,
  WorkbookUpdate,
  WorkbookTemplate,
  TileExecuteRequest,
  TileExecuteResponse,
} from '../../shared/models/workbook.model';
import { environment } from '../../../environments/environment';

@Injectable({ providedIn: 'root' })
export class WorkbookService {
  private http = inject(HttpClient);
  private baseUrl = `${environment.apiUrl}/workbooks`;

  /**
   * List workbooks with pagination.
   */
  listWorkbooks(params?: {
    page?: number;
    page_size?: number;
    is_public?: boolean;
  }): Observable<{
    items: Workbook[];
    total: number;
    page: number;
    page_size: number;
    pages: number;
  }> {
    let httpParams = new HttpParams();
    if (params?.page) httpParams = httpParams.set('page', params.page);
    if (params?.page_size) httpParams = httpParams.set('page_size', params.page_size);
    if (params?.is_public !== undefined) httpParams = httpParams.set('is_public', params.is_public);

    return this.http.get<{
      items: Workbook[];
      total: number;
      page: number;
      page_size: number;
      pages: number;
    }>(this.baseUrl, { params: httpParams });
  }

  /**
   * Get a workbook by ID.
   */
  getWorkbook(id: string): Observable<Workbook> {
    return this.http.get<Workbook>(`${this.baseUrl}/${id}`);
  }

  /**
   * Create a new workbook.
   */
  createWorkbook(workbook: WorkbookCreate): Observable<Workbook> {
    return this.http.post<Workbook>(this.baseUrl, workbook);
  }

  /**
   * Update a workbook.
   */
  updateWorkbook(id: string, update: WorkbookUpdate): Observable<Workbook> {
    return this.http.patch<Workbook>(`${this.baseUrl}/${id}`, update);
  }

  /**
   * Delete a workbook.
   */
  deleteWorkbook(id: string): Observable<{ status: string; id: string }> {
    return this.http.delete<{ status: string; id: string }>(`${this.baseUrl}/${id}`);
  }

  /**
   * Clone a workbook.
   */
  cloneWorkbook(id: string, name: string): Observable<Workbook> {
    const params = new HttpParams().set('name', name);
    return this.http.post<Workbook>(`${this.baseUrl}/${id}/clone`, {}, { params });
  }

  /**
   * List available templates.
   */
  listTemplates(): Observable<WorkbookTemplate[]> {
    return this.http.get<WorkbookTemplate[]>(`${this.baseUrl}/templates`);
  }

  /**
   * Create workbook from template.
   */
  createFromTemplate(templateName: string, name: string): Observable<Workbook> {
    const params = new HttpParams().set('name', name);
    return this.http.post<Workbook>(
      `${this.baseUrl}/templates/${encodeURIComponent(templateName)}`,
      {},
      { params }
    );
  }

  /**
   * Execute a workbook tile.
   */
  executeTile(request: TileExecuteRequest): Observable<TileExecuteResponse> {
    return this.http.post<TileExecuteResponse>(`${this.baseUrl}/execute-tile`, request);
  }
}
