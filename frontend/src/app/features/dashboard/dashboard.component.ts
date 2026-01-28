import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { MatCardModule } from '@angular/material/card';
import { MatIconModule } from '@angular/material/icon';
import { MatButtonModule } from '@angular/material/button';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatChipsModule } from '@angular/material/chips';
import { MatTooltipModule } from '@angular/material/tooltip';
import { IntegrationService } from '../../core/api/integration.service';
import { CaseService } from '../../core/api/case.service';
import { CollectionService } from '../../core/api/collection.service';
import { WorkflowService } from '../../core/api/workflow.service';
import { IntegrationStatus, Case, Hunt, ApprovalRequest } from '../../shared/models';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [
    CommonModule,
    RouterModule,
    MatCardModule,
    MatIconModule,
    MatButtonModule,
    MatProgressSpinnerModule,
    MatChipsModule,
    MatTooltipModule
  ],
  template: `
    <div class="dashboard">
      <!-- Integration Status Cards -->
      <section class="section">
        <h2 class="section-title">Integration Status</h2>
        <div class="integration-grid">
          @if (isLoading()) {
            <div class="loading-container">
              <mat-spinner diameter="40"></mat-spinner>
            </div>
          } @else {
            @for (integration of integrations(); track integration.name) {
              <mat-card class="integration-card" [class.healthy]="integration.status === 'connected'"
                        [class.unhealthy]="integration.status !== 'connected'">
                <mat-card-header>
                  <mat-icon mat-card-avatar [class]="'status-' + integration.status">
                    {{ getIntegrationIcon(integration.name) }}
                  </mat-icon>
                  <mat-card-title>{{ integration.name | titlecase }}</mat-card-title>
                  <mat-card-subtitle>{{ integration.description }}</mat-card-subtitle>
                </mat-card-header>
                <mat-card-content>
                  <div class="status-row">
                    <span class="status-badge" [class]="'status-' + integration.status">
                      {{ integration.status }}
                    </span>
                    @if (integration.version) {
                      <span class="version">v{{ integration.version }}</span>
                    }
                  </div>
                  @if (integration.message && integration.status !== 'connected') {
                    <p class="error-message">{{ integration.message }}</p>
                  }
                </mat-card-content>
                <mat-card-actions align="end">
                  <button mat-button color="accent" (click)="testIntegration(integration.name)">
                    Test Connection
                  </button>
                </mat-card-actions>
              </mat-card>
            }
          }
        </div>
      </section>

      <!-- Stats Row -->
      <section class="section">
        <div class="stats-grid">
          <mat-card class="stat-card">
            <div class="stat-accent"></div>
            <div class="stat-icon bg-info">
              <mat-icon>report_problem</mat-icon>
            </div>
            <div class="stat-content">
              <span class="stat-value">{{ openCases() }}</span>
              <span class="stat-label">Open Cases</span>
            </div>
          </mat-card>

          <mat-card class="stat-card">
            <div class="stat-accent warning"></div>
            <div class="stat-icon bg-warning">
              <mat-icon>priority_high</mat-icon>
            </div>
            <div class="stat-content">
              <span class="stat-value">{{ criticalCases() }}</span>
              <span class="stat-label">Critical</span>
            </div>
          </mat-card>

          <mat-card class="stat-card">
            <div class="stat-accent success"></div>
            <div class="stat-icon bg-success">
              <mat-icon>search</mat-icon>
            </div>
            <div class="stat-content">
              <span class="stat-value">{{ activeHunts() }}</span>
              <span class="stat-label">Active Hunts</span>
            </div>
          </mat-card>

          <mat-card class="stat-card">
            <div class="stat-accent accent"></div>
            <div class="stat-icon bg-accent">
              <mat-icon>pending_actions</mat-icon>
            </div>
            <div class="stat-content">
              <span class="stat-value">{{ pendingApprovals() }}</span>
              <span class="stat-label">Pending Approvals</span>
            </div>
          </mat-card>
        </div>
      </section>

      <!-- Recent Cases -->
      <section class="section">
        <div class="section-header">
          <h2 class="section-title">Recent Cases</h2>
          <button mat-button color="accent" routerLink="/incidents">View All</button>
        </div>
        <div class="cases-list">
          @if (recentCases().length === 0) {
            <mat-card class="empty-card">
              <mat-icon>inbox</mat-icon>
              <p>No recent cases</p>
            </mat-card>
          } @else {
            @for (caseItem of recentCases(); track caseItem.id) {
              <mat-card class="case-card" [routerLink]="['/incidents', caseItem.id]">
                <div class="case-accent"></div>
                <div class="case-header">
                  <span class="case-number">{{ caseItem.case_number }}</span>
                  <mat-chip [class]="'severity-' + caseItem.severity">
                    {{ caseItem.severity | uppercase }}
                  </mat-chip>
                </div>
                <h3 class="case-title">{{ caseItem.title }}</h3>
                <div class="case-meta">
                  <span class="status-badge" [class]="'status-' + caseItem.status">
                    {{ caseItem.status | titlecase }}
                  </span>
                  <span class="case-date">{{ caseItem.created_at | date:'short' }}</span>
                  @if (caseItem.assignee_name) {
                    <span class="assignee">
                      <mat-icon>person</mat-icon>
                      {{ caseItem.assignee_name }}
                    </span>
                  }
                </div>
              </mat-card>
            }
          }
        </div>
      </section>

      <!-- Active Hunts -->
      <section class="section">
        <div class="section-header">
          <h2 class="section-title">Active Hunts</h2>
          <button mat-button color="accent" routerLink="/hunting">View All</button>
        </div>
        <div class="hunts-list">
          @if (hunts().length === 0) {
            <mat-card class="empty-card">
              <mat-icon>search_off</mat-icon>
              <p>No active hunts</p>
            </mat-card>
          } @else {
            @for (hunt of hunts(); track hunt.id) {
              <mat-card class="hunt-card">
                <div class="hunt-header">
                  <h3>{{ hunt.name }}</h3>
                  <span class="status-badge" [class]="'status-' + hunt.status">
                    {{ hunt.status | titlecase }}
                  </span>
                </div>
                <p class="hunt-artifact">{{ hunt.artifact }}</p>
                <div class="hunt-progress">
                  <div class="progress-bar">
                    <div class="progress-fill"
                         [style.width.%]="(hunt.completed_clients / hunt.total_clients) * 100">
                    </div>
                  </div>
                  <span class="progress-text">
                    {{ hunt.completed_clients }}/{{ hunt.total_clients }} endpoints
                  </span>
                </div>
              </mat-card>
            }
          }
        </div>
      </section>
    </div>
  `,
  styles: [`
    /*
     * DESIGN: Refined dashboard styles matching project-eleanor.com
     * - Subtle hover effects (border transitions, no dramatic transforms)
     * - Glow accents using CSS variables
     * - Clean, understated elevation
     */
    .dashboard {
      max-width: 1400px;
      margin: 0 auto;
      animation: fadeIn 0.4s ease-out;
    }

    @keyframes fadeIn {
      from { opacity: 0; transform: translateY(12px); }
      to { opacity: 1; transform: translateY(0); }
    }

    .section {
      margin-bottom: 40px;
    }

    .section-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 20px;
    }

    .section-title {
      font-family: var(--font-display);
      font-size: 16px;
      font-weight: 600;
      color: var(--text-secondary);
      margin: 0 0 20px 0;
      letter-spacing: 0.5px;
      text-transform: uppercase;
    }

    .loading-container {
      display: flex;
      justify-content: center;
      padding: 64px;
    }

    /* Integration Grid - Refined */
    .integration-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
      gap: 20px;
    }

    .integration-card {
      background: rgba(20, 26, 36, 0.6);
      backdrop-filter: blur(12px);
      -webkit-backdrop-filter: blur(12px);
      border: 1px solid rgba(74, 158, 255, 0.1);
      border-radius: 12px;
      transition: border-color 0.2s ease, background-color 0.2s ease, box-shadow 0.3s ease;

      &:hover {
        border-color: rgba(74, 158, 255, 0.25);
        background: rgba(20, 26, 36, 0.75);
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3), 0 0 20px rgba(74, 158, 255, 0.1);
      }

      &.healthy {
        border-color: rgba(63, 185, 80, 0.2);

        &:hover {
          border-color: var(--success);
          box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3), 0 0 30px var(--glow-success);
        }
      }

      &.unhealthy {
        border-color: rgba(248, 81, 73, 0.2);

        &:hover {
          border-color: var(--danger);
          box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3), 0 0 30px var(--glow-danger);
        }
      }

      mat-card-avatar {
        font-size: 24px;
        width: 40px;
        height: 40px;
        display: flex;
        align-items: center;
        justify-content: center;
        border-radius: 10px;
        background: var(--glow-accent);
      }

      mat-card-title {
        font-family: var(--font-display);
        font-weight: 600;
        font-size: 15px;
      }

      mat-card-subtitle {
        font-size: 13px;
        color: var(--text-secondary);
      }
    }

    .status-row {
      display: flex;
      align-items: center;
      gap: 12px;
      margin-top: 12px;
    }

    .status-badge {
      display: inline-flex;
      align-items: center;
      padding: 5px 12px;
      border-radius: 6px;
      font-size: 11px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.3px;

      &.status-connected { background: var(--glow-success); color: var(--success); border: 1px solid var(--success); }
      &.status-disconnected { background: rgba(74, 85, 104, 0.2); color: var(--text-muted); border: 1px solid var(--text-muted); }
      &.status-error { background: var(--glow-danger); color: var(--danger); border: 1px solid var(--danger); }
      &.status-running { background: var(--glow-accent); color: var(--accent); border: 1px solid var(--accent); }
      &.status-pending { background: var(--glow-warning); color: var(--warning); border: 1px solid var(--warning); }
      &.status-open { background: var(--glow-accent); color: var(--accent); border: 1px solid var(--accent); }
      &.status-in_progress { background: var(--glow-warning); color: var(--warning); border: 1px solid var(--warning); }
      &.status-closed { background: var(--glow-success); color: var(--success); border: 1px solid var(--success); }
    }

    .version {
      color: var(--text-muted);
      font-size: 11px;
      font-family: var(--font-mono);
    }

    .error-message {
      color: var(--danger);
      font-size: 12px;
      margin-top: 8px;
      opacity: 0.9;
    }

    .status-connected { color: var(--success); }
    .status-disconnected { color: var(--text-muted); }
    .status-error { color: var(--danger); }

    /* Stats Grid - Refined */
    .stats-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
      gap: 20px;
    }

    .stat-card {
      display: flex;
      align-items: center;
      gap: 20px;
      padding: 24px;
      background: rgba(20, 26, 36, 0.6);
      backdrop-filter: blur(12px);
      -webkit-backdrop-filter: blur(12px);
      border: 1px solid rgba(74, 158, 255, 0.1);
      border-radius: 12px;
      position: relative;
      overflow: hidden;
      transition: border-color 0.2s ease, background-color 0.2s ease, box-shadow 0.3s ease;

      &:hover {
        border-color: rgba(74, 158, 255, 0.25);
        background: rgba(20, 26, 36, 0.75);
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3), 0 0 20px rgba(74, 158, 255, 0.1);

        .stat-accent {
          opacity: 1;
        }

        .stat-icon {
          transform: scale(1.05);
        }
      }
    }

    .stat-accent {
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      height: 2px;
      background: var(--accent);
      opacity: 0;
      transition: opacity 0.3s ease;

      &.warning { background: var(--warning); }
      &.success { background: var(--success); }
      &.accent { background: var(--accent); }
    }

    .stat-icon {
      width: 48px;
      height: 48px;
      border-radius: 12px;
      display: flex;
      align-items: center;
      justify-content: center;
      transition: transform 0.2s ease;

      mat-icon {
        font-size: 24px;
        width: 24px;
        height: 24px;
      }

      &.bg-info {
        background: var(--glow-accent);
        mat-icon { color: var(--accent); }
      }
      &.bg-warning {
        background: var(--glow-warning);
        mat-icon { color: var(--warning); }
      }
      &.bg-success {
        background: var(--glow-success);
        mat-icon { color: var(--success); }
      }
      &.bg-accent {
        background: var(--glow-accent);
        mat-icon { color: var(--accent); }
      }
    }

    .stat-content {
      display: flex;
      flex-direction: column;
    }

    .stat-value {
      font-family: var(--font-display);
      font-size: 28px;
      font-weight: 700;
      color: var(--text-primary);
      line-height: 1;
    }

    .stat-label {
      font-size: 13px;
      color: var(--text-secondary);
      margin-top: 6px;
    }

    /* Cases List - Refined */
    .cases-list {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
      gap: 20px;
    }

    .case-card {
      padding: 20px;
      background: rgba(20, 26, 36, 0.6);
      backdrop-filter: blur(12px);
      -webkit-backdrop-filter: blur(12px);
      border: 1px solid rgba(74, 158, 255, 0.1);
      border-radius: 12px;
      cursor: pointer;
      position: relative;
      overflow: hidden;
      transition: border-color 0.2s ease, background-color 0.2s ease, box-shadow 0.3s ease;

      &:hover {
        border-color: rgba(74, 158, 255, 0.25);
        background: rgba(20, 26, 36, 0.75);
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3), 0 0 20px rgba(74, 158, 255, 0.1);

        .case-accent {
          opacity: 1;
        }
      }
    }

    .case-accent {
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      height: 2px;
      background: linear-gradient(90deg, var(--accent), var(--accent-light));
      opacity: 0;
      transition: opacity 0.3s ease;
    }

    .case-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 10px;
    }

    .case-number {
      font-size: 11px;
      color: var(--text-muted);
      font-family: var(--font-mono);
      letter-spacing: 0.5px;
    }

    .case-title {
      font-family: var(--font-display);
      font-size: 15px;
      font-weight: 600;
      color: var(--text-primary);
      margin: 0 0 14px 0;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .case-meta {
      display: flex;
      align-items: center;
      gap: 14px;
      font-size: 12px;
      color: var(--text-secondary);

      .assignee {
        display: flex;
        align-items: center;
        gap: 5px;

        mat-icon {
          font-size: 14px;
          width: 14px;
          height: 14px;
          opacity: 0.7;
        }
      }
    }

    /* Hunts List - Refined */
    .hunts-list {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
      gap: 20px;
    }

    .hunt-card {
      padding: 20px;
      background: rgba(20, 26, 36, 0.6);
      backdrop-filter: blur(12px);
      -webkit-backdrop-filter: blur(12px);
      border: 1px solid rgba(74, 158, 255, 0.1);
      border-radius: 12px;
      transition: border-color 0.2s ease, background-color 0.2s ease, box-shadow 0.3s ease;

      &:hover {
        border-color: rgba(74, 158, 255, 0.25);
        background: rgba(20, 26, 36, 0.75);
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3), 0 0 20px rgba(74, 158, 255, 0.1);
      }
    }

    .hunt-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 10px;

      h3 {
        font-family: var(--font-display);
        font-size: 15px;
        font-weight: 600;
        margin: 0;
        color: var(--text-primary);
      }
    }

    .hunt-artifact {
      font-size: 11px;
      color: var(--text-muted);
      margin: 0 0 14px 0;
      font-family: var(--font-mono);
      letter-spacing: 0.3px;
    }

    .hunt-progress {
      display: flex;
      align-items: center;
      gap: 14px;
    }

    .progress-bar {
      flex: 1;
      height: 4px;
      background: var(--bg-tertiary);
      border-radius: 2px;
      overflow: hidden;
    }

    .progress-fill {
      height: 100%;
      background: var(--success);
      border-radius: 2px;
      transition: width 0.4s ease;
    }

    .progress-text {
      font-size: 11px;
      color: var(--text-muted);
      white-space: nowrap;
      font-family: var(--font-mono);
    }

    .empty-card {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      padding: 64px;
      background: rgba(20, 26, 36, 0.5);
      backdrop-filter: blur(12px);
      -webkit-backdrop-filter: blur(12px);
      border: 1px solid rgba(74, 158, 255, 0.08);
      border-radius: 12px;
      color: var(--text-muted);

      mat-icon {
        font-size: 40px;
        width: 40px;
        height: 40px;
        margin-bottom: 16px;
        opacity: 0.4;
      }

      p {
        margin: 0;
        font-size: 13px;
      }
    }

    /* Severity chips - Refined */
    .severity-critical {
      background: var(--glow-danger) !important;
      color: var(--danger) !important;
      border: 1px solid var(--danger) !important;
    }
    .severity-high {
      background: rgba(249, 115, 22, 0.15) !important;
      color: #f97316 !important;
      border: 1px solid #f97316 !important;
    }
    .severity-medium {
      background: var(--glow-warning) !important;
      color: var(--warning) !important;
      border: 1px solid var(--warning) !important;
    }
    .severity-low {
      background: var(--glow-accent) !important;
      color: var(--accent) !important;
      border: 1px solid var(--accent) !important;
    }
    .severity-info {
      background: rgba(110, 118, 129, 0.15) !important;
      color: #6e7681 !important;
      border: 1px solid #6e7681 !important;
    }
  `]
})
export class DashboardComponent implements OnInit {
  isLoading = signal(true);
  integrations = signal<IntegrationStatus[]>([]);
  recentCases = signal<Case[]>([]);
  hunts = signal<Hunt[]>([]);

  openCases = signal(0);
  criticalCases = signal(0);
  activeHunts = signal(0);
  pendingApprovals = signal(0);

  constructor(
    private integrationService: IntegrationService,
    private caseService: CaseService,
    private collectionService: CollectionService,
    private workflowService: WorkflowService
  ) {}

  ngOnInit(): void {
    this.loadData();
  }

  private loadData(): void {
    // Load integrations
    this.integrationService.getStatus().subscribe({
      next: (response) => {
        this.integrations.set(response.integrations);
        this.isLoading.set(false);
      },
      error: () => this.isLoading.set(false)
    });

    // Load cases
    this.caseService.list({ page_size: 5 }).subscribe({
      next: (response) => {
        this.recentCases.set(response.items);
        this.openCases.set(response.total);
      }
    });

    // Load critical cases count
    this.caseService.list({ severity: 'critical', status: 'open' }).subscribe({
      next: (response) => this.criticalCases.set(response.total)
    });

    // Load hunts
    this.collectionService.getHunts({ status: 'running', page_size: 3 }).subscribe({
      next: (response) => {
        this.hunts.set(response.items);
        this.activeHunts.set(response.total);
      }
    });

    // Load pending approvals
    this.workflowService.getApprovals().subscribe({
      next: (approvals) => this.pendingApprovals.set(approvals.length)
    });
  }

  getIntegrationIcon(name: string): string {
    const icons: Record<string, string> = {
      velociraptor: 'radar',
      iris: 'policy',
      opencti: 'security',
      shuffle: 'autorenew',
      timesketch: 'timeline'
    };
    return icons[name] || 'extension';
  }

  testIntegration(name: string): void {
    this.integrationService.test(name).subscribe({
      next: (result) => {
        const integration = this.integrations().find(i => i.name === name);
        if (integration) {
          integration.status = result.status as IntegrationStatus['status'];
          integration.message = result.message;
          this.integrations.set([...this.integrations()]);
        }
      }
    });
  }
}
