import { Component, OnInit, signal, computed, effect } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterModule, ActivatedRoute } from '@angular/router';
import { MatCardModule } from '@angular/material/card';
import { MatIconModule } from '@angular/material/icon';
import { MatButtonModule } from '@angular/material/button';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatChipsModule } from '@angular/material/chips';
import { MatTabsModule } from '@angular/material/tabs';
import { MatButtonToggleModule } from '@angular/material/button-toggle';
import { MatMenuModule } from '@angular/material/menu';
import {
  MitreService,
  MitreMatrixColumn,
  MitreTechniqueBasic,
  MitreTechniqueDetail,
  TechniqueCoverage,
  HeatmapItem,
  TimeRange
} from '../../core/services/mitre.service';
import { MitreBadgeComponent } from '../../shared/components/mitre-badge.component';
import { CoverageAnalysisComponent } from './coverage-analysis.component';
import { LayerManagerComponent } from './layer-manager.component';

type ViewMode = 'coverage' | 'heatmap';

@Component({
  selector: 'app-mitre',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    RouterModule,
    MatCardModule,
    MatIconModule,
    MatButtonModule,
    MatTooltipModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    MatProgressSpinnerModule,
    MatChipsModule,
    MatTabsModule,
    MatButtonToggleModule,
    MatMenuModule,
    MitreBadgeComponent,
    CoverageAnalysisComponent,
    LayerManagerComponent
  ],
  template: `
    <div class="mitre">
      <!-- Header -->
      <div class="page-header">
        <div class="header-content">
          <h1>
            <mat-icon>security</mat-icon>
            MITRE ATT&CK Framework
          </h1>
          <p class="subtitle">Visualize adversary tactics and techniques mapped to your detections and incidents</p>
        </div>
        <div class="header-actions">
          <mat-form-field appearance="outline" class="search-field">
            <mat-label>Search techniques</mat-label>
            <mat-icon matPrefix>search</mat-icon>
            <input matInput [(ngModel)]="searchQuery" (keyup)="filterTechniques()" placeholder="e.g., T1059 or PowerShell">
          </mat-form-field>
          <button mat-icon-button [matMenuTriggerFor]="actionsMenu" matTooltip="Actions">
            <mat-icon>more_vert</mat-icon>
          </button>
          <mat-menu #actionsMenu="matMenu">
            <button mat-menu-item (click)="exportLayer()">
              <mat-icon>download</mat-icon>
              <span>Export Navigator Layer</span>
            </button>
            <button mat-menu-item (click)="refresh()">
              <mat-icon>refresh</mat-icon>
              <span>Refresh Data</span>
            </button>
          </mat-menu>
        </div>
      </div>

      <!-- Tabs -->
      <mat-tab-group [(selectedIndex)]="selectedTab">
        <!-- Matrix Tab -->
        <mat-tab label="Attack Matrix">
          <div class="tab-content">
            <!-- View Controls -->
            <div class="view-controls">
              <div class="control-group">
                <span class="control-label">View:</span>
                <mat-button-toggle-group [value]="viewMode()" (change)="setViewMode($event.value)">
                  <mat-button-toggle value="coverage">
                    <mat-icon>verified</mat-icon>
                    Coverage
                  </mat-button-toggle>
                  <mat-button-toggle value="heatmap">
                    <mat-icon>whatshot</mat-icon>
                    Activity
                  </mat-button-toggle>
                </mat-button-toggle-group>
              </div>
              @if (viewMode() === 'heatmap') {
                <div class="control-group">
                  <span class="control-label">Time Range:</span>
                  <mat-button-toggle-group [value]="timeRange()" (change)="setTimeRange($event.value)">
                    <mat-button-toggle value="24h">24h</mat-button-toggle>
                    <mat-button-toggle value="7d">7d</mat-button-toggle>
                    <mat-button-toggle value="30d">30d</mat-button-toggle>
                  </mat-button-toggle-group>
                </div>
              }
              <div class="legend">
                @if (viewMode() === 'coverage') {
                  <span class="legend-title">Coverage:</span>
                  <div class="legend-item">
                    <div class="legend-color high"></div>
                    <span>3+ rules</span>
                  </div>
                  <div class="legend-item">
                    <div class="legend-color medium"></div>
                    <span>1-2 rules</span>
                  </div>
                  <div class="legend-item">
                    <div class="legend-color none"></div>
                    <span>No coverage</span>
                  </div>
                } @else {
                  <span class="legend-title">Activity:</span>
                  <div class="legend-item">
                    <div class="legend-color hot"></div>
                    <span>High</span>
                  </div>
                  <div class="legend-item">
                    <div class="legend-color warm"></div>
                    <span>Medium</span>
                  </div>
                  <div class="legend-item">
                    <div class="legend-color cool"></div>
                    <span>Low</span>
                  </div>
                }
              </div>
            </div>

            <!-- Matrix Grid -->
            @if (isLoading()) {
              <div class="loading">
                <mat-spinner diameter="40"></mat-spinner>
              </div>
            } @else {
              <div class="matrix-container">
                <div class="matrix-scroll">
                  <div class="matrix">
                    @for (column of matrixColumns(); track column.tactic.id) {
                      <div class="tactic-column">
                        <div class="tactic-header" [matTooltip]="column.tactic.description">
                          <span class="tactic-name">{{ formatTacticName(column.tactic.name) }}</span>
                          <span class="technique-count">{{ getFilteredTechniques(column).length }} techniques</span>
                        </div>
                        <div class="techniques-list">
                          @for (technique of getFilteredTechniques(column); track technique.id) {
                            <div class="technique-cell"
                                 [class]="getTechniqueClasses(technique)"
                                 [class.highlighted]="isHighlighted(technique)"
                                 (click)="selectTechnique(technique)"
                                 [matTooltip]="getTechniqueTooltip(technique)">
                              <span class="technique-id">{{ technique.id }}</span>
                              <span class="technique-name">{{ technique.name }}</span>
                              @if (getActivityCount(technique.id) > 0) {
                                <span class="activity-badge">{{ getActivityCount(technique.id) }}</span>
                              }
                              @if (technique.subtechniques.length > 0) {
                                <span class="subtechnique-indicator">+{{ technique.subtechniques.length }}</span>
                              }
                            </div>
                          }
                        </div>
                      </div>
                    }
                  </div>
                </div>
              </div>
            }

            <!-- Selected Technique Detail -->
            @if (selectedTechnique()) {
              <mat-card class="technique-detail">
                <mat-card-header>
                  <mat-icon mat-card-avatar>security</mat-icon>
                  <mat-card-title>{{ selectedTechnique()!.id }}: {{ selectedTechnique()!.name }}</mat-card-title>
                  <mat-card-subtitle>
                    Tactics: {{ selectedTechnique()!.tactics.join(', ') }}
                  </mat-card-subtitle>
                </mat-card-header>
                <mat-card-content>
                  <p class="technique-description">{{ selectedTechnique()!.description }}</p>

                  @if (selectedTechnique()!.platforms.length > 0) {
                    <div class="technique-platforms">
                      <span class="label">Platforms:</span>
                      <div class="platform-chips">
                        @for (platform of selectedTechnique()!.platforms; track platform) {
                          <span class="platform-chip">{{ platform }}</span>
                        }
                      </div>
                    </div>
                  }

                  @if (selectedTechnique()!.subtechniques.length > 0) {
                    <div class="subtechniques">
                      <span class="label">Sub-techniques:</span>
                      <div class="subtechnique-list">
                        @for (subId of selectedTechnique()!.subtechniques; track subId) {
                          <app-mitre-badge [techniqueId]="subId" [compact]="true" />
                        }
                      </div>
                    </div>
                  }

                  <div class="technique-stats">
                    <div class="stat-box">
                      <span class="stat-value">{{ getCoverageRuleCount(selectedTechnique()!.id) }}</span>
                      <span class="stat-label">Detection Rules</span>
                    </div>
                    <div class="stat-box">
                      <span class="stat-value">{{ getActivityCount(selectedTechnique()!.id) }}</span>
                      <span class="stat-label">Recent Alerts</span>
                    </div>
                  </div>
                </mat-card-content>
                <mat-card-actions align="end">
                  <button mat-button [routerLink]="['/analytics']" [queryParams]="{technique: selectedTechnique()!.id}">
                    <mat-icon>rule</mat-icon>
                    View Rules
                  </button>
                  <button mat-button [routerLink]="['/hunting']" [queryParams]="{technique: selectedTechnique()!.id}">
                    <mat-icon>manage_search</mat-icon>
                    Hunt
                  </button>
                  <a mat-button [href]="selectedTechnique()!.url" target="_blank" color="primary">
                    <mat-icon>open_in_new</mat-icon>
                    MITRE ATT&CK
                  </a>
                </mat-card-actions>
              </mat-card>
            }

            <!-- Coverage Summary -->
            <div class="coverage-summary">
              <mat-card class="summary-card">
                <h3>Coverage Summary</h3>
                <div class="summary-grid">
                  <div class="summary-item">
                    <span class="summary-value">{{ techniqueCount() }}</span>
                    <span class="summary-label">Total Techniques</span>
                  </div>
                  <div class="summary-item">
                    <span class="summary-value">{{ coveredCount() }}</span>
                    <span class="summary-label">With Detection</span>
                  </div>
                  <div class="summary-item">
                    <span class="summary-value">{{ coveragePercent() }}%</span>
                    <span class="summary-label">Coverage</span>
                  </div>
                  <div class="summary-item">
                    <span class="summary-value">{{ activeCount() }}</span>
                    <span class="summary-label">With Activity</span>
                  </div>
                </div>
              </mat-card>
            </div>
          </div>
        </mat-tab>

        <!-- Coverage Analysis Tab -->
        <mat-tab label="Coverage Analysis">
          <app-coverage-analysis />
        </mat-tab>

        <!-- Navigator Layers Tab -->
        <mat-tab label="Navigator Layers">
          <app-layer-manager (layerApplied)="onLayerApplied($event)" />
        </mat-tab>
      </mat-tab-group>
    </div>
  `,
  styles: [`
    .mitre {
      max-width: 100%;
    }

    .page-header {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      margin-bottom: 24px;
      flex-wrap: wrap;
      gap: 16px;
    }

    .header-content h1 {
      display: flex;
      align-items: center;
      gap: 12px;
      font-family: var(--font-display);
      font-size: 24px;
      font-weight: 700;
      margin: 0 0 4px 0;
      color: var(--text-primary);

      mat-icon {
        font-size: 28px;
        width: 28px;
        height: 28px;
        color: var(--accent);
      }
    }

    .subtitle {
      color: var(--text-secondary);
      margin: 0;
      font-size: 14px;
    }

    .header-actions {
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .search-field {
      width: 280px;
    }

    /* Tab Content */
    .tab-content {
      padding: 24px 0;
    }

    /* View Controls */
    .view-controls {
      display: flex;
      align-items: center;
      gap: 24px;
      margin-bottom: 16px;
      padding: 12px 16px;
      background: var(--bg-card);
      border: 1px solid var(--border-color);
      border-radius: 8px;
      flex-wrap: wrap;
    }

    .control-group {
      display: flex;
      align-items: center;
      gap: 12px;
    }

    .control-label {
      font-size: 13px;
      font-weight: 500;
      color: var(--text-secondary);
    }

    mat-button-toggle-group {
      height: 32px;
      border: 1px solid var(--border-color);

      ::ng-deep .mat-button-toggle {
        background: var(--bg-card);

        &.mat-button-toggle-checked {
          background: var(--accent);
          color: white;
        }

        .mat-button-toggle-label-content {
          display: flex;
          align-items: center;
          gap: 4px;
          font-size: 12px;
          line-height: 30px;
          padding: 0 12px;

          mat-icon {
            font-size: 16px;
            width: 16px;
            height: 16px;
          }
        }
      }
    }

    /* Legend */
    .legend {
      display: flex;
      align-items: center;
      gap: 16px;
      margin-left: auto;
    }

    .legend-title {
      font-size: 12px;
      font-weight: 500;
      color: var(--text-secondary);
    }

    .legend-item {
      display: flex;
      align-items: center;
      gap: 6px;
      font-size: 11px;
      color: var(--text-secondary);
    }

    .legend-color {
      width: 14px;
      height: 14px;
      border-radius: 3px;

      &.high { background: var(--success); }
      &.medium { background: var(--warning); }
      &.none { background: var(--bg-tertiary); }
      &.hot { background: var(--danger); }
      &.warm { background: #ff7b6b; }
      &.cool { background: #ffa198; }
    }

    .loading {
      display: flex;
      justify-content: center;
      padding: 48px;
    }

    /* Matrix Container */
    .matrix-container {
      background: var(--bg-card);
      border: 1px solid var(--border-color);
      border-radius: 8px;
      padding: 16px;
      margin-bottom: 24px;
    }

    .matrix-scroll {
      overflow-x: auto;
    }

    .matrix {
      display: flex;
      gap: 2px;
      min-width: max-content;
    }

    .tactic-column {
      width: 160px;
      flex-shrink: 0;
    }

    .tactic-header {
      background: var(--bg-tertiary);
      padding: 12px 8px;
      text-align: center;
      border-radius: 4px 4px 0 0;
      margin-bottom: 2px;
      cursor: help;
    }

    .tactic-name {
      display: block;
      font-size: 11px;
      font-weight: 600;
      color: var(--text-primary);
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }

    .technique-count {
      display: block;
      font-size: 10px;
      color: var(--text-muted);
      margin-top: 2px;
    }

    .techniques-list {
      display: flex;
      flex-direction: column;
      gap: 2px;
    }

    .technique-cell {
      background: var(--bg-tertiary);
      padding: 6px 8px;
      border-radius: 3px;
      cursor: pointer;
      transition: all 0.15s ease;
      position: relative;
      border-left: 3px solid transparent;

      &:hover {
        background: rgba(88, 166, 255, 0.2);
        border-left-color: var(--accent);
      }

      &.highlighted {
        background: rgba(88, 166, 255, 0.3);
        border-left-color: var(--accent);
      }

      &.coverage-high {
        background: rgba(63, 185, 80, 0.15);
        border-left-color: var(--success);
      }

      &.coverage-medium {
        background: rgba(210, 153, 34, 0.15);
        border-left-color: var(--warning);
      }

      &.activity-hot {
        background: rgba(248, 81, 73, 0.2);
        border-left-color: var(--danger);
      }

      &.activity-warm {
        background: rgba(255, 123, 114, 0.15);
        border-left-color: #ff7b6b;
      }

      &.activity-cool {
        background: rgba(255, 161, 152, 0.1);
        border-left-color: #ffa198;
      }
    }

    .technique-id {
      display: block;
      font-size: 9px;
      font-family: var(--font-mono);
      color: var(--accent);
      margin-bottom: 1px;
    }

    .technique-name {
      display: block;
      font-size: 10px;
      color: var(--text-primary);
      line-height: 1.3;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .activity-badge {
      position: absolute;
      top: 4px;
      right: 4px;
      background: var(--danger);
      color: white;
      font-size: 9px;
      padding: 1px 4px;
      border-radius: 3px;
      font-weight: 600;
    }

    .subtechnique-indicator {
      position: absolute;
      bottom: 2px;
      right: 4px;
      font-size: 9px;
      color: var(--text-muted);
    }

    /* Technique Detail */
    .technique-detail {
      background: var(--bg-card);
      border: 1px solid var(--border-color);
      margin-bottom: 24px;
    }

    .technique-description {
      color: var(--text-secondary);
      line-height: 1.6;
      margin-bottom: 16px;
      max-height: 100px;
      overflow: hidden;
    }

    .technique-platforms, .subtechniques {
      margin-bottom: 16px;
    }

    .label {
      display: block;
      font-size: 11px;
      font-weight: 500;
      color: var(--text-muted);
      text-transform: uppercase;
      margin-bottom: 8px;
    }

    .platform-chips, .subtechnique-list {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
    }

    .platform-chip {
      font-size: 11px;
      padding: 4px 10px;
      background: var(--bg-tertiary);
      border-radius: 4px;
      color: var(--text-secondary);
    }

    .technique-stats {
      display: flex;
      gap: 24px;
    }

    .stat-box {
      display: flex;
      flex-direction: column;
      padding: 16px 24px;
      background: var(--bg-tertiary);
      border-radius: 8px;
    }

    .stat-value {
      font-family: var(--font-display);
      font-size: 24px;
      font-weight: 700;
      color: var(--text-primary);
    }

    .stat-label {
      font-size: 12px;
      color: var(--text-secondary);
    }

    /* Coverage Summary */
    .coverage-summary {
      margin-bottom: 24px;
    }

    .summary-card {
      background: var(--bg-card);
      border: 1px solid var(--border-color);
      padding: 20px;

      h3 {
        margin: 0 0 16px 0;
        font-size: 16px;
        font-weight: 600;
      }
    }

    .summary-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
      gap: 16px;
    }

    .summary-item {
      display: flex;
      flex-direction: column;
      align-items: center;
      padding: 16px;
      background: var(--bg-tertiary);
      border-radius: 8px;
    }

    .summary-value {
      font-family: var(--font-display);
      font-size: 28px;
      font-weight: 700;
      color: var(--accent);
    }

    .summary-label {
      font-size: 12px;
      color: var(--text-secondary);
      text-align: center;
    }
  `]
})
export class MitreComponent implements OnInit {
  private mitreService: MitreService;
  private route: ActivatedRoute;

  searchQuery = '';
  selectedTab = 0;

  viewMode = signal<ViewMode>('coverage');
  timeRange = signal<TimeRange>('7d');
  selectedTechnique = signal<MitreTechniqueDetail | null>(null);

  // From service
  isLoading = computed(() => this.mitreService.isLoading());
  matrixColumns = computed(() => this.mitreService.matrixColumns());
  techniqueCount = computed(() => this.mitreService.techniqueCount());
  coverageMap = computed(() => this.mitreService.coverageMap());
  heatmapMap = computed(() => this.mitreService.heatmapMap());
  coverageStats = computed(() => this.mitreService.coverageStats());

  // Computed stats
  coveredCount = computed(() => this.coverageStats()?.covered_techniques ?? 0);
  coveragePercent = computed(() => this.coverageStats()?.coverage_percent ?? 0);
  activeCount = computed(() => this.mitreService.heatmap()?.unique_techniques ?? 0);

  constructor(mitreService: MitreService, route: ActivatedRoute) {
    this.mitreService = mitreService;
    this.route = route;

    // Load heatmap when view mode changes
    effect(() => {
      if (this.viewMode() === 'heatmap') {
        this.mitreService.loadHeatmap(this.timeRange());
      }
    });
  }

  ngOnInit(): void {
    // Load initial data
    this.mitreService.loadMatrix();
    this.mitreService.loadCoverage();

    // Check for technique in query params
    this.route.queryParams.subscribe(params => {
      const techniqueId = params['technique'];
      if (techniqueId) {
        this.loadTechniqueDetail(techniqueId);
      }
    });
  }

  setViewMode(mode: ViewMode): void {
    this.viewMode.set(mode);
  }

  setTimeRange(range: TimeRange): void {
    this.timeRange.set(range);
    this.mitreService.loadHeatmap(range);
  }

  filterTechniques(): void {
    // Filtering is handled in getFilteredTechniques
  }

  getFilteredTechniques(column: MitreMatrixColumn): MitreTechniqueBasic[] {
    if (!this.searchQuery) return column.techniques;

    const query = this.searchQuery.toLowerCase();
    return column.techniques.filter(t =>
      t.id.toLowerCase().includes(query) ||
      t.name.toLowerCase().includes(query)
    );
  }

  formatTacticName(name: string): string {
    // Shorten long tactic names
    if (name.length > 16) {
      return name.split(' ').map(w => w.substring(0, 3)).join(' ');
    }
    return name;
  }

  getTechniqueClasses(technique: MitreTechniqueBasic): string {
    const classes: string[] = [];
    const mode = this.viewMode();

    if (mode === 'coverage') {
      const coverage = this.coverageMap().get(technique.id);
      if (coverage) {
        if (coverage.rule_count >= 3) {
          classes.push('coverage-high');
        } else {
          classes.push('coverage-medium');
        }
      }
    } else {
      const heatmap = this.heatmapMap().get(technique.id);
      if (heatmap) {
        if (heatmap.intensity > 0.7) {
          classes.push('activity-hot');
        } else if (heatmap.intensity > 0.3) {
          classes.push('activity-warm');
        } else {
          classes.push('activity-cool');
        }
      }
    }

    return classes.join(' ');
  }

  isHighlighted(technique: MitreTechniqueBasic): boolean {
    return this.selectedTechnique()?.id === technique.id;
  }

  getTechniqueTooltip(technique: MitreTechniqueBasic): string {
    const coverage = this.coverageMap().get(technique.id);
    const heatmap = this.heatmapMap().get(technique.id);

    let tooltip = `${technique.id}: ${technique.name}`;
    if (coverage) {
      tooltip += `\nRules: ${coverage.rule_count}`;
    }
    if (heatmap) {
      tooltip += `\nAlerts: ${heatmap.count}`;
    }
    return tooltip;
  }

  getCoverageRuleCount(techniqueId: string): number {
    return this.coverageMap().get(techniqueId)?.rule_count ?? 0;
  }

  getActivityCount(techniqueId: string): number {
    return this.heatmapMap().get(techniqueId)?.count ?? 0;
  }

  selectTechnique(technique: MitreTechniqueBasic): void {
    this.loadTechniqueDetail(technique.id);
  }

  private loadTechniqueDetail(techniqueId: string): void {
    this.mitreService.getTechnique(techniqueId).subscribe({
      next: (detail) => this.selectedTechnique.set(detail),
      error: () => this.selectedTechnique.set(null)
    });
  }

  exportLayer(): void {
    this.mitreService.downloadLayer('Eleanor Detection Coverage');
  }

  refresh(): void {
    this.mitreService.refreshAll();
  }

  onLayerApplied(layer: any): void {
    // Could overlay imported layer colors on matrix
    console.log('Layer applied:', layer);
    this.selectedTab = 0; // Switch to matrix tab
  }
}
