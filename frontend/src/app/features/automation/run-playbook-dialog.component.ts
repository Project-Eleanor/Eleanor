import { Component, Inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, FormGroup, Validators, ReactiveFormsModule } from '@angular/forms';
import { MAT_DIALOG_DATA, MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatTooltipModule } from '@angular/material/tooltip';
import { Workflow, WorkflowParameter } from '../../shared/models';
import { WorkflowService } from '../../core/api/workflow.service';

@Component({
  selector: 'app-run-playbook-dialog',
  standalone: true,
  imports: [
    CommonModule,
    ReactiveFormsModule,
    MatDialogModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    MatButtonModule,
    MatIconModule,
    MatCheckboxModule,
    MatProgressSpinnerModule,
    MatTooltipModule
  ],
  template: `
    <div class="dialog-header">
      <mat-icon class="playbook-icon" [class]="'category-' + data.category">
        {{ getCategoryIcon(data.category) }}
      </mat-icon>
      <div class="header-text">
        <h2 mat-dialog-title>Run {{ data.name }}</h2>
        @if (data.requires_approval) {
          <div class="approval-notice">
            <mat-icon>gavel</mat-icon>
            This playbook requires approval before execution
          </div>
        }
      </div>
    </div>

    <form [formGroup]="form" (ngSubmit)="onSubmit()">
      <mat-dialog-content>
        @if (data.parameters.length === 0) {
          <div class="no-params">
            <mat-icon>check_circle</mat-icon>
            <p>This playbook has no configurable parameters.</p>
            <span>Click "Run" to execute immediately.</span>
          </div>
        } @else {
          <div class="params-section">
            <h4>Parameters</h4>
            @for (param of data.parameters; track param.name) {
              <div class="param-field">
                @switch (param.type) {
                  @case ('string') {
                    <mat-form-field appearance="outline" class="full-width">
                      <mat-label>{{ param.name }}</mat-label>
                      <input matInput [formControlName]="param.name"
                             [placeholder]="param.description || ''">
                      @if (param.description) {
                        <mat-hint>{{ param.description }}</mat-hint>
                      }
                      @if (form.get(param.name)?.hasError('required')) {
                        <mat-error>{{ param.name }} is required</mat-error>
                      }
                    </mat-form-field>
                  }
                  @case ('number') {
                    <mat-form-field appearance="outline" class="full-width">
                      <mat-label>{{ param.name }}</mat-label>
                      <input matInput type="number" [formControlName]="param.name"
                             [placeholder]="param.description || ''">
                      @if (param.description) {
                        <mat-hint>{{ param.description }}</mat-hint>
                      }
                      @if (form.get(param.name)?.hasError('required')) {
                        <mat-error>{{ param.name }} is required</mat-error>
                      }
                    </mat-form-field>
                  }
                  @case ('boolean') {
                    <div class="checkbox-field">
                      <mat-checkbox [formControlName]="param.name" color="primary">
                        {{ param.name }}
                      </mat-checkbox>
                      @if (param.description) {
                        <span class="checkbox-hint">{{ param.description }}</span>
                      }
                    </div>
                  }
                  @case ('select') {
                    <mat-form-field appearance="outline" class="full-width">
                      <mat-label>{{ param.name }}</mat-label>
                      <mat-select [formControlName]="param.name">
                        @for (option of param.options; track option) {
                          <mat-option [value]="option">{{ option }}</mat-option>
                        }
                      </mat-select>
                      @if (param.description) {
                        <mat-hint>{{ param.description }}</mat-hint>
                      }
                      @if (form.get(param.name)?.hasError('required')) {
                        <mat-error>{{ param.name }} is required</mat-error>
                      }
                    </mat-form-field>
                  }
                  @case ('entity') {
                    <mat-form-field appearance="outline" class="full-width">
                      <mat-label>{{ param.name }}</mat-label>
                      <input matInput [formControlName]="param.name"
                             [placeholder]="param.description || 'Enter entity (hostname, IP, username)'">
                      <mat-icon matSuffix matTooltip="Entity reference">
                        {{ getEntityIcon(param.name) }}
                      </mat-icon>
                      @if (param.description) {
                        <mat-hint>{{ param.description }}</mat-hint>
                      }
                      @if (form.get(param.name)?.hasError('required')) {
                        <mat-error>{{ param.name }} is required</mat-error>
                      }
                    </mat-form-field>
                  }
                  @default {
                    <mat-form-field appearance="outline" class="full-width">
                      <mat-label>{{ param.name }}</mat-label>
                      <input matInput [formControlName]="param.name"
                             [placeholder]="param.description || ''">
                      @if (param.description) {
                        <mat-hint>{{ param.description }}</mat-hint>
                      }
                    </mat-form-field>
                  }
                }
              </div>
            }
          </div>
        }

        @if (errorMessage) {
          <div class="error-message">
            <mat-icon>error</mat-icon>
            {{ errorMessage }}
          </div>
        }
      </mat-dialog-content>

      <mat-dialog-actions align="end">
        <button mat-button type="button" (click)="onCancel()">Cancel</button>
        <button mat-flat-button color="primary" type="submit"
                [disabled]="!form.valid || isSubmitting">
          @if (isSubmitting) {
            <mat-spinner diameter="20"></mat-spinner>
          } @else {
            <mat-icon>play_arrow</mat-icon>
            {{ data.requires_approval ? 'Submit for Approval' : 'Run' }}
          }
        </button>
      </mat-dialog-actions>
    </form>
  `,
  styles: [`
    .dialog-header {
      display: flex;
      gap: 16px;
      padding: 16px 24px 0;
    }

    .playbook-icon {
      font-size: 32px;
      width: 32px;
      height: 32px;
      padding: 8px;
      border-radius: 8px;
      background: var(--bg-tertiary);

      &.category-containment { color: var(--danger); }
      &.category-enrichment { color: var(--info); }
      &.category-notification { color: var(--warning); }
      &.category-remediation { color: var(--success); }
    }

    .header-text h2 {
      margin: 0;
      font-size: 20px;
      font-weight: 600;
    }

    .approval-notice {
      display: flex;
      align-items: center;
      gap: 6px;
      margin-top: 8px;
      padding: 6px 12px;
      border-radius: 6px;
      font-size: 12px;
      background: rgba(245, 158, 11, 0.15);
      color: var(--warning);

      mat-icon {
        font-size: 16px;
        width: 16px;
        height: 16px;
      }
    }

    mat-dialog-content {
      min-width: 450px;
      max-width: 550px;
    }

    .no-params {
      display: flex;
      flex-direction: column;
      align-items: center;
      padding: 32px;
      text-align: center;

      mat-icon {
        font-size: 48px;
        width: 48px;
        height: 48px;
        color: var(--success);
        margin-bottom: 12px;
      }

      p {
        margin: 0 0 4px 0;
        font-weight: 500;
        color: var(--text-primary);
      }

      span {
        color: var(--text-secondary);
        font-size: 14px;
      }
    }

    .params-section {
      h4 {
        font-size: 12px;
        font-weight: 600;
        color: var(--text-secondary);
        margin: 0 0 16px 0;
        text-transform: uppercase;
        letter-spacing: 0.5px;
      }
    }

    .param-field {
      margin-bottom: 8px;
    }

    .full-width {
      width: 100%;
    }

    .checkbox-field {
      display: flex;
      flex-direction: column;
      gap: 4px;
      padding: 8px 0;
    }

    .checkbox-hint {
      font-size: 12px;
      color: var(--text-secondary);
      margin-left: 32px;
    }

    .error-message {
      display: flex;
      align-items: center;
      gap: 8px;
      color: var(--danger);
      background: rgba(239, 68, 68, 0.1);
      padding: 12px;
      border-radius: 8px;
      margin-top: 16px;
    }
  `]
})
export class RunPlaybookDialogComponent implements OnInit {
  form: FormGroup;
  isSubmitting = false;
  errorMessage = '';

  constructor(
    private fb: FormBuilder,
    @Inject(MAT_DIALOG_DATA) public data: Workflow,
    private dialogRef: MatDialogRef<RunPlaybookDialogComponent>,
    private workflowService: WorkflowService
  ) {
    this.form = this.fb.group({});
  }

  ngOnInit(): void {
    // Build form dynamically based on parameters
    for (const param of this.data.parameters) {
      const validators = param.required ? [Validators.required] : [];
      const defaultValue = param.default_value ?? (param.type === 'boolean' ? false : '');
      this.form.addControl(param.name, this.fb.control(defaultValue, validators));
    }
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

  getEntityIcon(paramName: string): string {
    const name = paramName.toLowerCase();
    if (name.includes('host') || name.includes('machine')) return 'computer';
    if (name.includes('user')) return 'person';
    if (name.includes('ip')) return 'language';
    return 'label';
  }

  onSubmit(): void {
    if (!this.form.valid) return;

    this.isSubmitting = true;
    this.errorMessage = '';

    const parameters = this.form.value;

    this.workflowService.trigger(this.data.id, parameters).subscribe({
      next: (execution) => {
        this.dialogRef.close(execution);
      },
      error: (error) => {
        this.isSubmitting = false;
        this.errorMessage = error.error?.detail || 'Failed to trigger playbook';
      }
    });
  }

  onCancel(): void {
    this.dialogRef.close();
  }
}
