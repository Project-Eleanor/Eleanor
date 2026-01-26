import { Component, Inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatDialogModule, MatDialogRef, MAT_DIALOG_DATA } from '@angular/material/dialog';
import { MatTabsModule } from '@angular/material/tabs';
import { MatChipsModule } from '@angular/material/chips';
import { MatDividerModule } from '@angular/material/divider';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatTooltipModule } from '@angular/material/tooltip';
import { TileDefinition, TileType, TileConfig, ChartType } from '../../../shared/models/workbook.model';
import { TilePreviewComponent } from './tile-preview.component';

interface SchemaField {
  name: string;
  type: string;
  description?: string;
}

@Component({
  selector: 'app-tile-config-dialog',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatButtonModule,
    MatIconModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    MatDialogModule,
    MatTabsModule,
    MatChipsModule,
    MatDividerModule,
    MatProgressSpinnerModule,
    MatTooltipModule,
    TilePreviewComponent,
  ],
  template: `
    <div class="tile-config-dialog">
      <div class="dialog-header">
        <h2>{{ isNew ? 'Add' : 'Edit' }} {{ getTypeLabel(tile.type) }} Tile</h2>
        <button mat-icon-button (click)="close()">
          <mat-icon>close</mat-icon>
        </button>
      </div>

      <div class="dialog-body">
        <!-- Left: Configuration -->
        <div class="config-panel">
          <mat-tab-group>
            <!-- General Tab -->
            <mat-tab label="General">
              <div class="tab-content">
                <mat-form-field appearance="outline">
                  <mat-label>Title</mat-label>
                  <input matInput [(ngModel)]="tile.title">
                </mat-form-field>

                @if (tile.type === 'chart') {
                  <mat-form-field appearance="outline">
                    <mat-label>Chart Type</mat-label>
                    <mat-select [(ngModel)]="tile.config.chart_type">
                      <mat-option value="bar">
                        <mat-icon>bar_chart</mat-icon>
                        Bar Chart
                      </mat-option>
                      <mat-option value="line">
                        <mat-icon>show_chart</mat-icon>
                        Line Chart
                      </mat-option>
                      <mat-option value="pie">
                        <mat-icon>pie_chart</mat-icon>
                        Pie Chart
                      </mat-option>
                      <mat-option value="area">
                        <mat-icon>area_chart</mat-icon>
                        Area Chart
                      </mat-option>
                    </mat-select>
                  </mat-form-field>
                }

                <div class="size-fields">
                  <mat-form-field appearance="outline">
                    <mat-label>Width (columns)</mat-label>
                    <mat-select [(ngModel)]="tile.position.width">
                      @for (w of [1,2,3,4,5,6,8,10,12]; track w) {
                        <mat-option [value]="w">{{ w }}</mat-option>
                      }
                    </mat-select>
                  </mat-form-field>
                  <mat-form-field appearance="outline">
                    <mat-label>Height (rows)</mat-label>
                    <mat-select [(ngModel)]="tile.position.height">
                      @for (h of [1,2,3,4,5,6,8]; track h) {
                        <mat-option [value]="h">{{ h }}</mat-option>
                      }
                    </mat-select>
                  </mat-form-field>
                </div>
              </div>
            </mat-tab>

            <!-- Query Tab -->
            @if (tile.type !== 'markdown') {
              <mat-tab label="Data">
                <div class="tab-content">
                  <mat-form-field appearance="outline" class="full-width">
                    <mat-label>Query (KQL)</mat-label>
                    <textarea matInput
                              [(ngModel)]="tile.config.query"
                              rows="6"
                              placeholder="Enter KQL query..."></textarea>
                    <mat-hint>Use KQL to query your data</mat-hint>
                  </mat-form-field>

                  <!-- Schema Fields -->
                  <div class="schema-section">
                    <h4>Available Fields</h4>
                    <div class="schema-chips">
                      @for (field of schemaFields; track field.name) {
                        <mat-chip (click)="insertField(field.name)" matTooltip="{{ field.description }}">
                          {{ field.name }}
                          <span class="field-type">{{ field.type }}</span>
                        </mat-chip>
                      }
                    </div>
                  </div>

                  <mat-divider></mat-divider>

                  <!-- Chart-specific fields -->
                  @if (tile.type === 'chart') {
                    <h4>Chart Configuration</h4>
                    <div class="field-grid">
                      <mat-form-field appearance="outline">
                        <mat-label>X-Axis Field</mat-label>
                        <mat-select [(ngModel)]="tile.config.x_field">
                          @for (field of schemaFields; track field.name) {
                            <mat-option [value]="field.name">{{ field.name }}</mat-option>
                          }
                        </mat-select>
                      </mat-form-field>
                      <mat-form-field appearance="outline">
                        <mat-label>Y-Axis Field</mat-label>
                        <mat-select [(ngModel)]="tile.config.y_field">
                          @for (field of schemaFields; track field.name) {
                            <mat-option [value]="field.name">{{ field.name }}</mat-option>
                          }
                        </mat-select>
                      </mat-form-field>
                      <mat-form-field appearance="outline">
                        <mat-label>Group By</mat-label>
                        <mat-select [(ngModel)]="tile.config.group_by">
                          <mat-option value="">None</mat-option>
                          @for (field of schemaFields; track field.name) {
                            <mat-option [value]="field.name">{{ field.name }}</mat-option>
                          }
                        </mat-select>
                      </mat-form-field>
                      <mat-form-field appearance="outline">
                        <mat-label>Time Interval</mat-label>
                        <mat-select [(ngModel)]="tile.config.interval">
                          <mat-option value="">Auto</mat-option>
                          <mat-option value="1m">1 minute</mat-option>
                          <mat-option value="5m">5 minutes</mat-option>
                          <mat-option value="1h">1 hour</mat-option>
                          <mat-option value="1d">1 day</mat-option>
                        </mat-select>
                      </mat-form-field>
                    </div>
                  }

                  @if (tile.type === 'table') {
                    <h4>Table Configuration</h4>
                    <mat-form-field appearance="outline" class="full-width">
                      <mat-label>Columns</mat-label>
                      <mat-select [(ngModel)]="selectedColumns" multiple>
                        @for (field of schemaFields; track field.name) {
                          <mat-option [value]="field.name">{{ field.name }}</mat-option>
                        }
                      </mat-select>
                    </mat-form-field>
                    <div class="field-grid">
                      <mat-form-field appearance="outline">
                        <mat-label>Page Size</mat-label>
                        <mat-select [(ngModel)]="tile.config.page_size">
                          <mat-option [value]="5">5</mat-option>
                          <mat-option [value]="10">10</mat-option>
                          <mat-option [value]="25">25</mat-option>
                          <mat-option [value]="50">50</mat-option>
                        </mat-select>
                      </mat-form-field>
                      <mat-form-field appearance="outline">
                        <mat-label>Sort Field</mat-label>
                        <mat-select [(ngModel)]="sortField">
                          @for (field of schemaFields; track field.name) {
                            <mat-option [value]="field.name">{{ field.name }}</mat-option>
                          }
                        </mat-select>
                      </mat-form-field>
                    </div>
                  }

                  @if (tile.type === 'metric') {
                    <h4>Metric Configuration</h4>
                    <div class="field-grid">
                      <mat-form-field appearance="outline">
                        <mat-label>Aggregation</mat-label>
                        <mat-select [(ngModel)]="tile.config.aggregation">
                          <mat-option value="count">Count</mat-option>
                          <mat-option value="sum">Sum</mat-option>
                          <mat-option value="avg">Average</mat-option>
                          <mat-option value="min">Minimum</mat-option>
                          <mat-option value="max">Maximum</mat-option>
                          <mat-option value="cardinality">Unique Count</mat-option>
                        </mat-select>
                      </mat-form-field>
                      <mat-form-field appearance="outline">
                        <mat-label>Field</mat-label>
                        <mat-select [(ngModel)]="tile.config.field">
                          @for (field of schemaFields; track field.name) {
                            <mat-option [value]="field.name">{{ field.name }}</mat-option>
                          }
                        </mat-select>
                      </mat-form-field>
                    </div>
                  }
                </div>
              </mat-tab>
            } @else {
              <mat-tab label="Content">
                <div class="tab-content">
                  <mat-form-field appearance="outline" class="full-width">
                    <mat-label>Markdown Content</mat-label>
                    <textarea matInput
                              [(ngModel)]="tile.config.content"
                              rows="15"
                              placeholder="Enter markdown..."></textarea>
                  </mat-form-field>
                  <div class="markdown-help">
                    <span># Heading</span>
                    <span>**bold**</span>
                    <span>*italic*</span>
                    <span>\`code\`</span>
                    <span>- list item</span>
                  </div>
                </div>
              </mat-tab>
            }

            <!-- Options Tab -->
            <mat-tab label="Options">
              <div class="tab-content">
                <mat-form-field appearance="outline">
                  <mat-label>Refresh Interval</mat-label>
                  <mat-select [(ngModel)]="tile.config.refresh_interval">
                    <mat-option [value]="0">Manual only</mat-option>
                    <mat-option [value]="30">30 seconds</mat-option>
                    <mat-option [value]="60">1 minute</mat-option>
                    <mat-option [value]="300">5 minutes</mat-option>
                    <mat-option [value]="900">15 minutes</mat-option>
                  </mat-select>
                </mat-form-field>

                <mat-form-field appearance="outline">
                  <mat-label>Result Limit</mat-label>
                  <mat-select [(ngModel)]="tile.config.limit">
                    <mat-option [value]="10">10</mat-option>
                    <mat-option [value]="25">25</mat-option>
                    <mat-option [value]="50">50</mat-option>
                    <mat-option [value]="100">100</mat-option>
                    <mat-option [value]="500">500</mat-option>
                  </mat-select>
                </mat-form-field>
              </div>
            </mat-tab>
          </mat-tab-group>
        </div>

        <!-- Right: Preview -->
        <div class="preview-panel">
          <h4>Preview</h4>
          <div class="preview-container">
            <app-tile-preview [tile]="tile" [isEditing]="true"></app-tile-preview>
          </div>
          <button mat-stroked-button (click)="testQuery()" [disabled]="isTestingQuery()">
            @if (isTestingQuery()) {
              <mat-spinner diameter="18"></mat-spinner>
            } @else {
              <mat-icon>play_arrow</mat-icon>
            }
            Test Query
          </button>
        </div>
      </div>

      <div class="dialog-actions">
        <button mat-button (click)="close()">Cancel</button>
        <button mat-flat-button color="primary" (click)="save()">
          {{ isNew ? 'Add Tile' : 'Save Changes' }}
        </button>
      </div>
    </div>
  `,
  styles: [`
    .tile-config-dialog {
      display: flex;
      flex-direction: column;
      width: 900px;
      max-width: 90vw;
      max-height: 85vh;
    }

    .dialog-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 16px 24px;
      border-bottom: 1px solid #333;

      h2 {
        margin: 0;
        font-size: 18px;
        font-weight: 500;
      }
    }

    .dialog-body {
      flex: 1;
      display: flex;
      gap: 24px;
      padding: 24px;
      overflow: hidden;
    }

    .config-panel {
      flex: 1;
      min-width: 0;
      display: flex;
      flex-direction: column;
    }

    .preview-panel {
      width: 300px;
      display: flex;
      flex-direction: column;

      h4 {
        margin: 0 0 12px;
        font-size: 12px;
        color: #888;
        text-transform: uppercase;
      }
    }

    .preview-container {
      flex: 1;
      background: #1e1e1e;
      border: 1px solid #333;
      border-radius: 8px;
      padding: 16px;
      margin-bottom: 12px;
      overflow: hidden;
    }

    mat-tab-group {
      flex: 1;
    }

    .tab-content {
      padding: 16px 0;
      overflow-y: auto;
      max-height: 400px;
    }

    mat-form-field {
      width: 100%;
      margin-bottom: 12px;
    }

    .full-width {
      width: 100%;
    }

    .size-fields, .field-grid {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 12px;

      mat-form-field {
        margin-bottom: 0;
      }
    }

    .schema-section {
      margin: 16px 0;

      h4 {
        margin: 0 0 8px;
        font-size: 12px;
        color: #888;
        text-transform: uppercase;
      }
    }

    .schema-chips {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;

      mat-chip {
        cursor: pointer;
        font-size: 12px;

        .field-type {
          margin-left: 4px;
          opacity: 0.6;
          font-size: 10px;
        }
      }
    }

    h4 {
      margin: 16px 0 12px;
      font-size: 12px;
      color: #888;
      text-transform: uppercase;
    }

    .markdown-help {
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      font-size: 12px;
      color: #666;
      font-family: monospace;
    }

    .dialog-actions {
      display: flex;
      justify-content: flex-end;
      gap: 8px;
      padding: 16px 24px;
      border-top: 1px solid #333;
    }
  `]
})
export class TileConfigDialogComponent {
  tile: TileDefinition;
  isNew: boolean;
  isTestingQuery = signal(false);

  selectedColumns: string[] = [];
  sortField = '';

  schemaFields: SchemaField[] = [
    { name: '@timestamp', type: 'date', description: 'Event timestamp' },
    { name: 'message', type: 'text', description: 'Event message' },
    { name: 'host.name', type: 'keyword', description: 'Hostname' },
    { name: 'user.name', type: 'keyword', description: 'Username' },
    { name: 'event.action', type: 'keyword', description: 'Event action' },
    { name: 'event.category', type: 'keyword', description: 'Event category' },
    { name: 'source.ip', type: 'ip', description: 'Source IP address' },
    { name: 'destination.ip', type: 'ip', description: 'Destination IP' },
    { name: 'process.name', type: 'keyword', description: 'Process name' },
    { name: 'file.path', type: 'keyword', description: 'File path' }
  ];

  constructor(
    private dialogRef: MatDialogRef<TileConfigDialogComponent>,
    @Inject(MAT_DIALOG_DATA) public data: { tile: TileDefinition; isNew: boolean }
  ) {
    this.tile = JSON.parse(JSON.stringify(data.tile));
    this.isNew = data.isNew;
    this.selectedColumns = this.tile.config.columns || [];
  }

  getTypeLabel(type: TileType): string {
    const labels: Record<TileType, string> = {
      chart: 'Chart',
      table: 'Table',
      metric: 'Metric',
      timeline: 'Timeline',
      markdown: 'Markdown',
      query: 'Query'
    };
    return labels[type] || type;
  }

  insertField(fieldName: string): void {
    const query = this.tile.config.query || '';
    this.tile.config.query = query + (query ? ' ' : '') + fieldName;
  }

  async testQuery(): Promise<void> {
    this.isTestingQuery.set(true);
    // Simulate query test
    await new Promise(resolve => setTimeout(resolve, 1000));
    this.isTestingQuery.set(false);
  }

  save(): void {
    if (this.tile.type === 'table') {
      this.tile.config.columns = this.selectedColumns;
    }
    this.dialogRef.close(this.tile);
  }

  close(): void {
    this.dialogRef.close();
  }
}
