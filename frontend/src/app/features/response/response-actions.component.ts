import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatTabsModule } from '@angular/material/tabs';
import { MatChipsModule } from '@angular/material/chips';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatTableModule } from '@angular/material/table';
import { MatDialogModule, MatDialog } from '@angular/material/dialog';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { WorkflowService } from '../../core/api/workflow.service';
import { Workflow, WorkflowExecution, ApprovalRequest } from '../../shared/models';
import { TriggerWorkflowDialogComponent } from './trigger-workflow-dialog.component';

@Component({
  selector: 'app-response-actions',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatCardModule,
    MatButtonModule,
    MatIconModule,
    MatTabsModule,
    MatChipsModule,
    MatProgressSpinnerModule,
    MatTableModule,
    MatDialogModule,
    MatTooltipModule,
    MatSnackBarModule
  ],
  template: `
    <div class="response-actions">
      <h1>Response Actions</h1>

      <mat-tab-group>
        <!-- Available Actions -->
        <mat-tab label="Available Actions">
          <div class="tab-content">
            <div class="actions-grid">
              <!-- Quick Actions -->
              <mat-card class="quick-actions-card">
                <mat-card-header>
                  <mat-card-title>Quick Actions</mat-card-title>
                </mat-card-header>
                <mat-card-content>
                  <div class="quick-actions">
                    @for (action of quickActions; track action.id) {
                      <button mat-stroked-button
                              class="quick-action"
                              [class.danger]="action.danger"
                              (click)="triggerQuickAction(action)">
                        <mat-icon>{{ action.icon }}</mat-icon>
                        {{ action.label }}
                      </button>
                    }
                  </div>
                </mat-card-content>
              </mat-card>

              <!-- Workflow List -->
              @for (workflow of workflows(); track workflow.id) {
                <mat-card class="workflow-card" (click)="openWorkflow(workflow)">
                  <div class="workflow-header">
                    <mat-icon [class]="'category-' + workflow.category">
                      {{ getWorkflowIcon(workflow.category) }}
                    </mat-icon>
                    <div class="workflow-info">
                      <h3>{{ workflow.name }}</h3>
                      <span class="category">{{ workflow.category }}</span>
                    </div>
                    @if (workflow.requires_approval) {
                      <mat-chip class="approval-chip">Requires Approval</mat-chip>
                    }
                  </div>
                  <p class="workflow-description">{{ workflow.description }}</p>
                  <div class="workflow-footer">
                    <span class="trigger-type">{{ workflow.trigger_type }}</span>
                    <button mat-flat-button color="accent" (click)="runWorkflow(workflow); $event.stopPropagation()">
                      <mat-icon>play_arrow</mat-icon>
                      Run
                    </button>
                  </div>
                </mat-card>
              }
            </div>
          </div>
        </mat-tab>

        <!-- Executions -->
        <mat-tab label="Executions ({{ executions().length }})">
          <div class="tab-content">
            @if (isLoadingExecutions()) {
              <div class="loading">
                <mat-spinner diameter="40"></mat-spinner>
              </div>
            } @else if (executions().length === 0) {
              <div class="empty-state">
                <mat-icon>history</mat-icon>
                <p>No recent executions</p>
              </div>
            } @else {
              <div class="executions-list">
                <table mat-table [dataSource]="executions()">
                  <ng-container matColumnDef="workflow">
                    <th mat-header-cell *matHeaderCellDef>Workflow</th>
                    <td mat-cell *matCellDef="let row">{{ row.workflow_name }}</td>
                  </ng-container>

                  <ng-container matColumnDef="status">
                    <th mat-header-cell *matHeaderCellDef>Status</th>
                    <td mat-cell *matCellDef="let row">
                      <span class="status-badge" [class]="'status-' + row.status">
                        {{ row.status | titlecase }}
                      </span>
                    </td>
                  </ng-container>

                  <ng-container matColumnDef="started">
                    <th mat-header-cell *matHeaderCellDef>Started</th>
                    <td mat-cell *matCellDef="let row">{{ row.started_at | date:'short' }}</td>
                  </ng-container>

                  <ng-container matColumnDef="started_by">
                    <th mat-header-cell *matHeaderCellDef>Started By</th>
                    <td mat-cell *matCellDef="let row">{{ row.started_by }}</td>
                  </ng-container>

                  <ng-container matColumnDef="actions">
                    <th mat-header-cell *matHeaderCellDef></th>
                    <td mat-cell *matCellDef="let row">
                      @if (row.status === 'running') {
                        <button mat-icon-button matTooltip="Cancel" (click)="cancelExecution(row)">
                          <mat-icon>cancel</mat-icon>
                        </button>
                      }
                      <button mat-icon-button matTooltip="View Details">
                        <mat-icon>visibility</mat-icon>
                      </button>
                    </td>
                  </ng-container>

                  <tr mat-header-row *matHeaderRowDef="executionColumns"></tr>
                  <tr mat-row *matRowDef="let row; columns: executionColumns;"></tr>
                </table>
              </div>
            }
          </div>
        </mat-tab>

        <!-- Pending Approvals -->
        <mat-tab>
          <ng-template mat-tab-label>
            Approvals
            @if (approvals().length > 0) {
              <span class="badge">{{ approvals().length }}</span>
            }
          </ng-template>
          <div class="tab-content">
            @if (approvals().length === 0) {
              <div class="empty-state">
                <mat-icon>check_circle</mat-icon>
                <p>No pending approvals</p>
              </div>
            } @else {
              <div class="approvals-list">
                @for (approval of approvals(); track approval.id) {
                  <mat-card class="approval-card">
                    <div class="approval-header">
                      <h3>{{ approval.workflow_name }}</h3>
                      <span class="requested-by">
                        Requested by {{ approval.requested_by }} at {{ approval.requested_at | date:'short' }}
                      </span>
                    </div>

                    <div class="approval-params">
                      <h4>Parameters:</h4>
                      @for (entry of getParamEntries(approval.parameters); track entry[0]) {
                        <div class="param">
                          <span class="key">{{ entry[0] }}:</span>
                          <span class="value">{{ entry[1] }}</span>
                        </div>
                      }
                    </div>

                    <div class="approval-actions">
                      <button mat-stroked-button color="warn" (click)="reject(approval)">
                        <mat-icon>close</mat-icon>
                        Reject
                      </button>
                      <button mat-flat-button color="accent" (click)="approve(approval)">
                        <mat-icon>check</mat-icon>
                        Approve
                      </button>
                    </div>
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
    .response-actions {
      max-width: 1200px;
      margin: 0 auto;
    }

    h1 {
      font-size: 24px;
      margin-bottom: 24px;
    }

    .tab-content {
      padding: 24px 0;
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
      padding: 48px;
      color: var(--text-muted);

      mat-icon {
        font-size: 48px;
        width: 48px;
        height: 48px;
        margin-bottom: 16px;
      }
    }

    .actions-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
      gap: 16px;
    }

    .quick-actions-card {
      grid-column: 1 / -1;
      background: var(--bg-card);
    }

    .quick-actions {
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
    }

    .quick-action {
      display: flex;
      align-items: center;
      gap: 8px;

      &.danger {
        color: var(--danger);
        border-color: var(--danger);
      }
    }

    .workflow-card {
      padding: 16px;
      background: var(--bg-card);
      cursor: pointer;
      transition: border-color 0.15s ease;

      &:hover {
        border-color: var(--accent);
      }
    }

    .workflow-header {
      display: flex;
      align-items: flex-start;
      gap: 12px;
      margin-bottom: 12px;

      mat-icon {
        font-size: 32px;
        width: 32px;
        height: 32px;

        &.category-containment { color: var(--danger); }
        &.category-collection { color: var(--info); }
        &.category-enrichment { color: var(--success); }
        &.category-notification { color: var(--warning); }
      }
    }

    .workflow-info {
      flex: 1;

      h3 {
        margin: 0;
        font-size: 16px;
      }

      .category {
        font-size: 12px;
        color: var(--text-secondary);
      }
    }

    .approval-chip {
      font-size: 10px;
      min-height: 22px !important;
      background: var(--warning) !important;
      color: black !important;
    }

    .workflow-description {
      font-size: 13px;
      color: var(--text-secondary);
      margin: 0 0 12px;
    }

    .workflow-footer {
      display: flex;
      justify-content: space-between;
      align-items: center;
    }

    .trigger-type {
      font-size: 11px;
      color: var(--text-muted);
      text-transform: uppercase;
    }

    .executions-list {
      background: var(--bg-card);
      border: 1px solid var(--border-color);
      border-radius: 8px;
      overflow: hidden;

      table {
        width: 100%;
      }
    }

    .status-badge {
      padding: 4px 12px;
      border-radius: 12px;
      font-size: 12px;

      &.status-pending { background: var(--text-muted); color: white; }
      &.status-running { background: var(--info); color: white; }
      &.status-completed { background: var(--success); color: black; }
      &.status-failed { background: var(--danger); color: white; }
      &.status-cancelled { background: var(--text-muted); color: white; }
      &.status-awaiting_approval { background: var(--warning); color: black; }
    }

    .approvals-list {
      display: flex;
      flex-direction: column;
      gap: 16px;
    }

    .approval-card {
      padding: 16px;
      background: var(--bg-card);
      border-left: 4px solid var(--warning);
    }

    .approval-header {
      margin-bottom: 16px;

      h3 {
        margin: 0 0 4px;
      }

      .requested-by {
        font-size: 12px;
        color: var(--text-secondary);
      }
    }

    .approval-params {
      background: var(--bg-surface);
      padding: 12px;
      border-radius: 8px;
      margin-bottom: 16px;

      h4 {
        margin: 0 0 8px;
        font-size: 12px;
        color: var(--text-secondary);
      }

      .param {
        display: flex;
        gap: 8px;
        padding: 4px 0;
        font-size: 13px;

        .key {
          color: var(--text-secondary);
        }

        .value {
          font-family: monospace;
        }
      }
    }

    .approval-actions {
      display: flex;
      gap: 8px;
      justify-content: flex-end;
    }

    .badge {
      background: var(--accent);
      color: white;
      padding: 2px 8px;
      border-radius: 10px;
      font-size: 11px;
      margin-left: 8px;
    }

    ::ng-deep .mat-mdc-tab-labels {
      background: var(--bg-secondary);
    }
  `]
})
export class ResponseActionsComponent implements OnInit {
  workflows = signal<Workflow[]>([]);
  executions = signal<WorkflowExecution[]>([]);
  approvals = signal<ApprovalRequest[]>([]);
  isLoadingExecutions = signal(false);

  executionColumns = ['workflow', 'status', 'started', 'started_by', 'actions'];

  quickActions = [
    { id: 'isolate', label: 'Isolate Host', icon: 'block', danger: true },
    { id: 'block-ip', label: 'Block IP', icon: 'shield', danger: true },
    { id: 'disable-user', label: 'Disable User', icon: 'person_off', danger: true },
    { id: 'collect', label: 'Collect Artifacts', icon: 'download', danger: false },
    { id: 'scan', label: 'Trigger Scan', icon: 'search', danger: false },
    { id: 'notify', label: 'Send Alert', icon: 'notifications', danger: false }
  ];

  constructor(
    private workflowService: WorkflowService,
    private dialog: MatDialog,
    private snackBar: MatSnackBar
  ) {}

  ngOnInit(): void {
    this.loadWorkflows();
    this.loadExecutions();
    this.loadApprovals();
  }

  private loadWorkflows(): void {
    this.workflowService.list({ status: 'active' }).subscribe({
      next: (workflows) => this.workflows.set(workflows)
    });
  }

  private loadExecutions(): void {
    this.isLoadingExecutions.set(true);
    this.workflowService.getExecutions({ page_size: 20 }).subscribe({
      next: (response) => {
        this.executions.set(response.items);
        this.isLoadingExecutions.set(false);
      },
      error: () => this.isLoadingExecutions.set(false)
    });
  }

  private loadApprovals(): void {
    this.workflowService.getApprovals().subscribe({
      next: (approvals) => this.approvals.set(approvals)
    });
  }

  openWorkflow(workflow: Workflow): void {
    this.runWorkflow(workflow);
  }

  runWorkflow(workflow: Workflow): void {
    const dialogRef = this.dialog.open(TriggerWorkflowDialogComponent, {
      width: '500px',
      data: { workflow }
    });

    dialogRef.afterClosed().subscribe(result => {
      if (result) {
        this.loadExecutions();
        this.snackBar.open('Workflow started', 'Dismiss', { duration: 3000 });
      }
    });
  }

  triggerQuickAction(action: { id: string; label: string }): void {
    this.snackBar.open(`${action.label} action coming soon`, 'Dismiss', { duration: 3000 });
  }

  cancelExecution(execution: WorkflowExecution): void {
    this.workflowService.cancelExecution(execution.id).subscribe({
      next: () => {
        this.loadExecutions();
        this.snackBar.open('Execution cancelled', 'Dismiss', { duration: 3000 });
      }
    });
  }

  approve(approval: ApprovalRequest): void {
    this.workflowService.approve(approval.id).subscribe({
      next: () => {
        this.loadApprovals();
        this.loadExecutions();
        this.snackBar.open('Approved', 'Dismiss', { duration: 3000 });
      }
    });
  }

  reject(approval: ApprovalRequest): void {
    this.workflowService.reject(approval.id).subscribe({
      next: () => {
        this.loadApprovals();
        this.snackBar.open('Rejected', 'Dismiss', { duration: 3000 });
      }
    });
  }

  getWorkflowIcon(category: string): string {
    const icons: Record<string, string> = {
      containment: 'security',
      collection: 'download',
      enrichment: 'auto_awesome',
      notification: 'notifications'
    };
    return icons[category] || 'play_circle';
  }

  getParamEntries(params: Record<string, unknown>): [string, string][] {
    return Object.entries(params).map(([k, v]) => [k, String(v)]);
  }
}
