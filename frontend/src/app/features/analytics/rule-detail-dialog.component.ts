import { Component, Inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MAT_DIALOG_DATA, MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatChipsModule } from '@angular/material/chips';
import { MatDividerModule } from '@angular/material/divider';
import { MatTabsModule } from '@angular/material/tabs';
import { MatTooltipModule } from '@angular/material/tooltip';
import { AnalyticsRule } from './analytics.component';

@Component({
  selector: 'app-rule-detail-dialog',
  standalone: true,
  imports: [
    CommonModule,
    MatDialogModule,
    MatButtonModule,
    MatIconModule,
    MatChipsModule,
    MatDividerModule,
    MatTabsModule,
    MatTooltipModule
  ],
  template: `
    <div class="dialog-header">
      <div class="header-content">
        <h2 mat-dialog-title>{{ data.name }}</h2>
        <span class="severity-badge" [class]="'severity-' + data.severity">
          {{ data.severity | uppercase }}
        </span>
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
                <span class="label">Status</span>
                <span class="value">
                  <mat-icon [class.enabled]="data.enabled">
                    {{ data.enabled ? 'check_circle' : 'cancel' }}
                  </mat-icon>
                  {{ data.enabled ? 'Enabled' : 'Disabled' }}
                </span>
              </div>

              <div class="detail-item">
                <span class="label">Source</span>
                <span class="source-badge" [class]="'source-' + data.source">
                  {{ data.source }}
                </span>
              </div>

              <div class="detail-item">
                <span class="label">Trigger Count</span>
                <span class="value">{{ data.trigger_count }}</span>
              </div>

              <div class="detail-item">
                <span class="label">Last Triggered</span>
                <span class="value">
                  {{ data.last_triggered ? (data.last_triggered | date:'medium') : 'Never' }}
                </span>
              </div>

              <div class="detail-item">
                <span class="label">Created</span>
                <span class="value">{{ data.created_at | date:'medium' }}</span>
              </div>

              <div class="detail-item">
                <span class="label">Updated</span>
                <span class="value">{{ data.updated_at | date:'medium' }}</span>
              </div>
            </div>
          </div>
        </mat-tab>

        <mat-tab label="MITRE ATT&CK">
          <div class="tab-content">
            <div class="detail-section">
              <h4>Tactics</h4>
              @if (data.tactics.length > 0) {
                <div class="chip-list">
                  @for (tactic of data.tactics; track tactic) {
                    <span class="tactic-chip">{{ tactic }}</span>
                  }
                </div>
              } @else {
                <p class="no-data">No tactics mapped</p>
              }
            </div>

            <div class="detail-section">
              <h4>Techniques</h4>
              @if (data.techniques.length > 0) {
                <div class="chip-list">
                  @for (technique of data.techniques; track technique) {
                    <span class="technique-chip">{{ technique }}</span>
                  }
                </div>
              } @else {
                <p class="no-data">No techniques mapped</p>
              }
            </div>
          </div>
        </mat-tab>
      </mat-tab-group>
    </mat-dialog-content>

    <mat-dialog-actions align="end">
      <button mat-button (click)="onClose()">Close</button>
      <button mat-flat-button color="primary" (click)="onEdit()">
        <mat-icon>edit</mat-icon>
        Edit Rule
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
      align-items: center;
      gap: 12px;
    }

    h2 {
      margin: 0;
      font-size: 20px;
      font-weight: 600;
    }

    mat-dialog-content {
      min-width: 550px;
      max-width: 700px;
    }

    .tab-content {
      padding: 24px 0;
    }

    .detail-section {
      margin-bottom: 24px;

      h4 {
        font-size: 14px;
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

          &.enabled {
            color: var(--success);
          }
        }
      }
    }

    .severity-badge {
      display: inline-block;
      padding: 4px 10px;
      border-radius: 4px;
      font-size: 11px;
      font-weight: 600;

      &.severity-critical { background: var(--danger); color: white; }
      &.severity-high { background: #f97316; color: white; }
      &.severity-medium { background: var(--warning); color: black; }
      &.severity-low { background: var(--info); color: white; }
      &.severity-informational { background: var(--text-muted); color: white; }
    }

    .source-badge {
      display: inline-block;
      padding: 4px 10px;
      border-radius: 4px;
      font-size: 12px;
      text-transform: capitalize;

      &.source-sigma { background: #7c3aed; color: white; }
      &.source-elastic { background: #059669; color: white; }
      &.source-custom { background: var(--accent); color: white; }
    }

    .chip-list {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }

    .tactic-chip {
      display: inline-block;
      padding: 6px 12px;
      border-radius: 6px;
      font-size: 13px;
      background: var(--bg-tertiary);
      color: var(--text-primary);
      border: 1px solid var(--border-color);
    }

    .technique-chip {
      display: inline-block;
      padding: 6px 12px;
      border-radius: 6px;
      font-size: 13px;
      font-family: monospace;
      background: var(--accent);
      color: white;
    }

    .no-data {
      color: var(--text-muted);
      font-style: italic;
      margin: 0;
    }
  `]
})
export class RuleDetailDialogComponent {
  constructor(
    @Inject(MAT_DIALOG_DATA) public data: AnalyticsRule,
    private dialogRef: MatDialogRef<RuleDetailDialogComponent>
  ) {}

  onClose(): void {
    this.dialogRef.close();
  }

  onEdit(): void {
    this.dialogRef.close({ action: 'edit', rule: this.data });
  }
}
