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
  };
}

interface DialogResult {
  reason: string;
  caseId?: string;
}

@Component({
  selector: 'app-isolate-dialog',
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
      <mat-icon class="warning-icon">warning</mat-icon>
      Isolate Host
    </h2>

    <mat-dialog-content>
      <div class="warning-banner">
        <mat-icon>info</mat-icon>
        <p>
          This will disconnect <strong>{{ data.endpoint.hostname }}</strong> from all network
          communication except to the management server. The endpoint will remain manageable
          via Velociraptor.
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
        @if (data.endpoint.os) {
          <div class="info-row">
            <span class="label">OS:</span>
            <span class="value">{{ data.endpoint.os }}</span>
          </div>
        }
      </div>

      <mat-form-field appearance="outline" class="full-width">
        <mat-label>Reason for isolation (required)</mat-label>
        <textarea matInput
                  [(ngModel)]="reason"
                  rows="3"
                  placeholder="Enter the reason for isolating this host..."
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
    </mat-dialog-content>

    <mat-dialog-actions align="end">
      <button mat-button mat-dialog-close>Cancel</button>
      <button mat-flat-button
              color="warn"
              [disabled]="reason.length < 10"
              (click)="confirm()">
        <mat-icon>block</mat-icon>
        Isolate Host
      </button>
    </mat-dialog-actions>
  `,
  styles: [`
    .warning-icon {
      color: var(--warning);
      vertical-align: middle;
      margin-right: 8px;
    }

    .warning-banner {
      display: flex;
      gap: 12px;
      background: rgba(var(--warning-rgb), 0.15);
      border: 1px solid var(--warning);
      border-radius: 8px;
      padding: 16px;
      margin-bottom: 24px;

      mat-icon {
        color: var(--warning);
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
      min-width: 100px;
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

    mat-dialog-actions {
      padding: 16px 24px;
    }
  `]
})
export class IsolateDialogComponent {
  reason = '';
  selectedCaseId: string | null = null;
  cases: { id: string; title: string }[] = [];

  constructor(
    public dialogRef: MatDialogRef<IsolateDialogComponent, DialogResult>,
    @Inject(MAT_DIALOG_DATA) public data: DialogData,
    private caseService: CaseService
  ) {
    this.loadCases();
  }

  private loadCases(): void {
    this.caseService.list({ status: 'open', limit: 50 }).subscribe({
      next: (response) => {
        this.cases = response.items.map(c => ({ id: c.id, title: c.title }));
      }
    });
  }

  confirm(): void {
    if (this.reason.length < 10) return;

    this.dialogRef.close({
      reason: this.reason,
      caseId: this.selectedCaseId || undefined
    });
  }
}
