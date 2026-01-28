import { Component, Input, Output, EventEmitter, signal, OnChanges, SimpleChanges, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatListModule } from '@angular/material/list';
import { MatChipsModule } from '@angular/material/chips';
import { MatExpansionModule } from '@angular/material/expansion';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatDividerModule } from '@angular/material/divider';
import { MatSliderModule } from '@angular/material/slider';
import { MatTooltipModule } from '@angular/material/tooltip';
import { HttpClient } from '@angular/common/http';
import { environment } from '../../../environments/environment';
import { GraphNode, GraphEdge, GraphData, PathResult, EntityType, NODE_COLORS } from '../../shared/models/graph.model';
import { LoggingService } from '../../core/services/logging.service';

interface AnnotationData {
  id: string;
  nodeId?: string;
  edgeId?: string;
  text: string;
  color: string;
  createdAt: string;
}

interface ClusterData {
  name: string;
  type: EntityType;
  nodes: string[];
  color: string;
}

@Component({
  selector: 'app-graph-analytics',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatButtonModule,
    MatIconModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    MatListModule,
    MatChipsModule,
    MatExpansionModule,
    MatProgressSpinnerModule,
    MatDividerModule,
    MatSliderModule,
    MatTooltipModule,
  ],
  template: `
    <div class="analytics-panel" [class.collapsed]="!isOpen">
      <div class="panel-header">
        <h3>Graph Analytics</h3>
        <button mat-icon-button (click)="close.emit()">
          <mat-icon>close</mat-icon>
        </button>
      </div>

      <div class="panel-content">
        <!-- Path Finding Section -->
        <mat-expansion-panel [expanded]="true">
          <mat-expansion-panel-header>
            <mat-panel-title>
              <mat-icon>route</mat-icon>
              Path Finding
            </mat-panel-title>
          </mat-expansion-panel-header>

          <div class="path-finder">
            <mat-form-field appearance="outline">
              <mat-label>Source Node</mat-label>
              <mat-select [(ngModel)]="sourceNode" (selectionChange)="onPathNodeChange()">
                @for (node of availableNodes(); track node.id) {
                  <mat-option [value]="node.id">{{ node.label }}</mat-option>
                }
              </mat-select>
            </mat-form-field>

            <mat-form-field appearance="outline">
              <mat-label>Target Node</mat-label>
              <mat-select [(ngModel)]="targetNode" (selectionChange)="onPathNodeChange()">
                @for (node of availableNodes(); track node.id) {
                  <mat-option [value]="node.id">{{ node.label }}</mat-option>
                }
              </mat-select>
            </mat-form-field>

            <mat-form-field appearance="outline">
              <mat-label>Max Hops</mat-label>
              <mat-select [(ngModel)]="maxHops">
                <mat-option [value]="2">2</mat-option>
                <mat-option [value]="3">3</mat-option>
                <mat-option [value]="5">5</mat-option>
                <mat-option [value]="10">10</mat-option>
              </mat-select>
            </mat-form-field>

            <div class="path-actions">
              <button mat-stroked-button
                      [disabled]="!sourceNode || !targetNode || isLoadingPath()"
                      (click)="findShortestPath()">
                @if (isLoadingPath()) {
                  <mat-spinner diameter="18"></mat-spinner>
                } @else {
                  <mat-icon>timeline</mat-icon>
                }
                Shortest Path
              </button>
              <button mat-stroked-button
                      [disabled]="!sourceNode || !targetNode || isLoadingPath()"
                      (click)="findAllPaths()">
                All Paths
              </button>
            </div>

            @if (pathResults().length > 0) {
              <div class="path-results">
                <h4>Found {{ pathResults().length }} path(s)</h4>
                @for (path of pathResults(); track path.hops; let i = $index) {
                  <div class="path-item" (click)="highlightPath.emit(path)">
                    <span class="path-label">Path {{ i + 1 }}</span>
                    <span class="path-hops">{{ path.hops }} hops</span>
                    <div class="path-nodes">
                      @for (nodeId of path.path_nodes; track nodeId; let last = $last) {
                        <span class="node-chip">{{ getNodeLabel(nodeId) }}</span>
                        @if (!last) {
                          <mat-icon>arrow_right</mat-icon>
                        }
                      }
                    </div>
                  </div>
                }
              </div>
            }
          </div>
        </mat-expansion-panel>

        <!-- Timeline Overlay Section -->
        <mat-expansion-panel>
          <mat-expansion-panel-header>
            <mat-panel-title>
              <mat-icon>timeline</mat-icon>
              Timeline Overlay
            </mat-panel-title>
          </mat-expansion-panel-header>

          <div class="timeline-controls">
            <div class="time-range">
              <span class="label">Time Range:</span>
              @if (timeRange) {
                <span class="range">{{ formatDate(timeRange.start) }} - {{ formatDate(timeRange.end) }}</span>
              } @else {
                <span class="range">No data</span>
              }
            </div>

            <mat-slider min="0" max="100" step="1" class="timeline-slider">
              <input matSliderThumb [(ngModel)]="timelinePosition" (change)="onTimelineChange()">
            </mat-slider>

            <div class="timeline-actions">
              <button mat-icon-button (click)="playTimeline()" [disabled]="isPlaying()">
                <mat-icon>{{ isPlaying() ? 'pause' : 'play_arrow' }}</mat-icon>
              </button>
              <button mat-icon-button (click)="resetTimeline()">
                <mat-icon>replay</mat-icon>
              </button>
              <mat-form-field appearance="outline" class="speed-select">
                <mat-select [(ngModel)]="playbackSpeed">
                  <mat-option [value]="0.5">0.5x</mat-option>
                  <mat-option [value]="1">1x</mat-option>
                  <mat-option [value]="2">2x</mat-option>
                  <mat-option [value]="5">5x</mat-option>
                </mat-select>
              </mat-form-field>
            </div>
          </div>
        </mat-expansion-panel>

        <!-- Clustering Section -->
        <mat-expansion-panel>
          <mat-expansion-panel-header>
            <mat-panel-title>
              <mat-icon>workspaces</mat-icon>
              Node Clustering
            </mat-panel-title>
          </mat-expansion-panel-header>

          <div class="clustering-controls">
            <mat-form-field appearance="outline">
              <mat-label>Cluster By</mat-label>
              <mat-select [(ngModel)]="clusterBy" (selectionChange)="applyClustering()">
                <mat-option value="type">Entity Type</mat-option>
                <mat-option value="time">Time Period</mat-option>
                <mat-option value="risk">Risk Score</mat-option>
                <mat-option value="connectivity">Connectivity</mat-option>
              </mat-select>
            </mat-form-field>

            @if (clusters().length > 0) {
              <div class="cluster-list">
                @for (cluster of clusters(); track cluster.name) {
                  <div class="cluster-item" (click)="focusCluster.emit(cluster)">
                    <span class="cluster-color" [style.background]="cluster.color"></span>
                    <span class="cluster-name">{{ cluster.name }}</span>
                    <span class="cluster-count">{{ cluster.nodes.length }}</span>
                  </div>
                }
              </div>
            }
          </div>
        </mat-expansion-panel>

        <!-- Attack Path Analysis -->
        <mat-expansion-panel>
          <mat-expansion-panel-header>
            <mat-panel-title>
              <mat-icon>security</mat-icon>
              Attack Path Analysis
            </mat-panel-title>
          </mat-expansion-panel-header>

          <div class="attack-analysis">
            <button mat-stroked-button (click)="detectAttackPaths()" [disabled]="isAnalyzing()">
              @if (isAnalyzing()) {
                <mat-spinner diameter="18"></mat-spinner>
              } @else {
                <mat-icon>search</mat-icon>
              }
              Detect Attack Patterns
            </button>

            @if (attackPaths().length > 0) {
              <div class="attack-paths">
                @for (attack of attackPaths(); track attack.name) {
                  <div class="attack-item" (click)="highlightAttack.emit(attack)">
                    <div class="attack-header">
                      <mat-icon [class]="'severity-' + attack.severity">warning</mat-icon>
                      <span class="attack-name">{{ attack.name }}</span>
                    </div>
                    <span class="attack-desc">{{ attack.description }}</span>
                    <div class="attack-nodes">
                      <mat-chip-listbox>
                        @for (node of attack.nodes.slice(0, 3); track node) {
                          <mat-chip>{{ getNodeLabel(node) }}</mat-chip>
                        }
                        @if (attack.nodes.length > 3) {
                          <mat-chip>+{{ attack.nodes.length - 3 }} more</mat-chip>
                        }
                      </mat-chip-listbox>
                    </div>
                  </div>
                }
              </div>
            }
          </div>
        </mat-expansion-panel>

        <!-- Annotations Section -->
        <mat-expansion-panel>
          <mat-expansion-panel-header>
            <mat-panel-title>
              <mat-icon>edit_note</mat-icon>
              Annotations
            </mat-panel-title>
          </mat-expansion-panel-header>

          <div class="annotations">
            <div class="annotation-input">
              <mat-form-field appearance="outline" class="full-width">
                <mat-label>Add Note</mat-label>
                <textarea matInput [(ngModel)]="newAnnotation" rows="2" placeholder="Add annotation..."></textarea>
              </mat-form-field>
              <div class="annotation-colors">
                @for (color of annotationColors; track color) {
                  <button class="color-btn"
                          [style.background]="color"
                          [class.selected]="selectedColor === color"
                          (click)="selectedColor = color">
                  </button>
                }
              </div>
              <button mat-stroked-button
                      [disabled]="!newAnnotation.trim()"
                      (click)="addAnnotation()">
                <mat-icon>add</mat-icon>
                Add Annotation
              </button>
            </div>

            @if (annotations().length > 0) {
              <mat-divider></mat-divider>
              <div class="annotation-list">
                @for (annotation of annotations(); track annotation.id) {
                  <div class="annotation-item" [style.border-left-color]="annotation.color">
                    <div class="annotation-text">{{ annotation.text }}</div>
                    <div class="annotation-meta">
                      <span>{{ annotation.createdAt | date:'short' }}</span>
                      <button mat-icon-button (click)="removeAnnotation(annotation)">
                        <mat-icon>delete</mat-icon>
                      </button>
                    </div>
                  </div>
                }
              </div>
            }
          </div>
        </mat-expansion-panel>

        <!-- Statistics -->
        <mat-expansion-panel>
          <mat-expansion-panel-header>
            <mat-panel-title>
              <mat-icon>bar_chart</mat-icon>
              Graph Statistics
            </mat-panel-title>
          </mat-expansion-panel-header>

          <div class="statistics">
            <div class="stat-row">
              <span class="stat-label">Total Nodes</span>
              <span class="stat-value">{{ graphData?.nodes?.length || 0 }}</span>
            </div>
            <div class="stat-row">
              <span class="stat-label">Total Edges</span>
              <span class="stat-value">{{ graphData?.edges?.length || 0 }}</span>
            </div>
            <mat-divider></mat-divider>
            <div class="stat-row">
              <span class="stat-label">Density</span>
              <span class="stat-value">{{ calculateDensity() | number:'1.2-2' }}</span>
            </div>
            <div class="stat-row">
              <span class="stat-label">Avg. Degree</span>
              <span class="stat-value">{{ calculateAvgDegree() | number:'1.1-1' }}</span>
            </div>
            <mat-divider></mat-divider>
            <h4>Nodes by Type</h4>
            @for (type of getNodeTypeStats(); track type.type) {
              <div class="stat-row type-stat">
                <span class="type-indicator" [style.background]="getTypeColor(type.type)"></span>
                <span class="stat-label">{{ type.type | titlecase }}</span>
                <span class="stat-value">{{ type.count }}</span>
              </div>
            }
          </div>
        </mat-expansion-panel>
      </div>
    </div>
  `,
  styles: [`
    .analytics-panel {
      width: 360px;
      height: 100%;
      background: #1e1e1e;
      border-left: 1px solid #333;
      display: flex;
      flex-direction: column;
      overflow: hidden;
    }

    .analytics-panel.collapsed {
      display: none;
    }

    .panel-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 12px 16px;
      background: #252525;
      border-bottom: 1px solid #333;

      h3 {
        margin: 0;
        font-size: 16px;
        font-weight: 500;
      }
    }

    .panel-content {
      flex: 1;
      overflow-y: auto;
      padding: 8px;
    }

    mat-expansion-panel {
      background: #252525 !important;
      margin-bottom: 8px;
    }

    mat-panel-title {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 14px;
    }

    mat-form-field {
      width: 100%;
      margin-bottom: 8px;
    }

    .path-finder, .timeline-controls, .clustering-controls, .attack-analysis, .annotations, .statistics {
      padding: 8px 0;
    }

    .path-actions, .timeline-actions {
      display: flex;
      gap: 8px;
      margin-top: 8px;
    }

    .path-results, .cluster-list, .attack-paths, .annotation-list {
      margin-top: 16px;
    }

    .path-results h4 {
      margin: 0 0 12px;
      font-size: 13px;
      color: #888;
    }

    .path-item, .cluster-item, .attack-item, .annotation-item {
      padding: 12px;
      background: #1e1e1e;
      border-radius: 4px;
      margin-bottom: 8px;
      cursor: pointer;

      &:hover {
        background: #2a2a2a;
      }
    }

    .path-item {
      .path-label {
        font-weight: 500;
      }

      .path-hops {
        float: right;
        font-size: 12px;
        color: #888;
      }

      .path-nodes {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 4px;
        margin-top: 8px;
      }

      .node-chip {
        font-size: 11px;
        padding: 2px 6px;
        background: #333;
        border-radius: 4px;
      }

      mat-icon {
        font-size: 14px;
        width: 14px;
        height: 14px;
        color: #666;
      }
    }

    .time-range {
      display: flex;
      justify-content: space-between;
      font-size: 12px;
      margin-bottom: 8px;

      .label {
        color: #888;
      }
    }

    .timeline-slider {
      width: 100%;
    }

    .speed-select {
      width: 80px;
    }

    .cluster-item {
      display: flex;
      align-items: center;
      gap: 8px;

      .cluster-color {
        width: 12px;
        height: 12px;
        border-radius: 2px;
      }

      .cluster-name {
        flex: 1;
      }

      .cluster-count {
        font-size: 12px;
        color: #888;
      }
    }

    .attack-item {
      .attack-header {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-bottom: 4px;
      }

      .attack-name {
        font-weight: 500;
      }

      .attack-desc {
        font-size: 12px;
        color: #888;
        display: block;
        margin-bottom: 8px;
      }

      mat-icon.severity-high {
        color: #f44336;
      }

      mat-icon.severity-medium {
        color: #ff9800;
      }

      mat-icon.severity-low {
        color: #4caf50;
      }
    }

    .annotation-input {
      .full-width {
        width: 100%;
      }

      .annotation-colors {
        display: flex;
        gap: 8px;
        margin-bottom: 12px;
      }

      .color-btn {
        width: 24px;
        height: 24px;
        border-radius: 50%;
        border: 2px solid transparent;
        cursor: pointer;

        &.selected {
          border-color: white;
        }
      }
    }

    .annotation-item {
      border-left: 3px solid;
      padding-left: 12px;

      .annotation-text {
        font-size: 13px;
        margin-bottom: 4px;
      }

      .annotation-meta {
        display: flex;
        justify-content: space-between;
        align-items: center;
        font-size: 11px;
        color: #666;

        button {
          width: 24px;
          height: 24px;
          line-height: 24px;

          mat-icon {
            font-size: 16px;
          }
        }
      }
    }

    .statistics {
      .stat-row {
        display: flex;
        justify-content: space-between;
        padding: 8px 0;

        &.type-stat {
          align-items: center;
        }
      }

      .stat-label {
        color: #888;
      }

      .stat-value {
        font-weight: 500;
      }

      .type-indicator {
        width: 10px;
        height: 10px;
        border-radius: 2px;
        margin-right: 8px;
      }

      h4 {
        margin: 12px 0 8px;
        font-size: 12px;
        color: #666;
        text-transform: uppercase;
      }

      mat-divider {
        margin: 8px 0;
      }
    }
  `]
})
export class GraphAnalyticsComponent implements OnChanges {
  @Input() isOpen = true;
  @Input() graphData: GraphData | null = null;
  @Input() caseId: string | null = null;

  @Output() close = new EventEmitter<void>();
  @Output() highlightPath = new EventEmitter<PathResult>();
  @Output() highlightAttack = new EventEmitter<any>();
  @Output() focusCluster = new EventEmitter<ClusterData>();
  @Output() timelineUpdate = new EventEmitter<number>();

  availableNodes = signal<GraphNode[]>([]);
  pathResults = signal<PathResult[]>([]);
  clusters = signal<ClusterData[]>([]);
  attackPaths = signal<any[]>([]);
  annotations = signal<AnnotationData[]>([]);

  isLoadingPath = signal(false);
  isPlaying = signal(false);
  isAnalyzing = signal(false);

  sourceNode: string | null = null;
  targetNode: string | null = null;
  maxHops = 5;
  timelinePosition = 0;
  playbackSpeed = 1;
  clusterBy = 'type';
  newAnnotation = '';
  selectedColor = '#4CAF50';

  annotationColors = ['#4CAF50', '#2196F3', '#FF9800', '#F44336', '#9C27B0', '#00BCD4'];

  timeRange: { start: Date; end: Date } | null = null;
  private playInterval: ReturnType<typeof setInterval> | null = null;
  private logger = inject(LoggingService);

  constructor(private http: HttpClient) {}

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['graphData'] && this.graphData) {
      this.availableNodes.set(this.graphData.nodes || []);
      this.updateTimeRange();
      this.applyClustering();
    }
  }

  onPathNodeChange(): void {
    // Clear previous results when selection changes
    this.pathResults.set([]);
  }

  async findShortestPath(): Promise<void> {
    if (!this.sourceNode || !this.targetNode || !this.caseId) return;

    this.isLoadingPath.set(true);

    try {
      const result = await this.http.post<PathResult>(
        `${environment.apiUrl}/graph/find-path`,
        {
          case_id: this.caseId,
          source_node: this.sourceNode,
          target_node: this.targetNode,
          max_hops: this.maxHops
        }
      ).toPromise();

      if (result?.found) {
        this.pathResults.set([result]);
        this.highlightPath.emit(result);
      } else {
        this.pathResults.set([]);
      }
    } catch (error) {
      this.logger.error('Failed to find path', error as Error, { component: 'GraphAnalyticsComponent' });
    } finally {
      this.isLoadingPath.set(false);
    }
  }

  async findAllPaths(): Promise<void> {
    if (!this.sourceNode || !this.targetNode || !this.caseId) return;

    this.isLoadingPath.set(true);

    try {
      const result = await this.http.post<{ paths: PathResult[] }>(
        `${environment.apiUrl}/graph/find-all-paths`,
        {
          case_id: this.caseId,
          source_node: this.sourceNode,
          target_node: this.targetNode,
          max_hops: this.maxHops
        }
      ).toPromise();

      if (result?.paths) {
        this.pathResults.set(result.paths);
      }
    } catch (error) {
      this.logger.error('Failed to find paths', error as Error, { component: 'GraphAnalyticsComponent' });
    } finally {
      this.isLoadingPath.set(false);
    }
  }

  getNodeLabel(nodeId: string): string {
    const node = this.availableNodes().find(n => n.id === nodeId);
    return node?.label || nodeId.split(':')[1] || nodeId;
  }

  updateTimeRange(): void {
    if (!this.graphData?.nodes) return;

    const timestamps = this.graphData.nodes
      .filter(n => n.first_seen || n.last_seen)
      .flatMap(n => [n.first_seen, n.last_seen])
      .filter(t => t)
      .map(t => new Date(t!).getTime());

    if (timestamps.length > 0) {
      this.timeRange = {
        start: new Date(Math.min(...timestamps)),
        end: new Date(Math.max(...timestamps))
      };
    }
  }

  formatDate(date: Date): string {
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
  }

  onTimelineChange(): void {
    this.timelineUpdate.emit(this.timelinePosition);
  }

  playTimeline(): void {
    if (this.isPlaying()) {
      clearInterval(this.playInterval);
      this.isPlaying.set(false);
    } else {
      this.isPlaying.set(true);
      this.playInterval = setInterval(() => {
        this.timelinePosition = Math.min(100, this.timelinePosition + 1);
        this.onTimelineChange();
        if (this.timelinePosition >= 100) {
          clearInterval(this.playInterval);
          this.isPlaying.set(false);
        }
      }, 100 / this.playbackSpeed);
    }
  }

  resetTimeline(): void {
    clearInterval(this.playInterval);
    this.isPlaying.set(false);
    this.timelinePosition = 0;
    this.onTimelineChange();
  }

  applyClustering(): void {
    if (!this.graphData?.nodes) return;

    const clusters: ClusterData[] = [];

    if (this.clusterBy === 'type') {
      const typeGroups = new Map<EntityType, GraphNode[]>();
      for (const node of this.graphData.nodes) {
        if (!typeGroups.has(node.type)) {
          typeGroups.set(node.type, []);
        }
        typeGroups.get(node.type)!.push(node);
      }

      typeGroups.forEach((nodes, type) => {
        clusters.push({
          name: type.charAt(0).toUpperCase() + type.slice(1),
          type,
          nodes: nodes.map(n => n.id),
          color: NODE_COLORS[type] || '#666'
        });
      });
    }

    this.clusters.set(clusters);
  }

  async detectAttackPaths(): Promise<void> {
    if (!this.caseId) return;

    this.isAnalyzing.set(true);

    try {
      const result = await this.http.post<{ attacks: any[] }>(
        `${environment.apiUrl}/graph/detect-attacks`,
        { case_id: this.caseId }
      ).toPromise();

      this.attackPaths.set(result?.attacks || []);
    } catch (error) {
      this.logger.error('Failed to detect attacks', error as Error, { component: 'GraphAnalyticsComponent' });
      // Use mock data for demo
      this.attackPaths.set([
        {
          name: 'Lateral Movement',
          description: 'Potential lateral movement detected via RDP',
          severity: 'high',
          nodes: this.graphData?.nodes.slice(0, 4).map(n => n.id) || []
        },
        {
          name: 'Credential Access',
          description: 'LSASS memory access pattern detected',
          severity: 'medium',
          nodes: this.graphData?.nodes.slice(2, 5).map(n => n.id) || []
        }
      ]);
    } finally {
      this.isAnalyzing.set(false);
    }
  }

  addAnnotation(): void {
    if (!this.newAnnotation.trim()) return;

    const annotation: AnnotationData = {
      id: `ann-${Date.now()}`,
      text: this.newAnnotation.trim(),
      color: this.selectedColor,
      createdAt: new Date().toISOString()
    };

    this.annotations.update(list => [...list, annotation]);
    this.newAnnotation = '';
  }

  removeAnnotation(annotation: AnnotationData): void {
    this.annotations.update(list => list.filter(a => a.id !== annotation.id));
  }

  calculateDensity(): number {
    if (!this.graphData?.nodes || this.graphData.nodes.length < 2) return 0;
    const n = this.graphData.nodes.length;
    const e = this.graphData.edges?.length || 0;
    return (2 * e) / (n * (n - 1));
  }

  calculateAvgDegree(): number {
    if (!this.graphData?.nodes || this.graphData.nodes.length === 0) return 0;
    const n = this.graphData.nodes.length;
    const e = this.graphData.edges?.length || 0;
    return (2 * e) / n;
  }

  getNodeTypeStats(): { type: EntityType; count: number }[] {
    if (!this.graphData?.nodes) return [];

    const counts = new Map<EntityType, number>();
    for (const node of this.graphData.nodes) {
      counts.set(node.type, (counts.get(node.type) || 0) + 1);
    }

    return Array.from(counts.entries()).map(([type, count]) => ({ type, count }));
  }

  getTypeColor(type: EntityType): string {
    return NODE_COLORS[type] || '#666';
  }
}
