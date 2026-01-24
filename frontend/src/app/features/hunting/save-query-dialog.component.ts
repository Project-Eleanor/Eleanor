import { Component, Inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, FormGroup, Validators, ReactiveFormsModule } from '@angular/forms';
import { MAT_DIALOG_DATA, MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatButtonModule } from '@angular/material/button';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { SearchService } from '../../core/api/search.service';

@Component({
  selector: 'app-save-query-dialog',
  standalone: true,
  imports: [
    CommonModule,
    ReactiveFormsModule,
    MatDialogModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    MatButtonModule,
    MatCheckboxModule,
    MatProgressSpinnerModule
  ],
  template: `
    <h2 mat-dialog-title>Save Query</h2>
    <form [formGroup]="form" (ngSubmit)="onSubmit()">
      <mat-dialog-content>
        <mat-form-field appearance="outline" class="full-width">
          <mat-label>Name</mat-label>
          <input matInput formControlName="name" placeholder="Query name">
          @if (form.get('name')?.hasError('required') && form.get('name')?.touched) {
            <mat-error>Name is required</mat-error>
          }
        </mat-form-field>

        <mat-form-field appearance="outline" class="full-width">
          <mat-label>Description</mat-label>
          <textarea matInput formControlName="description" rows="2"
                    placeholder="Optional description"></textarea>
        </mat-form-field>

        <mat-form-field appearance="outline" class="full-width">
          <mat-label>Query Type</mat-label>
          <mat-select formControlName="query_type">
            <mat-option value="esql">ES|QL</mat-option>
            <mat-option value="kql">KQL</mat-option>
            <mat-option value="lucene">Lucene</mat-option>
          </mat-select>
        </mat-form-field>

        <mat-form-field appearance="outline" class="full-width">
          <mat-label>Query</mat-label>
          <textarea matInput formControlName="query" rows="4" readonly
                    class="code-font"></textarea>
        </mat-form-field>

        <mat-checkbox formControlName="is_public">
          Make this query public (visible to all users)
        </mat-checkbox>
      </mat-dialog-content>

      <mat-dialog-actions align="end">
        <button mat-button type="button" (click)="onCancel()">Cancel</button>
        <button mat-flat-button color="accent" type="submit"
                [disabled]="!form.valid || isSubmitting">
          @if (isSubmitting) {
            <mat-spinner diameter="20"></mat-spinner>
          } @else {
            Save
          }
        </button>
      </mat-dialog-actions>
    </form>
  `,
  styles: [`
    mat-dialog-content {
      min-width: 400px;
    }

    .full-width {
      width: 100%;
      margin-bottom: 8px;
    }

    .code-font {
      font-family: monospace;
      font-size: 12px;
    }

    mat-checkbox {
      margin-top: 8px;
    }
  `]
})
export class SaveQueryDialogComponent {
  form: FormGroup;
  isSubmitting = false;

  constructor(
    private fb: FormBuilder,
    private dialogRef: MatDialogRef<SaveQueryDialogComponent>,
    private searchService: SearchService,
    @Inject(MAT_DIALOG_DATA) public data: { query: string }
  ) {
    this.form = this.fb.group({
      name: ['', Validators.required],
      description: [''],
      query: [data.query, Validators.required],
      query_type: ['esql'],
      is_public: [false]
    });
  }

  onSubmit(): void {
    if (!this.form.valid) return;

    this.isSubmitting = true;

    this.searchService.createSavedQuery(this.form.value).subscribe({
      next: (saved) => {
        this.dialogRef.close(saved);
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
