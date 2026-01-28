import {
  Component,
  ElementRef,
  EventEmitter,
  Input,
  OnChanges,
  OnDestroy,
  OnInit,
  Output,
  SimpleChanges,
  ViewChild,
  AfterViewInit,
  NgZone
} from '@angular/core';
import { CommonModule } from '@angular/common';

// D3 types - will be loaded dynamically
declare const d3: any;

export interface TimelineItem {
  id: string;
  timestamp: Date | string;
  title: string;
  description?: string;
  category?: string;
  severity?: 'low' | 'medium' | 'high' | 'critical';
  data?: Record<string, unknown>;
}

export interface TimelineConfig {
  height?: number;
  margin?: { top: number; right: number; bottom: number; left: number };
  categoryColors?: Record<string, string>;
  showLabels?: boolean;
  enableBrush?: boolean;
  enableZoom?: boolean;
}

@Component({
  selector: 'app-d3-timeline',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="d3-timeline-wrapper" #wrapper>
      <div class="timeline-toolbar">
        <div class="time-range">
          @if (visibleRange) {
            <span>{{ formatDate(visibleRange.start) }} - {{ formatDate(visibleRange.end) }}</span>
          }
        </div>
        <div class="toolbar-actions">
          <button class="tool-btn" (click)="resetZoom()" title="Reset Zoom">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 5V1L7 6l5 5V7c3.31 0 6 2.69 6 6s-2.69 6-6 6-6-2.69-6-6H4c0 4.42 3.58 8 8 8s8-3.58 8-8-3.58-8-8-8z"/>
            </svg>
          </button>
          <button class="tool-btn" (click)="zoomIn()" title="Zoom In">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
              <path d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z"/>
            </svg>
          </button>
          <button class="tool-btn" (click)="zoomOut()" title="Zoom Out">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
              <path d="M19 13H5v-2h14v2z"/>
            </svg>
          </button>
        </div>
      </div>
      <svg #chart class="timeline-chart"></svg>
      <div class="timeline-legend">
        @for (cat of categories; track cat.name) {
          <div class="legend-item" (click)="toggleCategory(cat.name)">
            <span class="legend-color" [style.background]="cat.color"></span>
            <span class="legend-label" [class.dimmed]="!cat.visible">{{ cat.name }}</span>
          </div>
        }
      </div>
    </div>
  `,
  styles: [`
    .d3-timeline-wrapper {
      width: 100%;
      background: var(--bg-card);
      border: 1px solid var(--border-color);
      border-radius: 8px;
      overflow: hidden;
    }

    .timeline-toolbar {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 12px 16px;
      border-bottom: 1px solid var(--border-color);
      background: var(--bg-surface);
    }

    .time-range {
      font-size: 13px;
      color: var(--text-secondary);
    }

    .toolbar-actions {
      display: flex;
      gap: 4px;
    }

    .tool-btn {
      display: flex;
      align-items: center;
      justify-content: center;
      width: 32px;
      height: 32px;
      background: transparent;
      border: 1px solid var(--border-color);
      border-radius: 4px;
      color: var(--text-secondary);
      cursor: pointer;
      transition: all 0.15s ease;

      &:hover {
        background: var(--bg-tertiary);
        color: var(--text-primary);
        border-color: var(--accent);
      }
    }

    .timeline-chart {
      width: 100%;
      display: block;
    }

    :host ::ng-deep {
      .axis-x line,
      .axis-x path {
        stroke: var(--border-color);
      }

      .axis-x text {
        fill: var(--text-secondary);
        font-size: 11px;
      }

      .event-dot {
        cursor: pointer;
        transition: r 0.15s ease;

        &:hover {
          r: 8;
        }
      }

      .event-dot.selected {
        stroke: white;
        stroke-width: 2;
      }

      .brush .selection {
        fill: var(--accent);
        fill-opacity: 0.2;
        stroke: var(--accent);
      }

      .zoom-rect {
        fill: none;
        pointer-events: all;
      }

      .tooltip {
        position: absolute;
        background: var(--bg-card);
        border: 1px solid var(--border-color);
        border-radius: 4px;
        padding: 8px 12px;
        font-size: 12px;
        pointer-events: none;
        z-index: 1000;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);

        .tooltip-title {
          font-weight: 500;
          margin-bottom: 4px;
        }

        .tooltip-time {
          color: var(--text-secondary);
          font-size: 11px;
        }
      }
    }

    .timeline-legend {
      display: flex;
      flex-wrap: wrap;
      gap: 16px;
      padding: 12px 16px;
      border-top: 1px solid var(--border-color);
      background: var(--bg-surface);
    }

    .legend-item {
      display: flex;
      align-items: center;
      gap: 6px;
      cursor: pointer;
      user-select: none;

      &:hover .legend-label {
        color: var(--text-primary);
      }
    }

    .legend-color {
      width: 12px;
      height: 12px;
      border-radius: 50%;
    }

    .legend-label {
      font-size: 12px;
      color: var(--text-secondary);
      transition: color 0.15s ease;

      &.dimmed {
        opacity: 0.4;
      }
    }
  `]
})
export class D3TimelineComponent implements OnInit, OnChanges, AfterViewInit, OnDestroy {
  @ViewChild('wrapper') wrapper!: ElementRef<HTMLDivElement>;
  @ViewChild('chart') chartElement!: ElementRef<SVGElement>;

  @Input() items: TimelineItem[] = [];
  @Input() config: TimelineConfig = {};
  @Input() selectedId: string | null = null;

  @Output() itemSelected = new EventEmitter<TimelineItem>();
  @Output() rangeChanged = new EventEmitter<{ start: Date; end: Date }>();

  private svg: any = null;
  private xScale: any = null;
  private xAxis: any = null;
  private zoom: any = null;
  private currentTransform: any = null;
  private tooltip: any = null;
  private d3Loaded = false;

  categories: { name: string; color: string; visible: boolean }[] = [];
  visibleRange: { start: Date; end: Date } | null = null;

  private defaultColors: Record<string, string> = {
    process: '#3b82f6',
    network: '#f59e0b',
    file: '#10b981',
    authentication: '#e94560',
    persistence: '#ef4444',
    registry: '#8b5cf6',
    memory: '#06b6d4',
    default: '#6b7280'
  };

  constructor(private ngZone: NgZone) {}

  ngOnInit(): void {
    this.loadD3();
  }

  ngAfterViewInit(): void {
    if (this.d3Loaded) {
      this.initChart();
    }
  }

  ngOnChanges(changes: SimpleChanges): void {
    if (this.d3Loaded && (changes['items'] || changes['selectedId'])) {
      this.updateChart();
    }
  }

  ngOnDestroy(): void {
    if (this.tooltip) {
      this.tooltip.remove();
    }
  }

  private loadD3(): void {
    if (typeof d3 !== 'undefined') {
      this.d3Loaded = true;
      this.initChart();
      return;
    }

    const script = document.createElement('script');
    script.src = 'https://cdn.jsdelivr.net/npm/d3@7/dist/d3.min.js';
    script.onload = () => {
      this.d3Loaded = true;
      this.ngZone.run(() => this.initChart());
    };
    document.head.appendChild(script);
  }

  private initChart(): void {
    if (!this.chartElement?.nativeElement || !this.d3Loaded) return;

    const margin = this.config.margin || { top: 20, right: 30, bottom: 40, left: 30 };
    const height = this.config.height || 150;
    const width = this.wrapper.nativeElement.clientWidth;

    // Clear previous
    d3.select(this.chartElement.nativeElement).selectAll('*').remove();

    this.svg = d3.select(this.chartElement.nativeElement)
      .attr('width', width)
      .attr('height', height);

    const chartGroup = this.svg.append('g')
      .attr('class', 'chart-group')
      .attr('transform', `translate(${margin.left},${margin.top})`);

    // Create tooltip
    this.tooltip = d3.select(this.wrapper.nativeElement)
      .append('div')
      .attr('class', 'tooltip')
      .style('display', 'none');

    // Initialize scales
    this.xScale = d3.scaleTime()
      .range([0, width - margin.left - margin.right]);

    // Initialize zoom
    this.zoom = d3.zoom()
      .scaleExtent([1, 100])
      .translateExtent([[0, 0], [width, height]])
      .extent([[0, 0], [width, height]])
      .on('zoom', (event: any) => this.onZoom(event));

    // Add zoom rect
    this.svg.append('rect')
      .attr('class', 'zoom-rect')
      .attr('width', width)
      .attr('height', height)
      .call(this.zoom);

    // X axis
    chartGroup.append('g')
      .attr('class', 'axis-x')
      .attr('transform', `translate(0,${height - margin.top - margin.bottom})`);

    // Events group
    chartGroup.append('g')
      .attr('class', 'events-group');

    this.updateChart();
  }

  private updateChart(): void {
    if (!this.svg || !this.items.length) return;

    const margin = this.config.margin || { top: 20, right: 30, bottom: 40, left: 30 };
    const height = this.config.height || 150;
    const width = this.wrapper.nativeElement.clientWidth;

    // Parse dates
    const data = this.items.map(item => ({
      ...item,
      date: new Date(item.timestamp)
    }));

    // Update categories
    const cats = [...new Set(data.map(d => d.category || 'default'))];
    const colors = { ...this.defaultColors, ...this.config.categoryColors };

    this.categories = cats.map(name => ({
      name,
      color: colors[name] || colors['default'],
      visible: this.categories.find(c => c.name === name)?.visible ?? true
    }));

    // Update scale domain
    const extent = d3.extent(data, (d: any) => d.date) as [Date, Date];
    this.xScale.domain(extent);

    // Apply current transform if exists
    if (this.currentTransform) {
      const newXScale = this.currentTransform.rescaleX(this.xScale);
      this.visibleRange = { start: newXScale.domain()[0], end: newXScale.domain()[1] };
    } else {
      this.visibleRange = { start: extent[0], end: extent[1] };
    }

    // Update axis
    this.xAxis = d3.axisBottom(this.currentTransform ?
      this.currentTransform.rescaleX(this.xScale) : this.xScale)
      .ticks(8)
      .tickFormat(d3.timeFormat('%b %d %H:%M'));

    this.svg.select('.axis-x')
      .transition()
      .duration(200)
      .call(this.xAxis);

    // Filter visible categories
    const visibleData = data.filter(d =>
      this.categories.find(c => c.name === (d.category || 'default'))?.visible
    );

    // Update events
    const eventsGroup = this.svg.select('.events-group');
    const chartHeight = height - margin.top - margin.bottom;

    const dots = eventsGroup.selectAll('.event-dot')
      .data(visibleData, (d: any) => d.id);

    // Enter
    dots.enter()
      .append('circle')
      .attr('class', 'event-dot')
      .attr('r', 0)
      .attr('cy', chartHeight / 2)
      .attr('fill', (d: any) => colors[d.category || 'default'] || colors['default'])
      .on('click', (event: any, d: any) => {
        event.stopPropagation();
        this.ngZone.run(() => this.itemSelected.emit(d));
      })
      .on('mouseenter', (event: any, d: any) => this.showTooltip(event, d))
      .on('mouseleave', () => this.hideTooltip())
      .transition()
      .duration(300)
      .attr('cx', (d: any) => this.getXPosition(d.date))
      .attr('r', (d: any) => d.id === this.selectedId ? 8 : 6);

    // Update
    dots.transition()
      .duration(200)
      .attr('cx', (d: any) => this.getXPosition(d.date))
      .attr('r', (d: any) => d.id === this.selectedId ? 8 : 6)
      .attr('class', (d: any) => `event-dot ${d.id === this.selectedId ? 'selected' : ''}`);

    // Exit
    dots.exit()
      .transition()
      .duration(200)
      .attr('r', 0)
      .remove();
  }

  private getXPosition(date: Date): number {
    if (this.currentTransform) {
      return this.currentTransform.rescaleX(this.xScale)(date);
    }
    return this.xScale(date);
  }

  private onZoom(event: any): void {
    this.currentTransform = event.transform;

    const newXScale = event.transform.rescaleX(this.xScale);
    this.visibleRange = { start: newXScale.domain()[0], end: newXScale.domain()[1] };

    // Update axis
    this.svg.select('.axis-x').call(
      d3.axisBottom(newXScale)
        .ticks(8)
        .tickFormat(d3.timeFormat('%b %d %H:%M'))
    );

    // Update dot positions
    this.svg.selectAll('.event-dot')
      .attr('cx', (d: any) => newXScale(d.date));

    this.ngZone.run(() => {
      this.rangeChanged.emit(this.visibleRange!);
    });
  }

  private showTooltip(event: any, d: TimelineItem): void {
    const [x, y] = d3.pointer(event, this.wrapper.nativeElement);

    this.tooltip
      .style('display', 'block')
      .style('left', `${x + 10}px`)
      .style('top', `${y - 10}px`)
      .html(`
        <div class="tooltip-title">${d.title}</div>
        <div class="tooltip-time">${this.formatDate(new Date(d.timestamp))}</div>
      `);
  }

  private hideTooltip(): void {
    this.tooltip.style('display', 'none');
  }

  formatDate(date: Date): string {
    return date.toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  }

  toggleCategory(name: string): void {
    const cat = this.categories.find(c => c.name === name);
    if (cat) {
      cat.visible = !cat.visible;
      this.updateChart();
    }
  }

  zoomIn(): void {
    this.svg.transition().duration(300).call(
      this.zoom.scaleBy, 1.5
    );
  }

  zoomOut(): void {
    this.svg.transition().duration(300).call(
      this.zoom.scaleBy, 0.67
    );
  }

  resetZoom(): void {
    this.svg.transition().duration(300).call(
      this.zoom.transform, d3.zoomIdentity
    );
    this.currentTransform = null;
  }
}
