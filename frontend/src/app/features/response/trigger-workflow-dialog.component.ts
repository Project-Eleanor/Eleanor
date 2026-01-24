import { Component, Inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, FormGroup, ReactiveFormsModule } from '@angular/forms';
import { MAT_DIALOG_DATA, MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatButtonModule } from '@angular/material/button';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { WorkflowService } from '../../core/api/workflow.service';
import { Workflow } from '../../shared/models';

@Component({
  selector: 'app-trigger-workflow-dialog',
  standalone: true,
  imports: [
    CommonModule,
    ReactiveFormsModule,
    MatDialogModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    MatButtonModule,
    MatProgressSpinnerModule
  ],
  template: `
    <h2 mat-dialog-title>Run {{ data.workflow.name }}</h2>
    <form [formGroup]="form" (ngSubmit)="onSubmit()">
      <mat-dialog-content>
        @if (data.workflow.description) {
          <p class="description">{{ data.workflow.description }}</p>
        }

        @if (data.workflow.requires_approval) {
          <div class="approval-notice">
            <strong>Note:</strong> This workflow requires approval before execution.
          </div>
        }

        @if (data.workflow.parameters.length > 0) {
          <div class="parameters">
            @for (param of data.workflow.parameters; track param.name) {
              <mat-form-field appearance="outline" class="full-width">
                <mat-label>{{ param.name }}</mat-label>
                @if (param.type === 'select' && param.options) {
                  <mat-select [formControlName]="param.name">
                    @for (option of param.options; track option) {
                      <mat-option [value]="option">{{ option }}</mat-option>
                    }
                  </mat-select>
                } @else {
                  <input matInput [formControlName]="param.name"
                         [type]="param.type === 'number' ? 'number' : 'text'">
                }
                @if (param.description) {
                  <mat-hint>{{ param.description }}</mat-hint>
                }
              </mat-form-field>
            }
          </div>
        } @else {
          <p class="no-params">This workflow has no parameters.</p>
        }
      </mat-dialog-content>

      <mat-dialog-actions align="end">
        <button mat-button type="button" (click)="onCancel()">Cancel</button>
        <button mat-flat-button color="accent" type="submit"
                [disabled]="isSubmitting">
          @if (isSubmitting) {
            <mat-spinner diameter="20"></mat-spinner>
          } @else {
            Run Workflow
          }
        </button>
      </mat-dialog-actions>
    </form>
  `,
  styles: [`
    mat-dialog-content {
      min-width: 400px;
    }

    .description {
      color: var(--text-secondary);
      margin-bottom: 16px;
    }

    .approval-notice {
      background: rgba(251, 191, 36, 0.1);
      border: 1px solid var(--warning);
      border-radius: 8px;
      padding: 12px;
      margin-bottom: 16px;
      font-size: 13px;
    }

    .parameters {
      display: flex;
      flex-direction: column;
      gap: 8px;
    }

    .full-width {
      width: 100%;
    }

    .no-params {
      color: var(--text-muted);
      font-style: italic;
    }
  `]
})
export class TriggerWorkflowDialogComponent {
  form: FormGroup;
  isSubmitting = false;

  constructor(
    private fb: FormBuilder,
    private dialogRef: MatDialogRef<TriggerWorkflowDialogComponent>,
    private workflowService: WorkflowService,
    @Inject(MAT_DIALOG_DATA) public data: { workflow: Workflow }
  ) {
    const controls: Record<string, unknown> = {};
    for (const param of data.workflow.parameters) {
      controls[param.name] = [param.default_value || ''];
    }
    this.form = this.fb.group(controls);
  }

  onSubmit(): void {
    this.isSubmitting = true;

    this.workflowService.trigger(this.data.workflow.id, this.form.value).subscribe({
      next: (execution) => {
        this.dialogRef.close(execution);
      },
      error: () => {
        this.isSubmitting = false;
      }
    });
  }

  onCancel(): void {
    this.dialogRef.close();
  }
}
