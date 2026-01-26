import { Component, Inject, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MAT_DIALOG_DATA, MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatTabsModule } from '@angular/material/tabs';
import { MatDividerModule } from '@angular/material/divider';
import { WorkflowExecution, ExecutionResult } from '../../shared/models';
import { WorkflowService } from '../../core/api/workflow.service';

@Component({
  selector: 'app-execution-detail-dialog',
  standalone: true,
  imports: [
    CommonModule,
    MatDialogModule,
    MatButtonModule,
    MatIconModule,
    MatProgressSpinnerModule,
    MatTooltipModule,
    MatTabsModule,
    MatDividerModule
  ],
  template: `
    <div class="dialog-header">
      <div class="header-content">
        <div class="status-icon" [class]="'status-' + execution().status">
          <mat-icon>{{ getStatusIcon(execution().status) }}</mat-icon>
        </div>
        <div class="header-text">
          <h2 mat-dialog-title>{{ execution().workflow_name }}</h2>
          <div class="header-meta">
            <span class="status-badge" [class]="'status-' + execution().status">
              {{ formatStatus(execution().status) }}
            </span>
            <span class="meta-item">
              Started by {{ execution().started_by }}
            </span>
          </div>
        </div>
      </div>
      <button mat-icon-button (click)="onClose()" matTooltip="Close">
        <mat-icon>close</mat-icon>
      </button>
    </div>

    <mat-dialog-content>
      @if (isLoading()) {
        <div class="loading">
          <mat-spinner diameter="40"></mat-spinner>
        </div>
      } @else {
        <mat-tab-group>
          <mat-tab label="Summary">
            <div class="tab-content">
              <div class="detail-grid">
                <div class="detail-item">
                  <span class="label">Execution ID</span>
                  <code class="value">{{ execution().id }}</code>
                </div>

                <div class="detail-item">
                  <span class="label">Status</span>
                  <span class="value status-text" [class]="'status-' + execution().status">
                    {{ formatStatus(execution().status) }}
                  </span>
                </div>

                <div class="detail-item">
                  <span class="label">Started</span>
                  <span class="value">{{ execution().started_at | date:'medium' }}</span>
                </div>

                <div class="detail-item">
                  <span class="label">Completed</span>
                  <span class="value">
                    @if (execution().completed_at) {
                      {{ execution().completed_at | date:'medium' }}
                    } @else {
                      -
                    }
                  </span>
                </div>

                <div class="detail-item">
                  <span class="label">Duration</span>
                  <span class="value">
                    @if (execution().completed_at) {
                      {{ getDuration(execution().started_at, execution().completed_at) }}
                    } @else if (execution().status === 'running') {
                      <span class="running">Running...</span>
                    } @else {
                      -
                    }
                  </span>
                </div>

                <div class="detail-item">
                  <span class="label">Started By</span>
                  <span class="value">{{ execution().started_by }}</span>
                </div>

                @if (execution().approved_by) {
                  <div class="detail-item">
                    <span class="label">Approved By</span>
                    <span class="value">{{ execution().approved_by }}</span>
                  </div>
                }
              </div>

              @if (execution().error) {
                <div class="error-section">
                  <h4>Error</h4>
                  <div class="error-box">
                    <mat-icon>error</mat-icon>
                    <span>{{ execution().error }}</span>
                  </div>
                </div>
              }
            </div>
          </mat-tab>

          <mat-tab label="Parameters">
            <div class="tab-content">
              @if (getParamEntries().length === 0) {
                <div class="empty-section">
                  <mat-icon>tune</mat-icon>
                  <p>No parameters were provided</p>
                </div>
              } @else {
                <div class="params-grid">
                  @for (param of getParamEntries(); track param.key) {
                    <div class="param-item">
                      <span class="param-key">{{ param.key }}</span>
                      <code class="param-value">{{ param.value }}</code>
                    </div>
                  }
                </div>
              }
            </div>
          </mat-tab>

          <mat-tab label="Actions">
            <div class="tab-content">
              @if (execution().results.length === 0) {
                <div class="empty-section">
                  <mat-icon>
                    {{ execution().status === 'running' ? 'hourglass_empty' : 'layers' }}
                  </mat-icon>
                  <p>
                    @if (execution().status === 'running') {
                      Actions are being executed...
                    } @else {
                      No action results available
                    }
                  </p>
                </div>
              } @else {
                <div class="results-timeline">
                  @for (result of execution().results; track result.action_id; let i = $index; let last = $last) {
                    <div class="result-step" [class]="'result-' + result.status">
                      <div class="step-indicator">
                        <mat-icon>{{ getResultIcon(result.status) }}</mat-icon>
                      </div>
                      <div class="step-content">
                        <div class="step-header">
                          <span class="step-name">{{ result.action_name }}</span>
                          <span class="step-status" [class]="'status-' + result.status">
                            {{ result.status | titlecase }}
                          </span>
                          <span class="step-time">{{ result.executed_at | date:'shortTime' }}</span>
                        </div>
                        @if (result.error) {
                          <div class="step-error">
                            <mat-icon>warning</mat-icon>
                            {{ result.error }}
                          </div>
                        }
                        @if (result.output && getOutputEntries(result.output).length > 0) {
                          <div class="step-output">
                            @for (entry of getOutputEntries(result.output); track entry.key) {
                              <div class="output-item">
                                <span class="output-key">{{ entry.key }}:</span>
                                <span class="output-value">{{ entry.value }}</span>
                              </div>
                            }
                          </div>
                        }
                      </div>
                      @if (!last) {
                        <div class="step-connector"></div>
                      }
                    </div>
                  }
                </div>
              }
            </div>
          </mat-tab>
        </mat-tab-group>
      }
    </mat-dialog-content>

    <mat-dialog-actions align="end">
      @if (execution().status === 'running') {
        <button mat-button color="warn" (click)="onCancel()">
          <mat-icon>cancel</mat-icon>
          Cancel Execution
        </button>
      }
      @if (execution().status === 'failed') {
        <button mat-button (click)="onRetry()">
          <mat-icon>refresh</mat-icon>
          Retry
        </button>
      }
      <button mat-flat-button color="primary" (click)="onClose()">Close</button>
    </mat-dialog-actions>
  `,
  styles: [`
    .dialog-header {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      padding: 16px 24px 0;
    }

    .header-content {
      display: flex;
      gap: 16px;
    }

    .status-icon {
      width: 48px;
      height: 48px;
      border-radius: 12px;
      display: flex;
      align-items: center;
      justify-content: center;

      mat-icon {
        font-size: 28px;
        width: 28px;
        height: 28px;
      }

      &.status-completed {
        background: rgba(16, 185, 129, 0.15);
        color: var(--success);
      }
      &.status-running {
        background: rgba(59, 130, 246, 0.15);
        color: var(--info);
      }
      &.status-failed {
        background: rgba(239, 68, 68, 0.15);
        color: var(--danger);
      }
      &.status-pending, &.status-awaiting_approval {
        background: rgba(245, 158, 11, 0.15);
        color: var(--warning);
      }
      &.status-cancelled {
        background: var(--bg-tertiary);
        color: var(--text-muted);
      }
    }

    .header-text h2 {
      margin: 0 0 8px 0;
      font-size: 20px;
      font-weight: 600;
    }

    .header-meta {
      display: flex;
      align-items: center;
      gap: 12px;
    }

    .status-badge {
      display: inline-block;
      padding: 2px 8px;
      border-radius: 4px;
      font-size: 11px;
      font-weight: 500;

      &.status-completed { background: var(--success); color: black; }
      &.status-running { background: var(--info); color: white; }
      &.status-failed { background: var(--danger); color: white; }
      &.status-pending { background: var(--text-muted); color: white; }
      &.status-awaiting_approval { background: var(--warning); color: black; }
      &.status-cancelled { background: var(--text-muted); color: white; }
    }

    .meta-item {
      font-size: 13px;
      color: var(--text-secondary);
    }

    mat-dialog-content {
      min-width: 550px;
      max-width: 700px;
      min-height: 300px;
    }

    .loading {
      display: flex;
      justify-content: center;
      align-items: center;
      padding: 48px;
    }

    .tab-content {
      padding: 24px 0;
    }

    .detail-grid {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 16px;
    }

    .detail-item {
      display: flex;
      flex-direction: column;
      gap: 4px;

      .label {
        font-size: 12px;
        color: var(--text-secondary);
        text-transform: uppercase;
        letter-spacing: 0.5px;
      }

      .value {
        font-size: 14px;
        color: var(--text-primary);
      }

      code.value {
        font-family: 'Monaco', 'Menlo', monospace;
        font-size: 12px;
        color: var(--accent);
      }
    }

    .status-text {
      &.status-completed { color: var(--success); }
      &.status-running { color: var(--info); }
      &.status-failed { color: var(--danger); }
      &.status-pending { color: var(--text-muted); }
      &.status-awaiting_approval { color: var(--warning); }
    }

    .running {
      color: var(--info);
      font-style: italic;
    }

    .error-section {
      margin-top: 24px;

      h4 {
        font-size: 12px;
        font-weight: 600;
        color: var(--text-secondary);
        margin: 0 0 8px 0;
        text-transform: uppercase;
        letter-spacing: 0.5px;
      }
    }

    .error-box {
      display: flex;
      align-items: flex-start;
      gap: 12px;
      padding: 16px;
      border-radius: 8px;
      background: rgba(239, 68, 68, 0.1);
      color: var(--danger);

      mat-icon {
        flex-shrink: 0;
      }

      span {
        font-family: monospace;
        font-size: 13px;
        line-height: 1.5;
      }
    }

    .empty-section {
      display: flex;
      flex-direction: column;
      align-items: center;
      padding: 32px;
      color: var(--text-muted);

      mat-icon {
        font-size: 48px;
        width: 48px;
        height: 48px;
        margin-bottom: 12px;
      }

      p {
        margin: 0;
      }
    }

    .params-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
      gap: 16px;
    }

    .param-item {
      display: flex;
      flex-direction: column;
      gap: 4px;
    }

    .param-key {
      font-size: 11px;
      color: var(--text-muted);
      text-transform: uppercase;
    }

    .param-value {
      font-family: 'Monaco', 'Menlo', monospace;
      font-size: 13px;
      color: var(--accent);
    }

    .results-timeline {
      padding: 8px 0;
    }

    .result-step {
      position: relative;
      display: flex;
      gap: 16px;
      padding-bottom: 24px;
    }

    .step-indicator {
      width: 32px;
      height: 32px;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;

      mat-icon {
        font-size: 18px;
        width: 18px;
        height: 18px;
      }
    }

    .result-step.result-success .step-indicator {
      background: rgba(16, 185, 129, 0.15);
      color: var(--success);
    }

    .result-step.result-failed .step-indicator {
      background: rgba(239, 68, 68, 0.15);
      color: var(--danger);
    }

    .result-step.result-skipped .step-indicator {
      background: var(--bg-tertiary);
      color: var(--text-muted);
    }

    .step-content {
      flex: 1;
      padding-top: 4px;
    }

    .step-header {
      display: flex;
      align-items: center;
      gap: 12px;
      margin-bottom: 8px;
    }

    .step-name {
      font-weight: 500;
      color: var(--text-primary);
    }

    .step-status {
      font-size: 11px;
      padding: 2px 8px;
      border-radius: 4px;

      &.status-success { background: var(--success); color: black; }
      &.status-failed { background: var(--danger); color: white; }
      &.status-skipped { background: var(--text-muted); color: white; }
    }

    .step-time {
      font-size: 12px;
      color: var(--text-muted);
    }

    .step-error {
      display: flex;
      align-items: flex-start;
      gap: 8px;
      padding: 12px;
      border-radius: 6px;
      background: rgba(239, 68, 68, 0.1);
      color: var(--danger);
      font-size: 13px;
      margin-bottom: 8px;

      mat-icon {
        font-size: 16px;
        width: 16px;
        height: 16px;
        flex-shrink: 0;
      }
    }

    .step-output {
      background: var(--bg-tertiary);
      border-radius: 6px;
      padding: 12px;
    }

    .output-item {
      display: flex;
      gap: 8px;
      font-size: 13px;

      &:not(:last-child) {
        margin-bottom: 4px;
      }
    }

    .output-key {
      color: var(--text-muted);
    }

    .output-value {
      color: var(--text-primary);
      font-family: monospace;
    }

    .step-connector {
      position: absolute;
      left: 15px;
      top: 40px;
      bottom: 0;
      width: 2px;
      background: var(--border-color);
    }
  `]
})
export class ExecutionDetailDialogComponent implements OnInit {
  isLoading = signal(true);
  execution = signal<WorkflowExecution>(this.data);

  constructor(
    @Inject(MAT_DIALOG_DATA) public data: WorkflowExecution,
    private dialogRef: MatDialogRef<ExecutionDetailDialogComponent>,
    private workflowService: WorkflowService
  ) {}

  ngOnInit(): void {
    this.loadExecution();
  }

  loadExecution(): void {
    this.isLoading.set(true);
    this.workflowService.getExecution(this.data.id).subscribe({
      next: (exec) => {
        this.execution.set(exec);
        this.isLoading.set(false);
      },
      error: () => {
        this.execution.set(this.data);
        this.isLoading.set(false);
      }
    });
  }

  getStatusIcon(status: string): string {
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

  getResultIcon(status: string): string {
    const icons: Record<string, string> = {
      success: 'check',
      failed: 'close',
      skipped: 'remove'
    };
    return icons[status] || 'help';
  }

  formatStatus(status: string): string {
    return status.replace('_', ' ').split(' ')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ');
  }

  getDuration(start: string, end: string | null): string {
    if (!end) return '-';
    const startDate = new Date(start);
    const endDate = new Date(end);
    const diffMs = endDate.getTime() - startDate.getTime();
    const diffSecs = Math.floor(diffMs / 1000);

    if (diffSecs < 60) return `${diffSecs}s`;
    if (diffSecs < 3600) return `${Math.floor(diffSecs / 60)}m ${diffSecs % 60}s`;
    return `${Math.floor(diffSecs / 3600)}h ${Math.floor((diffSecs % 3600) / 60)}m`;
  }

  getParamEntries(): { key: string; value: string }[] {
    return Object.entries(this.execution().parameters).map(([key, value]) => ({
      key,
      value: typeof value === 'object' ? JSON.stringify(value) : String(value)
    }));
  }

  getOutputEntries(output: Record<string, unknown>): { key: string; value: string }[] {
    return Object.entries(output).map(([key, value]) => ({
      key,
      value: typeof value === 'object' ? JSON.stringify(value) : String(value)
    }));
  }

  onCancel(): void {
    this.workflowService.cancelExecution(this.execution().id).subscribe({
      next: () => {
        this.dialogRef.close({ action: 'cancelled' });
      }
    });
  }

  onRetry(): void {
    this.dialogRef.close({ action: 'retry', execution: this.execution() });
  }

  onClose(): void {
    this.dialogRef.close();
  }
}
