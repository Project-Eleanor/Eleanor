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
    .dashboard {
      max-width: 1400px;
      margin: 0 auto;
      animation: fadeIn 0.3s ease-out;
    }

    @keyframes fadeIn {
      from {
        opacity: 0;
        transform: translateY(8px);
      }
      to {
        opacity: 1;
        transform: translateY(0);
      }
    }

    .section {
      margin-bottom: 32px;
    }

    .section-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 16px;
    }

    .section-title {
      font-family: var(--font-display);
      font-size: 18px;
      font-weight: 600;
      color: var(--text-primary);
      margin: 0 0 16px 0;
      letter-spacing: -0.3px;
    }

    .loading-container {
      display: flex;
      justify-content: center;
      padding: 48px;
    }

    /* Integration Grid */
    .integration-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
      gap: 16px;
    }

    .integration-card {
      background: var(--bg-card);
      border: 1px solid var(--border-color);
      transition: border-color 0.2s ease, box-shadow 0.2s ease, transform 0.2s ease;

      &:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.2);
      }

      &.healthy {
        border-color: rgba(63, 185, 80, 0.3);

        &:hover {
          border-color: var(--success);
        }
      }

      &.unhealthy {
        border-color: rgba(248, 81, 73, 0.3);

        &:hover {
          border-color: var(--danger);
        }
      }

      mat-card-avatar {
        font-size: 28px;
        width: 40px;
        height: 40px;
        display: flex;
        align-items: center;
        justify-content: center;
      }

      mat-card-title {
        font-family: var(--font-display);
        font-weight: 600;
      }
    }

    .status-row {
      display: flex;
      align-items: center;
      gap: 12px;
      margin-top: 8px;
    }

    .status-badge {
      display: inline-flex;
      align-items: center;
      padding: 4px 12px;
      border-radius: 12px;
      font-size: 12px;
      font-weight: 500;
      text-transform: capitalize;

      &.status-connected { background: var(--success); color: black; }
      &.status-disconnected { background: var(--text-muted); color: white; }
      &.status-error { background: var(--danger); color: white; }
      &.status-running { background: var(--info); color: white; }
      &.status-pending { background: var(--warning); color: black; }
      &.status-open { background: var(--info); color: white; }
      &.status-in_progress { background: var(--warning); color: black; }
      &.status-closed { background: var(--success); color: black; }
    }

    .version {
      color: var(--text-secondary);
      font-size: 12px;
      font-family: var(--font-mono);
    }

    .error-message {
      color: var(--danger);
      font-size: 12px;
      margin-top: 8px;
    }

    .status-connected { color: var(--success); }
    .status-disconnected { color: var(--text-muted); }
    .status-error { color: var(--danger); }

    /* Stats Grid */
    .stats-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
      gap: 16px;
    }

    .stat-card {
      display: flex;
      align-items: center;
      gap: 16px;
      padding: 24px;
      background: var(--bg-card);
      border: 1px solid var(--border-color);
      position: relative;
      overflow: hidden;
      transition: transform 0.2s ease, box-shadow 0.2s ease;

      &:hover {
        transform: translateY(-4px);
        box-shadow: 0 12px 32px rgba(0, 0, 0, 0.25);

        .stat-accent {
          height: 100%;
        }
      }
    }

    .stat-accent {
      position: absolute;
      left: 0;
      bottom: 0;
      width: 3px;
      height: 0;
      background: var(--accent);
      transition: height 0.3s ease;

      &.warning { background: var(--warning); }
      &.success { background: var(--success); }
      &.accent { background: var(--accent); }
    }

    .stat-icon {
      width: 52px;
      height: 52px;
      border-radius: 12px;
      display: flex;
      align-items: center;
      justify-content: center;

      mat-icon {
        color: white;
        font-size: 26px;
        width: 26px;
        height: 26px;
      }

      &.bg-info { background: linear-gradient(135deg, var(--info) 0%, #3d8bd9 100%); }
      &.bg-warning { background: linear-gradient(135deg, var(--warning) 0%, #b8840a 100%); mat-icon { color: black; } }
      &.bg-success { background: linear-gradient(135deg, var(--success) 0%, #2d9a40 100%); mat-icon { color: black; } }
      &.bg-accent { background: linear-gradient(135deg, var(--accent) 0%, #2d7dd2 100%); }
    }

    .stat-content {
      display: flex;
      flex-direction: column;
    }

    .stat-value {
      font-family: var(--font-display);
      font-size: 32px;
      font-weight: 700;
      color: var(--text-primary);
      line-height: 1;
    }

    .stat-label {
      font-size: 14px;
      color: var(--text-secondary);
      margin-top: 4px;
    }

    /* Cases List */
    .cases-list {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
      gap: 16px;
    }

    .case-card {
      padding: 20px;
      background: var(--bg-card);
      border: 1px solid var(--border-color);
      cursor: pointer;
      position: relative;
      overflow: hidden;
      transition: border-color 0.2s ease, transform 0.2s ease, box-shadow 0.2s ease;

      &:hover {
        border-color: rgba(74, 158, 255, 0.5);
        transform: translateY(-2px);
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.2);

        .case-accent {
          width: 100%;
        }
      }
    }

    .case-accent {
      position: absolute;
      bottom: 0;
      left: 0;
      width: 0;
      height: 2px;
      background: linear-gradient(90deg, var(--accent), var(--accent-light));
      transition: width 0.3s ease;
    }

    .case-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 8px;
    }

    .case-number {
      font-size: 12px;
      color: var(--text-secondary);
      font-family: var(--font-mono);
    }

    .case-title {
      font-family: var(--font-display);
      font-size: 16px;
      font-weight: 600;
      color: var(--text-primary);
      margin: 0 0 12px 0;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .case-meta {
      display: flex;
      align-items: center;
      gap: 12px;
      font-size: 12px;
      color: var(--text-secondary);

      .assignee {
        display: flex;
        align-items: center;
        gap: 4px;

        mat-icon {
          font-size: 14px;
          width: 14px;
          height: 14px;
        }
      }
    }

    /* Hunts List */
    .hunts-list {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
      gap: 16px;
    }

    .hunt-card {
      padding: 20px;
      background: var(--bg-card);
      border: 1px solid var(--border-color);
      transition: border-color 0.2s ease, transform 0.2s ease;

      &:hover {
        border-color: rgba(74, 158, 255, 0.3);
        transform: translateY(-2px);
      }
    }

    .hunt-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 8px;

      h3 {
        font-family: var(--font-display);
        font-size: 16px;
        font-weight: 600;
        margin: 0;
        color: var(--text-primary);
      }
    }

    .hunt-artifact {
      font-size: 12px;
      color: var(--text-secondary);
      margin: 0 0 12px 0;
      font-family: var(--font-mono);
    }

    .hunt-progress {
      display: flex;
      align-items: center;
      gap: 12px;
    }

    .progress-bar {
      flex: 1;
      height: 6px;
      background: var(--bg-tertiary);
      border-radius: 3px;
      overflow: hidden;
    }

    .progress-fill {
      height: 100%;
      background: linear-gradient(90deg, var(--success) 0%, #4ade80 100%);
      transition: width 0.3s ease;
    }

    .progress-text {
      font-size: 12px;
      color: var(--text-secondary);
      white-space: nowrap;
      font-family: var(--font-mono);
    }

    .empty-card {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      padding: 48px;
      background: var(--bg-card);
      border: 1px solid var(--border-color);
      color: var(--text-muted);

      mat-icon {
        font-size: 48px;
        width: 48px;
        height: 48px;
        margin-bottom: 12px;
        opacity: 0.5;
      }

      p {
        margin: 0;
        font-size: 14px;
      }
    }

    /* Severity chips */
    .severity-critical { background: var(--severity-critical) !important; color: white !important; }
    .severity-high { background: var(--severity-high) !important; color: white !important; }
    .severity-medium { background: var(--severity-medium) !important; color: black !important; }
    .severity-low { background: var(--severity-low) !important; color: white !important; }
    .severity-info { background: var(--severity-info) !important; color: white !important; }
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
