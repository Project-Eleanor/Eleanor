import { Component, OnInit, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { MatCardModule } from '@angular/material/card';
import { MatIconModule } from '@angular/material/icon';
import { MatButtonModule } from '@angular/material/button';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatTabsModule } from '@angular/material/tabs';
import { MatChipsModule } from '@angular/material/chips';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatExpansionModule } from '@angular/material/expansion';
import { MitreService, CoverageResponse, CoverageGap, TacticCoverage, TechniqueCoverage } from '../../core/services/mitre.service';
import { MitreBadgeComponent } from '../../shared/components/mitre-badge.component';

@Component({
  selector: 'app-coverage-analysis',
  standalone: true,
  imports: [
    CommonModule,
    RouterModule,
    MatCardModule,
    MatIconModule,
    MatButtonModule,
    MatProgressBarModule,
    MatProgressSpinnerModule,
    MatTabsModule,
    MatChipsModule,
    MatTooltipModule,
    MatExpansionModule,
    MitreBadgeComponent
  ],
  template: `
    <div class="coverage-analysis">
      @if (isLoading()) {
        <div class="loading">
          <mat-spinner diameter="40"></mat-spinner>
          <span>Loading coverage analysis...</span>
        </div>
      } @else {
        <!-- Summary Cards -->
        <div class="summary-cards">
          <mat-card class="summary-card coverage-card">
            <div class="summary-icon success">
              <mat-icon>verified</mat-icon>
            </div>
            <div class="summary-content">
              <span class="summary-value">{{ stats()?.coverage_percent }}%</span>
              <span class="summary-label">Overall Coverage</span>
            </div>
            <mat-progress-bar mode="determinate" [value]="stats()?.coverage_percent ?? 0"></mat-progress-bar>
          </mat-card>

          <mat-card class="summary-card">
            <div class="summary-icon info">
              <mat-icon>security</mat-icon>
            </div>
            <div class="summary-content">
              <span class="summary-value">{{ stats()?.covered_techniques }} / {{ stats()?.total_techniques }}</span>
              <span class="summary-label">Techniques Covered</span>
            </div>
          </mat-card>

          <mat-card class="summary-card">
            <div class="summary-icon accent">
              <mat-icon>rule</mat-icon>
            </div>
            <div class="summary-content">
              <span class="summary-value">{{ stats()?.total_rules }}</span>
              <span class="summary-label">Detection Rules</span>
            </div>
          </mat-card>

          <mat-card class="summary-card">
            <div class="summary-icon warning">
              <mat-icon>warning_amber</mat-icon>
            </div>
            <div class="summary-content">
              <span class="summary-value">{{ gaps().length }}</span>
              <span class="summary-label">Coverage Gaps</span>
            </div>
          </mat-card>
        </div>

        <mat-tab-group>
          <!-- By Tactic Tab -->
          <mat-tab label="By Tactic">
            <div class="tab-content">
              <div class="tactic-list">
                @for (tactic of tacticCoverage(); track tactic.tactic_id) {
                  <div class="tactic-row">
                    <div class="tactic-info">
                      <span class="tactic-name">{{ tactic.tactic_name }}</span>
                      <span class="tactic-stats">
                        {{ tactic.covered_techniques }}/{{ tactic.total_techniques }} techniques
                      </span>
                    </div>
                    <div class="tactic-progress">
                      <mat-progress-bar
                        mode="determinate"
                        [value]="tactic.coverage_percent"
                        [class]="getCoverageClass(tactic.coverage_percent)">
                      </mat-progress-bar>
                      <span class="coverage-percent">{{ tactic.coverage_percent }}%</span>
                    </div>
                  </div>
                }
              </div>
            </div>
          </mat-tab>

          <!-- Covered Techniques Tab -->
          <mat-tab label="Covered Techniques">
            <div class="tab-content">
              <div class="technique-list">
                @for (tech of coveredTechniques(); track tech.technique_id) {
                  <mat-expansion-panel>
                    <mat-expansion-panel-header>
                      <mat-panel-title>
                        <app-mitre-badge [techniqueId]="tech.technique_id" [clickable]="false" />
                        <span class="tech-name">{{ tech.technique_name }}</span>
                      </mat-panel-title>
                      <mat-panel-description>
                        <span class="rule-count">{{ tech.rule_count }} rules</span>
                      </mat-panel-description>
                    </mat-expansion-panel-header>

                    <div class="rules-list">
                      @for (rule of tech.rules; track rule.id) {
                        <div class="rule-item" [routerLink]="['/analytics']" [queryParams]="{rule: rule.id}">
                          <span class="rule-name">{{ rule.name }}</span>
                          <span class="severity-badge" [class]="rule.severity">{{ rule.severity }}</span>
                        </div>
                      }
                    </div>
                  </mat-expansion-panel>
                }
              </div>
            </div>
          </mat-tab>

          <!-- Coverage Gaps Tab -->
          <mat-tab label="Coverage Gaps">
            <div class="tab-content">
              @if (gaps().length === 0) {
                <div class="empty-state">
                  <mat-icon>check_circle</mat-icon>
                  <p>Excellent! No high-priority coverage gaps detected.</p>
                </div>
              } @else {
                <div class="gaps-list">
                  @for (gap of gaps(); track gap.technique_id) {
                    <mat-card class="gap-card">
                      <div class="gap-header">
                        <app-mitre-badge [techniqueId]="gap.technique_id" [techniqueName]="gap.technique_name" [showName]="true" />
                        <a mat-icon-button [href]="gap.url" target="_blank" matTooltip="View on MITRE ATT&CK">
                          <mat-icon>open_in_new</mat-icon>
                        </a>
                      </div>
                      <div class="gap-details">
                        <div class="gap-row">
                          <span class="gap-label">Tactics:</span>
                          <span class="gap-value">{{ gap.tactics.join(', ') }}</span>
                        </div>
                        @if (gap.platforms.length > 0) {
                          <div class="gap-row">
                            <span class="gap-label">Platforms:</span>
                            <div class="platform-chips">
                              @for (platform of gap.platforms.slice(0, 5); track platform) {
                                <span class="platform-chip">{{ platform }}</span>
                              }
                            </div>
                          </div>
                        }
                        @if (gap.detection_guidance) {
                          <div class="gap-row">
                            <span class="gap-label">Detection Guidance:</span>
                            <p class="detection-guidance">{{ gap.detection_guidance }}</p>
                          </div>
                        }
                      </div>
                      <div class="gap-actions">
                        <button mat-button color="primary" [routerLink]="['/analytics']" [queryParams]="{newRule: true, technique: gap.technique_id}">
                          <mat-icon>add</mat-icon>
                          Create Rule
                        </button>
                        <button mat-button [routerLink]="['/hunting']" [queryParams]="{technique: gap.technique_id}">
                          <mat-icon>search</mat-icon>
                          Hunt
                        </button>
                      </div>
                    </mat-card>
                  }
                </div>
              }
            </div>
          </mat-tab>
        </mat-tab-group>
      }
    </div>
  `,
  styles: [`
    .coverage-analysis {
      padding: 16px 0;
    }

    .loading {
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 16px;
      padding: 48px;
      color: var(--text-secondary);
    }

    /* Summary Cards */
    .summary-cards {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
      gap: 16px;
      margin-bottom: 24px;
    }

    .summary-card {
      display: flex;
      align-items: center;
      gap: 16px;
      padding: 20px;
      background: var(--bg-card);
      border: 1px solid var(--border-color);

      &.coverage-card {
        flex-direction: column;
        align-items: stretch;

        mat-progress-bar {
          margin-top: 12px;
        }

        .summary-icon, .summary-content {
          width: auto;
        }

        .summary-content {
          text-align: center;
        }
      }
    }

    .summary-icon {
      width: 48px;
      height: 48px;
      border-radius: 12px;
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;

      mat-icon {
        font-size: 24px;
        width: 24px;
        height: 24px;
      }

      &.success { background: rgba(63, 185, 80, 0.2); mat-icon { color: var(--success); } }
      &.info { background: rgba(88, 166, 255, 0.2); mat-icon { color: var(--info); } }
      &.accent { background: rgba(74, 158, 255, 0.2); mat-icon { color: var(--accent); } }
      &.warning { background: rgba(210, 153, 34, 0.2); mat-icon { color: var(--warning); } }
    }

    .summary-content {
      display: flex;
      flex-direction: column;
    }

    .summary-value {
      font-family: var(--font-display);
      font-size: 24px;
      font-weight: 700;
      color: var(--text-primary);
    }

    .summary-label {
      font-size: 12px;
      color: var(--text-secondary);
    }

    /* Tabs */
    .tab-content {
      padding: 24px 0;
    }

    /* Tactic List */
    .tactic-list {
      display: flex;
      flex-direction: column;
      gap: 12px;
    }

    .tactic-row {
      display: flex;
      align-items: center;
      gap: 16px;
      padding: 12px 16px;
      background: var(--bg-card);
      border: 1px solid var(--border-color);
      border-radius: 8px;
    }

    .tactic-info {
      width: 200px;
      flex-shrink: 0;
    }

    .tactic-name {
      display: block;
      font-weight: 500;
      color: var(--text-primary);
    }

    .tactic-stats {
      font-size: 12px;
      color: var(--text-secondary);
    }

    .tactic-progress {
      flex: 1;
      display: flex;
      align-items: center;
      gap: 12px;

      mat-progress-bar {
        flex: 1;
      }
    }

    .coverage-percent {
      width: 50px;
      text-align: right;
      font-family: var(--font-mono);
      font-size: 13px;
      color: var(--text-secondary);
    }

    /* Progress bar colors */
    ::ng-deep {
      .mat-mdc-progress-bar {
        &.high .mdc-linear-progress__bar-inner {
          border-color: var(--success);
        }
        &.medium .mdc-linear-progress__bar-inner {
          border-color: var(--warning);
        }
        &.low .mdc-linear-progress__bar-inner {
          border-color: var(--danger);
        }
      }
    }

    /* Technique List */
    .technique-list {
      display: flex;
      flex-direction: column;
      gap: 8px;
    }

    .tech-name {
      margin-left: 8px;
      color: var(--text-primary);
    }

    .rule-count {
      font-size: 12px;
      color: var(--text-secondary);
    }

    .rules-list {
      padding: 8px 0;
    }

    .rule-item {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 8px 12px;
      cursor: pointer;
      border-radius: 4px;
      transition: background 0.2s ease;

      &:hover {
        background: var(--bg-secondary);
      }
    }

    .rule-name {
      font-size: 13px;
      color: var(--text-primary);
    }

    .severity-badge {
      font-size: 10px;
      font-weight: 600;
      padding: 2px 8px;
      border-radius: 4px;
      text-transform: uppercase;

      &.critical { background: var(--severity-critical); color: white; }
      &.high { background: var(--severity-high); color: white; }
      &.medium { background: var(--severity-medium); color: black; }
      &.low { background: var(--severity-low); color: white; }
    }

    /* Gaps List */
    .empty-state {
      display: flex;
      flex-direction: column;
      align-items: center;
      padding: 48px;
      color: var(--success);

      mat-icon {
        font-size: 48px;
        width: 48px;
        height: 48px;
        margin-bottom: 16px;
      }

      p {
        margin: 0;
        font-size: 16px;
      }
    }

    .gaps-list {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(400px, 1fr));
      gap: 16px;
    }

    .gap-card {
      padding: 16px;
      background: var(--bg-card);
      border: 1px solid var(--border-color);
    }

    .gap-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 12px;
    }

    .gap-details {
      display: flex;
      flex-direction: column;
      gap: 8px;
    }

    .gap-row {
      display: flex;
      flex-direction: column;
      gap: 4px;
    }

    .gap-label {
      font-size: 11px;
      font-weight: 500;
      color: var(--text-muted);
      text-transform: uppercase;
    }

    .gap-value {
      font-size: 13px;
      color: var(--text-secondary);
    }

    .platform-chips {
      display: flex;
      flex-wrap: wrap;
      gap: 4px;
    }

    .platform-chip {
      font-size: 11px;
      padding: 2px 8px;
      background: var(--bg-tertiary);
      border-radius: 4px;
      color: var(--text-secondary);
    }

    .detection-guidance {
      font-size: 12px;
      color: var(--text-secondary);
      line-height: 1.5;
      margin: 0;
      max-height: 80px;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    .gap-actions {
      display: flex;
      gap: 8px;
      margin-top: 12px;
      padding-top: 12px;
      border-top: 1px solid var(--border-color);
    }
  `]
})
export class CoverageAnalysisComponent implements OnInit {
  private mitreService: MitreService;

  isLoading = signal(true);
  coverage = signal<CoverageResponse | null>(null);
  gaps = signal<CoverageGap[]>([]);

  stats = computed(() => this.coverage()?.statistics ?? null);
  tacticCoverage = computed(() => this.coverage()?.by_tactic ?? []);
  coveredTechniques = computed(() =>
    (this.coverage()?.coverage_map ?? []).sort((a, b) => b.rule_count - a.rule_count)
  );

  constructor(mitreService: MitreService) {
    this.mitreService = mitreService;
  }

  ngOnInit(): void {
    this.loadData();
  }

  loadData(): void {
    this.isLoading.set(true);

    // Load coverage and gaps in parallel
    this.mitreService.getCoverage().subscribe(coverage => {
      this.coverage.set(coverage);
      this.isLoading.set(false);
    });

    this.mitreService.getCoverageGaps().subscribe(gaps => {
      this.gaps.set(gaps);
    });
  }

  getCoverageClass(percent: number): string {
    if (percent >= 70) return 'high';
    if (percent >= 40) return 'medium';
    return 'low';
  }
}
