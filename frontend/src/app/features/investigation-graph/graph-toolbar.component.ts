import { Component, Input, Output, EventEmitter, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatMenuModule } from '@angular/material/menu';
import { MatSliderModule } from '@angular/material/slider';
import { MatDividerModule } from '@angular/material/divider';
import { MatButtonToggleModule } from '@angular/material/button-toggle';
import { MatBadgeModule } from '@angular/material/badge';
import { LayoutType } from '../../shared/components/cytoscape-graph/cytoscape-graph.component';

export type ToolMode = 'select' | 'pan' | 'path' | 'annotate';

@Component({
  selector: 'app-graph-toolbar',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatButtonModule,
    MatIconModule,
    MatTooltipModule,
    MatMenuModule,
    MatSliderModule,
    MatDividerModule,
    MatButtonToggleModule,
    MatBadgeModule,
  ],
  template: `
    <div class="graph-toolbar">
      <!-- Mode Selection -->
      <div class="toolbar-section">
        <mat-button-toggle-group [(ngModel)]="activeMode" (change)="onModeChange()">
          <mat-button-toggle value="select" matTooltip="Select Mode">
            <mat-icon>arrow_selector_tool</mat-icon>
          </mat-button-toggle>
          <mat-button-toggle value="pan" matTooltip="Pan Mode">
            <mat-icon>pan_tool</mat-icon>
          </mat-button-toggle>
          <mat-button-toggle value="path" matTooltip="Path Finding Mode">
            <mat-icon>route</mat-icon>
          </mat-button-toggle>
          <mat-button-toggle value="annotate" matTooltip="Annotate Mode">
            <mat-icon>edit_note</mat-icon>
          </mat-button-toggle>
        </mat-button-toggle-group>
      </div>

      <mat-divider vertical></mat-divider>

      <!-- Layout -->
      <div class="toolbar-section">
        <button mat-icon-button [matMenuTriggerFor]="layoutMenu" matTooltip="Layout">
          <mat-icon>account_tree</mat-icon>
        </button>
        <mat-menu #layoutMenu="matMenu">
          <button mat-menu-item (click)="changeLayout.emit('dagre')">
            <mat-icon>account_tree</mat-icon>
            Hierarchical (Dagre)
          </button>
          <button mat-menu-item (click)="changeLayout.emit('cola')">
            <mat-icon>bubble_chart</mat-icon>
            Force-Directed (Cola)
          </button>
          <button mat-menu-item (click)="changeLayout.emit('cose')">
            <mat-icon>scatter_plot</mat-icon>
            COSE
          </button>
          <button mat-menu-item (click)="changeLayout.emit('circle')">
            <mat-icon>radio_button_unchecked</mat-icon>
            Circle
          </button>
          <button mat-menu-item (click)="changeLayout.emit('concentric')">
            <mat-icon>adjust</mat-icon>
            Concentric
          </button>
          <button mat-menu-item (click)="changeLayout.emit('grid')">
            <mat-icon>grid_view</mat-icon>
            Grid
          </button>
        </mat-menu>
      </div>

      <mat-divider vertical></mat-divider>

      <!-- View Controls -->
      <div class="toolbar-section">
        <button mat-icon-button (click)="zoomIn.emit()" matTooltip="Zoom In">
          <mat-icon>add</mat-icon>
        </button>
        <button mat-icon-button (click)="zoomOut.emit()" matTooltip="Zoom Out">
          <mat-icon>remove</mat-icon>
        </button>
        <button mat-icon-button (click)="fitToView.emit()" matTooltip="Fit to View">
          <mat-icon>fit_screen</mat-icon>
        </button>
        <button mat-icon-button (click)="resetView.emit()" matTooltip="Reset View">
          <mat-icon>restart_alt</mat-icon>
        </button>
      </div>

      <mat-divider vertical></mat-divider>

      <!-- Path Finding -->
      <div class="toolbar-section">
        <button mat-icon-button
                [matBadge]="pathNodesSelected > 0 ? pathNodesSelected : null"
                matBadgeColor="accent"
                matBadgeSize="small"
                (click)="togglePathMode()"
                [class.active]="activeMode === 'path'"
                matTooltip="Find Path Between Nodes">
          <mat-icon>route</mat-icon>
        </button>
        @if (activeMode === 'path') {
          <button mat-icon-button (click)="clearPath.emit()" matTooltip="Clear Path">
            <mat-icon>clear</mat-icon>
          </button>
        }
      </div>

      <mat-divider vertical></mat-divider>

      <!-- Analytics -->
      <div class="toolbar-section">
        <button mat-icon-button [matMenuTriggerFor]="analyticsMenu" matTooltip="Analytics">
          <mat-icon>insights</mat-icon>
        </button>
        <mat-menu #analyticsMenu="matMenu">
          <button mat-menu-item (click)="showAnalytics.emit('cluster')">
            <mat-icon>workspaces</mat-icon>
            Cluster by Type
          </button>
          <button mat-menu-item (click)="showAnalytics.emit('timeline')">
            <mat-icon>timeline</mat-icon>
            Timeline Overlay
          </button>
          <button mat-menu-item (click)="showAnalytics.emit('centrality')">
            <mat-icon>hub</mat-icon>
            Centrality Analysis
          </button>
          <button mat-menu-item (click)="showAnalytics.emit('attack-path')">
            <mat-icon>security</mat-icon>
            Highlight Attack Paths
          </button>
        </mat-menu>

        <button mat-icon-button (click)="toggleAnalyticsPanel.emit()" matTooltip="Analytics Panel">
          <mat-icon>analytics</mat-icon>
        </button>
      </div>

      <mat-divider vertical></mat-divider>

      <!-- Selection Actions -->
      <div class="toolbar-section">
        <button mat-icon-button
                [disabled]="selectedCount === 0"
                [matMenuTriggerFor]="selectionMenu"
                [matBadge]="selectedCount > 0 ? selectedCount : null"
                matBadgeColor="primary"
                matBadgeSize="small"
                matTooltip="Selection Actions">
          <mat-icon>checklist</mat-icon>
        </button>
        <mat-menu #selectionMenu="matMenu">
          <button mat-menu-item (click)="isolateSelection.emit()">
            <mat-icon>filter_center_focus</mat-icon>
            Isolate Selection
          </button>
          <button mat-menu-item (click)="expandSelection.emit()">
            <mat-icon>open_in_full</mat-icon>
            Expand Connections
          </button>
          <button mat-menu-item (click)="hideSelection.emit()">
            <mat-icon>visibility_off</mat-icon>
            Hide Selected
          </button>
          <mat-divider></mat-divider>
          <button mat-menu-item (click)="addToGroup.emit()">
            <mat-icon>folder</mat-icon>
            Add to Group
          </button>
          <button mat-menu-item (click)="tagSelection.emit()">
            <mat-icon>label</mat-icon>
            Tag Selection
          </button>
        </mat-menu>
      </div>

      <mat-divider vertical></mat-divider>

      <!-- Export -->
      <div class="toolbar-section">
        <button mat-icon-button [matMenuTriggerFor]="exportMenu" matTooltip="Export">
          <mat-icon>download</mat-icon>
        </button>
        <mat-menu #exportMenu="matMenu">
          <button mat-menu-item (click)="exportGraph.emit('png')">
            <mat-icon>image</mat-icon>
            Export as PNG
          </button>
          <button mat-menu-item (click)="exportGraph.emit('svg')">
            <mat-icon>draw</mat-icon>
            Export as SVG
          </button>
          <button mat-menu-item (click)="exportGraph.emit('json')">
            <mat-icon>code</mat-icon>
            Export as JSON
          </button>
          <mat-divider></mat-divider>
          <button mat-menu-item (click)="exportSubgraph.emit()">
            <mat-icon>content_cut</mat-icon>
            Export Subgraph
          </button>
        </mat-menu>
      </div>

      <div class="toolbar-spacer"></div>

      <!-- Display Options -->
      <div class="toolbar-section">
        <button mat-icon-button [matMenuTriggerFor]="displayMenu" matTooltip="Display Options">
          <mat-icon>visibility</mat-icon>
        </button>
        <mat-menu #displayMenu="matMenu">
          <div class="menu-slider">
            <span>Node Size</span>
            <mat-slider min="20" max="60" step="5" [displayWith]="formatSlider">
              <input matSliderThumb [(ngModel)]="nodeSize" (change)="onNodeSizeChange()">
            </mat-slider>
          </div>
          <div class="menu-slider">
            <span>Edge Width</span>
            <mat-slider min="1" max="6" step="1" [displayWith]="formatSlider">
              <input matSliderThumb [(ngModel)]="edgeWidth" (change)="onEdgeWidthChange()">
            </mat-slider>
          </div>
          <mat-divider></mat-divider>
          <button mat-menu-item (click)="toggleLabels.emit()">
            <mat-icon>{{ showLabels ? 'check_box' : 'check_box_outline_blank' }}</mat-icon>
            Show Labels
          </button>
          <button mat-menu-item (click)="toggleEdgeLabels.emit()">
            <mat-icon>{{ showEdgeLabels ? 'check_box' : 'check_box_outline_blank' }}</mat-icon>
            Show Edge Labels
          </button>
        </mat-menu>
      </div>
    </div>
  `,
  styles: [`
    .graph-toolbar {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 8px 16px;
      background: #252525;
      border-bottom: 1px solid #333;
    }

    .toolbar-section {
      display: flex;
      align-items: center;
      gap: 4px;
    }

    .toolbar-spacer {
      flex: 1;
    }

    mat-divider[vertical] {
      height: 24px;
      margin: 0 4px;
    }

    button.active {
      background: rgba(var(--accent-rgb), 0.2);
    }

    mat-button-toggle-group {
      height: 36px;
    }

    ::ng-deep .mat-button-toggle-appearance-standard .mat-button-toggle-label-content {
      line-height: 36px;
      padding: 0 8px;
    }

    .menu-slider {
      display: flex;
      align-items: center;
      gap: 16px;
      padding: 8px 16px;
      min-width: 200px;

      span {
        font-size: 13px;
        white-space: nowrap;
      }

      mat-slider {
        flex: 1;
      }
    }
  `]
})
export class GraphToolbarComponent {
  @Input() selectedCount = 0;
  @Input() showLabels = true;
  @Input() showEdgeLabels = false;
  @Input() pathNodesSelected = 0;

  @Output() modeChange = new EventEmitter<ToolMode>();
  @Output() changeLayout = new EventEmitter<LayoutType>();
  @Output() zoomIn = new EventEmitter<void>();
  @Output() zoomOut = new EventEmitter<void>();
  @Output() fitToView = new EventEmitter<void>();
  @Output() resetView = new EventEmitter<void>();
  @Output() clearPath = new EventEmitter<void>();
  @Output() showAnalytics = new EventEmitter<string>();
  @Output() toggleAnalyticsPanel = new EventEmitter<void>();
  @Output() isolateSelection = new EventEmitter<void>();
  @Output() expandSelection = new EventEmitter<void>();
  @Output() hideSelection = new EventEmitter<void>();
  @Output() addToGroup = new EventEmitter<void>();
  @Output() tagSelection = new EventEmitter<void>();
  @Output() exportGraph = new EventEmitter<string>();
  @Output() exportSubgraph = new EventEmitter<void>();
  @Output() toggleLabels = new EventEmitter<void>();
  @Output() toggleEdgeLabels = new EventEmitter<void>();
  @Output() nodeSizeChange = new EventEmitter<number>();
  @Output() edgeWidthChange = new EventEmitter<number>();

  activeMode: ToolMode = 'select';
  nodeSize = 30;
  edgeWidth = 2;

  onModeChange(): void {
    this.modeChange.emit(this.activeMode);
  }

  togglePathMode(): void {
    this.activeMode = this.activeMode === 'path' ? 'select' : 'path';
    this.onModeChange();
  }

  onNodeSizeChange(): void {
    this.nodeSizeChange.emit(this.nodeSize);
  }

  onEdgeWidthChange(): void {
    this.edgeWidthChange.emit(this.edgeWidth);
  }

  formatSlider(value: number): string {
    return value.toString();
  }
}
