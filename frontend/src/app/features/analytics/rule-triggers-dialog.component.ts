import { Component, Inject, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MAT_DIALOG_DATA, MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatTableModule } from '@angular/material/table';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatChipsModule } from '@angular/material/chips';
import { AnalyticsService, RuleExecution } from '../../core/api/analytics.service';
import { AnalyticsRule } from './analytics.component';

@Component({
  selector: 'app-rule-triggers-dialog',
  standalone: true,
  imports: [
    CommonModule,
    MatDialogModule,
    MatButtonModule,
    MatIconModule,
    MatTableModule,
    MatProgressSpinnerModule,
    MatTooltipModule,
    MatChipsModule
  ],
  template: `
    <div class="dialog-header">
      <div class="header-content">
        <h2 mat-dialog-title>Trigger History</h2>
        <span class="rule-name">{{ data.name }}</span>
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
      } @else if (executions().length === 0) {
        <div class="empty-state">
          <mat-icon>history</mat-icon>
          <p>No execution history available</p>
          <span>This rule hasn't been triggered yet</span>
        </div>
      } @else {
        <div class="stats-row">
          <div class="stat">
            <span class="stat-value">{{ executions().length }}</span>
            <span class="stat-label">Total Runs</span>
          </div>
          <div class="stat">
            <span class="stat-value">{{ totalHits() }}</span>
            <span class="stat-label">Total Hits</span>
          </div>
          <div class="stat">
            <span class="stat-value">{{ incidentsCreated() }}</span>
            <span class="stat-label">Incidents Created</span>
          </div>
          <div class="stat">
            <span class="stat-value">{{ avgDuration() }}ms</span>
            <span class="stat-label">Avg Duration</span>
          </div>
        </div>

        <table mat-table [dataSource]="executions()" class="executions-table">
          <ng-container matColumnDef="status">
            <th mat-header-cell *matHeaderCellDef>Status</th>
            <td mat-cell *matCellDef="let exec">
              <span class="status-badge" [class]="'status-' + exec.status">
                <mat-icon>{{ getStatusIcon(exec.status) }}</mat-icon>
                {{ exec.status }}
              </span>
            </td>
          </ng-container>

          <ng-container matColumnDef="started_at">
            <th mat-header-cell *matHeaderCellDef>Started</th>
            <td mat-cell *matCellDef="let exec">
              {{ exec.started_at | date:'short' }}
            </td>
          </ng-container>

          <ng-container matColumnDef="duration">
            <th mat-header-cell *matHeaderCellDef>Duration</th>
            <td mat-cell *matCellDef="let exec">
              {{ exec.duration_ms ? exec.duration_ms + 'ms' : '-' }}
            </td>
          </ng-container>

          <ng-container matColumnDef="events_scanned">
            <th mat-header-cell *matHeaderCellDef>Events Scanned</th>
            <td mat-cell *matCellDef="let exec">
              {{ exec.events_scanned | number }}
            </td>
          </ng-container>

          <ng-container matColumnDef="hits">
            <th mat-header-cell *matHeaderCellDef>Hits</th>
            <td mat-cell *matCellDef="let exec">
              <span [class.has-hits]="exec.hits_count > 0">
                {{ exec.hits_count }}
              </span>
            </td>
          </ng-container>

          <ng-container matColumnDef="incidents">
            <th mat-header-cell *matHeaderCellDef>Incidents</th>
            <td mat-cell *matCellDef="let exec">
              @if (exec.incidents_created > 0) {
                <span class="incidents-badge">{{ exec.incidents_created }}</span>
              } @else {
                -
              }
            </td>
          </ng-container>

          <ng-container matColumnDef="error">
            <th mat-header-cell *matHeaderCellDef></th>
            <td mat-cell *matCellDef="let exec">
              @if (exec.error_message) {
                <mat-icon class="error-icon"
                          [matTooltip]="exec.error_message">
                  error_outline
                </mat-icon>
              }
            </td>
          </ng-container>

          <tr mat-header-row *matHeaderRowDef="displayedColumns"></tr>
          <tr mat-row *matRowDef="let row; columns: displayedColumns;"></tr>
        </table>
      }
    </mat-dialog-content>

    <mat-dialog-actions align="end">
      <button mat-button (click)="refresh()">
        <mat-icon>refresh</mat-icon>
        Refresh
      </button>
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
      flex-direction: column;
      gap: 4px;
    }

    h2 {
      margin: 0;
      font-size: 20px;
      font-weight: 600;
    }

    .rule-name {
      font-size: 14px;
      color: var(--text-secondary);
    }

    mat-dialog-content {
      min-width: 650px;
      max-width: 800px;
      min-height: 300px;
    }

    .loading {
      display: flex;
      justify-content: center;
      align-items: center;
      padding: 48px;
    }

    .empty-state {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      padding: 48px;
      text-align: center;

      mat-icon {
        font-size: 48px;
        width: 48px;
        height: 48px;
        color: var(--text-muted);
        margin-bottom: 16px;
      }

      p {
        font-size: 16px;
        font-weight: 500;
        color: var(--text-primary);
        margin: 0 0 4px 0;
      }

      span {
        font-size: 14px;
        color: var(--text-secondary);
      }
    }

    .stats-row {
      display: flex;
      gap: 24px;
      padding: 16px;
      background: var(--bg-tertiary);
      border-radius: 8px;
      margin-bottom: 16px;
    }

    .stat {
      display: flex;
      flex-direction: column;
      gap: 2px;
    }

    .stat-value {
      font-size: 20px;
      font-weight: 700;
      color: var(--text-primary);
    }

    .stat-label {
      font-size: 12px;
      color: var(--text-secondary);
    }

    .executions-table {
      width: 100%;
      background: transparent;
    }

    .status-badge {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      padding: 4px 8px;
      border-radius: 4px;
      font-size: 12px;
      text-transform: capitalize;

      mat-icon {
        font-size: 14px;
        width: 14px;
        height: 14px;
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

      &.status-pending {
        background: var(--bg-tertiary);
        color: var(--text-secondary);
      }
    }

    .has-hits {
      font-weight: 600;
      color: var(--warning);
    }

    .incidents-badge {
      display: inline-block;
      padding: 2px 8px;
      border-radius: 4px;
      font-size: 12px;
      font-weight: 600;
      background: var(--accent);
      color: white;
    }

    .error-icon {
      color: var(--danger);
      cursor: help;
    }
  `]
})
export class RuleTriggersDialogComponent implements OnInit {
  isLoading = signal(true);
  executions = signal<RuleExecution[]>([]);

  displayedColumns = ['status', 'started_at', 'duration', 'events_scanned', 'hits', 'incidents', 'error'];

  constructor(
    @Inject(MAT_DIALOG_DATA) public data: AnalyticsRule,
    private dialogRef: MatDialogRef<RuleTriggersDialogComponent>,
    private analyticsService: AnalyticsService
  ) {}

  ngOnInit(): void {
    this.loadExecutions();
  }

  loadExecutions(): void {
    this.isLoading.set(true);
    this.analyticsService.getRuleExecutions(this.data.id, 50).subscribe({
      next: (executions) => {
        this.executions.set(executions);
        this.isLoading.set(false);
      },
      error: (err) => {
        console.error('Failed to load executions:', err);
        this.isLoading.set(false);
      }
    });
  }

  totalHits(): number {
    return this.executions().reduce((sum, e) => sum + e.hits_count, 0);
  }

  incidentsCreated(): number {
    return this.executions().reduce((sum, e) => sum + e.incidents_created, 0);
  }

  avgDuration(): number {
    const execs = this.executions().filter(e => e.duration_ms);
    if (execs.length === 0) return 0;
    return Math.round(execs.reduce((sum, e) => sum + (e.duration_ms || 0), 0) / execs.length);
  }

  getStatusIcon(status: string): string {
    switch (status) {
      case 'completed': return 'check_circle';
      case 'running': return 'sync';
      case 'failed': return 'error';
      default: return 'schedule';
    }
  }

  refresh(): void {
    this.loadExecutions();
  }

  onClose(): void {
    this.dialogRef.close();
  }
}
