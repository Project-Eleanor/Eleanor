import { Component, OnInit, signal, inject, ViewChild, ElementRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterModule } from '@angular/router';
import { CdkDragDrop, CdkDragEnd, DragDropModule } from '@angular/cdk/drag-drop';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatMenuModule } from '@angular/material/menu';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatDialogModule, MatDialog } from '@angular/material/dialog';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { MatDividerModule } from '@angular/material/divider';
import { MatSliderModule } from '@angular/material/slider';
import { MatChipsModule } from '@angular/material/chips';
import { MatTabsModule } from '@angular/material/tabs';
import { WorkbookService } from '../../core/api/workbook.service';
import {
  Workbook,
  WorkbookDefinition,
  TileDefinition,
  TileType,
  TileConfig,
  TilePosition,
  ChartType
} from '../../shared/models/workbook.model';
import { TileConfigDialogComponent } from './tiles/tile-config-dialog.component';
import { TilePreviewComponent } from './tiles/tile-preview.component';

@Component({
  selector: 'app-workbook-editor',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    RouterModule,
    DragDropModule,
    MatButtonModule,
    MatIconModule,
    MatMenuModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    MatDialogModule,
    MatProgressSpinnerModule,
    MatTooltipModule,
    MatSnackBarModule,
    MatDividerModule,
    MatSliderModule,
    MatChipsModule,
    MatTabsModule,
    TilePreviewComponent,
  ],
  template: `
    <div class="workbook-editor">
      <!-- Toolbar -->
      <div class="editor-toolbar">
        <div class="toolbar-left">
          <button mat-icon-button (click)="goBack()" matTooltip="Back">
            <mat-icon>arrow_back</mat-icon>
          </button>
          <mat-form-field appearance="outline" class="name-field">
            <input matInput [(ngModel)]="workbookName" placeholder="Workbook Name">
          </mat-form-field>
        </div>

        <div class="toolbar-center">
          <button mat-stroked-button [matMenuTriggerFor]="addTileMenu">
            <mat-icon>add</mat-icon>
            Add Tile
          </button>
          <mat-menu #addTileMenu="matMenu">
            <button mat-menu-item (click)="addTile('chart')">
              <mat-icon>bar_chart</mat-icon>
              Chart
            </button>
            <button mat-menu-item (click)="addTile('table')">
              <mat-icon>table_chart</mat-icon>
              Table
            </button>
            <button mat-menu-item (click)="addTile('metric')">
              <mat-icon>speed</mat-icon>
              Metric
            </button>
            <button mat-menu-item (click)="addTile('timeline')">
              <mat-icon>timeline</mat-icon>
              Timeline
            </button>
            <button mat-menu-item (click)="addTile('markdown')">
              <mat-icon>text_fields</mat-icon>
              Markdown
            </button>
          </mat-menu>

          <mat-divider vertical></mat-divider>

          <button mat-icon-button (click)="undo()" [disabled]="!canUndo()" matTooltip="Undo">
            <mat-icon>undo</mat-icon>
          </button>
          <button mat-icon-button (click)="redo()" [disabled]="!canRedo()" matTooltip="Redo">
            <mat-icon>redo</mat-icon>
          </button>

          <mat-divider vertical></mat-divider>

          <button mat-icon-button [matMenuTriggerFor]="layoutMenu" matTooltip="Layout Settings">
            <mat-icon>grid_view</mat-icon>
          </button>
          <mat-menu #layoutMenu="matMenu">
            <div class="menu-setting">
              <span>Columns</span>
              <mat-slider min="6" max="24" step="2">
                <input matSliderThumb [(ngModel)]="gridColumns" (change)="updateLayout()">
              </mat-slider>
              <span class="slider-value">{{ gridColumns }}</span>
            </div>
            <div class="menu-setting">
              <span>Row Height</span>
              <mat-slider min="40" max="100" step="10">
                <input matSliderThumb [(ngModel)]="rowHeight" (change)="updateLayout()">
              </mat-slider>
              <span class="slider-value">{{ rowHeight }}px</span>
            </div>
          </mat-menu>
        </div>

        <div class="toolbar-right">
          <button mat-stroked-button (click)="previewWorkbook()" matTooltip="Preview">
            <mat-icon>visibility</mat-icon>
            Preview
          </button>
          <button mat-flat-button color="primary" (click)="saveWorkbook()" [disabled]="isSaving()">
            @if (isSaving()) {
              <mat-spinner diameter="18"></mat-spinner>
            } @else {
              <mat-icon>save</mat-icon>
            }
            Save
          </button>
        </div>
      </div>

      <!-- Main Content -->
      <div class="editor-content">
        <!-- Tile Palette -->
        <div class="tile-palette">
          <h3>Tiles</h3>
          <div class="palette-tiles">
            @for (tile of tiles(); track tile.id) {
              <div class="palette-tile"
                   [class.selected]="selectedTile()?.id === tile.id"
                   (click)="selectTile(tile)">
                <mat-icon>{{ getTileIcon(tile.type) }}</mat-icon>
                <span class="tile-name">{{ tile.title }}</span>
                <button mat-icon-button class="edit-btn" (click)="editTile(tile, $event)" matTooltip="Edit">
                  <mat-icon>edit</mat-icon>
                </button>
                <button mat-icon-button class="delete-btn" (click)="deleteTile(tile, $event)" matTooltip="Delete">
                  <mat-icon>delete</mat-icon>
                </button>
              </div>
            }
            @if (tiles().length === 0) {
              <div class="empty-palette">
                <p>No tiles yet</p>
                <span>Click "Add Tile" to get started</span>
              </div>
            }
          </div>
        </div>

        <!-- Canvas -->
        <div class="canvas-container">
          <div class="canvas"
               [style.--columns]="gridColumns"
               [style.--row-height]="rowHeight + 'px'"
               #canvas>
            @for (tile of tiles(); track tile.id) {
              <div class="canvas-tile"
                   cdkDrag
                   [cdkDragData]="tile"
                   [style.grid-column]="(tile.position.x + 1) + ' / span ' + tile.position.width"
                   [style.grid-row]="(tile.position.y + 1) + ' / span ' + tile.position.height"
                   [class.selected]="selectedTile()?.id === tile.id"
                   (click)="selectTile(tile)"
                   (cdkDragEnded)="onTileDragEnd($event, tile)">
                <div class="tile-header">
                  <span class="tile-title">{{ tile.title }}</span>
                  <div class="tile-actions">
                    <button mat-icon-button (click)="editTile(tile, $event)">
                      <mat-icon>settings</mat-icon>
                    </button>
                  </div>
                </div>
                <div class="tile-content">
                  <app-tile-preview
                    [tile]="tile"
                    [isEditing]="true"
                  ></app-tile-preview>
                </div>
                <!-- Resize Handles -->
                <div class="resize-handle resize-e" (mousedown)="startResize($event, tile, 'e')"></div>
                <div class="resize-handle resize-s" (mousedown)="startResize($event, tile, 's')"></div>
                <div class="resize-handle resize-se" (mousedown)="startResize($event, tile, 'se')"></div>
              </div>
            }

            <!-- Grid overlay for positioning -->
            <div class="grid-overlay">
              @for (row of gridRows; track row) {
                @for (col of gridCols; track col) {
                  <div class="grid-cell"
                       [class.highlight]="isDropTarget(col, row)"
                       (dragover)="onGridDragOver($event, col, row)"
                       (drop)="onGridDrop($event, col, row)">
                  </div>
                }
              }
            </div>
          </div>
        </div>

        <!-- Properties Panel -->
        @if (selectedTile()) {
          <div class="properties-panel">
            <div class="panel-header">
              <h3>Properties</h3>
              <button mat-icon-button (click)="clearSelection()">
                <mat-icon>close</mat-icon>
              </button>
            </div>

            <mat-tab-group>
              <!-- General Tab -->
              <mat-tab label="General">
                <div class="panel-content">
                  <mat-form-field appearance="outline">
                    <mat-label>Title</mat-label>
                    <input matInput [(ngModel)]="selectedTile()!.title" (change)="onTileChange()">
                  </mat-form-field>

                  <div class="position-grid">
                    <mat-form-field appearance="outline">
                      <mat-label>X</mat-label>
                      <input matInput type="number" [(ngModel)]="selectedTile()!.position.x" (change)="onTileChange()">
                    </mat-form-field>
                    <mat-form-field appearance="outline">
                      <mat-label>Y</mat-label>
                      <input matInput type="number" [(ngModel)]="selectedTile()!.position.y" (change)="onTileChange()">
                    </mat-form-field>
                    <mat-form-field appearance="outline">
                      <mat-label>Width</mat-label>
                      <input matInput type="number" [(ngModel)]="selectedTile()!.position.width" (change)="onTileChange()">
                    </mat-form-field>
                    <mat-form-field appearance="outline">
                      <mat-label>Height</mat-label>
                      <input matInput type="number" [(ngModel)]="selectedTile()!.position.height" (change)="onTileChange()">
                    </mat-form-field>
                  </div>
                </div>
              </mat-tab>

              <!-- Query Tab -->
              <mat-tab label="Query">
                <div class="panel-content">
                  @if (selectedTile()!.type !== 'markdown') {
                    <mat-form-field appearance="outline" class="full-width">
                      <mat-label>Query (KQL)</mat-label>
                      <textarea matInput
                                [(ngModel)]="selectedTile()!.config.query"
                                rows="6"
                                (change)="onTileChange()"
                                placeholder="Enter KQL query..."></textarea>
                    </mat-form-field>

                    @if (selectedTile()!.type === 'chart') {
                      <mat-form-field appearance="outline">
                        <mat-label>Chart Type</mat-label>
                        <mat-select [(ngModel)]="selectedTile()!.config.chart_type" (selectionChange)="onTileChange()">
                          <mat-option value="bar">Bar</mat-option>
                          <mat-option value="line">Line</mat-option>
                          <mat-option value="pie">Pie</mat-option>
                          <mat-option value="area">Area</mat-option>
                        </mat-select>
                      </mat-form-field>

                      <mat-form-field appearance="outline">
                        <mat-label>X Field</mat-label>
                        <input matInput [(ngModel)]="selectedTile()!.config.x_field" (change)="onTileChange()">
                      </mat-form-field>

                      <mat-form-field appearance="outline">
                        <mat-label>Y Field</mat-label>
                        <input matInput [(ngModel)]="selectedTile()!.config.y_field" (change)="onTileChange()">
                      </mat-form-field>

                      <mat-form-field appearance="outline">
                        <mat-label>Group By</mat-label>
                        <input matInput [(ngModel)]="selectedTile()!.config.group_by" (change)="onTileChange()">
                      </mat-form-field>
                    }

                    @if (selectedTile()!.type === 'table') {
                      <mat-form-field appearance="outline">
                        <mat-label>Columns (comma-separated)</mat-label>
                        <input matInput
                               [ngModel]="selectedTile()!.config.columns?.join(',')"
                               (ngModelChange)="updateColumns($event)"
                               (change)="onTileChange()">
                      </mat-form-field>

                      <mat-form-field appearance="outline">
                        <mat-label>Page Size</mat-label>
                        <mat-select [(ngModel)]="selectedTile()!.config.page_size" (selectionChange)="onTileChange()">
                          <mat-option [value]="5">5</mat-option>
                          <mat-option [value]="10">10</mat-option>
                          <mat-option [value]="25">25</mat-option>
                          <mat-option [value]="50">50</mat-option>
                        </mat-select>
                      </mat-form-field>
                    }

                    @if (selectedTile()!.type === 'metric') {
                      <mat-form-field appearance="outline">
                        <mat-label>Aggregation</mat-label>
                        <mat-select [(ngModel)]="selectedTile()!.config.aggregation" (selectionChange)="onTileChange()">
                          <mat-option value="count">Count</mat-option>
                          <mat-option value="sum">Sum</mat-option>
                          <mat-option value="avg">Average</mat-option>
                          <mat-option value="cardinality">Unique Count</mat-option>
                        </mat-select>
                      </mat-form-field>

                      <mat-form-field appearance="outline">
                        <mat-label>Field</mat-label>
                        <input matInput [(ngModel)]="selectedTile()!.config.field" (change)="onTileChange()">
                      </mat-form-field>
                    }
                  } @else {
                    <mat-form-field appearance="outline" class="full-width">
                      <mat-label>Markdown Content</mat-label>
                      <textarea matInput
                                [(ngModel)]="selectedTile()!.config.content"
                                rows="10"
                                (change)="onTileChange()"
                                placeholder="Enter markdown..."></textarea>
                    </mat-form-field>
                  }
                </div>
              </mat-tab>

              <!-- Style Tab -->
              <mat-tab label="Style">
                <div class="panel-content">
                  <mat-form-field appearance="outline">
                    <mat-label>Refresh Interval (seconds)</mat-label>
                    <mat-select [(ngModel)]="selectedTile()!.config.refresh_interval" (selectionChange)="onTileChange()">
                      <mat-option [value]="0">Manual</mat-option>
                      <mat-option [value]="30">30 seconds</mat-option>
                      <mat-option [value]="60">1 minute</mat-option>
                      <mat-option [value]="300">5 minutes</mat-option>
                    </mat-select>
                  </mat-form-field>
                </div>
              </mat-tab>
            </mat-tab-group>
          </div>
        }
      </div>
    </div>
  `,
  styles: [`
    :host {
      display: block;
      height: 100%;
    }

    .workbook-editor {
      display: flex;
      flex-direction: column;
      height: 100%;
      background: #121212;
    }

    .editor-toolbar {
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

    .name-field {
      width: 300px;
    }

    mat-divider[vertical] {
      height: 24px;
      margin: 0 8px;
    }

    .menu-setting {
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 8px 16px;
      min-width: 250px;

      span:first-child {
        min-width: 80px;
      }

      mat-slider {
        flex: 1;
      }

      .slider-value {
        min-width: 40px;
        text-align: right;
      }
    }

    .editor-content {
      flex: 1;
      display: flex;
      overflow: hidden;
    }

    .tile-palette {
      width: 250px;
      background: #1e1e1e;
      border-right: 1px solid #333;
      display: flex;
      flex-direction: column;
      overflow: hidden;
    }

    .tile-palette h3 {
      margin: 0;
      padding: 12px 16px;
      font-size: 14px;
      border-bottom: 1px solid #333;
    }

    .palette-tiles {
      flex: 1;
      overflow-y: auto;
      padding: 8px;
    }

    .palette-tile {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 10px 12px;
      background: #252525;
      border-radius: 4px;
      margin-bottom: 4px;
      cursor: pointer;
      transition: all 0.15s ease;

      &:hover {
        background: #333;
      }

      &.selected {
        background: rgba(var(--accent-rgb), 0.2);
        border: 1px solid var(--accent);
      }

      .tile-name {
        flex: 1;
        font-size: 13px;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }

      .edit-btn, .delete-btn {
        width: 28px;
        height: 28px;
        line-height: 28px;
        opacity: 0;
      }

      &:hover .edit-btn,
      &:hover .delete-btn {
        opacity: 1;
      }

      .delete-btn:hover {
        color: var(--danger);
      }
    }

    .empty-palette {
      display: flex;
      flex-direction: column;
      align-items: center;
      padding: 32px 16px;
      color: #666;
      text-align: center;

      p {
        margin: 0 0 8px;
      }

      span {
        font-size: 12px;
      }
    }

    .canvas-container {
      flex: 1;
      overflow: auto;
      padding: 16px;
      background: #0a0a0a;
    }

    .canvas {
      position: relative;
      display: grid;
      grid-template-columns: repeat(var(--columns), 1fr);
      grid-auto-rows: var(--row-height);
      gap: 8px;
      min-height: 600px;
      background: repeating-linear-gradient(
        0deg,
        transparent,
        transparent calc(var(--row-height) - 1px),
        #333 calc(var(--row-height) - 1px),
        #333 var(--row-height)
      );
    }

    .canvas-tile {
      position: relative;
      background: #1e1e1e;
      border: 1px solid #333;
      border-radius: 8px;
      display: flex;
      flex-direction: column;
      overflow: hidden;
      cursor: move;

      &.selected {
        border-color: var(--accent);
        box-shadow: 0 0 0 2px rgba(var(--accent-rgb), 0.3);
      }

      &.cdk-drag-dragging {
        opacity: 0.7;
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.5);
      }
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
      font-size: 13px;
      font-weight: 500;
    }

    .tile-actions {
      display: flex;
      gap: 4px;

      button {
        width: 28px;
        height: 28px;
        line-height: 28px;
      }
    }

    .tile-content {
      flex: 1;
      padding: 8px;
      overflow: hidden;
    }

    .resize-handle {
      position: absolute;
      background: transparent;
      z-index: 10;
    }

    .resize-e {
      top: 0;
      right: 0;
      width: 8px;
      height: 100%;
      cursor: e-resize;
    }

    .resize-s {
      bottom: 0;
      left: 0;
      width: 100%;
      height: 8px;
      cursor: s-resize;
    }

    .resize-se {
      bottom: 0;
      right: 0;
      width: 16px;
      height: 16px;
      cursor: se-resize;
    }

    .grid-overlay {
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      bottom: 0;
      display: grid;
      grid-template-columns: repeat(var(--columns), 1fr);
      grid-auto-rows: var(--row-height);
      gap: 8px;
      pointer-events: none;
    }

    .grid-cell {
      border: 1px dashed transparent;
      transition: all 0.15s ease;
      pointer-events: auto;

      &.highlight {
        background: rgba(var(--accent-rgb), 0.1);
        border-color: var(--accent);
      }
    }

    .properties-panel {
      width: 320px;
      background: #1e1e1e;
      border-left: 1px solid #333;
      display: flex;
      flex-direction: column;
    }

    .panel-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 12px 16px;
      border-bottom: 1px solid #333;

      h3 {
        margin: 0;
        font-size: 14px;
      }
    }

    .panel-content {
      padding: 16px;
      overflow-y: auto;
    }

    mat-form-field {
      width: 100%;
      margin-bottom: 8px;
    }

    .full-width {
      width: 100%;
    }

    .position-grid {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 8px;
    }

    mat-tab-group {
      flex: 1;
      display: flex;
      flex-direction: column;
    }

    ::ng-deep .mat-mdc-tab-body-wrapper {
      flex: 1;
    }
  `]
})
export class WorkbookEditorComponent implements OnInit {
  @ViewChild('canvas') canvasEl!: ElementRef;

  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private workbookService = inject(WorkbookService);
  private dialog = inject(MatDialog);
  private snackBar = inject(MatSnackBar);

  workbookId = signal<string | null>(null);
  workbookName = 'New Workbook';
  tiles = signal<TileDefinition[]>([]);
  selectedTile = signal<TileDefinition | null>(null);
  isSaving = signal(false);

  gridColumns = 12;
  rowHeight = 60;
  gridRows = Array.from({ length: 10 }, (_, i) => i);
  gridCols = Array.from({ length: 12 }, (_, i) => i);

  private history: TileDefinition[][] = [];
  private historyIndex = -1;
  private dropTargetCell: { x: number; y: number } | null = null;
  private resizing = false;

  ngOnInit(): void {
    this.route.params.subscribe(params => {
      if (params['id'] && params['id'] !== 'new') {
        this.workbookId.set(params['id']);
        this.loadWorkbook(params['id']);
      } else {
        this.saveToHistory();
      }
    });

    this.updateGridArrays();
  }

  async loadWorkbook(id: string): Promise<void> {
    try {
      const workbook = await this.workbookService.getWorkbook(id).toPromise();
      if (workbook) {
        this.workbookName = workbook.name;
        this.tiles.set(workbook.definition.tiles);
        this.gridColumns = workbook.definition.layout?.columns || 12;
        this.rowHeight = workbook.definition.layout?.row_height || 60;
        this.updateGridArrays();
        this.saveToHistory();
      }
    } catch (error) {
      console.error('Failed to load workbook:', error);
      this.snackBar.open('Failed to load workbook', 'Close', { duration: 3000 });
    }
  }

  updateGridArrays(): void {
    this.gridCols = Array.from({ length: this.gridColumns }, (_, i) => i);
    this.gridRows = Array.from({ length: 10 }, (_, i) => i);
  }

  updateLayout(): void {
    this.updateGridArrays();
  }

  addTile(type: TileType): void {
    const newTile: TileDefinition = {
      id: `tile-${Date.now()}`,
      type,
      title: this.getDefaultTitle(type),
      position: this.findEmptyPosition(),
      config: this.getDefaultConfig(type)
    };

    this.tiles.update(list => [...list, newTile]);
    this.selectTile(newTile);
    this.saveToHistory();
  }

  private getDefaultTitle(type: TileType): string {
    const titles: Record<TileType, string> = {
      chart: 'New Chart',
      table: 'New Table',
      metric: 'New Metric',
      timeline: 'New Timeline',
      markdown: 'New Text',
      query: 'New Query'
    };
    return titles[type] || 'New Tile';
  }

  private getDefaultConfig(type: TileType): TileConfig {
    switch (type) {
      case 'chart':
        return { chart_type: 'bar', query: '', x_field: '@timestamp', y_field: 'count' };
      case 'table':
        return { query: '', columns: ['@timestamp', 'message'], page_size: 10 };
      case 'metric':
        return { query: '', aggregation: 'count' };
      case 'timeline':
        return { query: '', timestamp_field: '@timestamp' };
      case 'markdown':
        return { content: '# Heading\n\nEnter your content here.' };
      default:
        return { query: '' };
    }
  }

  private findEmptyPosition(): TilePosition {
    const tiles = this.tiles();
    let y = 0;

    while (true) {
      for (let x = 0; x <= this.gridColumns - 4; x++) {
        if (!this.isPositionOccupied(x, y, 4, 3)) {
          return { x, y, width: 4, height: 3 };
        }
      }
      y++;
      if (y > 20) break;
    }

    return { x: 0, y: tiles.length * 3, width: 4, height: 3 };
  }

  private isPositionOccupied(x: number, y: number, width: number, height: number, excludeId?: string): boolean {
    for (const tile of this.tiles()) {
      if (tile.id === excludeId) continue;

      const overlapsX = x < tile.position.x + tile.position.width && x + width > tile.position.x;
      const overlapsY = y < tile.position.y + tile.position.height && y + height > tile.position.y;

      if (overlapsX && overlapsY) return true;
    }
    return false;
  }

  selectTile(tile: TileDefinition): void {
    this.selectedTile.set(tile);
  }

  clearSelection(): void {
    this.selectedTile.set(null);
  }

  editTile(tile: TileDefinition, event: Event): void {
    event.stopPropagation();
    this.selectTile(tile);
    // Could open a full dialog here
  }

  deleteTile(tile: TileDefinition, event: Event): void {
    event.stopPropagation();
    if (confirm(`Delete tile "${tile.title}"?`)) {
      this.tiles.update(list => list.filter(t => t.id !== tile.id));
      if (this.selectedTile()?.id === tile.id) {
        this.clearSelection();
      }
      this.saveToHistory();
    }
  }

  onTileChange(): void {
    this.tiles.update(list => [...list]);
    this.saveToHistory();
  }

  updateColumns(value: string): void {
    const tile = this.selectedTile();
    if (tile) {
      tile.config.columns = value.split(',').map(c => c.trim()).filter(c => c);
    }
  }

  onTileDragEnd(event: CdkDragEnd, tile: TileDefinition): void {
    // Update position based on drop target
    if (this.dropTargetCell) {
      tile.position.x = this.dropTargetCell.x;
      tile.position.y = this.dropTargetCell.y;
      this.tiles.update(list => [...list]);
      this.saveToHistory();
    }
    this.dropTargetCell = null;
  }

  onGridDragOver(event: DragEvent, x: number, y: number): void {
    event.preventDefault();
    this.dropTargetCell = { x, y };
  }

  onGridDrop(event: DragEvent, x: number, y: number): void {
    this.dropTargetCell = { x, y };
  }

  isDropTarget(x: number, y: number): boolean {
    return this.dropTargetCell?.x === x && this.dropTargetCell?.y === y;
  }

  startResize(event: MouseEvent, tile: TileDefinition, direction: string): void {
    event.preventDefault();
    event.stopPropagation();

    this.resizing = true;
    const startX = event.clientX;
    const startY = event.clientY;
    const startWidth = tile.position.width;
    const startHeight = tile.position.height;
    const cellWidth = this.canvasEl.nativeElement.clientWidth / this.gridColumns;
    const cellHeight = this.rowHeight;

    const onMouseMove = (e: MouseEvent) => {
      const deltaX = e.clientX - startX;
      const deltaY = e.clientY - startY;

      if (direction.includes('e')) {
        tile.position.width = Math.max(1, startWidth + Math.round(deltaX / cellWidth));
      }
      if (direction.includes('s')) {
        tile.position.height = Math.max(1, startHeight + Math.round(deltaY / cellHeight));
      }

      this.tiles.update(list => [...list]);
    };

    const onMouseUp = () => {
      this.resizing = false;
      this.saveToHistory();
      document.removeEventListener('mousemove', onMouseMove);
      document.removeEventListener('mouseup', onMouseUp);
    };

    document.addEventListener('mousemove', onMouseMove);
    document.addEventListener('mouseup', onMouseUp);
  }

  getTileIcon(type: TileType): string {
    const icons: Record<TileType, string> = {
      chart: 'bar_chart',
      table: 'table_chart',
      metric: 'speed',
      timeline: 'timeline',
      markdown: 'text_fields',
      query: 'code'
    };
    return icons[type] || 'widgets';
  }

  canUndo(): boolean {
    return this.historyIndex > 0;
  }

  canRedo(): boolean {
    return this.historyIndex < this.history.length - 1;
  }

  undo(): void {
    if (this.canUndo()) {
      this.historyIndex--;
      this.tiles.set([...this.history[this.historyIndex]]);
    }
  }

  redo(): void {
    if (this.canRedo()) {
      this.historyIndex++;
      this.tiles.set([...this.history[this.historyIndex]]);
    }
  }

  private saveToHistory(): void {
    // Remove any redo history
    this.history = this.history.slice(0, this.historyIndex + 1);
    // Add current state
    this.history.push(JSON.parse(JSON.stringify(this.tiles())));
    this.historyIndex = this.history.length - 1;
  }

  async saveWorkbook(): Promise<void> {
    this.isSaving.set(true);

    try {
      const definition: WorkbookDefinition = {
        tiles: this.tiles(),
        layout: {
          columns: this.gridColumns,
          row_height: this.rowHeight
        },
        variables: {}
      };

      if (this.workbookId()) {
        await this.workbookService.updateWorkbook(this.workbookId()!, {
          name: this.workbookName,
          definition
        }).toPromise();
      } else {
        const created = await this.workbookService.createWorkbook({
          name: this.workbookName,
          definition
        }).toPromise();
        if (created) {
          this.workbookId.set(created.id);
          this.router.navigate(['/workbooks', created.id, 'edit'], { replaceUrl: true });
        }
      }

      this.snackBar.open('Workbook saved', 'Close', { duration: 2000 });
    } catch (error) {
      console.error('Failed to save workbook:', error);
      this.snackBar.open('Failed to save workbook', 'Close', { duration: 3000 });
    } finally {
      this.isSaving.set(false);
    }
  }

  previewWorkbook(): void {
    const id = this.workbookId();
    if (id) {
      this.router.navigate(['/workbooks', id]);
    } else {
      this.snackBar.open('Save workbook first to preview', 'Close', { duration: 3000 });
    }
  }

  goBack(): void {
    this.router.navigate(['/workbooks']);
  }
}
