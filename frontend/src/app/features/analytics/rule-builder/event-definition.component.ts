import { Component, Input, Output, EventEmitter } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatExpansionModule } from '@angular/material/expansion';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatChipsModule } from '@angular/material/chips';
import { AvailableField } from './rule-builder.service';

interface FieldCondition {
  field: string;
  operator: string;
  value: any;
  negate?: boolean;
}

interface EventDefinition {
  id: string;
  name: string;
  description?: string;
  conditions: FieldCondition[];
  raw_query?: string;
}

@Component({
  selector: 'app-event-definition',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatCardModule,
    MatButtonModule,
    MatIconModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    MatExpansionModule,
    MatTooltipModule,
    MatChipsModule
  ],
  template: `
    <mat-expansion-panel class="event-panel" [expanded]="expanded">
      <mat-expansion-panel-header>
        <mat-panel-title>
          <div class="event-header">
            <span class="event-badge">E{{ index + 1 }}</span>
            <span class="event-name">{{ event.name || event.id }}</span>
            <mat-chip *ngIf="event.conditions.length > 0" class="condition-count">
              {{ event.conditions.length }} conditions
            </mat-chip>
          </div>
        </mat-panel-title>
        <mat-panel-description>
          {{ event.description || 'No description' }}
        </mat-panel-description>
      </mat-expansion-panel-header>

      <div class="event-content">
        <!-- Basic Info -->
        <div class="basic-info">
          <mat-form-field appearance="outline">
            <mat-label>Event ID</mat-label>
            <input matInput [(ngModel)]="event.id" (ngModelChange)="emitChange()" placeholder="e.g., failed_login">
            <mat-hint>Unique identifier for this event type</mat-hint>
          </mat-form-field>
          <mat-form-field appearance="outline">
            <mat-label>Display Name</mat-label>
            <input matInput [(ngModel)]="event.name" (ngModelChange)="emitChange()" placeholder="e.g., Failed Login Attempt">
          </mat-form-field>
        </div>

        <!-- Conditions -->
        <div class="conditions-section">
          <h4>
            Conditions
            <button mat-icon-button (click)="addCondition()" matTooltip="Add condition">
              <mat-icon>add</mat-icon>
            </button>
          </h4>

          @for (condition of event.conditions; track $index; let i = $index) {
            <div class="condition-row">
              <mat-form-field appearance="outline" class="field-select">
                <mat-label>Field</mat-label>
                <mat-select [(ngModel)]="condition.field" (ngModelChange)="emitChange()">
                  @for (field of fields; track field.path) {
                    <mat-option [value]="field.path">{{ field.path }}</mat-option>
                  }
                </mat-select>
              </mat-form-field>

              <mat-form-field appearance="outline" class="operator-select">
                <mat-label>Operator</mat-label>
                <mat-select [(ngModel)]="condition.operator" (ngModelChange)="emitChange()">
                  <mat-option value="eq">equals</mat-option>
                  <mat-option value="neq">not equals</mat-option>
                  <mat-option value="contains">contains</mat-option>
                  <mat-option value="starts_with">starts with</mat-option>
                  <mat-option value="ends_with">ends with</mat-option>
                  <mat-option value="gt">greater than</mat-option>
                  <mat-option value="gte">greater or equal</mat-option>
                  <mat-option value="lt">less than</mat-option>
                  <mat-option value="lte">less or equal</mat-option>
                  <mat-option value="exists">exists</mat-option>
                  <mat-option value="not_exists">not exists</mat-option>
                  <mat-option value="regex">matches regex</mat-option>
                  <mat-option value="in">in list</mat-option>
                </mat-select>
              </mat-form-field>

              <mat-form-field appearance="outline" class="value-input"
                             *ngIf="!['exists', 'not_exists'].includes(condition.operator)">
                <mat-label>Value</mat-label>
                <input matInput [(ngModel)]="condition.value" (ngModelChange)="emitChange()"
                       placeholder="Value to match">
              </mat-form-field>

              <button mat-icon-button (click)="removeCondition(i)" matTooltip="Remove condition">
                <mat-icon>delete</mat-icon>
              </button>
            </div>
          }

          @if (event.conditions.length === 0) {
            <div class="no-conditions">
              <p>No conditions defined. Add conditions or use a raw query.</p>
            </div>
          }
        </div>

        <!-- Raw Query (Advanced) -->
        <mat-expansion-panel class="advanced-panel">
          <mat-expansion-panel-header>
            <mat-panel-title>Advanced: Raw Query</mat-panel-title>
          </mat-expansion-panel-header>
          <mat-form-field appearance="outline" class="full-width">
            <mat-label>Raw KQL/Lucene Query</mat-label>
            <textarea matInput [(ngModel)]="event.raw_query" (ngModelChange)="emitChange()"
                      rows="3" placeholder="event.action:logon_failed AND user.name:*"></textarea>
            <mat-hint>Overrides conditions if specified</mat-hint>
          </mat-form-field>
        </mat-expansion-panel>

        <!-- Actions -->
        <div class="event-actions">
          <button mat-stroked-button color="warn" (click)="remove()">
            <mat-icon>delete</mat-icon>
            Remove Event
          </button>
        </div>
      </div>
    </mat-expansion-panel>
  `,
  styles: [`
    .event-panel {
      margin-bottom: 8px;
    }

    .event-header {
      display: flex;
      align-items: center;
      gap: 12px;
    }

    .event-badge {
      width: 28px;
      height: 28px;
      background: var(--primary-color);
      color: white;
      border-radius: 6px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 12px;
      font-weight: 600;
    }

    .event-name {
      font-weight: 500;
    }

    .condition-count {
      font-size: 11px;
    }

    .event-content {
      padding-top: 16px;
    }

    .basic-info {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 16px;
      margin-bottom: 24px;
    }

    .conditions-section h4 {
      display: flex;
      align-items: center;
      gap: 8px;
      margin: 0 0 16px;
    }

    .condition-row {
      display: flex;
      gap: 12px;
      align-items: flex-start;
      margin-bottom: 12px;
    }

    .field-select {
      flex: 2;
    }

    .operator-select {
      flex: 1;
      min-width: 140px;
    }

    .value-input {
      flex: 2;
    }

    .no-conditions {
      padding: 24px;
      text-align: center;
      background: var(--hover-bg);
      border-radius: 8px;
      color: var(--text-secondary);
    }

    .advanced-panel {
      margin-top: 16px;
    }

    .full-width {
      width: 100%;
    }

    .event-actions {
      margin-top: 16px;
      padding-top: 16px;
      border-top: 1px solid var(--border-color);
    }

    @media (max-width: 768px) {
      .basic-info {
        grid-template-columns: 1fr;
      }
      .condition-row {
        flex-wrap: wrap;
      }
      .field-select, .operator-select, .value-input {
        flex: 100%;
      }
    }
  `]
})
export class EventDefinitionComponent {
  @Input() event!: EventDefinition;
  @Input() index = 0;
  @Input() fields: AvailableField[] = [];
  @Output() eventChanged = new EventEmitter<EventDefinition>();
  @Output() eventRemoved = new EventEmitter<void>();

  expanded = true;

  addCondition() {
    this.event.conditions = [...this.event.conditions, {
      field: '',
      operator: 'eq',
      value: ''
    }];
    this.emitChange();
  }

  removeCondition(index: number) {
    this.event.conditions = this.event.conditions.filter((_, i) => i !== index);
    this.emitChange();
  }

  emitChange() {
    this.eventChanged.emit({ ...this.event });
  }

  remove() {
    this.eventRemoved.emit();
  }
}
