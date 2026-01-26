import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatCardModule } from '@angular/material/card';
import { MatIconModule } from '@angular/material/icon';
import { MatButtonModule } from '@angular/material/button';
import { MatTabsModule } from '@angular/material/tabs';
import { MatTableModule } from '@angular/material/table';
import { MatChipsModule } from '@angular/material/chips';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatMenuModule } from '@angular/material/menu';
import { MatBadgeModule } from '@angular/material/badge';
import { MatDialogModule, MatDialog } from '@angular/material/dialog';
import { MatPaginatorModule, PageEvent } from '@angular/material/paginator';
import { WorkflowService } from '../../core/api/workflow.service';
import { Workflow, WorkflowExecution, ApprovalRequest, ExecutionStatus } from '../../shared/models';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { PlaybookDetailDialogComponent } from './playbook-detail-dialog.component';
import { RunPlaybookDialogComponent } from './run-playbook-dialog.component';
import { ExecutionDetailDialogComponent } from './execution-detail-dialog.component';

@Component({
  selector: 'app-automation',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatCardModule,
    MatIconModule,
    MatButtonModule,
    MatTabsModule,
    MatTableModule,
    MatChipsModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    MatProgressSpinnerModule,
    MatTooltipModule,
    MatMenuModule,
    MatBadgeModule,
    MatDialogModule,
    MatPaginatorModule,
    MatSnackBarModule
  ],
  template: `
    <div class="automation">
      <!-- Header -->
      <div class="page-header">
        <div class="header-content">
          <h1>Automation</h1>
          <p class="subtitle">Manage playbooks, view execution history, and handle approvals</p>
        </div>
        <div class="header-actions">
          <button mat-stroked-button (click)="refresh()">
            <mat-icon>refresh</mat-icon>
            Refresh
          </button>
        </div>
      </div>

      <!-- Stats Cards -->
      <div class="stats-row">
        <mat-card class="stat-card">
          <div class="stat-icon bg-info">
            <mat-icon>play_circle</mat-icon>
          </div>
          <div class="stat-content">
            <span class="stat-value">{{ totalPlaybooks() }}</span>
            <span class="stat-label">Playbooks</span>
          </div>
        </mat-card>

        <mat-card class="stat-card">
          <div class="stat-icon bg-success">
            <mat-icon>check_circle</mat-icon>
          </div>
          <div class="stat-content">
            <span class="stat-value">{{ completedExecutions() }}</span>
            <span class="stat-label">Completed (24h)</span>
          </div>
        </mat-card>

        <mat-card class="stat-card">
          <div class="stat-icon bg-warning">
            <mat-icon>hourglass_empty</mat-icon>
          </div>
          <div class="stat-content">
            <span class="stat-value">{{ runningExecutions() }}</span>
            <span class="stat-label">Running</span>
          </div>
        </mat-card>

        <mat-card class="stat-card clickable" (click)="switchToApprovals()">
          <div class="stat-icon bg-accent">
            <mat-icon>pending_actions</mat-icon>
          </div>
          <div class="stat-content">
            <span class="stat-value">{{ pendingApprovals().length }}</span>
            <span class="stat-label">Pending Approvals</span>
          </div>
        </mat-card>
      </div>

      <!-- Tabs -->
      <mat-tab-group animationDuration="200ms" [(selectedIndex)]="selectedTab">
        <!-- Playbooks Tab -->
        <mat-tab>
          <ng-template mat-tab-label>
            <mat-icon>play_circle</mat-icon>
            <span>Playbooks</span>
          </ng-template>

          <div class="tab-content">
            <!-- Filters -->
            <div class="filters-row">
              <mat-form-field appearance="outline" class="search-field">
                <mat-label>Search playbooks</mat-label>
                <mat-icon matPrefix>search</mat-icon>
                <input matInput [(ngModel)]="playbookSearch" placeholder="Search by name">
              </mat-form-field>

              <mat-form-field appearance="outline" class="filter-field">
                <mat-label>Category</mat-label>
                <mat-select [(value)]="categoryFilter" (selectionChange)="loadPlaybooks()">
                  <mat-option value="">All</mat-option>
                  <mat-option value="containment">Containment</mat-option>
                  <mat-option value="enrichment">Enrichment</mat-option>
                  <mat-option value="notification">Notification</mat-option>
                  <mat-option value="remediation">Remediation</mat-option>
                </mat-select>
              </mat-form-field>

              <mat-form-field appearance="outline" class="filter-field">
                <mat-label>Status</mat-label>
                <mat-select [(value)]="statusFilter" (selectionChange)="loadPlaybooks()">
                  <mat-option value="">All</mat-option>
                  <mat-option value="active">Active</mat-option>
                  <mat-option value="inactive">Inactive</mat-option>
                  <mat-option value="draft">Draft</mat-option>
                </mat-select>
              </mat-form-field>
            </div>

            @if (isLoadingPlaybooks()) {
              <div class="loading">
                <mat-spinner diameter="40"></mat-spinner>
              </div>
            } @else {
              <div class="playbooks-grid">
                @for (playbook of filteredPlaybooks(); track playbook.id) {
                  <mat-card class="playbook-card" [class.inactive]="playbook.status !== 'active'">
                    <mat-card-header>
                      <mat-icon mat-card-avatar class="playbook-icon"
                                [class]="'category-' + playbook.category">
                        {{ getCategoryIcon(playbook.category) }}
                      </mat-icon>
                      <mat-card-title>{{ playbook.name }}</mat-card-title>
                      <mat-card-subtitle>
                        <span class="category-badge">{{ playbook.category | titlecase }}</span>
                        <span class="status-badge" [class]="'status-' + playbook.status">
                          {{ playbook.status | titlecase }}
                        </span>
                      </mat-card-subtitle>
                    </mat-card-header>

                    <mat-card-content>
                      <p class="playbook-description">
                        {{ playbook.description || 'No description available' }}
                      </p>

                      <div class="playbook-meta">
                        <div class="meta-item">
                          <mat-icon>bolt</mat-icon>
                          <span>{{ playbook.trigger_type | titlecase }}</span>
                        </div>
                        @if (playbook.requires_approval) {
                          <div class="meta-item approval-required">
                            <mat-icon>gavel</mat-icon>
                            <span>Requires Approval</span>
                          </div>
                        }
                        <div class="meta-item">
                          <mat-icon>layers</mat-icon>
                          <span>{{ playbook.actions.length }} actions</span>
                        </div>
                      </div>
                    </mat-card-content>

                    <mat-card-actions align="end">
                      <button mat-button (click)="viewPlaybook(playbook)">
                        <mat-icon>visibility</mat-icon>
                        Details
                      </button>
                      <button mat-flat-button color="primary"
                              [disabled]="playbook.status !== 'active'"
                              (click)="runPlaybook(playbook)">
                        <mat-icon>play_arrow</mat-icon>
                        Run
                      </button>
                    </mat-card-actions>
                  </mat-card>
                }
              </div>
            }
          </div>
        </mat-tab>

        <!-- Execution History Tab -->
        <mat-tab>
          <ng-template mat-tab-label>
            <mat-icon>history</mat-icon>
            <span>Execution History</span>
          </ng-template>

          <div class="tab-content">
            <mat-form-field appearance="outline" class="filter-field">
              <mat-label>Status Filter</mat-label>
              <mat-select [(value)]="executionStatusFilter" (selectionChange)="loadExecutions()">
                <mat-option value="">All</mat-option>
                <mat-option value="running">Running</mat-option>
                <mat-option value="completed">Completed</mat-option>
                <mat-option value="failed">Failed</mat-option>
                <mat-option value="awaiting_approval">Awaiting Approval</mat-option>
              </mat-select>
            </mat-form-field>

            @if (isLoadingExecutions()) {
              <div class="loading">
                <mat-spinner diameter="40"></mat-spinner>
              </div>
            } @else {
              <table mat-table [dataSource]="executions()" class="executions-table">
                <ng-container matColumnDef="status">
                  <th mat-header-cell *matHeaderCellDef>Status</th>
                  <td mat-cell *matCellDef="let exec">
                    <div class="status-indicator" [class]="'status-' + exec.status">
                      <mat-icon>{{ getStatusIcon(exec.status) }}</mat-icon>
                      <span>{{ formatStatus(exec.status) }}</span>
                    </div>
                  </td>
                </ng-container>

                <ng-container matColumnDef="workflow">
                  <th mat-header-cell *matHeaderCellDef>Playbook</th>
                  <td mat-cell *matCellDef="let exec">{{ exec.workflow_name }}</td>
                </ng-container>

                <ng-container matColumnDef="started_at">
                  <th mat-header-cell *matHeaderCellDef>Started</th>
                  <td mat-cell *matCellDef="let exec">{{ exec.started_at | date:'medium' }}</td>
                </ng-container>

                <ng-container matColumnDef="duration">
                  <th mat-header-cell *matHeaderCellDef>Duration</th>
                  <td mat-cell *matCellDef="let exec">
                    @if (exec.completed_at) {
                      {{ getDuration(exec.started_at, exec.completed_at) }}
                    } @else if (exec.status === 'running') {
                      <span class="running-indicator">Running...</span>
                    } @else {
                      -
                    }
                  </td>
                </ng-container>

                <ng-container matColumnDef="started_by">
                  <th mat-header-cell *matHeaderCellDef>Started By</th>
                  <td mat-cell *matCellDef="let exec">{{ exec.started_by }}</td>
                </ng-container>

                <ng-container matColumnDef="actions">
                  <th mat-header-cell *matHeaderCellDef></th>
                  <td mat-cell *matCellDef="let exec">
                    <button mat-icon-button [matMenuTriggerFor]="execMenu">
                      <mat-icon>more_vert</mat-icon>
                    </button>
                    <mat-menu #execMenu="matMenu">
                      <button mat-menu-item (click)="viewExecution(exec)">
                        <mat-icon>visibility</mat-icon>
                        <span>View Details</span>
                      </button>
                      @if (exec.status === 'running') {
                        <button mat-menu-item (click)="cancelExecution(exec)">
                          <mat-icon>cancel</mat-icon>
                          <span>Cancel</span>
                        </button>
                      }
                      @if (exec.status === 'failed') {
                        <button mat-menu-item (click)="retryExecution(exec)">
                          <mat-icon>refresh</mat-icon>
                          <span>Retry</span>
                        </button>
                      }
                    </mat-menu>
                  </td>
                </ng-container>

                <tr mat-header-row *matHeaderRowDef="executionColumns"></tr>
                <tr mat-row *matRowDef="let row; columns: executionColumns;"></tr>
              </table>

              <mat-paginator [length]="totalExecutions()"
                             [pageSize]="20"
                             [pageSizeOptions]="[10, 20, 50]"
                             (page)="onExecutionPageChange($event)">
              </mat-paginator>
            }
          </div>
        </mat-tab>

        <!-- Approvals Tab -->
        <mat-tab>
          <ng-template mat-tab-label>
            <mat-icon [matBadge]="pendingApprovals().length"
                      [matBadgeHidden]="pendingApprovals().length === 0"
                      matBadgeColor="accent">
              pending_actions
            </mat-icon>
            <span>Approvals</span>
          </ng-template>

          <div class="tab-content">
            @if (isLoadingApprovals()) {
              <div class="loading">
                <mat-spinner diameter="40"></mat-spinner>
              </div>
            } @else if (pendingApprovals().length === 0) {
              <div class="empty-state">
                <mat-icon>check_circle</mat-icon>
                <h3>No Pending Approvals</h3>
                <p>All workflow executions have been processed</p>
              </div>
            } @else {
              <div class="approvals-list">
                @for (approval of pendingApprovals(); track approval.id) {
                  <mat-card class="approval-card">
                    <div class="approval-header">
                      <mat-icon class="approval-icon">gavel</mat-icon>
                      <div class="approval-info">
                        <h3>{{ approval.workflow_name }}</h3>
                        <span class="approval-meta">
                          Requested by {{ approval.requested_by }} on {{ approval.requested_at | date:'medium' }}
                        </span>
                      </div>
                      <span class="status-badge status-pending">Pending</span>
                    </div>

                    <div class="approval-params">
                      <h4>Parameters</h4>
                      <div class="params-grid">
                        @for (param of getParamEntries(approval.parameters); track param.key) {
                          <div class="param-item">
                            <span class="param-key">{{ param.key }}</span>
                            <span class="param-value">{{ param.value }}</span>
                          </div>
                        }
                      </div>
                    </div>

                    <mat-card-actions align="end">
                      <button mat-button color="warn" (click)="rejectApproval(approval)">
                        <mat-icon>close</mat-icon>
                        Reject
                      </button>
                      <button mat-flat-button color="primary" (click)="approveRequest(approval)">
                        <mat-icon>check</mat-icon>
                        Approve
                      </button>
                    </mat-card-actions>
                  </mat-card>
                }
              </div>
            }
          </div>
        </mat-tab>
      </mat-tab-group>
    </div>
  `,
  styles: [`
    .automation {
      max-width: 1400px;
      margin: 0 auto;
    }

    .page-header {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      margin-bottom: 24px;
    }

    .header-content h1 {
      font-size: 24px;
      font-weight: 600;
      margin: 0 0 4px 0;
    }

    .subtitle {
      color: var(--text-secondary);
      margin: 0;
    }

    /* Stats Row */
    .stats-row {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
      gap: 16px;
      margin-bottom: 24px;
    }

    .stat-card {
      display: flex;
      align-items: center;
      gap: 16px;
      padding: 20px;
      background: var(--bg-card);
      border: 1px solid var(--border-color);

      &.clickable {
        cursor: pointer;
        transition: border-color 0.15s ease;

        &:hover {
          border-color: var(--accent);
        }
      }
    }

    .stat-icon {
      width: 48px;
      height: 48px;
      border-radius: 12px;
      display: flex;
      align-items: center;
      justify-content: center;

      mat-icon {
        color: white;
        font-size: 24px;
        width: 24px;
        height: 24px;
      }

      &.bg-info { background: var(--info); }
      &.bg-success { background: var(--success); mat-icon { color: black; } }
      &.bg-warning { background: var(--warning); mat-icon { color: black; } }
      &.bg-accent { background: var(--accent); }
    }

    .stat-content {
      display: flex;
      flex-direction: column;
    }

    .stat-value {
      font-size: 28px;
      font-weight: 700;
      color: var(--text-primary);
    }

    .stat-label {
      font-size: 14px;
      color: var(--text-secondary);
    }

    .tab-content {
      padding: 24px 0;
    }

    .filters-row {
      display: flex;
      gap: 16px;
      margin-bottom: 16px;
      flex-wrap: wrap;
    }

    .search-field {
      flex: 1;
      min-width: 250px;
    }

    .filter-field {
      width: 180px;
    }

    .loading {
      display: flex;
      justify-content: center;
      padding: 48px;
    }

    .empty-state {
      display: flex;
      flex-direction: column;
      align-items: center;
      padding: 64px;
      color: var(--text-muted);

      mat-icon {
        font-size: 64px;
        width: 64px;
        height: 64px;
        margin-bottom: 16px;
        color: var(--success);
      }

      h3 {
        margin: 0 0 8px 0;
        color: var(--text-primary);
      }

      p {
        margin: 0;
      }
    }

    /* Playbooks Grid */
    .playbooks-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
      gap: 16px;
    }

    .playbook-card {
      background: var(--bg-card);
      border: 1px solid var(--border-color);
      transition: border-color 0.15s ease;

      &:hover {
        border-color: var(--accent);
      }

      &.inactive {
        opacity: 0.7;
      }
    }

    .playbook-icon {
      background: var(--bg-tertiary);
      border-radius: 8px;
      padding: 8px;

      &.category-containment { color: var(--danger); }
      &.category-enrichment { color: var(--info); }
      &.category-notification { color: var(--warning); }
      &.category-remediation { color: var(--success); }
    }

    .category-badge {
      display: inline-block;
      padding: 2px 8px;
      border-radius: 4px;
      font-size: 11px;
      background: var(--bg-tertiary);
      color: var(--text-secondary);
      margin-right: 8px;
    }

    .status-badge {
      display: inline-block;
      padding: 2px 8px;
      border-radius: 4px;
      font-size: 11px;
      font-weight: 500;

      &.status-active { background: var(--success); color: black; }
      &.status-inactive { background: var(--text-muted); color: white; }
      &.status-draft { background: var(--warning); color: black; }
      &.status-pending { background: var(--accent); color: white; }
    }

    .playbook-description {
      color: var(--text-secondary);
      font-size: 14px;
      line-height: 1.5;
      margin-bottom: 16px;
    }

    .playbook-meta {
      display: flex;
      flex-wrap: wrap;
      gap: 16px;
    }

    .meta-item {
      display: flex;
      align-items: center;
      gap: 4px;
      font-size: 12px;
      color: var(--text-secondary);

      mat-icon {
        font-size: 16px;
        width: 16px;
        height: 16px;
      }

      &.approval-required {
        color: var(--warning);
      }
    }

    /* Executions Table */
    .executions-table {
      width: 100%;
      background: transparent;
    }

    .status-indicator {
      display: flex;
      align-items: center;
      gap: 6px;

      mat-icon {
        font-size: 18px;
        width: 18px;
        height: 18px;
      }

      &.status-completed { color: var(--success); }
      &.status-running { color: var(--info); }
      &.status-failed { color: var(--danger); }
      &.status-pending { color: var(--text-muted); }
      &.status-awaiting_approval { color: var(--warning); }
      &.status-cancelled { color: var(--text-muted); }
    }

    .running-indicator {
      color: var(--info);
      font-style: italic;
    }

    /* Approvals List */
    .approvals-list {
      display: flex;
      flex-direction: column;
      gap: 16px;
    }

    .approval-card {
      padding: 20px;
      background: var(--bg-card);
      border: 1px solid var(--border-color);
      border-left: 4px solid var(--accent);
    }

    .approval-header {
      display: flex;
      align-items: flex-start;
      gap: 16px;
      margin-bottom: 16px;
    }

    .approval-icon {
      font-size: 32px;
      width: 32px;
      height: 32px;
      color: var(--accent);
    }

    .approval-info {
      flex: 1;

      h3 {
        margin: 0 0 4px 0;
        font-size: 16px;
        font-weight: 500;
      }
    }

    .approval-meta {
      font-size: 12px;
      color: var(--text-secondary);
    }

    .approval-params {
      background: var(--bg-tertiary);
      border-radius: 8px;
      padding: 16px;
      margin-bottom: 16px;

      h4 {
        margin: 0 0 12px 0;
        font-size: 12px;
        text-transform: uppercase;
        color: var(--text-muted);
      }
    }

    .params-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
      gap: 12px;
    }

    .param-item {
      display: flex;
      flex-direction: column;
      gap: 2px;
    }

    .param-key {
      font-size: 11px;
      color: var(--text-muted);
      text-transform: uppercase;
    }

    .param-value {
      font-size: 14px;
      color: var(--text-primary);
      font-family: monospace;
    }
  `]
})
export class AutomationComponent implements OnInit {
  selectedTab = 0;
  playbookSearch = '';
  categoryFilter = '';
  statusFilter = '';
  executionStatusFilter = '';

  isLoadingPlaybooks = signal(false);
  isLoadingExecutions = signal(false);
  isLoadingApprovals = signal(false);

  playbooks = signal<Workflow[]>([]);
  filteredPlaybooks = signal<Workflow[]>([]);
  executions = signal<WorkflowExecution[]>([]);
  totalExecutions = signal(0);
  pendingApprovals = signal<ApprovalRequest[]>([]);

  totalPlaybooks = signal(0);
  completedExecutions = signal(0);
  runningExecutions = signal(0);

  executionColumns = ['status', 'workflow', 'started_at', 'duration', 'started_by', 'actions'];

  constructor(
    private workflowService: WorkflowService,
    private dialog: MatDialog,
    private snackBar: MatSnackBar
  ) {}

  ngOnInit(): void {
    this.loadPlaybooks();
    this.loadExecutions();
    this.loadApprovals();
  }

  loadPlaybooks(): void {
    this.isLoadingPlaybooks.set(true);
    this.workflowService.list({
      category: this.categoryFilter || undefined,
      status: this.statusFilter || undefined
    }).subscribe({
      next: (workflows) => {
        this.playbooks.set(workflows);
        this.filterPlaybooks();
        this.totalPlaybooks.set(workflows.length);
        this.isLoadingPlaybooks.set(false);
      },
      error: () => this.isLoadingPlaybooks.set(false)
    });
  }

  filterPlaybooks(): void {
    let filtered = this.playbooks();
    if (this.playbookSearch) {
      const search = this.playbookSearch.toLowerCase();
      filtered = filtered.filter(p =>
        p.name.toLowerCase().includes(search) ||
        (p.description?.toLowerCase().includes(search) ?? false)
      );
    }
    this.filteredPlaybooks.set(filtered);
  }

  loadExecutions(page = 1, pageSize = 20): void {
    this.isLoadingExecutions.set(true);
    this.workflowService.getExecutions({
      status: (this.executionStatusFilter as ExecutionStatus) || undefined,
      page,
      page_size: pageSize
    }).subscribe({
      next: (response) => {
        this.executions.set(response.items);
        this.totalExecutions.set(response.total);
        this.updateExecutionStats(response.items);
        this.isLoadingExecutions.set(false);
      },
      error: () => this.isLoadingExecutions.set(false)
    });
  }

  updateExecutionStats(executions: WorkflowExecution[]): void {
    this.completedExecutions.set(executions.filter(e => e.status === 'completed').length);
    this.runningExecutions.set(executions.filter(e => e.status === 'running').length);
  }

  loadApprovals(): void {
    this.isLoadingApprovals.set(true);
    this.workflowService.getApprovals().subscribe({
      next: (approvals) => {
        this.pendingApprovals.set(approvals.filter(a => a.status === 'pending'));
        this.isLoadingApprovals.set(false);
      },
      error: () => this.isLoadingApprovals.set(false)
    });
  }

  refresh(): void {
    this.loadPlaybooks();
    this.loadExecutions();
    this.loadApprovals();
  }

  switchToApprovals(): void {
    this.selectedTab = 2;
  }

  onExecutionPageChange(event: PageEvent): void {
    this.loadExecutions(event.pageIndex + 1, event.pageSize);
  }

  getCategoryIcon(category: string): string {
    const icons: Record<string, string> = {
      containment: 'block',
      enrichment: 'search',
      notification: 'notifications',
      remediation: 'build'
    };
    return icons[category] || 'play_circle';
  }

  getStatusIcon(status: ExecutionStatus): string {
    const icons: Record<string, string> = {
      pending: 'schedule',
      running: 'sync',
      completed: 'check_circle',
      failed: 'error',
      cancelled: 'cancel',
      awaiting_approval: 'gavel'
    };
    return icons[status] || 'help';
  }

  formatStatus(status: string): string {
    return status.replace('_', ' ').split(' ')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ');
  }

  getDuration(start: string, end: string): string {
    const startDate = new Date(start);
    const endDate = new Date(end);
    const diffMs = endDate.getTime() - startDate.getTime();
    const diffSecs = Math.floor(diffMs / 1000);

    if (diffSecs < 60) return `${diffSecs}s`;
    if (diffSecs < 3600) return `${Math.floor(diffSecs / 60)}m ${diffSecs % 60}s`;
    return `${Math.floor(diffSecs / 3600)}h ${Math.floor((diffSecs % 3600) / 60)}m`;
  }

  getParamEntries(params: Record<string, unknown>): { key: string; value: string }[] {
    return Object.entries(params).map(([key, value]) => ({
      key,
      value: String(value)
    }));
  }

  viewPlaybook(playbook: Workflow): void {
    const dialogRef = this.dialog.open(PlaybookDetailDialogComponent, {
      data: playbook,
      panelClass: 'dark-dialog'
    });

    dialogRef.afterClosed().subscribe(result => {
      if (result?.action === 'run') {
        this.runPlaybook(result.playbook);
      }
    });
  }

  runPlaybook(playbook: Workflow): void {
    const dialogRef = this.dialog.open(RunPlaybookDialogComponent, {
      data: playbook,
      panelClass: 'dark-dialog'
    });

    dialogRef.afterClosed().subscribe(result => {
      if (result) {
        this.loadExecutions();
        const message = playbook.requires_approval
          ? 'Playbook submitted for approval'
          : 'Playbook execution started';
        this.snackBar.open(message, 'Dismiss', { duration: 3000 });
      }
    });
  }

  viewExecution(execution: WorkflowExecution): void {
    const dialogRef = this.dialog.open(ExecutionDetailDialogComponent, {
      data: execution,
      panelClass: 'dark-dialog'
    });

    dialogRef.afterClosed().subscribe(result => {
      if (result?.action === 'cancelled') {
        this.loadExecutions();
        this.snackBar.open('Execution cancelled', 'Dismiss', { duration: 2000 });
      } else if (result?.action === 'retry') {
        this.retryExecution(result.execution);
      }
    });
  }

  cancelExecution(execution: WorkflowExecution): void {
    this.workflowService.cancelExecution(execution.id).subscribe({
      next: () => {
        this.loadExecutions();
        this.snackBar.open('Execution cancelled', 'Dismiss', { duration: 2000 });
      },
      error: () => {
        this.snackBar.open('Failed to cancel execution', 'Dismiss', { duration: 3000 });
      }
    });
  }

  retryExecution(execution: WorkflowExecution): void {
    this.workflowService.trigger(execution.workflow_id, execution.parameters).subscribe({
      next: () => {
        this.loadExecutions();
        this.snackBar.open('Playbook execution restarted', 'Dismiss', { duration: 3000 });
      },
      error: () => {
        this.snackBar.open('Failed to retry execution', 'Dismiss', { duration: 3000 });
      }
    });
  }

  approveRequest(approval: ApprovalRequest): void {
    this.workflowService.approve(approval.id).subscribe({
      next: () => {
        this.loadApprovals();
        this.loadExecutions();
      }
    });
  }

  rejectApproval(approval: ApprovalRequest): void {
    const reason = prompt('Reason for rejection (optional):');
    this.workflowService.reject(approval.id, reason || undefined).subscribe({
      next: () => this.loadApprovals()
    });
  }
}
