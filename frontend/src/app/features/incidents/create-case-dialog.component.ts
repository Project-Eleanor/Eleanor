import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, FormGroup, Validators, ReactiveFormsModule } from '@angular/forms';
import { MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatChipsModule } from '@angular/material/chips';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { COMMA, ENTER } from '@angular/cdk/keycodes';
import { MatChipInputEvent } from '@angular/material/chips';
import { CaseService } from '../../core/api/case.service';

@Component({
  selector: 'app-create-case-dialog',
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
    MatChipsModule,
    MatProgressSpinnerModule
  ],
  template: `
    <h2 mat-dialog-title>Create New Case</h2>
    <form [formGroup]="form" (ngSubmit)="onSubmit()">
      <mat-dialog-content>
        <mat-form-field appearance="outline" class="full-width">
          <mat-label>Title</mat-label>
          <input matInput formControlName="title" placeholder="Case title">
          @if (form.get('title')?.hasError('required') && form.get('title')?.touched) {
            <mat-error>Title is required</mat-error>
          }
        </mat-form-field>

        <mat-form-field appearance="outline" class="full-width">
          <mat-label>Description</mat-label>
          <textarea matInput formControlName="description" rows="4"
                    placeholder="Case description"></textarea>
        </mat-form-field>

        <div class="form-row">
          <mat-form-field appearance="outline">
            <mat-label>Severity</mat-label>
            <mat-select formControlName="severity">
              <mat-option value="critical">Critical</mat-option>
              <mat-option value="high">High</mat-option>
              <mat-option value="medium">Medium</mat-option>
              <mat-option value="low">Low</mat-option>
              <mat-option value="info">Info</mat-option>
            </mat-select>
          </mat-form-field>

          <mat-form-field appearance="outline">
            <mat-label>Priority</mat-label>
            <mat-select formControlName="priority">
              <mat-option value="P1">P1 - Immediate</mat-option>
              <mat-option value="P2">P2 - High</mat-option>
              <mat-option value="P3">P3 - Medium</mat-option>
              <mat-option value="P4">P4 - Low</mat-option>
              <mat-option value="P5">P5 - Scheduled</mat-option>
            </mat-select>
          </mat-form-field>
        </div>

        <mat-form-field appearance="outline" class="full-width">
          <mat-label>Tags</mat-label>
          <mat-chip-grid #chipGrid>
            @for (tag of tags; track tag) {
              <mat-chip-row (removed)="removeTag(tag)">
                {{ tag }}
                <button matChipRemove>
                  <mat-icon>cancel</mat-icon>
                </button>
              </mat-chip-row>
            }
          </mat-chip-grid>
          <input placeholder="Add tag..."
                 [matChipInputFor]="chipGrid"
                 [matChipInputSeparatorKeyCodes]="separatorKeyCodes"
                 (matChipInputTokenEnd)="addTag($event)">
        </mat-form-field>

        @if (errorMessage) {
          <div class="error-message">
            <mat-icon>error</mat-icon>
            {{ errorMessage }}
          </div>
        }
      </mat-dialog-content>

      <mat-dialog-actions align="end">
        <button mat-button type="button" (click)="onCancel()">Cancel</button>
        <button mat-flat-button color="accent" type="submit"
                [disabled]="!form.valid || isSubmitting">
          @if (isSubmitting) {
            <mat-spinner diameter="20"></mat-spinner>
          } @else {
            Create Case
          }
        </button>
      </mat-dialog-actions>
    </form>
  `,
  styles: [`
    mat-dialog-content {
      min-width: 500px;
    }

    .full-width {
      width: 100%;
      margin-bottom: 8px;
    }

    .form-row {
      display: flex;
      gap: 16px;

      mat-form-field {
        flex: 1;
      }
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
export class CreateCaseDialogComponent {
  form: FormGroup;
  tags: string[] = [];
  separatorKeyCodes = [ENTER, COMMA];
  isSubmitting = false;
  errorMessage = '';

  constructor(
    private fb: FormBuilder,
    private dialogRef: MatDialogRef<CreateCaseDialogComponent>,
    private caseService: CaseService
  ) {
    this.form = this.fb.group({
      title: ['', Validators.required],
      description: [''],
      severity: ['medium'],
      priority: ['P3']
    });
  }

  addTag(event: MatChipInputEvent): void {
    const value = (event.value || '').trim();
    if (value && !this.tags.includes(value)) {
      this.tags.push(value);
    }
    event.chipInput.clear();
  }

  removeTag(tag: string): void {
    const index = this.tags.indexOf(tag);
    if (index >= 0) {
      this.tags.splice(index, 1);
    }
  }

  onSubmit(): void {
    if (!this.form.valid) return;

    this.isSubmitting = true;
    this.errorMessage = '';

    const data = {
      ...this.form.value,
      tags: this.tags
    };

    this.caseService.create(data).subscribe({
      next: (createdCase) => {
        this.dialogRef.close(createdCase);
      },
      error: (error) => {
        this.isSubmitting = false;
        this.errorMessage = error.error?.detail || 'Failed to create case';
      }
    });
  }

  onCancel(): void {
    this.dialogRef.close();
  }
}
