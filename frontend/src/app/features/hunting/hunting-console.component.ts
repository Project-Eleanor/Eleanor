import { Component, OnInit, signal, ViewChild } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute } from '@angular/router';
import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatSelectModule } from '@angular/material/select';
import { MatInputModule } from '@angular/material/input';
import { MatTableModule } from '@angular/material/table';
import { MatPaginatorModule, PageEvent } from '@angular/material/paginator';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatMenuModule } from '@angular/material/menu';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatChipsModule } from '@angular/material/chips';
import { MatDialogModule, MatDialog } from '@angular/material/dialog';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { MatButtonToggleModule } from '@angular/material/button-toggle';
import { SearchService } from '../../core/api/search.service';
import { SavedQuery, SearchResult } from '../../shared/models';
import { SaveQueryDialogComponent } from './save-query-dialog.component';
import { MonacoEditorComponent } from '../../shared/components/monaco-editor/monaco-editor.component';

@Component({
  selector: 'app-hunting-console',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatCardModule,
    MatButtonModule,
    MatIconModule,
    MatFormFieldModule,
    MatSelectModule,
    MatInputModule,
    MatTableModule,
    MatPaginatorModule,
    MatProgressSpinnerModule,
    MatMenuModule,
    MatTooltipModule,
    MatChipsModule,
    MatDialogModule,
    MatSnackBarModule,
    MatButtonToggleModule,
    MonacoEditorComponent
  ],
  template: `
    <div class="hunting-console">
      <!-- Query Panel -->
      <mat-card class="query-panel">
        <div class="query-header">
          <div class="query-controls">
            <mat-form-field appearance="outline" class="saved-queries">
              <mat-label>Saved Queries</mat-label>
              <mat-select (selectionChange)="loadSavedQuery($event.value)">
                @for (query of savedQueries(); track query.id) {
                  <mat-option [value]="query">
                    {{ query.name }}
                  </mat-option>
                }
              </mat-select>
            </mat-form-field>

            <button mat-stroked-button (click)="saveQuery()" [disabled]="!query">
              <mat-icon>save</mat-icon>
              Save Query
            </button>
          </div>

          <div class="query-actions">
            <button mat-stroked-button (click)="clearQuery()">
              <mat-icon>clear</mat-icon>
              Clear
            </button>
            <button mat-flat-button color="accent" (click)="executeQuery()" [disabled]="!query || isExecuting()">
              @if (isExecuting()) {
                <mat-spinner diameter="20"></mat-spinner>
              } @else {
                <mat-icon>play_arrow</mat-icon>
                Run Query
              }
            </button>
          </div>
        </div>

        <!-- Query Language Toggle -->
        <div class="language-toggle">
          <mat-button-toggle-group [(ngModel)]="queryLanguage" (change)="onLanguageChange()">
            <mat-button-toggle value="esql">ES|QL</mat-button-toggle>
            <mat-button-toggle value="kql">KQL</mat-button-toggle>
          </mat-button-toggle-group>
          <div class="editor-hint">Press Ctrl+Enter to run query</div>
        </div>

        <!-- Monaco Editor -->
        <div class="query-editor">
          <app-monaco-editor
            #monacoEditor
            [(ngModel)]="query"
            [language]="queryLanguage"
            (executeQuery)="executeQuery()">
          </app-monaco-editor>
        </div>

        <!-- Query Examples -->
        <div class="query-examples">
          <span class="examples-label">Examples:</span>
          @for (example of queryExamples; track example.label) {
            <button mat-stroked-button class="example-btn" (click)="useExample(example.query)"
                    [matTooltip]="example.query">
              {{ example.label }}
            </button>
          }
        </div>
      </mat-card>

      <!-- Results Panel -->
      <mat-card class="results-panel">
        <div class="results-header">
          <div class="results-info">
            @if (hasResults()) {
              <span>{{ totalResults() }} results in {{ executionTime() }}ms</span>
            } @else if (hasError()) {
              <span class="error-text">
                <mat-icon>error</mat-icon>
                {{ errorMessage() }}
              </span>
            } @else {
              <span class="placeholder">Run a query to see results</span>
            }
          </div>

          @if (hasResults()) {
            <div class="results-actions">
              <button mat-icon-button matTooltip="Export CSV" (click)="exportResults('csv')">
                <mat-icon>download</mat-icon>
              </button>
              <button mat-icon-button matTooltip="Add to Case" [matMenuTriggerFor]="addToCaseMenu">
                <mat-icon>add_to_photos</mat-icon>
              </button>
              <mat-menu #addToCaseMenu="matMenu">
                <button mat-menu-item>Add to existing case</button>
                <button mat-menu-item>Create new case</button>
              </mat-menu>
            </div>
          }
        </div>

        @if (isExecuting()) {
          <div class="loading">
            <mat-spinner diameter="40"></mat-spinner>
            <p>Executing query...</p>
          </div>
        } @else if (hasResults()) {
          <div class="results-table-container">
            <table mat-table [dataSource]="results()">
              @for (column of displayedColumns(); track column) {
                <ng-container [matColumnDef]="column">
                  <th mat-header-cell *matHeaderCellDef>{{ column }}</th>
                  <td mat-cell *matCellDef="let row">
                    <span class="cell-value" [matTooltip]="getCellValue(row, column)">
                      {{ getCellValue(row, column) }}
                    </span>
                  </td>
                </ng-container>
              }

              <tr mat-header-row *matHeaderRowDef="displayedColumns(); sticky: true"></tr>
              <tr mat-row *matRowDef="let row; columns: displayedColumns();"
                  (click)="selectResult(row)">
              </tr>
            </table>
          </div>

          <mat-paginator [length]="totalResults()"
                         [pageSize]="pageSize"
                         [pageIndex]="currentPage()"
                         [pageSizeOptions]="[25, 50, 100]"
                         (page)="onPageChange($event)">
          </mat-paginator>
        } @else {
          <div class="empty-state">
            <mat-icon>search</mat-icon>
            <h3>Threat Hunting Console</h3>
            <p>Write ES|QL queries to search across your security data</p>
          </div>
        }
      </mat-card>

      <!-- Result Detail Panel (sliding) -->
      @if (selectedResult()) {
        <div class="result-detail-panel">
          <div class="panel-header">
            <h3>Event Details</h3>
            <button mat-icon-button (click)="closeDetail()">
              <mat-icon>close</mat-icon>
            </button>
          </div>
          <div class="panel-content">
            @for (entry of getObjectEntries(selectedResult()!.source); track entry[0]) {
              <div class="detail-row">
                <span class="key">{{ entry[0] }}</span>
                <span class="value">{{ formatValue(entry[1]) }}</span>
              </div>
            }
          </div>
          <div class="panel-actions">
            <button mat-stroked-button (click)="enrichValue()">
              <mat-icon>security</mat-icon>
              Enrich
            </button>
            <button mat-stroked-button (click)="pivotSearch()">
              <mat-icon>search</mat-icon>
              Pivot
            </button>
          </div>
        </div>
      }
    </div>
  `,
  styles: [`
    .hunting-console {
      display: flex;
      flex-direction: column;
      height: 100%;
      gap: 16px;
    }

    .query-panel {
      background: var(--bg-card);
      border: 1px solid var(--border-color);
    }

    .query-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 16px;
    }

    .query-controls {
      display: flex;
      gap: 16px;
      align-items: center;
    }

    .saved-queries {
      min-width: 250px;
    }

    .query-actions {
      display: flex;
      gap: 8px;
    }

    .language-toggle {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 12px;

      ::ng-deep .mat-button-toggle-group {
        border: 1px solid var(--border-color);
        border-radius: 6px;
        overflow: hidden;
      }

      ::ng-deep .mat-button-toggle {
        background: var(--bg-surface);

        &.mat-button-toggle-checked {
          background: var(--accent);

          .mat-button-toggle-label-content {
            color: white;
          }
        }
      }

      .editor-hint {
        font-size: 11px;
        color: var(--text-muted);
      }
    }

    .query-editor {
      height: 200px;
      margin-bottom: 16px;
    }

    .query-examples {
      display: flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
    }

    .examples-label {
      font-size: 12px;
      color: var(--text-secondary);
    }

    .example-btn {
      font-size: 11px;
      min-height: 28px;
      padding: 0 12px;
    }

    .results-panel {
      flex: 1;
      display: flex;
      flex-direction: column;
      min-height: 0;
      background: var(--bg-card);
      border: 1px solid var(--border-color);
    }

    .results-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding-bottom: 16px;
      border-bottom: 1px solid var(--border-color);
      margin-bottom: 16px;
    }

    .results-info {
      font-size: 14px;
      color: var(--text-secondary);

      .placeholder {
        font-style: italic;
      }
    }

    .error-text {
      display: flex;
      align-items: center;
      gap: 8px;
      color: var(--danger);

      mat-icon {
        font-size: 18px;
        width: 18px;
        height: 18px;
      }
    }

    .results-actions {
      display: flex;
      gap: 4px;
    }

    .loading {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      padding: 48px;
      color: var(--text-secondary);

      p {
        margin-top: 16px;
      }
    }

    .results-table-container {
      flex: 1;
      overflow: auto;
    }

    table {
      width: 100%;
    }

    .cell-value {
      display: block;
      max-width: 300px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .mat-mdc-row {
      cursor: pointer;

      &:hover {
        background: rgba(255, 255, 255, 0.02);
      }
    }

    .empty-state {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      padding: 64px;
      text-align: center;
      color: var(--text-muted);

      mat-icon {
        font-size: 64px;
        width: 64px;
        height: 64px;
        margin-bottom: 16px;
      }

      h3 {
        margin: 0 0 8px;
        color: var(--text-primary);
      }

      p {
        margin: 0;
      }
    }

    .result-detail-panel {
      position: fixed;
      top: 0;
      right: 0;
      width: 450px;
      height: 100vh;
      background: var(--bg-card);
      border-left: 1px solid var(--border-color);
      display: flex;
      flex-direction: column;
      z-index: 1000;
      box-shadow: -4px 0 16px rgba(0, 0, 0, 0.3);
    }

    .panel-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 16px;
      border-bottom: 1px solid var(--border-color);

      h3 {
        margin: 0;
        font-size: 16px;
      }
    }

    .panel-content {
      flex: 1;
      overflow-y: auto;
      padding: 16px;
    }

    .detail-row {
      display: flex;
      flex-direction: column;
      padding: 8px 0;
      border-bottom: 1px solid var(--border-color);

      .key {
        font-size: 11px;
        color: var(--text-secondary);
        text-transform: uppercase;
        margin-bottom: 4px;
      }

      .value {
        font-family: monospace;
        font-size: 13px;
        word-break: break-all;
      }
    }

    .panel-actions {
      display: flex;
      gap: 8px;
      padding: 16px;
      border-top: 1px solid var(--border-color);
    }
  `]
})
export class HuntingConsoleComponent implements OnInit {
  @ViewChild('monacoEditor') monacoEditor!: MonacoEditorComponent;

  query = '';
  queryLanguage: 'esql' | 'kql' = 'esql';
  savedQueries = signal<SavedQuery[]>([]);
  results = signal<SearchResult[]>([]);
  displayedColumns = signal<string[]>([]);
  totalResults = signal(0);
  executionTime = signal(0);
  currentPage = signal(0);
  pageSize = 50;

  isExecuting = signal(false);
  hasResults = signal(false);
  hasError = signal(false);
  errorMessage = signal('');
  selectedResult = signal<SearchResult | null>(null);

  queryExamples = [
    { label: 'Process Events', query: 'FROM logs-* | WHERE event.category == "process"' },
    { label: 'Network Connections', query: 'FROM logs-* | WHERE event.category == "network"' },
    { label: 'Failed Logins', query: 'FROM logs-* | WHERE event.action == "logon-failed"' },
    { label: 'PowerShell', query: 'FROM logs-* | WHERE process.name == "powershell.exe"' }
  ];

  constructor(
    private route: ActivatedRoute,
    private searchService: SearchService,
    private dialog: MatDialog,
    private snackBar: MatSnackBar
  ) {}

  ngOnInit(): void {
    this.loadSavedQueries();

    const q = this.route.snapshot.queryParams['q'];
    if (q) {
      this.query = q;
      this.executeQuery();
    }
  }

  private loadSavedQueries(): void {
    this.searchService.getSavedQueries().subscribe({
      next: (queries) => this.savedQueries.set(queries)
    });
  }

  loadSavedQuery(saved: SavedQuery): void {
    this.query = saved.query;
  }

  clearQuery(): void {
    this.query = '';
    this.hasResults.set(false);
    this.hasError.set(false);
    this.results.set([]);
    this.selectedResult.set(null);
  }

  useExample(query: string): void {
    this.query = query;
    if (this.monacoEditor) {
      this.monacoEditor.setValue(query);
      this.monacoEditor.focus();
    }
  }

  onLanguageChange(): void {
    // Clear query when switching languages if incompatible syntax
    if (this.monacoEditor) {
      this.monacoEditor.focus();
    }
  }

  executeQuery(): void {
    if (!this.query || this.isExecuting()) return;

    this.isExecuting.set(true);
    this.hasError.set(false);
    this.selectedResult.set(null);

    const searchFn = this.queryLanguage === 'kql'
      ? this.searchService.kql(this.query, {
          from_: this.currentPage() * this.pageSize,
          size: this.pageSize
        })
      : this.searchService.esql(this.query, {
          from: this.currentPage() * this.pageSize,
          size: this.pageSize
        });

    searchFn.subscribe({
      next: (response) => {
        this.results.set(response.hits);
        this.totalResults.set(response.total);
        this.executionTime.set(response.took);
        this.hasResults.set(true);

        // Extract column names from results
        if (response.hits.length > 0) {
          const columns = Object.keys(response.hits[0].source);
          this.displayedColumns.set(columns.slice(0, 10)); // Limit columns
        }

        this.isExecuting.set(false);
      },
      error: (error) => {
        this.hasError.set(true);
        this.errorMessage.set(error.message || error.error?.detail || 'Query execution failed');
        this.hasResults.set(false);
        this.isExecuting.set(false);
      }
    });
  }

  onPageChange(event: PageEvent): void {
    this.currentPage.set(event.pageIndex);
    this.pageSize = event.pageSize;
    this.executeQuery();
  }

  selectResult(result: SearchResult): void {
    this.selectedResult.set(result);
  }

  closeDetail(): void {
    this.selectedResult.set(null);
  }

  getCellValue(row: SearchResult, column: string): string {
    const value = row.source[column];
    if (value === null || value === undefined) return '-';
    if (typeof value === 'object') return JSON.stringify(value);
    return String(value);
  }

  getObjectEntries(obj: Record<string, unknown>): [string, unknown][] {
    return Object.entries(obj);
  }

  formatValue(value: unknown): string {
    if (value === null || value === undefined) return '-';
    if (typeof value === 'object') return JSON.stringify(value, null, 2);
    return String(value);
  }

  saveQuery(): void {
    const dialogRef = this.dialog.open(SaveQueryDialogComponent, {
      width: '500px',
      data: { query: this.query }
    });

    dialogRef.afterClosed().subscribe(result => {
      if (result) {
        this.loadSavedQueries();
        this.snackBar.open('Query saved successfully', 'Dismiss', { duration: 3000 });
      }
    });
  }

  exportResults(format: 'csv' | 'json'): void {
    const data = this.results().map(r => r.source);

    if (format === 'csv') {
      const headers = this.displayedColumns().join(',');
      const rows = data.map(row =>
        this.displayedColumns().map(col => JSON.stringify(row[col] ?? '')).join(',')
      );
      const csv = [headers, ...rows].join('\n');
      this.downloadFile(csv, 'results.csv', 'text/csv');
    } else {
      const json = JSON.stringify(data, null, 2);
      this.downloadFile(json, 'results.json', 'application/json');
    }
  }

  private downloadFile(content: string, filename: string, mimeType: string): void {
    const blob = new Blob([content], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  }

  enrichValue(): void {
    this.snackBar.open('Enrichment feature coming soon', 'Dismiss', { duration: 3000 });
  }

  pivotSearch(): void {
    this.snackBar.open('Pivot search coming soon', 'Dismiss', { duration: 3000 });
  }
}
