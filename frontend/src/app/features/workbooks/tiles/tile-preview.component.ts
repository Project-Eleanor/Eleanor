import { Component, Input, signal, OnChanges, SimpleChanges } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { NgxChartsModule } from '@swimlane/ngx-charts';
import { TileDefinition, TileType, ChartType } from '../../../shared/models/workbook.model';

@Component({
  selector: 'app-tile-preview',
  standalone: true,
  imports: [
    CommonModule,
    MatIconModule,
    MatProgressSpinnerModule,
    NgxChartsModule,
  ],
  template: `
    <div class="tile-preview" [class.editing]="isEditing">
      @switch (tile.type) {
        @case ('chart') {
          <div class="chart-preview">
            @if (isEditing && !tile.config.query) {
              <div class="placeholder">
                <mat-icon>bar_chart</mat-icon>
                <span>Configure query to see chart</span>
              </div>
            } @else {
              @switch (tile.config.chart_type) {
                @case ('bar') {
                  <ngx-charts-bar-vertical
                    [results]="sampleBarData"
                    [xAxis]="true"
                    [yAxis]="true"
                    [legend]="false"
                    [scheme]="colorScheme">
                  </ngx-charts-bar-vertical>
                }
                @case ('line') {
                  <ngx-charts-line-chart
                    [results]="sampleLineData"
                    [xAxis]="true"
                    [yAxis]="true"
                    [legend]="false"
                    [autoScale]="true"
                    [scheme]="colorScheme">
                  </ngx-charts-line-chart>
                }
                @case ('pie') {
                  <ngx-charts-pie-chart
                    [results]="sampleBarData"
                    [legend]="true"
                    [doughnut]="false"
                    [scheme]="colorScheme">
                  </ngx-charts-pie-chart>
                }
                @case ('area') {
                  <ngx-charts-area-chart
                    [results]="sampleLineData"
                    [xAxis]="true"
                    [yAxis]="true"
                    [legend]="false"
                    [autoScale]="true"
                    [gradient]="true"
                    [scheme]="colorScheme">
                  </ngx-charts-area-chart>
                }
                @default {
                  <ngx-charts-bar-vertical
                    [results]="sampleBarData"
                    [xAxis]="true"
                    [yAxis]="true"
                    [legend]="false"
                    [scheme]="colorScheme">
                  </ngx-charts-bar-vertical>
                }
              }
            }
          </div>
        }
        @case ('table') {
          <div class="table-preview">
            @if (isEditing && !tile.config.query) {
              <div class="placeholder">
                <mat-icon>table_chart</mat-icon>
                <span>Configure query to see table</span>
              </div>
            } @else {
              <table>
                <thead>
                  <tr>
                    @for (col of tile.config.columns || ['timestamp', 'message']; track col) {
                      <th>{{ col }}</th>
                    }
                  </tr>
                </thead>
                <tbody>
                  @for (row of sampleTableData; track $index) {
                    <tr>
                      @for (col of tile.config.columns || ['timestamp', 'message']; track col) {
                        <td>{{ row[col] || '-' }}</td>
                      }
                    </tr>
                  }
                </tbody>
              </table>
            }
          </div>
        }
        @case ('metric') {
          <div class="metric-preview">
            @if (isEditing && !tile.config.query) {
              <div class="placeholder">
                <mat-icon>speed</mat-icon>
                <span>Configure query</span>
              </div>
            } @else {
              <span class="metric-value">1,234</span>
              <span class="metric-label">{{ tile.config.field || 'Count' }}</span>
            }
          </div>
        }
        @case ('timeline') {
          <div class="timeline-preview">
            @if (isEditing && !tile.config.query) {
              <div class="placeholder">
                <mat-icon>timeline</mat-icon>
                <span>Configure query</span>
              </div>
            } @else {
              <div class="timeline-mock">
                <div class="timeline-bar">
                  @for (dot of timelineDots; track dot.pos) {
                    <div class="timeline-dot" [style.left.%]="dot.pos" [style.background]="dot.color"></div>
                  }
                </div>
                <div class="timeline-axis">
                  <span>00:00</span>
                  <span>06:00</span>
                  <span>12:00</span>
                  <span>18:00</span>
                  <span>24:00</span>
                </div>
              </div>
            }
          </div>
        }
        @case ('markdown') {
          <div class="markdown-preview">
            @if (tile.config.content) {
              <div class="markdown-content" [innerHTML]="renderMarkdown(tile.config.content)"></div>
            } @else {
              <div class="placeholder">
                <mat-icon>text_fields</mat-icon>
                <span>Enter markdown content</span>
              </div>
            }
          </div>
        }
        @default {
          <div class="unknown-preview">
            <mat-icon>widgets</mat-icon>
            <span>Unknown tile type</span>
          </div>
        }
      }
    </div>
  `,
  styles: [`
    .tile-preview {
      width: 100%;
      height: 100%;
      display: flex;
      align-items: center;
      justify-content: center;
      overflow: hidden;
    }

    .tile-preview.editing {
      min-height: 120px;
    }

    .placeholder {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      color: #666;
      text-align: center;
      padding: 16px;

      mat-icon {
        font-size: 32px;
        width: 32px;
        height: 32px;
        margin-bottom: 8px;
        opacity: 0.5;
      }

      span {
        font-size: 12px;
      }
    }

    .chart-preview {
      width: 100%;
      height: 100%;

      ngx-charts-bar-vertical,
      ngx-charts-line-chart,
      ngx-charts-pie-chart,
      ngx-charts-area-chart {
        width: 100%;
        height: 100%;
      }
    }

    .table-preview {
      width: 100%;
      height: 100%;
      overflow: auto;

      table {
        width: 100%;
        border-collapse: collapse;
        font-size: 11px;
      }

      th, td {
        padding: 6px 8px;
        text-align: left;
        border-bottom: 1px solid #333;
      }

      th {
        background: #252525;
        font-weight: 500;
        position: sticky;
        top: 0;
      }
    }

    .metric-preview {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      text-align: center;

      .metric-value {
        font-size: 36px;
        font-weight: 600;
        color: #4CAF50;
      }

      .metric-label {
        font-size: 12px;
        color: #888;
        margin-top: 4px;
      }
    }

    .timeline-preview {
      width: 100%;
      padding: 16px;
    }

    .timeline-mock {
      width: 100%;
    }

    .timeline-bar {
      position: relative;
      height: 24px;
      background: #252525;
      border-radius: 4px;
      margin-bottom: 8px;
    }

    .timeline-dot {
      position: absolute;
      width: 8px;
      height: 8px;
      border-radius: 50%;
      top: 50%;
      transform: translateY(-50%);
    }

    .timeline-axis {
      display: flex;
      justify-content: space-between;
      font-size: 10px;
      color: #666;
    }

    .markdown-preview {
      width: 100%;
      height: 100%;
      padding: 8px;
      overflow: auto;
    }

    .markdown-content {
      font-size: 13px;
      line-height: 1.5;

      :host ::ng-deep {
        h1 { font-size: 18px; margin: 0 0 8px; }
        h2 { font-size: 16px; margin: 0 0 8px; }
        h3 { font-size: 14px; margin: 0 0 8px; }
        p { margin: 0 0 8px; }
        ul, ol { margin: 0 0 8px; padding-left: 20px; }
        code { background: #333; padding: 2px 4px; border-radius: 2px; font-size: 12px; }
        pre { background: #333; padding: 8px; border-radius: 4px; overflow-x: auto; }
      }
    }

    .unknown-preview {
      display: flex;
      flex-direction: column;
      align-items: center;
      color: #666;

      mat-icon {
        font-size: 32px;
        width: 32px;
        height: 32px;
        margin-bottom: 8px;
      }
    }
  `]
})
export class TilePreviewComponent implements OnChanges {
  @Input() tile!: TileDefinition;
  @Input() isEditing = false;

  colorScheme = 'cool';

  sampleBarData = [
    { name: 'Category A', value: 45 },
    { name: 'Category B', value: 32 },
    { name: 'Category C', value: 28 },
    { name: 'Category D', value: 18 }
  ];

  sampleLineData = [
    {
      name: 'Series 1',
      series: [
        { name: '00:00', value: 10 },
        { name: '06:00', value: 25 },
        { name: '12:00', value: 45 },
        { name: '18:00', value: 32 },
        { name: '24:00', value: 15 }
      ]
    }
  ];

  sampleTableData: Record<string, string>[] = [
    { timestamp: '2024-01-15 10:30:00', message: 'Event logged', host: 'server1' },
    { timestamp: '2024-01-15 10:31:00', message: 'Process started', host: 'server1' },
    { timestamp: '2024-01-15 10:32:00', message: 'Connection established', host: 'server2' }
  ];

  timelineDots = [
    { pos: 10, color: '#4CAF50' },
    { pos: 25, color: '#FF9800' },
    { pos: 35, color: '#4CAF50' },
    { pos: 50, color: '#F44336' },
    { pos: 65, color: '#4CAF50' },
    { pos: 80, color: '#2196F3' },
    { pos: 90, color: '#4CAF50' }
  ];

  ngOnChanges(changes: SimpleChanges): void {
    // Handle tile changes if needed
  }

  renderMarkdown(content: string): string {
    if (!content) return '';

    // Simple markdown rendering
    let html = content
      // Headers
      .replace(/^### (.*$)/gm, '<h3>$1</h3>')
      .replace(/^## (.*$)/gm, '<h2>$1</h2>')
      .replace(/^# (.*$)/gm, '<h1>$1</h1>')
      // Bold
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      // Italic
      .replace(/\*(.*?)\*/g, '<em>$1</em>')
      // Code
      .replace(/`(.*?)`/g, '<code>$1</code>')
      // Line breaks
      .replace(/\n/g, '<br>');

    return html;
  }
}
