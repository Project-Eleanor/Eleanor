import {
  Component,
  ElementRef,
  Input,
  Output,
  EventEmitter,
  OnInit,
  OnDestroy,
  AfterViewInit,
  ViewChild,
  signal,
  effect,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import cytoscape, { Core, NodeSingular, EdgeSingular } from 'cytoscape';
// @ts-expect-error - no types available for cytoscape-dagre
import dagre from 'cytoscape-dagre';
// @ts-expect-error - no types available for cytoscape-cola
import cola from 'cytoscape-cola';
import {
  GraphData,
  GraphNode,
  GraphEdge,
  NODE_COLORS,
  NODE_SHAPES,
  EntityType,
} from '../../models/graph.model';

// Register layouts
cytoscape.use(dagre);
cytoscape.use(cola);

export type LayoutType = 'dagre' | 'cola' | 'cose' | 'circle' | 'grid' | 'concentric';

@Component({
  selector: 'app-cytoscape-graph',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div #graphContainer class="graph-container"></div>
  `,
  styles: [`
    :host {
      display: block;
      width: 100%;
      height: 100%;
    }

    .graph-container {
      width: 100%;
      height: 100%;
      min-height: 400px;
      background: #1e1e1e;
      border-radius: 4px;
    }
  `],
})
export class CytoscapeGraphComponent implements OnInit, AfterViewInit, OnDestroy {
  @ViewChild('graphContainer', { static: true }) graphContainer!: ElementRef;

  @Input() set graphData(data: GraphData | null) {
    if (data) {
      this._graphData.set(data);
      if (this.cy) {
        this.loadData(data);
      }
    }
  }

  @Input() layout: LayoutType = 'dagre';
  @Input() showLabels = true;
  @Input() nodeSize = 30;
  @Input() edgeWidth = 2;

  @Output() nodeClick = new EventEmitter<GraphNode>();
  @Output() nodeDoubleClick = new EventEmitter<GraphNode>();
  @Output() edgeClick = new EventEmitter<GraphEdge>();
  @Output() selectionChange = new EventEmitter<{ nodes: GraphNode[]; edges: GraphEdge[] }>();
  @Output() layoutComplete = new EventEmitter<void>();

  private cy: Core | null = null;
  private _graphData = signal<GraphData | null>(null);

  constructor() {
    // React to graph data changes
    effect(() => {
      const data = this._graphData();
      if (data && this.cy) {
        this.loadData(data);
      }
    });
  }

  ngOnInit(): void {}

  ngAfterViewInit(): void {
    this.initCytoscape();
  }

  ngOnDestroy(): void {
    if (this.cy) {
      this.cy.destroy();
    }
  }

  private initCytoscape(): void {
    this.cy = cytoscape({
      container: this.graphContainer.nativeElement,
      style: this.getStylesheet(),
      minZoom: 0.1,
      maxZoom: 3,
      wheelSensitivity: 0.3,
    });

    this.setupEventHandlers();

    // Load initial data if available
    const data = this._graphData();
    if (data) {
      this.loadData(data);
    }
  }

  private getStylesheet(): cytoscape.Stylesheet[] {
    return [
      // Node styles
      {
        selector: 'node',
        style: {
          'label': this.showLabels ? 'data(label)' : '',
          'text-valign': 'bottom',
          'text-halign': 'center',
          'text-margin-y': 5,
          'font-size': 10,
          'color': '#fff',
          'text-outline-color': '#000',
          'text-outline-width': 1,
          'width': this.nodeSize,
          'height': this.nodeSize,
          'background-color': 'data(color)',
          'shape': 'data(shape)',
          'border-width': 2,
          'border-color': '#333',
        },
      },
      // Selected node
      {
        selector: 'node:selected',
        style: {
          'border-width': 4,
          'border-color': '#fff',
          'background-color': 'data(color)',
        },
      },
      // Hover node
      {
        selector: 'node:active',
        style: {
          'overlay-opacity': 0.2,
          'overlay-color': '#fff',
        },
      },
      // Edge styles
      {
        selector: 'edge',
        style: {
          'width': this.edgeWidth,
          'line-color': '#666',
          'target-arrow-color': '#666',
          'target-arrow-shape': 'triangle',
          'curve-style': 'bezier',
          'label': this.showLabels ? 'data(label)' : '',
          'font-size': 8,
          'color': '#999',
          'text-rotation': 'autorotate',
          'text-margin-y': -10,
        },
      },
      // Selected edge
      {
        selector: 'edge:selected',
        style: {
          'width': this.edgeWidth + 1,
          'line-color': '#4CAF50',
          'target-arrow-color': '#4CAF50',
        },
      },
      // Highlighted elements (for path finding)
      {
        selector: '.highlighted',
        style: {
          'border-color': '#FFD700',
          'border-width': 4,
          'line-color': '#FFD700',
          'target-arrow-color': '#FFD700',
        },
      },
      // Dimmed elements
      {
        selector: '.dimmed',
        style: {
          'opacity': 0.3,
        },
      },
    ];
  }

  private setupEventHandlers(): void {
    if (!this.cy) return;

    // Node click
    this.cy.on('tap', 'node', (event) => {
      const node = event.target;
      const nodeData = this.cyNodeToGraphNode(node);
      this.nodeClick.emit(nodeData);
    });

    // Node double-click
    this.cy.on('dbltap', 'node', (event) => {
      const node = event.target;
      const nodeData = this.cyNodeToGraphNode(node);
      this.nodeDoubleClick.emit(nodeData);
    });

    // Edge click
    this.cy.on('tap', 'edge', (event) => {
      const edge = event.target;
      const edgeData = this.cyEdgeToGraphEdge(edge);
      this.edgeClick.emit(edgeData);
    });

    // Selection change
    this.cy.on('select unselect', () => {
      const selectedNodes = this.cy!.$('node:selected').map((n: NodeSingular) =>
        this.cyNodeToGraphNode(n)
      );
      const selectedEdges = this.cy!.$('edge:selected').map((e: EdgeSingular) =>
        this.cyEdgeToGraphEdge(e)
      );
      this.selectionChange.emit({ nodes: selectedNodes, edges: selectedEdges });
    });
  }

  private loadData(data: GraphData): void {
    if (!this.cy) return;

    // Clear existing elements
    this.cy.elements().remove();

    // Add nodes
    const cyNodes = data.nodes.map((node) => ({
      data: {
        id: node.id,
        label: node.label,
        type: node.type,
        color: NODE_COLORS[node.type] || '#666',
        shape: NODE_SHAPES[node.type] || 'ellipse',
        event_count: node.event_count,
        first_seen: node.first_seen,
        last_seen: node.last_seen,
        risk_score: node.risk_score,
      },
    }));

    // Add edges
    const cyEdges = data.edges.map((edge, index) => ({
      data: {
        id: `edge-${index}`,
        source: edge.source,
        target: edge.target,
        label: edge.relationship,
        relationship: edge.relationship,
        weight: edge.weight,
        timestamp: edge.timestamp,
      },
    }));

    this.cy.add([...cyNodes, ...cyEdges]);

    // Run layout
    this.runLayout();
  }

  /**
   * Run the current layout algorithm.
   */
  runLayout(layoutName?: LayoutType): void {
    if (!this.cy) return;

    const name = layoutName || this.layout;

    const layoutOptions: Record<string, any> = {
      dagre: {
        name: 'dagre',
        rankDir: 'TB',
        nodeSep: 50,
        rankSep: 100,
        animate: true,
        animationDuration: 500,
      },
      cola: {
        name: 'cola',
        animate: true,
        animationDuration: 500,
        nodeSpacing: 50,
        edgeLength: 150,
      },
      cose: {
        name: 'cose',
        animate: true,
        animationDuration: 500,
        nodeRepulsion: 4000,
        idealEdgeLength: 100,
      },
      circle: {
        name: 'circle',
        animate: true,
        animationDuration: 500,
      },
      grid: {
        name: 'grid',
        animate: true,
        animationDuration: 500,
        rows: Math.ceil(Math.sqrt(this.cy.nodes().length)),
      },
      concentric: {
        name: 'concentric',
        animate: true,
        animationDuration: 500,
        minNodeSpacing: 50,
        concentric: (node: NodeSingular) => node.degree(),
      },
    };

    const layout = this.cy.layout(layoutOptions[name] || layoutOptions['dagre']);
    layout.on('layoutstop', () => this.layoutComplete.emit());
    layout.run();
  }

  /**
   * Add new nodes and edges to the graph.
   */
  addElements(data: GraphData): void {
    if (!this.cy) return;

    // Filter out existing nodes
    const existingIds = new Set(this.cy.nodes().map((n: NodeSingular) => n.id()));
    const newNodes = data.nodes.filter((n) => !existingIds.has(n.id));

    // Add new nodes
    const cyNodes = newNodes.map((node) => ({
      data: {
        id: node.id,
        label: node.label,
        type: node.type,
        color: NODE_COLORS[node.type] || '#666',
        shape: NODE_SHAPES[node.type] || 'ellipse',
        event_count: node.event_count,
      },
    }));

    // Add edges (filter duplicates)
    const existingEdges = new Set(
      this.cy.edges().map((e: EdgeSingular) => `${e.source().id()}-${e.target().id()}`)
    );
    const newEdges = data.edges.filter(
      (e) => !existingEdges.has(`${e.source}-${e.target}`)
    );

    const cyEdges = newEdges.map((edge, index) => ({
      data: {
        id: `edge-new-${Date.now()}-${index}`,
        source: edge.source,
        target: edge.target,
        label: edge.relationship,
        relationship: edge.relationship,
        weight: edge.weight,
      },
    }));

    this.cy.add([...cyNodes, ...cyEdges]);

    // Re-run layout if we added nodes
    if (newNodes.length > 0) {
      this.runLayout();
    }
  }

  /**
   * Highlight a path between nodes.
   */
  highlightPath(nodeIds: string[], edgeData?: GraphEdge[]): void {
    if (!this.cy) return;

    // Clear existing highlights
    this.cy.elements().removeClass('highlighted dimmed');

    // Dim all elements
    this.cy.elements().addClass('dimmed');

    // Highlight path nodes
    nodeIds.forEach((id) => {
      const node = this.cy!.$id(id);
      node.removeClass('dimmed').addClass('highlighted');
    });

    // Highlight path edges
    if (edgeData) {
      edgeData.forEach((edge) => {
        const cyEdge = this.cy!.edges().filter(
          (e: EdgeSingular) => e.source().id() === edge.source && e.target().id() === edge.target
        );
        cyEdge.removeClass('dimmed').addClass('highlighted');
      });
    }
  }

  /**
   * Clear all highlights.
   */
  clearHighlights(): void {
    if (!this.cy) return;
    this.cy.elements().removeClass('highlighted dimmed');
  }

  /**
   * Fit the graph to the viewport.
   */
  fit(): void {
    if (!this.cy) return;
    this.cy.fit(undefined, 50);
  }

  /**
   * Center on a specific node.
   */
  centerOnNode(nodeId: string): void {
    if (!this.cy) return;
    const node = this.cy.$id(nodeId);
    if (node.length > 0) {
      this.cy.center(node);
    }
  }

  /**
   * Get current graph positions.
   */
  getPositions(): Record<string, { x: number; y: number }> {
    if (!this.cy) return {};

    const positions: Record<string, { x: number; y: number }> = {};
    this.cy.nodes().forEach((node: NodeSingular) => {
      const pos = node.position();
      positions[node.id()] = { x: pos.x, y: pos.y };
    });
    return positions;
  }

  /**
   * Get current zoom and pan.
   */
  getViewport(): { zoom: number; pan: { x: number; y: number } } {
    if (!this.cy) return { zoom: 1, pan: { x: 0, y: 0 } };
    return {
      zoom: this.cy.zoom(),
      pan: this.cy.pan(),
    };
  }

  /**
   * Export graph as PNG.
   */
  exportPng(): string {
    if (!this.cy) return '';
    return this.cy.png({ bg: '#1e1e1e', full: true });
  }

  private cyNodeToGraphNode(node: NodeSingular): GraphNode {
    const data = node.data();
    return {
      id: data.id,
      label: data.label,
      type: data.type as EntityType,
      event_count: data.event_count,
      first_seen: data.first_seen,
      last_seen: data.last_seen,
      risk_score: data.risk_score,
    };
  }

  private cyEdgeToGraphEdge(edge: EdgeSingular): GraphEdge {
    const data = edge.data();
    return {
      source: data.source,
      target: data.target,
      relationship: data.relationship,
      weight: data.weight,
      timestamp: data.timestamp,
    };
  }
}
