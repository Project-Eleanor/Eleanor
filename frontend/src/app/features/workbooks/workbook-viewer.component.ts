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
import { NgxChartsModule } from '@swimlane/ngx-charts';

import { WorkbookService } from '../../core/api/workbook.service';
import {
  Workbook,
  TileDefinition,
  TileExecuteResponse,
  TileConfig,
  ChartData,
} from '../../shared/models/workbook.model';
import { D3TimelineComponent, TimelineItem } from '../../shared/components/d3-timeline/d3-timeline.component';
import { LoggingService } from '../../core/services/logging.service';

/** Data structure for metric tile values */
interface MetricTileData {
  value?: number;
  label?: string;
  change?: number;
}

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
    NgxChartsModule,
    D3TimelineComponent,
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
              <button mat-menu-item [matMenuTriggerFor]="exportMenu">
                <mat-icon>download</mat-icon>
                Export
              </button>
              <button mat-menu-item (click)="cloneWorkbook()">
                <mat-icon>content_copy</mat-icon>
                Clone
              </button>
            </mat-menu>
            <mat-menu #exportMenu="matMenu">
              <button mat-menu-item (click)="exportWorkbook()">
                <mat-icon>code</mat-icon>
                Export JSON
              </button>
              <button mat-menu-item (click)="exportToPdf()" [disabled]="isExporting()">
                <mat-icon>picture_as_pdf</mat-icon>
                Export PDF
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
                        @if (tileData()[tile.id]?.length > 0) {
                          @switch (tile.config.chart_type) {
                            @case ('bar') {
                              <ngx-charts-bar-vertical
                                [results]="transformChartData(tileData()[tile.id], tile.config)"
                                [xAxis]="true"
                                [yAxis]="true"
                                [legend]="false"
                                [showXAxisLabel]="true"
                                [showYAxisLabel]="true"
                                [xAxisLabel]="tile.config.x_field || 'Category'"
                                [yAxisLabel]="tile.config.y_field || 'Count'"
                                [gradient]="true"
                                [scheme]="chartColorScheme">
                              </ngx-charts-bar-vertical>
                            }
                            @case ('line') {
                              <ngx-charts-line-chart
                                [results]="transformMultiSeriesData(tileData()[tile.id], tile.config)"
                                [xAxis]="true"
                                [yAxis]="true"
                                [legend]="true"
                                [showXAxisLabel]="true"
                                [showYAxisLabel]="true"
                                [xAxisLabel]="tile.config.x_field || 'Time'"
                                [yAxisLabel]="tile.config.y_field || 'Value'"
                                [autoScale]="true"
                                [scheme]="chartColorScheme">
                              </ngx-charts-line-chart>
                            }
                            @case ('pie') {
                              <ngx-charts-pie-chart
                                [results]="transformChartData(tileData()[tile.id], tile.config)"
                                [legend]="true"
                                [legendTitle]="tile.config.group_by || 'Legend'"
                                [doughnut]="false"
                                [scheme]="chartColorScheme">
                              </ngx-charts-pie-chart>
                            }
                            @case ('area') {
                              <ngx-charts-area-chart
                                [results]="transformMultiSeriesData(tileData()[tile.id], tile.config)"
                                [xAxis]="true"
                                [yAxis]="true"
                                [legend]="true"
                                [showXAxisLabel]="true"
                                [showYAxisLabel]="true"
                                [xAxisLabel]="tile.config.x_field || 'Time'"
                                [yAxisLabel]="tile.config.y_field || 'Value'"
                                [autoScale]="true"
                                [gradient]="true"
                                [scheme]="chartColorScheme">
                              </ngx-charts-area-chart>
                            }
                            @default {
                              <ngx-charts-bar-vertical
                                [results]="transformChartData(tileData()[tile.id], tile.config)"
                                [xAxis]="true"
                                [yAxis]="true"
                                [legend]="false"
                                [scheme]="chartColorScheme">
                              </ngx-charts-bar-vertical>
                            }
                          }
                        } @else {
                          <div class="chart-placeholder">
                            <mat-icon>bar_chart</mat-icon>
                            <span>No data</span>
                          </div>
                        }
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
                        @if (tileData()[tile.id]?.length > 0) {
                          <app-d3-timeline
                            [items]="transformTimelineData(tileData()[tile.id])"
                            [config]="{
                              height: (tile.position.height * 60) - 60,
                              enableZoom: true,
                              enableBrush: false
                            }"
                            (itemSelected)="onTileEventSelected(tile.id, $event)">
                          </app-d3-timeline>
                        } @else {
                          <div class="timeline-placeholder">
                            <mat-icon>timeline</mat-icon>
                            <span>No timeline data</span>
                          </div>
                        }
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
      display: flex;
      flex-direction: column;
    }

    .chart-tile ngx-charts-bar-vertical,
    .chart-tile ngx-charts-line-chart,
    .chart-tile ngx-charts-pie-chart,
    .chart-tile ngx-charts-area-chart {
      width: 100%;
      height: 100%;
    }

    .timeline-tile app-d3-timeline {
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
  private logger = inject(LoggingService);

  workbook = signal<Workbook | null>(null);
  loading = signal(false);
  tileData = signal<Record<string, any>>({});
  tileLoading = signal<Record<string, boolean>>({});
  isExporting = signal(false);

  caseId = signal<string | null>(null);
  selectedCaseId = '';

  private refreshInterval: ReturnType<typeof setInterval> | null = null;

  // Chart color scheme (ngx-charts built-in scheme)
  chartColorScheme = 'cool';

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
      this.logger.error('Failed to load workbook', error as Error, { component: 'WorkbookViewerComponent' });
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
      this.logger.error(`Failed to load tile ${tile.id}`, error as Error, { component: 'WorkbookViewerComponent', tileId: tile.id });
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

  formatMetricValue(data: MetricTileData | null | undefined): string {
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
      this.logger.error('Failed to export workbook', error as Error, { component: 'WorkbookViewerComponent' });
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
      this.logger.error('Failed to clone workbook', error as Error, { component: 'WorkbookViewerComponent' });
      this.snackBar.open('Failed to clone workbook', 'Close', { duration: 3000 });
    }
  }

  /**
   * Transform API chart data to ngx-charts single series format.
   * Expected input: [{ key: string, count: number }] or raw data with configurable fields
   */
  transformChartData(data: any[], config: TileConfig): { name: string; value: number }[] {
    if (!data || data.length === 0) return [];

    // If data is already in ChartData format
    if (data[0]?.key !== undefined && data[0]?.count !== undefined) {
      return data.map((item: ChartData) => ({
        name: item.key || 'Unknown',
        value: item.count || 0
      }));
    }

    // Transform from raw API response using config fields
    const xField = config.x_field || config.group_by || 'key';
    const yField = config.y_field || 'count';

    return data.map((item: any) => ({
      name: this.getNestedValue(item, xField)?.toString() || 'Unknown',
      value: Number(this.getNestedValue(item, yField)) || 0
    }));
  }

  /**
   * Transform API data to ngx-charts multi-series format for line/area charts.
   * Format: [{ name: string, series: [{ name: string, value: number }] }]
   */
  transformMultiSeriesData(data: any[], config: TileConfig): any[] {
    if (!data || data.length === 0) return [];

    // If data has split_by field, create multiple series
    if (config.split_by && data[0]?.split) {
      const series: any[] = [];
      const seriesMap = new Map<string, { name: string; value: number }[]>();

      for (const item of data) {
        const xValue = item.key || item[config.x_field || 'timestamp'];
        if (item.split && Array.isArray(item.split)) {
          for (const split of item.split) {
            const seriesName = split.key || 'Unknown';
            if (!seriesMap.has(seriesName)) {
              seriesMap.set(seriesName, []);
            }
            seriesMap.get(seriesName)!.push({
              name: xValue?.toString() || '',
              value: split.count || 0
            });
          }
        }
      }

      seriesMap.forEach((points, name) => {
        series.push({ name, series: points });
      });

      return series;
    }

    // Single series - wrap in series format
    const xField = config.x_field || config.timestamp_field || 'timestamp';
    const yField = config.y_field || 'count';

    return [{
      name: config.y_field || 'Value',
      series: data.map((item: any) => ({
        name: this.getNestedValue(item, xField)?.toString() || '',
        value: Number(this.getNestedValue(item, yField)) || 0
      }))
    }];
  }

  /**
   * Transform API data to D3 timeline format.
   */
  transformTimelineData(data: any[]): TimelineItem[] {
    if (!data || data.length === 0) return [];

    return data.map((item: any, index: number) => ({
      id: item.id || `event-${index}`,
      timestamp: new Date(item['@timestamp'] || item.timestamp),
      title: item.message || item.event?.action || item.event_type || 'Event',
      category: item.event?.category?.[0] || item.category || 'unknown',
      data: item
    }));
  }

  /**
   * Handle timeline event selection from workbook tile.
   */
  onTileEventSelected(tileId: string, event: TimelineItem): void {
    this.logger.debug('Timeline event selected', { component: 'WorkbookViewerComponent', tileId, eventId: event.id });
    // Could open a detail panel or navigate to event details
    this.snackBar.open(`Event: ${event.title}`, 'Close', { duration: 3000 });
  }

  /**
   * Export workbook to PDF using html2canvas and jsPDF.
   */
  async exportToPdf(): Promise<void> {
    const element = document.querySelector('.tiles-container') as HTMLElement;
    if (!element) {
      this.snackBar.open('Unable to export: tiles container not found', 'Close', { duration: 3000 });
      return;
    }

    this.isExporting.set(true);
    this.snackBar.open('Generating PDF...', '', { duration: 2000 });

    try {
      // Dynamically import html2canvas and jsPDF
      const [html2canvasModule, jsPDFModule] = await Promise.all([
        import('html2canvas'),
        import('jspdf')
      ]);
      const html2canvas = html2canvasModule.default;
      const jsPDF = jsPDFModule.default;

      const canvas = await html2canvas(element, {
        backgroundColor: '#1e1e1e',
        scale: 2,
        useCORS: true,
        logging: false
      });

      const imgData = canvas.toDataURL('image/png');
      const imgWidth = canvas.width;
      const imgHeight = canvas.height;

      // Determine orientation based on aspect ratio
      const orientation = imgWidth > imgHeight ? 'landscape' : 'portrait';

      const pdf = new jsPDF({
        orientation,
        unit: 'px',
        format: [imgWidth / 2, imgHeight / 2] // Scale down for reasonable file size
      });

      pdf.addImage(imgData, 'PNG', 0, 0, imgWidth / 2, imgHeight / 2);

      const filename = `${this.workbook()?.name || 'workbook'}-${new Date().toISOString().split('T')[0]}.pdf`;
      pdf.save(filename);

      this.snackBar.open('PDF exported successfully', 'Close', { duration: 3000 });
    } catch (error) {
      this.logger.error('Failed to export PDF', error as Error, { component: 'WorkbookViewerComponent' });
      this.snackBar.open('Failed to export PDF. Make sure dependencies are installed.', 'Close', { duration: 5000 });
    } finally {
      this.isExporting.set(false);
    }
  }
}
