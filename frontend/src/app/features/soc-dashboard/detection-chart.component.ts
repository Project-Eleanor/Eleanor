import { Component, input, computed, signal, effect } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MatCardModule } from '@angular/material/card';
import { MatIconModule } from '@angular/material/icon';
import { MatButtonToggleModule } from '@angular/material/button-toggle';
import { MatTooltipModule } from '@angular/material/tooltip';
import { FormsModule } from '@angular/forms';
import { TimelineBucket, TimelineInterval } from '../../core/services/realtime-dashboard.service';

interface ChartBar {
  timestamp: string;
  label: string;
  total: number;
  critical: number;
  high: number;
  medium: number;
  low: number;
  info: number;
  height: number;
}

@Component({
  selector: 'app-detection-chart',
  standalone: true,
  imports: [
    CommonModule,
    MatCardModule,
    MatIconModule,
    MatButtonToggleModule,
    MatTooltipModule,
    FormsModule
  ],
  template: `
    <mat-card class="chart-card">
      <div class="chart-header">
        <div class="chart-title">
          <mat-icon>show_chart</mat-icon>
          <span>Alert Timeline</span>
        </div>
        <mat-button-toggle-group [value]="interval()" (change)="onIntervalChange($event.value)">
          <mat-button-toggle value="15m">15m</mat-button-toggle>
          <mat-button-toggle value="1h">1h</mat-button-toggle>
          <mat-button-toggle value="4h">4h</mat-button-toggle>
          <mat-button-toggle value="1d">1d</mat-button-toggle>
        </mat-button-toggle-group>
      </div>

      <div class="chart-content">
        @if (chartData().length === 0) {
          <div class="empty-chart">
            <mat-icon>timeline</mat-icon>
            <p>No data available</p>
          </div>
        } @else {
          <div class="chart-container">
            <div class="y-axis">
              @for (tick of yAxisTicks(); track tick) {
                <span class="y-tick">{{ formatNumber(tick) }}</span>
              }
            </div>
            <div class="chart-bars">
              @for (bar of chartData(); track bar.timestamp) {
                <div class="bar-container"
                     [matTooltip]="getTooltip(bar)"
                     matTooltipPosition="above">
                  <div class="bar-stack" [style.height.%]="bar.height">
                    @if (bar.critical > 0) {
                      <div class="bar-segment critical"
                           [style.flex-grow]="bar.critical">
                      </div>
                    }
                    @if (bar.high > 0) {
                      <div class="bar-segment high"
                           [style.flex-grow]="bar.high">
                      </div>
                    }
                    @if (bar.medium > 0) {
                      <div class="bar-segment medium"
                           [style.flex-grow]="bar.medium">
                      </div>
                    }
                    @if (bar.low > 0) {
                      <div class="bar-segment low"
                           [style.flex-grow]="bar.low">
                      </div>
                    }
                    @if (bar.info > 0) {
                      <div class="bar-segment info"
                           [style.flex-grow]="bar.info">
                      </div>
                    }
                  </div>
                  <span class="bar-label">{{ bar.label }}</span>
                </div>
              }
            </div>
          </div>

          <div class="chart-legend">
            <span class="legend-item">
              <span class="legend-color critical"></span>
              Critical
            </span>
            <span class="legend-item">
              <span class="legend-color high"></span>
              High
            </span>
            <span class="legend-item">
              <span class="legend-color medium"></span>
              Medium
            </span>
            <span class="legend-item">
              <span class="legend-color low"></span>
              Low
            </span>
            <span class="legend-item">
              <span class="legend-color info"></span>
              Info
            </span>
          </div>
        }
      </div>
    </mat-card>
  `,
  styles: [`
    .chart-card {
      background: var(--bg-card);
      border: 1px solid var(--border-color);
    }

    .chart-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 16px;
      border-bottom: 1px solid var(--border-color);
    }

    .chart-title {
      display: flex;
      align-items: center;
      gap: 8px;
      font-family: var(--font-display);
      font-weight: 600;
      font-size: 14px;
      color: var(--text-primary);

      mat-icon {
        color: var(--accent);
        font-size: 20px;
        width: 20px;
        height: 20px;
      }
    }

    mat-button-toggle-group {
      height: 32px;
      border: 1px solid var(--border-color);

      ::ng-deep .mat-button-toggle {
        background: var(--bg-card);

        &.mat-button-toggle-checked {
          background: var(--accent);
          color: white;
        }

        .mat-button-toggle-label-content {
          font-size: 12px;
          line-height: 30px;
          padding: 0 12px;
        }
      }
    }

    .chart-content {
      padding: 16px;
    }

    .empty-chart {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      height: 200px;
      color: var(--text-muted);

      mat-icon {
        font-size: 48px;
        width: 48px;
        height: 48px;
        opacity: 0.3;
        margin-bottom: 12px;
      }

      p {
        margin: 0;
        font-size: 14px;
      }
    }

    .chart-container {
      display: flex;
      gap: 8px;
      height: 200px;
    }

    .y-axis {
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      padding-bottom: 24px;
      width: 40px;
      text-align: right;
    }

    .y-tick {
      font-size: 10px;
      font-family: var(--font-mono);
      color: var(--text-muted);
    }

    .chart-bars {
      flex: 1;
      display: flex;
      align-items: flex-end;
      gap: 4px;
      border-bottom: 1px solid var(--border-color);
      padding-bottom: 24px;
    }

    .bar-container {
      flex: 1;
      display: flex;
      flex-direction: column;
      align-items: center;
      height: 100%;
      min-width: 0;
      cursor: pointer;

      &:hover .bar-stack {
        filter: brightness(1.2);
      }
    }

    .bar-stack {
      width: 100%;
      max-width: 40px;
      display: flex;
      flex-direction: column;
      border-radius: 4px 4px 0 0;
      overflow: hidden;
      transition: filter 0.2s ease, height 0.3s ease;
    }

    .bar-segment {
      min-height: 2px;
      transition: flex-grow 0.3s ease;

      &.critical { background: var(--severity-critical); }
      &.high { background: var(--severity-high); }
      &.medium { background: var(--severity-medium); }
      &.low { background: var(--severity-low); }
      &.info { background: var(--severity-info); }
    }

    .bar-label {
      position: absolute;
      bottom: 0;
      font-size: 9px;
      font-family: var(--font-mono);
      color: var(--text-muted);
      white-space: nowrap;
      transform: rotate(-45deg);
      transform-origin: top left;
      margin-top: 4px;
    }

    .chart-legend {
      display: flex;
      justify-content: center;
      gap: 16px;
      margin-top: 16px;
      padding-top: 16px;
      border-top: 1px solid var(--border-color);
    }

    .legend-item {
      display: flex;
      align-items: center;
      gap: 6px;
      font-size: 11px;
      color: var(--text-secondary);
    }

    .legend-color {
      width: 12px;
      height: 12px;
      border-radius: 2px;

      &.critical { background: var(--severity-critical); }
      &.high { background: var(--severity-high); }
      &.medium { background: var(--severity-medium); }
      &.low { background: var(--severity-low); }
      &.info { background: var(--severity-info); }
    }
  `]
})
export class DetectionChartComponent {
  timeline = input.required<TimelineBucket[]>();
  interval = input<TimelineInterval>('1h');
  intervalChange = signal<TimelineInterval>('1h');

  chartData = computed<ChartBar[]>(() => {
    const data = this.timeline();
    if (data.length === 0) return [];

    const maxValue = Math.max(...data.map(d => d.count), 1);

    return data.map(bucket => {
      const bySeverity = bucket.by_severity || {};
      const date = new Date(bucket.timestamp);

      return {
        timestamp: bucket.timestamp,
        label: this.formatLabel(date),
        total: bucket.count,
        critical: bySeverity['critical'] || 0,
        high: bySeverity['high'] || 0,
        medium: bySeverity['medium'] || 0,
        low: bySeverity['low'] || 0,
        info: bySeverity['info'] || 0,
        height: (bucket.count / maxValue) * 100
      };
    });
  });

  yAxisTicks = computed<number[]>(() => {
    const data = this.timeline();
    if (data.length === 0) return [0];

    const maxValue = Math.max(...data.map(d => d.count), 1);
    const step = Math.ceil(maxValue / 4);
    const ticks: number[] = [];

    for (let i = 4; i >= 0; i--) {
      ticks.push(Math.min(step * i, maxValue));
    }

    return ticks;
  });

  onIntervalChange(value: TimelineInterval): void {
    this.intervalChange.set(value);
  }

  formatLabel(date: Date): string {
    const interval = this.interval();
    if (interval === '15m' || interval === '1h') {
      return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } else if (interval === '4h') {
      return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } else {
      return date.toLocaleDateString([], { month: 'short', day: 'numeric' });
    }
  }

  formatNumber(value: number): string {
    if (value >= 1000) {
      return (value / 1000).toFixed(1) + 'K';
    }
    return value.toString();
  }

  getTooltip(bar: ChartBar): string {
    const parts = [`Total: ${bar.total}`];
    if (bar.critical > 0) parts.push(`Critical: ${bar.critical}`);
    if (bar.high > 0) parts.push(`High: ${bar.high}`);
    if (bar.medium > 0) parts.push(`Medium: ${bar.medium}`);
    if (bar.low > 0) parts.push(`Low: ${bar.low}`);
    if (bar.info > 0) parts.push(`Info: ${bar.info}`);
    return parts.join('\n');
  }
}
