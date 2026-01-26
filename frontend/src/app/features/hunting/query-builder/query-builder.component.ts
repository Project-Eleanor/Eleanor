import { Component, EventEmitter, OnInit, Output, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatSelectModule } from '@angular/material/select';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatChipsModule } from '@angular/material/chips';
import { SearchService, IndexInfo, IndexSchema } from '../../../core/api/search.service';

export interface QueryCondition {
  field: string;
  operator: string;
  value: string;
  connector: 'AND' | 'OR';
}

@Component({
  selector: 'app-query-builder',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatFormFieldModule,
    MatSelectModule,
    MatInputModule,
    MatButtonModule,
    MatIconModule,
    MatTooltipModule,
    MatChipsModule
  ],
  template: `
    <div class="query-builder">
      <!-- Index Selection -->
      <div class="builder-section">
        <h4>Data Source</h4>
        <mat-form-field appearance="outline" class="full-width">
          <mat-label>Index Pattern</mat-label>
          <mat-select [(value)]="selectedIndex" (selectionChange)="onIndexChange()">
            <mat-option value="logs-*">logs-* (All logs)</mat-option>
            @for (index of indices(); track index.index) {
              <mat-option [value]="index.index">
                {{ index.index }}
                <span class="index-meta">{{ index.docs_count }} docs</span>
              </mat-option>
            }
          </mat-select>
        </mat-form-field>
      </div>

      <!-- Filter Conditions -->
      <div class="builder-section">
        <div class="section-header">
          <h4>Filter Conditions</h4>
          <button mat-stroked-button (click)="addCondition()" class="add-btn">
            <mat-icon>add</mat-icon>
            Add Filter
          </button>
        </div>

        @if (conditions().length === 0) {
          <div class="empty-conditions">
            <mat-icon>filter_list</mat-icon>
            <p>No filters added. Click "Add Filter" to start building your query.</p>
          </div>
        } @else {
          <div class="conditions-list">
            @for (condition of conditions(); track condition; let i = $index) {
              <div class="condition-row" [class.first]="i === 0">
                @if (i > 0) {
                  <mat-form-field appearance="outline" class="connector-field">
                    <mat-select [(value)]="condition.connector" (selectionChange)="updateQuery()">
                      <mat-option value="AND">AND</mat-option>
                      <mat-option value="OR">OR</mat-option>
                    </mat-select>
                  </mat-form-field>
                }

                <mat-form-field appearance="outline" class="field-select">
                  <mat-label>Field</mat-label>
                  <mat-select [(value)]="condition.field" (selectionChange)="updateQuery()">
                    @for (field of schemaFields(); track field) {
                      <mat-option [value]="field">{{ field }}</mat-option>
                    }
                  </mat-select>
                </mat-form-field>

                <mat-form-field appearance="outline" class="operator-select">
                  <mat-label>Operator</mat-label>
                  <mat-select [(value)]="condition.operator" (selectionChange)="updateQuery()">
                    <mat-option value="==">equals</mat-option>
                    <mat-option value="!=">not equals</mat-option>
                    <mat-option value="LIKE">contains</mat-option>
                    <mat-option value=">">greater than</mat-option>
                    <mat-option value="<">less than</mat-option>
                    <mat-option value=">=">greater or equal</mat-option>
                    <mat-option value="<=">less or equal</mat-option>
                    <mat-option value="IS NOT NULL">exists</mat-option>
                    <mat-option value="IS NULL">not exists</mat-option>
                  </mat-select>
                </mat-form-field>

                @if (!isNullOperator(condition.operator)) {
                  <mat-form-field appearance="outline" class="value-field">
                    <mat-label>Value</mat-label>
                    <input matInput
                           [(ngModel)]="condition.value"
                           (ngModelChange)="updateQuery()"
                           placeholder="Enter value">
                  </mat-form-field>
                }

                <button mat-icon-button
                        color="warn"
                        (click)="removeCondition(i)"
                        matTooltip="Remove filter">
                  <mat-icon>delete</mat-icon>
                </button>
              </div>
            }
          </div>
        }
      </div>

      <!-- Result Options -->
      <div class="builder-section">
        <h4>Result Options</h4>
        <div class="options-row">
          <mat-form-field appearance="outline" class="limit-field">
            <mat-label>Limit</mat-label>
            <mat-select [(value)]="limit" (selectionChange)="updateQuery()">
              <mat-option [value]="10">10</mat-option>
              <mat-option [value]="25">25</mat-option>
              <mat-option [value]="50">50</mat-option>
              <mat-option [value]="100">100</mat-option>
              <mat-option [value]="500">500</mat-option>
            </mat-select>
          </mat-form-field>

          <mat-form-field appearance="outline" class="sort-field">
            <mat-label>Sort By</mat-label>
            <mat-select [(value)]="sortField" (selectionChange)="updateQuery()">
              <mat-option value="">Default</mat-option>
              <mat-option value="@timestamp">Timestamp</mat-option>
              @for (field of schemaFields().slice(0, 20); track field) {
                <mat-option [value]="field">{{ field }}</mat-option>
              }
            </mat-select>
          </mat-form-field>

          @if (sortField) {
            <mat-form-field appearance="outline" class="order-field">
              <mat-label>Order</mat-label>
              <mat-select [(value)]="sortOrder" (selectionChange)="updateQuery()">
                <mat-option value="DESC">Descending</mat-option>
                <mat-option value="ASC">Ascending</mat-option>
              </mat-select>
            </mat-form-field>
          }
        </div>
      </div>

      <!-- Generated Query Preview -->
      <div class="builder-section preview-section">
        <div class="section-header">
          <h4>Generated ES|QL Query</h4>
          <div class="preview-actions">
            <button mat-stroked-button (click)="copyQuery()" matTooltip="Copy to clipboard">
              <mat-icon>content_copy</mat-icon>
              Copy
            </button>
            <button mat-flat-button color="accent" (click)="applyQuery()">
              <mat-icon>play_arrow</mat-icon>
              Run Query
            </button>
          </div>
        </div>
        <pre class="query-preview">{{ generatedQuery() }}</pre>
      </div>
    </div>
  `,
  styles: [`
    .query-builder {
      display: flex;
      flex-direction: column;
      gap: 24px;
      padding: 16px;
    }

    .builder-section {
      background: var(--bg-surface);
      border: 1px solid var(--border-color);
      border-radius: 8px;
      padding: 16px;

      h4 {
        margin: 0 0 12px;
        font-size: 14px;
        font-weight: 500;
        color: var(--text-secondary);
      }
    }

    .section-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 12px;

      h4 {
        margin: 0;
      }
    }

    .full-width {
      width: 100%;
    }

    .index-meta {
      margin-left: 8px;
      font-size: 11px;
      color: var(--text-muted);
    }

    .add-btn {
      mat-icon {
        margin-right: 4px;
      }
    }

    .empty-conditions {
      display: flex;
      flex-direction: column;
      align-items: center;
      padding: 32px;
      color: var(--text-muted);
      text-align: center;

      mat-icon {
        font-size: 32px;
        width: 32px;
        height: 32px;
        margin-bottom: 8px;
        opacity: 0.5;
      }

      p {
        margin: 0;
        font-size: 13px;
      }
    }

    .conditions-list {
      display: flex;
      flex-direction: column;
      gap: 12px;
    }

    .condition-row {
      display: flex;
      align-items: flex-start;
      gap: 8px;

      &.first {
        padding-left: 80px; /* Align with rows that have connector */
      }
    }

    .connector-field {
      width: 72px;
      flex-shrink: 0;
    }

    .field-select {
      flex: 2;
      min-width: 150px;
    }

    .operator-select {
      flex: 1;
      min-width: 120px;
    }

    .value-field {
      flex: 2;
      min-width: 150px;
    }

    .options-row {
      display: flex;
      gap: 16px;
      flex-wrap: wrap;
    }

    .limit-field {
      width: 100px;
    }

    .sort-field {
      width: 180px;
    }

    .order-field {
      width: 140px;
    }

    .preview-section {
      background: var(--bg-card);
    }

    .preview-actions {
      display: flex;
      gap: 8px;
    }

    .query-preview {
      background: #1a1a2e;
      border: 1px solid var(--border-color);
      border-radius: 4px;
      padding: 16px;
      margin: 0;
      font-family: 'JetBrains Mono', 'Fira Code', monospace;
      font-size: 13px;
      color: #a3e635;
      white-space: pre-wrap;
      word-break: break-all;
      overflow-x: auto;
    }

    ::ng-deep {
      .mat-mdc-form-field-subscript-wrapper {
        display: none;
      }
    }
  `]
})
export class QueryBuilderComponent implements OnInit {
  @Output() queryGenerated = new EventEmitter<string>();

  indices = signal<IndexInfo[]>([]);
  schemaFields = signal<string[]>([]);
  conditions = signal<QueryCondition[]>([]);

  selectedIndex = 'logs-*';
  limit = 50;
  sortField = '@timestamp';
  sortOrder: 'ASC' | 'DESC' = 'DESC';

  private loadingSchema = false;

  generatedQuery = computed(() => {
    let query = `FROM ${this.selectedIndex}`;

    const validConditions = this.conditions()
      .filter(c => c.field && (this.isNullOperator(c.operator) || c.value));

    if (validConditions.length > 0) {
      const filters = validConditions.map((c, i) => {
        const connector = i > 0 ? ` ${c.connector} ` : '';
        if (this.isNullOperator(c.operator)) {
          return `${connector}${c.field} ${c.operator}`;
        }
        const value = c.operator === 'LIKE' ? `"*${c.value}*"` : `"${c.value}"`;
        return `${connector}${c.field} ${c.operator} ${value}`;
      }).join('');

      query += `\n| WHERE ${filters}`;
    }

    if (this.sortField) {
      query += `\n| SORT ${this.sortField} ${this.sortOrder}`;
    }

    query += `\n| LIMIT ${this.limit}`;

    return query;
  });

  constructor(private searchService: SearchService) {}

  ngOnInit(): void {
    this.loadIndices();
    this.loadSchema(this.selectedIndex);
  }

  private loadIndices(): void {
    this.searchService.getIndices().subscribe({
      next: (indices) => this.indices.set(indices),
      error: (err) => console.error('Failed to load indices:', err)
    });
  }

  loadSchema(index: string): void {
    if (this.loadingSchema) return;
    this.loadingSchema = true;

    this.searchService.getSchema(index).subscribe({
      next: (schema) => {
        const fields = this.extractFields(schema.mappings);
        this.schemaFields.set(fields.sort());
        this.loadingSchema = false;
      },
      error: (err) => {
        console.error('Failed to load schema:', err);
        // Provide default fields
        this.schemaFields.set([
          '@timestamp',
          'message',
          'host.name',
          'user.name',
          'process.name',
          'source.ip',
          'destination.ip',
          'event.action',
          'event.category',
          'event.type'
        ]);
        this.loadingSchema = false;
      }
    });
  }

  private extractFields(mappings: Record<string, unknown>, prefix = ''): string[] {
    const fields: string[] = [];

    const processProperties = (props: Record<string, any>, currentPrefix: string) => {
      for (const [key, value] of Object.entries(props)) {
        const fieldPath = currentPrefix ? `${currentPrefix}.${key}` : key;

        if (value.type) {
          fields.push(fieldPath);
        }
        if (value.properties) {
          processProperties(value.properties, fieldPath);
        }
      }
    };

    if (mappings && typeof mappings === 'object') {
      const props = (mappings as any).properties || mappings;
      if (props && typeof props === 'object') {
        processProperties(props as Record<string, any>, prefix);
      }
    }

    return fields;
  }

  onIndexChange(): void {
    this.loadSchema(this.selectedIndex);
    this.updateQuery();
  }

  addCondition(): void {
    this.conditions.update(conditions => [
      ...conditions,
      { field: '', operator: '==', value: '', connector: 'AND' }
    ]);
  }

  removeCondition(index: number): void {
    this.conditions.update(conditions =>
      conditions.filter((_, i) => i !== index)
    );
    this.updateQuery();
  }

  isNullOperator(operator: string): boolean {
    return operator === 'IS NULL' || operator === 'IS NOT NULL';
  }

  updateQuery(): void {
    // Trigger computed to recalculate
    // The computed signal will automatically update
  }

  copyQuery(): void {
    navigator.clipboard.writeText(this.generatedQuery()).then(() => {
      // Could show a snackbar here
    });
  }

  applyQuery(): void {
    this.queryGenerated.emit(this.generatedQuery());
  }
}
