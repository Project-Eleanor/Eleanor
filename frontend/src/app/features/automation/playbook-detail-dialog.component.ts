import { Component, Inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MAT_DIALOG_DATA, MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatChipsModule } from '@angular/material/chips';
import { MatDividerModule } from '@angular/material/divider';
import { MatTabsModule } from '@angular/material/tabs';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatTableModule } from '@angular/material/table';
import { Workflow } from '../../shared/models';

@Component({
  selector: 'app-playbook-detail-dialog',
  standalone: true,
  imports: [
    CommonModule,
    MatDialogModule,
    MatButtonModule,
    MatIconModule,
    MatChipsModule,
    MatDividerModule,
    MatTabsModule,
    MatTooltipModule,
    MatTableModule
  ],
  template: `
    <div class="dialog-header">
      <div class="header-content">
        <mat-icon class="playbook-icon" [class]="'category-' + data.category">
          {{ getCategoryIcon(data.category) }}
        </mat-icon>
        <div class="header-text">
          <h2 mat-dialog-title>{{ data.name }}</h2>
          <div class="header-badges">
            <span class="category-badge">{{ data.category | titlecase }}</span>
            <span class="status-badge" [class]="'status-' + data.status">
              {{ data.status | titlecase }}
            </span>
            @if (data.requires_approval) {
              <span class="approval-badge">
                <mat-icon>gavel</mat-icon>
                Requires Approval
              </span>
            }
          </div>
        </div>
      </div>
      <button mat-icon-button (click)="onClose()" matTooltip="Close">
        <mat-icon>close</mat-icon>
      </button>
    </div>

    <mat-dialog-content>
      <mat-tab-group>
        <mat-tab label="Overview">
          <div class="tab-content">
            <div class="detail-section">
              <h4>Description</h4>
              <p class="description">{{ data.description || 'No description provided' }}</p>
            </div>

            <div class="detail-grid">
              <div class="detail-item">
                <span class="label">Trigger Type</span>
                <span class="value">
                  <mat-icon>{{ getTriggerIcon(data.trigger_type) }}</mat-icon>
                  {{ data.trigger_type | titlecase }}
                </span>
              </div>

              <div class="detail-item">
                <span class="label">Actions</span>
                <span class="value">{{ data.actions.length }} steps</span>
              </div>

              <div class="detail-item">
                <span class="label">Created By</span>
                <span class="value">{{ data.created_by }}</span>
              </div>

              <div class="detail-item">
                <span class="label">Created</span>
                <span class="value">{{ data.created_at | date:'medium' }}</span>
              </div>

              <div class="detail-item">
                <span class="label">Last Updated</span>
                <span class="value">{{ data.updated_at | date:'medium' }}</span>
              </div>
            </div>
          </div>
        </mat-tab>

        <mat-tab label="Parameters">
          <div class="tab-content">
            @if (data.parameters.length === 0) {
              <div class="empty-section">
                <mat-icon>tune</mat-icon>
                <p>This playbook has no configurable parameters</p>
              </div>
            } @else {
              <table mat-table [dataSource]="data.parameters" class="params-table">
                <ng-container matColumnDef="name">
                  <th mat-header-cell *matHeaderCellDef>Name</th>
                  <td mat-cell *matCellDef="let param">
                    <code>{{ param.name }}</code>
                    @if (param.required) {
                      <span class="required-badge">Required</span>
                    }
                  </td>
                </ng-container>

                <ng-container matColumnDef="type">
                  <th mat-header-cell *matHeaderCellDef>Type</th>
                  <td mat-cell *matCellDef="let param">
                    <span class="type-badge">{{ param.type }}</span>
                  </td>
                </ng-container>

                <ng-container matColumnDef="description">
                  <th mat-header-cell *matHeaderCellDef>Description</th>
                  <td mat-cell *matCellDef="let param">
                    {{ param.description || '-' }}
                  </td>
                </ng-container>

                <ng-container matColumnDef="default">
                  <th mat-header-cell *matHeaderCellDef>Default</th>
                  <td mat-cell *matCellDef="let param">
                    @if (param.default_value !== null && param.default_value !== undefined) {
                      <code>{{ param.default_value }}</code>
                    } @else {
                      <span class="no-default">-</span>
                    }
                  </td>
                </ng-container>

                <tr mat-header-row *matHeaderRowDef="paramColumns"></tr>
                <tr mat-row *matRowDef="let row; columns: paramColumns;"></tr>
              </table>
            }
          </div>
        </mat-tab>

        <mat-tab label="Actions">
          <div class="tab-content">
            <div class="actions-timeline">
              @for (action of data.actions; track action.id; let i = $index; let last = $last) {
                <div class="action-step">
                  <div class="step-number">{{ i + 1 }}</div>
                  <div class="step-content">
                    <div class="step-header">
                      <span class="step-name">{{ action.name }}</span>
                      <span class="step-type">{{ action.type }}</span>
                    </div>
                    @if (action.config && getConfigEntries(action.config).length > 0) {
                      <div class="step-config">
                        @for (entry of getConfigEntries(action.config); track entry.key) {
                          <div class="config-item">
                            <span class="config-key">{{ entry.key }}:</span>
                            <span class="config-value">{{ entry.value }}</span>
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
          </div>
        </mat-tab>
      </mat-tab-group>
    </mat-dialog-content>

    <mat-dialog-actions align="end">
      <button mat-button (click)="onClose()">Close</button>
      <button mat-flat-button color="primary"
              [disabled]="data.status !== 'active'"
              (click)="onRun()">
        <mat-icon>play_arrow</mat-icon>
        Run Playbook
      </button>
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
      align-items: flex-start;
      gap: 16px;
    }

    .playbook-icon {
      font-size: 36px;
      width: 36px;
      height: 36px;
      padding: 8px;
      border-radius: 8px;
      background: var(--bg-tertiary);

      &.category-containment { color: var(--danger); }
      &.category-enrichment { color: var(--info); }
      &.category-notification { color: var(--warning); }
      &.category-remediation { color: var(--success); }
    }

    .header-text h2 {
      margin: 0 0 8px 0;
      font-size: 20px;
      font-weight: 600;
    }

    .header-badges {
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .category-badge {
      padding: 2px 8px;
      border-radius: 4px;
      font-size: 11px;
      background: var(--bg-tertiary);
      color: var(--text-secondary);
    }

    .status-badge {
      padding: 2px 8px;
      border-radius: 4px;
      font-size: 11px;
      font-weight: 500;

      &.status-active { background: var(--success); color: black; }
      &.status-inactive { background: var(--text-muted); color: white; }
      &.status-draft { background: var(--warning); color: black; }
    }

    .approval-badge {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      padding: 2px 8px;
      border-radius: 4px;
      font-size: 11px;
      background: var(--accent);
      color: white;

      mat-icon {
        font-size: 12px;
        width: 12px;
        height: 12px;
      }
    }

    mat-dialog-content {
      min-width: 600px;
      max-width: 750px;
    }

    .tab-content {
      padding: 24px 0;
    }

    .detail-section {
      margin-bottom: 24px;

      h4 {
        font-size: 12px;
        font-weight: 600;
        color: var(--text-secondary);
        margin: 0 0 8px 0;
        text-transform: uppercase;
        letter-spacing: 0.5px;
      }
    }

    .description {
      color: var(--text-primary);
      line-height: 1.6;
      margin: 0;
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
        display: flex;
        align-items: center;
        gap: 6px;

        mat-icon {
          font-size: 18px;
          width: 18px;
          height: 18px;
          color: var(--text-muted);
        }
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

    .params-table {
      width: 100%;
      background: transparent;
    }

    .required-badge {
      display: inline-block;
      margin-left: 8px;
      padding: 1px 6px;
      border-radius: 3px;
      font-size: 10px;
      background: var(--danger);
      color: white;
    }

    .type-badge {
      display: inline-block;
      padding: 2px 8px;
      border-radius: 4px;
      font-size: 11px;
      font-family: monospace;
      background: var(--bg-tertiary);
      color: var(--text-secondary);
    }

    code {
      font-family: 'Monaco', 'Menlo', monospace;
      font-size: 13px;
      color: var(--accent);
    }

    .no-default {
      color: var(--text-muted);
    }

    .actions-timeline {
      padding: 8px 0;
    }

    .action-step {
      position: relative;
      display: flex;
      gap: 16px;
      padding-bottom: 24px;
    }

    .step-number {
      width: 32px;
      height: 32px;
      border-radius: 50%;
      background: var(--accent);
      color: white;
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: 600;
      font-size: 14px;
      flex-shrink: 0;
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

    .step-type {
      padding: 2px 8px;
      border-radius: 4px;
      font-size: 11px;
      font-family: monospace;
      background: var(--bg-tertiary);
      color: var(--text-secondary);
    }

    .step-config {
      background: var(--bg-tertiary);
      border-radius: 8px;
      padding: 12px;
    }

    .config-item {
      display: flex;
      gap: 8px;
      font-size: 13px;

      &:not(:last-child) {
        margin-bottom: 4px;
      }
    }

    .config-key {
      color: var(--text-muted);
    }

    .config-value {
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
export class PlaybookDetailDialogComponent {
  paramColumns = ['name', 'type', 'description', 'default'];

  constructor(
    @Inject(MAT_DIALOG_DATA) public data: Workflow,
    private dialogRef: MatDialogRef<PlaybookDetailDialogComponent>
  ) {}

  getCategoryIcon(category: string): string {
    const icons: Record<string, string> = {
      containment: 'block',
      enrichment: 'search',
      notification: 'notifications',
      remediation: 'build'
    };
    return icons[category] || 'play_circle';
  }

  getTriggerIcon(trigger: string): string {
    const icons: Record<string, string> = {
      manual: 'touch_app',
      automated: 'smart_toy',
      scheduled: 'schedule'
    };
    return icons[trigger] || 'play_circle';
  }

  getConfigEntries(config: Record<string, unknown>): { key: string; value: string }[] {
    return Object.entries(config).map(([key, value]) => ({
      key,
      value: typeof value === 'object' ? JSON.stringify(value) : String(value)
    }));
  }

  onClose(): void {
    this.dialogRef.close();
  }

  onRun(): void {
    this.dialogRef.close({ action: 'run', playbook: this.data });
  }
}
