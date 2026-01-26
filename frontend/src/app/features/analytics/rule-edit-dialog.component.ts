import { Component, Inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, FormGroup, Validators, ReactiveFormsModule } from '@angular/forms';
import { MAT_DIALOG_DATA, MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatChipsModule } from '@angular/material/chips';
import { MatChipInputEvent } from '@angular/material/chips';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSlideToggleModule } from '@angular/material/slide-toggle';
import { MatTooltipModule } from '@angular/material/tooltip';
import { COMMA, ENTER } from '@angular/cdk/keycodes';
import { AnalyticsService, DetectionRule, RuleCreate } from '../../core/api/analytics.service';
import { AnalyticsRule } from './analytics.component';

export interface RuleEditDialogData {
  rule?: AnalyticsRule;
  mode: 'create' | 'edit' | 'duplicate';
}

@Component({
  selector: 'app-rule-edit-dialog',
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
    MatProgressSpinnerModule,
    MatSlideToggleModule,
    MatTooltipModule
  ],
  template: `
    <h2 mat-dialog-title>{{ dialogTitle }}</h2>
    <form [formGroup]="form" (ngSubmit)="onSubmit()">
      <mat-dialog-content>
        <mat-form-field appearance="outline" class="full-width">
          <mat-label>Rule Name</mat-label>
          <input matInput formControlName="name" placeholder="Enter rule name">
          @if (form.get('name')?.hasError('required') && form.get('name')?.touched) {
            <mat-error>Name is required</mat-error>
          }
        </mat-form-field>

        <mat-form-field appearance="outline" class="full-width">
          <mat-label>Description</mat-label>
          <textarea matInput formControlName="description" rows="3"
                    placeholder="Rule description"></textarea>
        </mat-form-field>

        <div class="form-row">
          <mat-form-field appearance="outline">
            <mat-label>Severity</mat-label>
            <mat-select formControlName="severity">
              <mat-option value="critical">Critical</mat-option>
              <mat-option value="high">High</mat-option>
              <mat-option value="medium">Medium</mat-option>
              <mat-option value="low">Low</mat-option>
              <mat-option value="informational">Informational</mat-option>
            </mat-select>
          </mat-form-field>

          <mat-form-field appearance="outline">
            <mat-label>Rule Type</mat-label>
            <mat-select formControlName="rule_type">
              <mat-option value="scheduled">Scheduled</mat-option>
              <mat-option value="realtime">Real-time</mat-option>
              <mat-option value="threshold">Threshold</mat-option>
              <mat-option value="correlation">Correlation</mat-option>
            </mat-select>
          </mat-form-field>
        </div>

        <div class="form-row">
          <mat-form-field appearance="outline">
            <mat-label>Query Language</mat-label>
            <mat-select formControlName="query_language">
              <mat-option value="esql">ES|QL</mat-option>
              <mat-option value="kql">KQL</mat-option>
              <mat-option value="lucene">Lucene</mat-option>
              <mat-option value="sigma">Sigma</mat-option>
            </mat-select>
          </mat-form-field>

          <mat-form-field appearance="outline">
            <mat-label>Category</mat-label>
            <mat-select formControlName="category">
              <mat-option value="sigma">Sigma</mat-option>
              <mat-option value="elastic">Elastic</mat-option>
              <mat-option value="custom">Custom</mat-option>
            </mat-select>
          </mat-form-field>
        </div>

        <mat-form-field appearance="outline" class="full-width">
          <mat-label>Query</mat-label>
          <textarea matInput formControlName="query" rows="5"
                    placeholder="Enter detection query" class="query-input"></textarea>
          @if (form.get('query')?.hasError('required') && form.get('query')?.touched) {
            <mat-error>Query is required</mat-error>
          }
        </mat-form-field>

        <div class="form-row">
          <mat-form-field appearance="outline">
            <mat-label>Schedule Interval (minutes)</mat-label>
            <input matInput type="number" formControlName="schedule_interval"
                   placeholder="e.g., 5">
          </mat-form-field>

          <mat-form-field appearance="outline">
            <mat-label>Lookback Period (minutes)</mat-label>
            <input matInput type="number" formControlName="lookback_period"
                   placeholder="e.g., 15">
          </mat-form-field>
        </div>

        <mat-form-field appearance="outline" class="full-width">
          <mat-label>MITRE Tactics</mat-label>
          <mat-chip-grid #tacticsGrid>
            @for (tactic of mitreTactics; track tactic) {
              <mat-chip-row (removed)="removeTactic(tactic)">
                {{ tactic }}
                <button matChipRemove>
                  <mat-icon>cancel</mat-icon>
                </button>
              </mat-chip-row>
            }
          </mat-chip-grid>
          <input placeholder="Add tactic..."
                 [matChipInputFor]="tacticsGrid"
                 [matChipInputSeparatorKeyCodes]="separatorKeyCodes"
                 (matChipInputTokenEnd)="addTactic($event)">
        </mat-form-field>

        <mat-form-field appearance="outline" class="full-width">
          <mat-label>MITRE Techniques</mat-label>
          <mat-chip-grid #techniquesGrid>
            @for (technique of mitreTechniques; track technique) {
              <mat-chip-row (removed)="removeTechnique(technique)">
                {{ technique }}
                <button matChipRemove>
                  <mat-icon>cancel</mat-icon>
                </button>
              </mat-chip-row>
            }
          </mat-chip-grid>
          <input placeholder="Add technique (e.g., T1059.001)..."
                 [matChipInputFor]="techniquesGrid"
                 [matChipInputSeparatorKeyCodes]="separatorKeyCodes"
                 (matChipInputTokenEnd)="addTechnique($event)">
        </mat-form-field>

        <mat-form-field appearance="outline" class="full-width">
          <mat-label>Tags</mat-label>
          <mat-chip-grid #tagsGrid>
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
                 [matChipInputFor]="tagsGrid"
                 [matChipInputSeparatorKeyCodes]="separatorKeyCodes"
                 (matChipInputTokenEnd)="addTag($event)">
        </mat-form-field>

        <div class="toggle-row">
          <mat-slide-toggle formControlName="auto_create_incident" color="primary">
            Auto-create incident on match
          </mat-slide-toggle>
        </div>

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
            {{ submitButtonText }}
          }
        </button>
      </mat-dialog-actions>
    </form>
  `,
  styles: [`
    mat-dialog-content {
      min-width: 550px;
      max-width: 650px;
      max-height: 70vh;
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

    .query-input {
      font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
      font-size: 13px;
    }

    .toggle-row {
      margin: 16px 0;
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
export class RuleEditDialogComponent implements OnInit {
  form: FormGroup;
  mitreTactics: string[] = [];
  mitreTechniques: string[] = [];
  tags: string[] = [];
  separatorKeyCodes = [ENTER, COMMA];
  isSubmitting = false;
  errorMessage = '';

  get dialogTitle(): string {
    switch (this.data.mode) {
      case 'create': return 'Create Detection Rule';
      case 'edit': return 'Edit Detection Rule';
      case 'duplicate': return 'Duplicate Detection Rule';
    }
  }

  get submitButtonText(): string {
    switch (this.data.mode) {
      case 'create': return 'Create Rule';
      case 'edit': return 'Save Changes';
      case 'duplicate': return 'Create Copy';
    }
  }

  constructor(
    private fb: FormBuilder,
    @Inject(MAT_DIALOG_DATA) public data: RuleEditDialogData,
    private dialogRef: MatDialogRef<RuleEditDialogComponent>,
    private analyticsService: AnalyticsService
  ) {
    this.form = this.fb.group({
      name: ['', Validators.required],
      description: [''],
      severity: ['medium'],
      rule_type: ['scheduled'],
      query: ['', Validators.required],
      query_language: ['esql'],
      category: ['custom'],
      schedule_interval: [5],
      lookback_period: [15],
      auto_create_incident: [false]
    });
  }

  ngOnInit(): void {
    if (this.data.rule) {
      const rule = this.data.rule;
      this.form.patchValue({
        name: this.data.mode === 'duplicate' ? `${rule.name} (Copy)` : rule.name,
        description: rule.description,
        severity: rule.severity,
        category: rule.source
      });
      this.mitreTactics = [...rule.tactics];
      this.mitreTechniques = [...rule.techniques];

      // For edit mode, we need to fetch full rule details including query
      if (this.data.mode === 'edit' || this.data.mode === 'duplicate') {
        this.analyticsService.getRule(rule.id).subscribe({
          next: (fullRule) => {
            this.form.patchValue({
              query: fullRule.query,
              query_language: fullRule.query_language,
              rule_type: fullRule.rule_type,
              schedule_interval: fullRule.schedule_interval,
              lookback_period: fullRule.lookback_period,
              auto_create_incident: fullRule.auto_create_incident
            });
            this.tags = [...fullRule.tags];
          },
          error: (err) => {
            console.error('Failed to load full rule details:', err);
          }
        });
      }
    }
  }

  addTactic(event: MatChipInputEvent): void {
    const value = (event.value || '').trim();
    if (value && !this.mitreTactics.includes(value)) {
      this.mitreTactics.push(value);
    }
    event.chipInput.clear();
  }

  removeTactic(tactic: string): void {
    const index = this.mitreTactics.indexOf(tactic);
    if (index >= 0) this.mitreTactics.splice(index, 1);
  }

  addTechnique(event: MatChipInputEvent): void {
    const value = (event.value || '').trim().toUpperCase();
    if (value && !this.mitreTechniques.includes(value)) {
      this.mitreTechniques.push(value);
    }
    event.chipInput.clear();
  }

  removeTechnique(technique: string): void {
    const index = this.mitreTechniques.indexOf(technique);
    if (index >= 0) this.mitreTechniques.splice(index, 1);
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
    if (index >= 0) this.tags.splice(index, 1);
  }

  onSubmit(): void {
    if (!this.form.valid) return;

    this.isSubmitting = true;
    this.errorMessage = '';

    const ruleData: RuleCreate = {
      ...this.form.value,
      mitre_tactics: this.mitreTactics,
      mitre_techniques: this.mitreTechniques,
      tags: this.tags
    };

    const request = this.data.mode === 'edit' && this.data.rule
      ? this.analyticsService.updateRule(this.data.rule.id, ruleData)
      : this.analyticsService.createRule(ruleData);

    request.subscribe({
      next: (savedRule) => {
        this.dialogRef.close(savedRule);
      },
      error: (error) => {
        this.isSubmitting = false;
        this.errorMessage = error.error?.detail || `Failed to ${this.data.mode} rule`;
      }
    });
  }

  onCancel(): void {
    this.dialogRef.close();
  }
}
