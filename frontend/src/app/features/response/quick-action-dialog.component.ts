import { Component, Inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatDialogModule, MAT_DIALOG_DATA, MatDialogRef } from '@angular/material/dialog';
import { MatButtonModule } from '@angular/material/button';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatIconModule } from '@angular/material/icon';
import { MatSelectModule } from '@angular/material/select';

export interface QuickActionDialogData {
  action: {
    id: string;
    label: string;
    icon: string;
    danger: boolean;
    targetType: 'host' | 'ip' | 'user' | 'message';
    targetPlaceholder: string;
  };
}

export interface QuickActionDialogResult {
  target: string;
  reason: string;
  severity?: string;
}

@Component({
  selector: 'app-quick-action-dialog',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatDialogModule,
    MatButtonModule,
    MatFormFieldModule,
    MatInputModule,
    MatIconModule,
    MatSelectModule
  ],
  template: `
    <h2 mat-dialog-title>
      <mat-icon [class.danger]="data.action.danger">{{ data.action.icon }}</mat-icon>
      {{ data.action.label }}
    </h2>

    <mat-dialog-content>
      @if (data.action.danger) {
        <div class="warning-banner">
          <mat-icon>warning</mat-icon>
          <span>This is a potentially disruptive action. Please confirm the target carefully.</span>
        </div>
      }

      @if (data.action.id === 'notify') {
        <mat-form-field appearance="outline" class="full-width">
          <mat-label>Alert Message</mat-label>
          <textarea matInput [(ngModel)]="target" rows="3" placeholder="Enter alert message"></textarea>
        </mat-form-field>

        <mat-form-field appearance="outline" class="full-width">
          <mat-label>Severity</mat-label>
          <mat-select [(ngModel)]="severity">
            <mat-option value="low">Low</mat-option>
            <mat-option value="medium">Medium</mat-option>
            <mat-option value="high">High</mat-option>
            <mat-option value="critical">Critical</mat-option>
          </mat-select>
        </mat-form-field>
      } @else {
        <mat-form-field appearance="outline" class="full-width">
          <mat-label>{{ data.action.targetPlaceholder }}</mat-label>
          <input matInput [(ngModel)]="target" [placeholder]="getTargetExample()">
        </mat-form-field>
      }

      <mat-form-field appearance="outline" class="full-width">
        <mat-label>Reason (optional)</mat-label>
        <textarea matInput [(ngModel)]="reason" rows="2" placeholder="Document reason for this action"></textarea>
      </mat-form-field>
    </mat-dialog-content>

    <mat-dialog-actions align="end">
      <button mat-stroked-button (click)="cancel()">Cancel</button>
      <button mat-flat-button
              [color]="data.action.danger ? 'warn' : 'accent'"
              [disabled]="!target"
              (click)="confirm()">
        <mat-icon>{{ data.action.icon }}</mat-icon>
        Execute
      </button>
    </mat-dialog-actions>
  `,
  styles: [`
    mat-dialog-title {
      display: flex;
      align-items: center;
      gap: 12px;

      mat-icon {
        font-size: 24px;
        width: 24px;
        height: 24px;

        &.danger {
          color: var(--danger);
        }
      }
    }

    .warning-banner {
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 12px 16px;
      background: rgba(var(--warning-rgb), 0.15);
      border: 1px solid var(--warning);
      border-radius: 8px;
      margin-bottom: 16px;
      color: var(--warning);

      mat-icon {
        flex-shrink: 0;
      }

      span {
        font-size: 13px;
      }
    }

    .full-width {
      width: 100%;
      margin-bottom: 8px;
    }

    mat-dialog-content {
      min-width: 400px;
    }
  `]
})
export class QuickActionDialogComponent {
  target = '';
  reason = '';
  severity = 'medium';

  constructor(
    public dialogRef: MatDialogRef<QuickActionDialogComponent>,
    @Inject(MAT_DIALOG_DATA) public data: QuickActionDialogData
  ) {}

  getTargetExample(): string {
    switch (this.data.action.id) {
      case 'isolate':
      case 'collect':
      case 'scan':
        return 'e.g., WORKSTATION-001';
      case 'block-ip':
        return 'e.g., 192.168.1.100';
      case 'disable-user':
        return 'e.g., jsmith@company.com';
      default:
        return '';
    }
  }

  cancel(): void {
    this.dialogRef.close();
  }

  confirm(): void {
    const result: QuickActionDialogResult = {
      target: this.target,
      reason: this.reason
    };

    if (this.data.action.id === 'notify') {
      result.severity = this.severity;
    }

    this.dialogRef.close(result);
  }
}
