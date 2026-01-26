import { Component, OnInit, OnDestroy, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, Router, RouterModule } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatMenuModule } from '@angular/material/menu';
import { MatSelectModule } from '@angular/material/select';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { MatCardModule } from '@angular/material/card';

import { WorkbookService } from '../../core/api/workbook.service';
import {
  Workbook,
  TileDefinition,
  TileExecuteResponse,
} from '../../shared/models/workbook.model';

@Component({
  selector: 'app-workbook-viewer',
  standalone: true,
  imports: [
    CommonModule,
    RouterModule,
    FormsModule,
    MatButtonModule,
    MatIconModule,
    MatMenuModule,
    MatSelectModule,
    MatProgressSpinnerModule,
    MatTooltipModule,
    MatSnackBarModule,
    MatCardModule,
  ],
  template: `
    <div class="workbook-viewer">
      @if (loading()) {
        <div class="loading-overlay">
          <mat-spinner diameter="48"></mat-spinner>
        </div>
      }

      @if (workbook()) {
        <!-- Toolbar -->
        <div class="toolbar">
          <div class="toolbar-left">
            <button mat-icon-button (click)="goBack()" matTooltip="Back">
              <mat-icon>arrow_back</mat-icon>
            </button>
            <h2>{{ workbook()!.name }}</h2>
          </div>

          <div class="toolbar-center">
            @if (caseId()) {
              <span class="case-badge">Case: {{ caseId() }}</span>
            }
            <mat-select
              [(value)]="selectedCaseId"
              placeholder="Select Case"
              (selectionChange)="onCaseChange()"
              style="width: 200px"
            >
              <mat-option value="">All Events</mat-option>
              <!-- Case options would be loaded dynamically -->
            </mat-select>
          </div>

          <div class="toolbar-right">
            <button mat-icon-button (click)="refreshAll()" matTooltip="Refresh All">
              <mat-icon>refresh</mat-icon>
            </button>
            <button mat-icon-button [routerLink]="['edit']" matTooltip="Edit">
              <mat-icon>edit</mat-icon>
            </button>
            <button mat-icon-button [matMenuTriggerFor]="moreMenu" matTooltip="More">
              <mat-icon>more_vert</mat-icon>
            </button>
            <mat-menu #moreMenu="matMenu">
              <button mat-menu-item (click)="exportWorkbook()">
                <mat-icon>download</mat-icon>
                Export
              </button>
              <button mat-menu-item (click)="cloneWorkbook()">
                <mat-icon>content_copy</mat-icon>
                Clone
              </button>
            </mat-menu>
          </div>
        </div>

        <!-- Tiles Grid -->
        <div
          class="tiles-container"
          [style.--columns]="workbook()!.definition.layout?.columns || 12"
          [style.--row-height]="(workbook()!.definition.layout?.row_height || 60) + 'px'"
        >
          @for (tile of workbook()!.definition.tiles; track tile.id) {
            <div
              class="tile"
              [style.grid-column]="'span ' + tile.position.width"
              [style.grid-row]="'span ' + tile.position.height"
            >
              <div class="tile-header">
                <span class="tile-title">{{ tile.title }}</span>
                <button mat-icon-button (click)="refreshTile(tile)" matTooltip="Refresh">
                  <mat-icon>refresh</mat-icon>
                </button>
              </div>
              <div class="tile-content" [class.loading]="tileLoading()[tile.id]">
                @if (tileLoading()[tile.id]) {
                  <mat-spinner diameter="24"></mat-spinner>
                } @else {
                  @switch (tile.type) {
                    @case ('metric') {
                      <div class="metric-tile">
                        <span class="metric-value">
                          {{ formatMetricValue(tileData()[tile.id]) }}
                        </span>
                      </div>
                    }
                    @case ('chart') {
                      <div class="chart-tile">
                        <!-- Chart would be rendered here with ngx-charts -->
                        <div class="chart-placeholder">
                          <mat-icon>bar_chart</mat-icon>
                          <span>{{ (tileData()[tile.id]?.length || 0) }} data points</span>
                        </div>
                      </div>
                    }
                    @case ('table') {
                      <div class="table-tile">
                        @if (tileData()[tile.id]?.length > 0) {
                          <table>
                            <thead>
                              <tr>
                                @for (col of getTableColumns(tile); track col) {
                                  <th>{{ col }}</th>
                                }
                              </tr>
                            </thead>
                            <tbody>
                              @for (row of tileData()[tile.id]?.slice(0, 10); track $index) {
                                <tr>
                                  @for (col of getTableColumns(tile); track col) {
                                    <td>{{ getNestedValue(row, col) }}</td>
                                  }
                                </tr>
                              }
                            </tbody>
                          </table>
                        } @else {
                          <div class="no-data">No data</div>
                        }
                      </div>
                    }
                    @case ('markdown') {
                      <div class="markdown-tile">
                        {{ tile.config.content }}
                      </div>
                    }
                    @case ('timeline') {
                      <div class="timeline-tile">
                        <div class="timeline-placeholder">
                          <mat-icon>timeline</mat-icon>
                          <span>{{ (tileData()[tile.id]?.length || 0) }} time buckets</span>
                        </div>
                      </div>
                    }
                    @default {
                      <div class="unknown-tile">
                        Unknown tile type: {{ tile.type }}
                      </div>
                    }
                  }
                }
              </div>
            </div>
          }
        </div>
      }
    </div>
  `,
  styles: [`
    :host {
      display: block;
      height: 100%;
    }

    .workbook-viewer {
      display: flex;
      flex-direction: column;
      height: 100%;
      background: #121212;
    }

    .loading-overlay {
      position: absolute;
      inset: 0;
      display: flex;
      align-items: center;
      justify-content: center;
      background: rgba(0, 0, 0, 0.5);
      z-index: 100;
    }

    .toolbar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 8px 16px;
      background: #1e1e1e;
      border-bottom: 1px solid #333;
    }

    .toolbar-left, .toolbar-center, .toolbar-right {
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .toolbar h2 {
      margin: 0;
      font-size: 18px;
    }

    .case-badge {
      padding: 4px 8px;
      background: #333;
      border-radius: 4px;
      font-size: 12px;
    }

    .tiles-container {
      flex: 1;
      display: grid;
      grid-template-columns: repeat(var(--columns), 1fr);
      grid-auto-rows: var(--row-height);
      gap: 16px;
      padding: 16px;
      overflow-y: auto;
    }

    .tile {
      background: #1e1e1e;
      border: 1px solid #333;
      border-radius: 8px;
      display: flex;
      flex-direction: column;
      overflow: hidden;
    }

    .tile-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 8px 12px;
      background: #252525;
      border-bottom: 1px solid #333;
    }

    .tile-title {
      font-size: 14px;
      font-weight: 500;
    }

    .tile-header button {
      width: 28px;
      height: 28px;
      line-height: 28px;
    }

    .tile-header button mat-icon {
      font-size: 18px;
    }

    .tile-content {
      flex: 1;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 16px;
      overflow: auto;
    }

    .tile-content.loading {
      opacity: 0.5;
    }

    .metric-tile {
      text-align: center;
    }

    .metric-value {
      font-size: 48px;
      font-weight: 600;
      color: #4CAF50;
    }

    .chart-tile, .timeline-tile {
      width: 100%;
      height: 100%;
    }

    .chart-placeholder, .timeline-placeholder {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      height: 100%;
      color: #666;
    }

    .chart-placeholder mat-icon, .timeline-placeholder mat-icon {
      font-size: 48px;
      width: 48px;
      height: 48px;
      margin-bottom: 8px;
    }

    .table-tile {
      width: 100%;
      height: 100%;
      overflow: auto;
    }

    .table-tile table {
      width: 100%;
      border-collapse: collapse;
      font-size: 12px;
    }

    .table-tile th, .table-tile td {
      padding: 8px;
      text-align: left;
      border-bottom: 1px solid #333;
    }

    .table-tile th {
      background: #252525;
      font-weight: 500;
      position: sticky;
      top: 0;
    }

    .no-data, .unknown-tile {
      color: #666;
      font-style: italic;
    }

    .markdown-tile {
      white-space: pre-wrap;
      font-family: inherit;
    }
  `],
})
export class WorkbookViewerComponent implements OnInit, OnDestroy {
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private workbookService = inject(WorkbookService);
  private snackBar = inject(MatSnackBar);

  workbook = signal<Workbook | null>(null);
  loading = signal(false);
  tileData = signal<Record<string, any>>({});
  tileLoading = signal<Record<string, boolean>>({});

  caseId = signal<string | null>(null);
  selectedCaseId = '';

  private refreshInterval: any;

  ngOnInit(): void {
    // Get case ID from query params
    this.route.queryParams.subscribe((params) => {
      this.caseId.set(params['case_id'] || null);
      this.selectedCaseId = params['case_id'] || '';
    });

    // Load workbook
    this.route.params.subscribe((params) => {
      const id = params['id'];
      if (id) {
        this.loadWorkbook(id);
      }
    });
  }

  ngOnDestroy(): void {
    if (this.refreshInterval) {
      clearInterval(this.refreshInterval);
    }
  }

  async loadWorkbook(id: string): Promise<void> {
    this.loading.set(true);
    try {
      const workbook = await this.workbookService.getWorkbook(id).toPromise();
      this.workbook.set(workbook || null);

      // Load all tiles
      if (workbook) {
        this.refreshAll();
      }
    } catch (error) {
      console.error('Failed to load workbook:', error);
      this.snackBar.open('Failed to load workbook', 'Close', { duration: 3000 });
    } finally {
      this.loading.set(false);
    }
  }

  async refreshAll(): Promise<void> {
    const workbook = this.workbook();
    if (!workbook) return;

    for (const tile of workbook.definition.tiles) {
      this.refreshTile(tile);
    }
  }

  async refreshTile(tile: TileDefinition): Promise<void> {
    this.tileLoading.update((state) => ({ ...state, [tile.id]: true }));

    try {
      const response = await this.workbookService
        .executeTile({
          tile_type: tile.type,
          config: tile.config,
          case_id: this.selectedCaseId || undefined,
          variables: this.workbook()?.definition.variables || {},
        })
        .toPromise();

      if (response) {
        this.tileData.update((data) => ({ ...data, [tile.id]: response.data }));
      }
    } catch (error) {
      console.error(`Failed to load tile ${tile.id}:`, error);
    } finally {
      this.tileLoading.update((state) => ({ ...state, [tile.id]: false }));
    }
  }

  onCaseChange(): void {
    // Update URL and refresh
    this.router.navigate([], {
      relativeTo: this.route,
      queryParams: { case_id: this.selectedCaseId || null },
      queryParamsHandling: 'merge',
    });
    this.refreshAll();
  }

  formatMetricValue(data: any): string {
    if (!data || data.value === undefined) return '-';
    const value = data.value;
    if (value >= 1000000) return `${(value / 1000000).toFixed(1)}M`;
    if (value >= 1000) return `${(value / 1000).toFixed(1)}K`;
    return value.toString();
  }

  getTableColumns(tile: TileDefinition): string[] {
    return tile.config.columns || ['@timestamp', 'message'];
  }

  getNestedValue(obj: any, path: string): any {
    return path.split('.').reduce((o, p) => o?.[p], obj) ?? '-';
  }

  goBack(): void {
    this.router.navigate(['/workbooks']);
  }

  exportWorkbook(): void {
    const workbook = this.workbook();
    if (!workbook) {
      this.snackBar.open('No workbook to export', 'Close', { duration: 3000 });
      return;
    }

    try {
      // Create export object with workbook definition
      const exportData = {
        name: workbook.name,
        description: workbook.description,
        definition: workbook.definition,
        exported_at: new Date().toISOString(),
        version: '1.0',
      };

      // Convert to JSON string with pretty formatting
      const jsonString = JSON.stringify(exportData, null, 2);

      // Create blob and download link
      const blob = new Blob([jsonString], { type: 'application/json' });
      const url = URL.createObjectURL(blob);

      const link = document.createElement('a');
      link.href = url;
      link.download = `workbook-${workbook.name.toLowerCase().replace(/\s+/g, '-')}-${new Date().toISOString().split('T')[0]}.json`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);

      // Clean up the URL object
      URL.revokeObjectURL(url);

      this.snackBar.open('Workbook exported successfully', 'Close', { duration: 3000 });
    } catch (error) {
      console.error('Failed to export workbook:', error);
      this.snackBar.open('Failed to export workbook', 'Close', { duration: 3000 });
    }
  }

  async cloneWorkbook(): Promise<void> {
    const workbook = this.workbook();
    if (!workbook) return;

    const name = prompt('Enter name for clone:', `${workbook.name} Copy`);
    if (!name) return;

    try {
      const clone = await this.workbookService.cloneWorkbook(workbook.id, name).toPromise();
      if (clone) {
        this.router.navigate(['/workbooks', clone.id]);
      }
    } catch (error) {
      console.error('Failed to clone workbook:', error);
      this.snackBar.open('Failed to clone workbook', 'Close', { duration: 3000 });
    }
  }
}
