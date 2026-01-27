import { Component, Inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatDialogModule, MAT_DIALOG_DATA, MatDialogRef } from '@angular/material/dialog';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatSelectModule } from '@angular/material/select';
import { CaseService } from '../../core/api/case.service';

interface DialogData {
  endpoint: {
    client_id: string;
    hostname: string;
    os?: string;
    isolation_status?: {
      is_isolated: boolean;
      last_action_at?: string;
      last_action_by?: string;
    };
  };
}

interface DialogResult {
  reason: string;
  caseId?: string;
}

@Component({
  selector: 'app-release-dialog',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatDialogModule,
    MatButtonModule,
    MatIconModule,
    MatInputModule,
    MatFormFieldModule,
    MatSelectModule
  ],
  template: `
    <h2 mat-dialog-title>
      <mat-icon class="success-icon">lock_open</mat-icon>
      Release Host from Isolation
    </h2>

    <mat-dialog-content>
      <div class="info-banner">
        <mat-icon>info</mat-icon>
        <p>
          This will restore full network connectivity to <strong>{{ data.endpoint.hostname }}</strong>.
          Ensure that the threat has been remediated before releasing.
        </p>
      </div>

      <div class="endpoint-info">
        <div class="info-row">
          <span class="label">Hostname:</span>
          <span class="value">{{ data.endpoint.hostname }}</span>
        </div>
        <div class="info-row">
          <span class="label">Client ID:</span>
          <span class="value monospace">{{ data.endpoint.client_id }}</span>
        </div>
        @if (data.endpoint.isolation_status?.last_action_at) {
          <div class="info-row">
            <span class="label">Isolated Since:</span>
            <span class="value">{{ data.endpoint.isolation_status.last_action_at | date:'short' }}</span>
          </div>
        }
      </div>

      <mat-form-field appearance="outline" class="full-width">
        <mat-label>Reason for release (required)</mat-label>
        <textarea matInput
                  [(ngModel)]="reason"
                  rows="3"
                  placeholder="Document the remediation performed and reason for release..."
                  required></textarea>
        <mat-hint>Minimum 10 characters for audit trail</mat-hint>
        <mat-error *ngIf="reason.length < 10">Reason must be at least 10 characters</mat-error>
      </mat-form-field>

      <mat-form-field appearance="outline" class="full-width">
        <mat-label>Link to Case (optional)</mat-label>
        <mat-select [(ngModel)]="selectedCaseId">
          <mat-option [value]="null">No case</mat-option>
          @for (case of cases; track case.id) {
            <mat-option [value]="case.id">{{ case.title }}</mat-option>
          }
        </mat-select>
      </mat-form-field>

      <div class="checklist">
        <h4>Pre-Release Checklist</h4>
        <label class="checkbox-item">
          <input type="checkbox" [(ngModel)]="checks.malwareRemoved">
          <span>Malware/threats have been removed</span>
        </label>
        <label class="checkbox-item">
          <input type="checkbox" [(ngModel)]="checks.credentialsReset">
          <span>Compromised credentials have been reset</span>
        </label>
        <label class="checkbox-item">
          <input type="checkbox" [(ngModel)]="checks.patched">
          <span>Vulnerabilities have been patched</span>
        </label>
        <label class="checkbox-item">
          <input type="checkbox" [(ngModel)]="checks.monitored">
          <span>Additional monitoring is in place</span>
        </label>
      </div>
    </mat-dialog-content>

    <mat-dialog-actions align="end">
      <button mat-button mat-dialog-close>Cancel</button>
      <button mat-flat-button
              color="primary"
              [disabled]="reason.length < 10 || !allChecked"
              (click)="confirm()">
        <mat-icon>lock_open</mat-icon>
        Release Host
      </button>
    </mat-dialog-actions>
  `,
  styles: [`
    .success-icon {
      color: var(--success);
      vertical-align: middle;
      margin-right: 8px;
    }

    .info-banner {
      display: flex;
      gap: 12px;
      background: rgba(var(--info-rgb), 0.15);
      border: 1px solid var(--info);
      border-radius: 8px;
      padding: 16px;
      margin-bottom: 24px;

      mat-icon {
        color: var(--info);
        flex-shrink: 0;
      }

      p {
        margin: 0;
        font-size: 14px;
      }
    }

    .endpoint-info {
      background: var(--bg-secondary);
      border-radius: 8px;
      padding: 16px;
      margin-bottom: 24px;
    }

    .info-row {
      display: flex;
      gap: 12px;
      padding: 8px 0;
      border-bottom: 1px solid var(--border-color);

      &:last-child {
        border-bottom: none;
      }
    }

    .label {
      color: var(--text-secondary);
      min-width: 120px;
    }

    .value {
      font-weight: 500;

      &.monospace {
        font-family: monospace;
        font-size: 12px;
      }
    }

    .full-width {
      width: 100%;
      margin-bottom: 16px;
    }

    .checklist {
      background: var(--bg-secondary);
      border-radius: 8px;
      padding: 16px;
      margin-bottom: 16px;

      h4 {
        margin: 0 0 12px;
        font-size: 14px;
      }
    }

    .checkbox-item {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 8px 0;
      cursor: pointer;

      input[type="checkbox"] {
        width: 18px;
        height: 18px;
        cursor: pointer;
      }

      span {
        font-size: 14px;
      }
    }

    mat-dialog-actions {
      padding: 16px 24px;
    }
  `]
})
export class ReleaseDialogComponent {
  reason = '';
  selectedCaseId: string | null = null;
  cases: { id: string; title: string }[] = [];

  checks = {
    malwareRemoved: false,
    credentialsReset: false,
    patched: false,
    monitored: false
  };

  constructor(
    public dialogRef: MatDialogRef<ReleaseDialogComponent, DialogResult>,
    @Inject(MAT_DIALOG_DATA) public data: DialogData,
    private caseService: CaseService
  ) {
    this.loadCases();
  }

  get allChecked(): boolean {
    return Object.values(this.checks).every(v => v);
  }

  private loadCases(): void {
    this.caseService.list({ status: 'open', limit: 50 }).subscribe({
      next: (response) => {
        this.cases = response.items.map(c => ({ id: c.id, title: c.title }));
      }
    });
  }

  confirm(): void {
    if (this.reason.length < 10 || !this.allChecked) return;

    this.dialogRef.close({
      reason: this.reason,
      caseId: this.selectedCaseId || undefined
    });
  }
}
