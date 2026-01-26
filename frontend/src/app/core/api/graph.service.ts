import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import {
  GraphData,
  SavedGraph,
  BuildGraphRequest,
  ExpandNodeRequest,
  FindPathRequest,
  PathResult,
  EntityRelationships,
} from '../../shared/models/graph.model';
import { environment } from '../../../environments/environment';

@Injectable({ providedIn: 'root' })
export class GraphService {
  private http = inject(HttpClient);
  private baseUrl = `${environment.apiUrl}/graphs`;

  /**
   * Build a graph from case events.
   */
  buildGraph(request: BuildGraphRequest): Observable<GraphData> {
    return this.http.post<GraphData>(`${this.baseUrl}/build`, request);
  }

  /**
   * Expand a node to show its connections.
   */
  expandNode(request: ExpandNodeRequest): Observable<GraphData> {
    return this.http.post<GraphData>(`${this.baseUrl}/expand`, request);
  }

  /**
   * Find path between two entities.
   */
  findPath(request: FindPathRequest): Observable<PathResult> {
    return this.http.post<PathResult>(`${this.baseUrl}/path`, request);
  }

  /**
   * Get all relationships for an entity.
   */
  getEntityRelationships(
    caseId: string,
    entityType: string,
    entityValue: string
  ): Observable<EntityRelationships> {
    const params = new HttpParams()
      .set('case_id', caseId)
      .set('entity_type', entityType)
      .set('entity_value', entityValue);

    return this.http.get<EntityRelationships>(
      `${this.baseUrl}/entity-relationships`,
      { params }
    );
  }

  /**
   * Save a graph configuration.
   */
  saveGraph(graph: Partial<SavedGraph>): Observable<SavedGraph> {
    return this.http.post<SavedGraph>(`${this.baseUrl}/saved`, graph);
  }

  /**
   * List saved graphs.
   */
  listSavedGraphs(caseId?: string): Observable<{ items: SavedGraph[]; total: number }> {
    let params = new HttpParams();
    if (caseId) {
      params = params.set('case_id', caseId);
    }
    return this.http.get<{ items: SavedGraph[]; total: number }>(
      `${this.baseUrl}/saved`,
      { params }
    );
  }

  /**
   * Get a saved graph by ID.
   */
  getSavedGraph(graphId: string): Observable<SavedGraph> {
    return this.http.get<SavedGraph>(`${this.baseUrl}/saved/${graphId}`);
  }

  /**
   * Delete a saved graph.
   */
  deleteSavedGraph(graphId: string): Observable<{ status: string; id: string }> {
    return this.http.delete<{ status: string; id: string }>(
      `${this.baseUrl}/saved/${graphId}`
    );
  }
}
