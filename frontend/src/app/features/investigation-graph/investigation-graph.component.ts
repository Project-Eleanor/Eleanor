import { Component, OnInit, inject, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterModule } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatMenuModule } from '@angular/material/menu';
import { MatSelectModule } from '@angular/material/select';
import { MatSliderModule } from '@angular/material/slider';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatChipsModule } from '@angular/material/chips';
import { MatCardModule } from '@angular/material/card';
import { MatDividerModule } from '@angular/material/divider';
import { MatDialog, MatDialogModule } from '@angular/material/dialog';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';

import { CytoscapeGraphComponent, LayoutType } from '../../shared/components/cytoscape-graph/cytoscape-graph.component';
import { GraphService } from '../../core/api/graph.service';
import {
  GraphData,
  GraphNode,
  GraphEdge,
  EntityType,
  NODE_COLORS,
  SavedGraph,
} from '../../shared/models/graph.model';

@Component({
  selector: 'app-investigation-graph',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    RouterModule,
    MatButtonModule,
    MatIconModule,
    MatMenuModule,
    MatSelectModule,
    MatSliderModule,
    MatTooltipModule,
    MatProgressSpinnerModule,
    MatChipsModule,
    MatCardModule,
    MatDividerModule,
    MatDialogModule,
    MatSnackBarModule,
    CytoscapeGraphComponent,
  ],
  template: `
    <div class="graph-page">
      <!-- Toolbar -->
      <div class="toolbar">
        <div class="toolbar-left">
          <button mat-icon-button (click)="goBack()" matTooltip="Back">
            <mat-icon>arrow_back</mat-icon>
          </button>
          <h2>Investigation Graph</h2>
          @if (caseId()) {
            <span class="case-badge">Case: {{ caseId() }}</span>
          }
        </div>

        <div class="toolbar-center">
          <!-- Entity Type Filters -->
          <mat-chip-listbox
            [multiple]="true"
            [(ngModel)]="selectedEntityTypes"
            (change)="rebuildGraph()"
          >
            @for (type of entityTypes; track type) {
              <mat-chip-option [value]="type" [style.--chip-color]="getEntityColor(type)">
                <mat-icon>{{ getEntityIcon(type) }}</mat-icon>
                {{ type | titlecase }}
              </mat-chip-option>
            }
          </mat-chip-listbox>
        </div>

        <div class="toolbar-right">
          <!-- Layout selector -->
          <mat-select [(value)]="selectedLayout" (selectionChange)="onLayoutChange()">
            <mat-option value="dagre">Hierarchical</mat-option>
            <mat-option value="cola">Force-Directed</mat-option>
            <mat-option value="cose">COSE</mat-option>
            <mat-option value="circle">Circle</mat-option>
            <mat-option value="concentric">Concentric</mat-option>
          </mat-select>

          <button mat-icon-button (click)="fitGraph()" matTooltip="Fit to View">
            <mat-icon>fit_screen</mat-icon>
          </button>

          <button mat-icon-button (click)="rebuildGraph()" matTooltip="Refresh">
            <mat-icon>refresh</mat-icon>
          </button>

          <button mat-icon-button [matMenuTriggerFor]="moreMenu" matTooltip="More">
            <mat-icon>more_vert</mat-icon>
          </button>
          <mat-menu #moreMenu="matMenu">
            <button mat-menu-item (click)="saveGraph()">
              <mat-icon>save</mat-icon>
              Save Graph
            </button>
            <button mat-menu-item (click)="loadSavedGraph()">
              <mat-icon>folder_open</mat-icon>
              Load Saved Graph
            </button>
            <mat-divider></mat-divider>
            <button mat-menu-item (click)="exportPng()">
              <mat-icon>image</mat-icon>
              Export as PNG
            </button>
          </mat-menu>
        </div>
      </div>

      <!-- Main Content -->
      <div class="main-content">
        <!-- Graph Canvas -->
        <div class="graph-wrapper" [class.loading]="loading()">
          @if (loading()) {
            <div class="loading-overlay">
              <mat-spinner diameter="48"></mat-spinner>
              <span>Building graph...</span>
            </div>
          }

          <app-cytoscape-graph
            [graphData]="graphData()"
            [layout]="selectedLayout"
            [showLabels]="showLabels"
            (nodeClick)="onNodeClick($event)"
            (nodeDoubleClick)="onNodeDoubleClick($event)"
            (edgeClick)="onEdgeClick($event)"
            #graphComponent
          ></app-cytoscape-graph>
        </div>

        <!-- Detail Panel -->
        @if (selectedNode()) {
          <div class="detail-panel">
            <div class="panel-header">
              <mat-icon [style.color]="getEntityColor(selectedNode()!.type)">
                {{ getEntityIcon(selectedNode()!.type) }}
              </mat-icon>
              <h3>{{ selectedNode()!.label }}</h3>
              <button mat-icon-button (click)="clearSelection()" matTooltip="Close">
                <mat-icon>close</mat-icon>
              </button>
            </div>

            <mat-divider></mat-divider>

            <div class="panel-content">
              <div class="detail-row">
                <span class="label">Type:</span>
                <span class="value">{{ selectedNode()!.type | titlecase }}</span>
              </div>
              @if (selectedNode()!.event_count) {
                <div class="detail-row">
                  <span class="label">Events:</span>
                  <span class="value">{{ selectedNode()!.event_count | number }}</span>
                </div>
              }
              @if (selectedNode()!.first_seen) {
                <div class="detail-row">
                  <span class="label">First Seen:</span>
                  <span class="value">{{ selectedNode()!.first_seen | date:'short' }}</span>
                </div>
              }
              @if (selectedNode()!.last_seen) {
                <div class="detail-row">
                  <span class="label">Last Seen:</span>
                  <span class="value">{{ selectedNode()!.last_seen | date:'short' }}</span>
                </div>
              }
              @if (selectedNode()!.risk_score !== undefined) {
                <div class="detail-row">
                  <span class="label">Risk Score:</span>
                  <span class="value risk-score" [class.high]="selectedNode()!.risk_score! >= 70">
                    {{ selectedNode()!.risk_score }}
                  </span>
                </div>
              }

              <mat-divider></mat-divider>

              <div class="panel-actions">
                <button mat-stroked-button (click)="expandNode(selectedNode()!)">
                  <mat-icon>open_in_full</mat-icon>
                  Expand Connections
                </button>
                <button mat-stroked-button (click)="viewInEntities(selectedNode()!)">
                  <mat-icon>person_search</mat-icon>
                  View in Entities
                </button>
                <button mat-stroked-button (click)="searchEvents(selectedNode()!)">
                  <mat-icon>search</mat-icon>
                  Search Events
                </button>
              </div>
            </div>
          </div>
        }
      </div>

      <!-- Legend -->
      <div class="legend">
        <span class="legend-title">Legend:</span>
        @for (type of entityTypes; track type) {
          <div class="legend-item">
            <span class="legend-color" [style.background]="getEntityColor(type)"></span>
            <span>{{ type | titlecase }}</span>
          </div>
        }
      </div>

      <!-- Stats Bar -->
      @if (graphData()) {
        <div class="stats-bar">
          <span>{{ graphData()!.nodes.length }} nodes</span>
          <span class="divider">|</span>
          <span>{{ graphData()!.edges.length }} edges</span>
          @if (graphData()!.metadata?.truncated) {
            <span class="divider">|</span>
            <span class="warning">Graph truncated (max {{ maxNodes }} nodes)</span>
          }
        </div>
      }
    </div>
  `,
  styles: [`
    :host {
      display: block;
      height: 100%;
    }

    .graph-page {
      display: flex;
      flex-direction: column;
      height: 100%;
      background: #121212;
    }

    .toolbar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 8px 16px;
      background: #1e1e1e;
      border-bottom: 1px solid #333;
    }

    .toolbar-left, .toolbar-right {
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .toolbar-center {
      display: flex;
      align-items: center;
      gap: 16px;
    }

    .toolbar h2 {
      margin: 0;
      font-size: 18px;
      font-weight: 500;
    }

    .case-badge {
      padding: 4px 8px;
      background: #333;
      border-radius: 4px;
      font-size: 12px;
      color: #aaa;
    }

    mat-chip-option {
      --mdc-chip-label-text-color: #fff;
    }

    mat-chip-option::before {
      background-color: var(--chip-color, #666);
    }

    .main-content {
      flex: 1;
      display: flex;
      position: relative;
      overflow: hidden;
    }

    .graph-wrapper {
      flex: 1;
      position: relative;
    }

    .graph-wrapper.loading {
      opacity: 0.5;
    }

    .loading-overlay {
      position: absolute;
      top: 50%;
      left: 50%;
      transform: translate(-50%, -50%);
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 16px;
      z-index: 10;
    }

    app-cytoscape-graph {
      height: 100%;
    }

    .detail-panel {
      width: 320px;
      background: #1e1e1e;
      border-left: 1px solid #333;
      display: flex;
      flex-direction: column;
    }

    .panel-header {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 16px;
    }

    .panel-header h3 {
      flex: 1;
      margin: 0;
      font-size: 16px;
      font-weight: 500;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .panel-content {
      padding: 16px;
      overflow-y: auto;
    }

    .detail-row {
      display: flex;
      justify-content: space-between;
      margin-bottom: 12px;
    }

    .detail-row .label {
      color: #888;
    }

    .detail-row .value {
      font-weight: 500;
    }

    .risk-score.high {
      color: #f44336;
    }

    .panel-actions {
      display: flex;
      flex-direction: column;
      gap: 8px;
      margin-top: 16px;
    }

    .panel-actions button {
      justify-content: flex-start;
    }

    .legend {
      display: flex;
      align-items: center;
      gap: 16px;
      padding: 8px 16px;
      background: #1e1e1e;
      border-top: 1px solid #333;
    }

    .legend-title {
      font-size: 12px;
      color: #888;
    }

    .legend-item {
      display: flex;
      align-items: center;
      gap: 4px;
      font-size: 12px;
    }

    .legend-color {
      width: 12px;
      height: 12px;
      border-radius: 2px;
    }

    .stats-bar {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 4px 16px;
      background: #252525;
      font-size: 12px;
      color: #888;
    }

    .stats-bar .divider {
      color: #444;
    }

    .stats-bar .warning {
      color: #ff9800;
    }
  `],
})
export class InvestigationGraphComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private graphService = inject(GraphService);
  private dialog = inject(MatDialog);
  private snackBar = inject(MatSnackBar);

  // State
  caseId = signal<string | null>(null);
  graphData = signal<GraphData | null>(null);
  selectedNode = signal<GraphNode | null>(null);
  loading = signal(false);

  // Configuration
  entityTypes: EntityType[] = ['host', 'user', 'ip', 'process', 'file', 'domain'];
  selectedEntityTypes: EntityType[] = ['host', 'user', 'ip', 'process'];
  selectedLayout: LayoutType = 'dagre';
  showLabels = true;
  maxNodes = 100;

  ngOnInit(): void {
    // Get case ID from route
    this.route.queryParams.subscribe((params) => {
      const caseId = params['case_id'];
      if (caseId) {
        this.caseId.set(caseId);
        this.loadGraph(caseId);
      }
    });
  }

  async loadGraph(caseId: string): Promise<void> {
    this.loading.set(true);

    try {
      const data = await this.graphService
        .buildGraph({
          case_id: caseId,
          max_nodes: this.maxNodes,
          entity_types: this.selectedEntityTypes,
        })
        .toPromise();

      this.graphData.set(data || null);
    } catch (error) {
      console.error('Failed to load graph:', error);
      this.snackBar.open('Failed to load graph', 'Close', { duration: 3000 });
    } finally {
      this.loading.set(false);
    }
  }

  rebuildGraph(): void {
    const caseId = this.caseId();
    if (caseId) {
      this.loadGraph(caseId);
    }
  }

  onNodeClick(node: GraphNode): void {
    this.selectedNode.set(node);
  }

  onNodeDoubleClick(node: GraphNode): void {
    this.expandNode(node);
  }

  onEdgeClick(edge: GraphEdge): void {
    // Could show edge details
    console.log('Edge clicked:', edge);
  }

  async expandNode(node: GraphNode): Promise<void> {
    const caseId = this.caseId();
    if (!caseId) return;

    this.loading.set(true);

    try {
      const expansion = await this.graphService
        .expandNode({
          case_id: caseId,
          node_id: node.id,
          max_connections: 20,
        })
        .toPromise();

      if (expansion) {
        // Merge with existing graph
        const current = this.graphData();
        if (current) {
          const existingIds = new Set(current.nodes.map((n) => n.id));
          const newNodes = expansion.nodes.filter((n) => !existingIds.has(n.id));

          this.graphData.set({
            nodes: [...current.nodes, ...newNodes],
            edges: [...current.edges, ...expansion.edges],
            metadata: current.metadata,
          });
        }
      }
    } catch (error) {
      console.error('Failed to expand node:', error);
      this.snackBar.open('Failed to expand node', 'Close', { duration: 3000 });
    } finally {
      this.loading.set(false);
    }
  }

  viewInEntities(node: GraphNode): void {
    const [type, value] = node.id.split(':');
    this.router.navigate(['/entities', type, value]);
  }

  searchEvents(node: GraphNode): void {
    const [type, value] = node.id.split(':');
    const fieldMap: Record<string, string> = {
      host: 'host.name',
      user: 'user.name',
      ip: 'source.ip OR destination.ip',
      process: 'process.name',
      file: 'file.name',
      domain: 'url.domain',
    };

    const field = fieldMap[type] || type;
    const query = `${field}:"${value}"`;
    this.router.navigate(['/hunting'], { queryParams: { q: query } });
  }

  clearSelection(): void {
    this.selectedNode.set(null);
  }

  onLayoutChange(): void {
    // Layout change handled by CytoscapeGraphComponent via input binding
  }

  fitGraph(): void {
    // Access through ViewChild if needed
  }

  saveGraph(): void {
    // Show save dialog
    this.snackBar.open('Save graph feature coming soon', 'Close', { duration: 3000 });
  }

  loadSavedGraph(): void {
    // Show load dialog
    this.snackBar.open('Load graph feature coming soon', 'Close', { duration: 3000 });
  }

  exportPng(): void {
    this.snackBar.open('Export feature coming soon', 'Close', { duration: 3000 });
  }

  goBack(): void {
    window.history.back();
  }

  getEntityColor(type: EntityType): string {
    return NODE_COLORS[type] || '#666';
  }

  getEntityIcon(type: EntityType): string {
    const icons: Record<EntityType, string> = {
      host: 'computer',
      user: 'person',
      ip: 'router',
      process: 'memory',
      file: 'description',
      domain: 'language',
    };
    return icons[type] || 'circle';
  }
}
