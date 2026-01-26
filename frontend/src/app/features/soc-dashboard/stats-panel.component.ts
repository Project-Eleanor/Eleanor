import { Component, input, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MatCardModule } from '@angular/material/card';
import { MatIconModule } from '@angular/material/icon';
import { MatTooltipModule } from '@angular/material/tooltip';

export interface StatCard {
  label: string;
  value: number;
  icon: string;
  color: 'info' | 'warning' | 'danger' | 'success' | 'accent';
  trend?: number;
  subtitle?: string;
}

@Component({
  selector: 'app-stats-panel',
  standalone: true,
  imports: [CommonModule, MatCardModule, MatIconModule, MatTooltipModule],
  template: `
    <div class="stats-panel">
      @for (stat of stats(); track stat.label) {
        <mat-card class="stat-card" [class]="'border-' + stat.color">
          <div class="stat-accent" [class]="stat.color"></div>
          <div class="stat-icon" [class]="'bg-' + stat.color">
            <mat-icon>{{ stat.icon }}</mat-icon>
          </div>
          <div class="stat-content">
            <span class="stat-value">{{ formatNumber(stat.value) }}</span>
            <span class="stat-label">{{ stat.label }}</span>
            @if (stat.subtitle) {
              <span class="stat-subtitle">{{ stat.subtitle }}</span>
            }
          </div>
          @if (stat.trend !== undefined) {
            <div class="stat-trend" [class.positive]="stat.trend > 0" [class.negative]="stat.trend < 0">
              <mat-icon>{{ stat.trend > 0 ? 'trending_up' : stat.trend < 0 ? 'trending_down' : 'trending_flat' }}</mat-icon>
              <span>{{ stat.trend > 0 ? '+' : '' }}{{ stat.trend }}%</span>
            </div>
          }
        </mat-card>
      }
    </div>
  `,
  styles: [`
    .stats-panel {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
      gap: 16px;
    }

    .stat-card {
      display: flex;
      align-items: center;
      gap: 16px;
      padding: 20px;
      background: var(--bg-card);
      border: 1px solid var(--border-color);
      position: relative;
      overflow: hidden;
      transition: transform 0.2s ease, box-shadow 0.2s ease;

      &:hover {
        transform: translateY(-4px);
        box-shadow: 0 12px 32px rgba(0, 0, 0, 0.25);

        .stat-accent {
          height: 100%;
        }
      }

      &.border-danger { border-left: 3px solid var(--danger); }
      &.border-warning { border-left: 3px solid var(--warning); }
      &.border-success { border-left: 3px solid var(--success); }
      &.border-info { border-left: 3px solid var(--info); }
      &.border-accent { border-left: 3px solid var(--accent); }
    }

    .stat-accent {
      position: absolute;
      left: 0;
      bottom: 0;
      width: 3px;
      height: 0;
      transition: height 0.3s ease;

      &.danger { background: var(--danger); }
      &.warning { background: var(--warning); }
      &.success { background: var(--success); }
      &.info { background: var(--info); }
      &.accent { background: var(--accent); }
    }

    .stat-icon {
      width: 48px;
      height: 48px;
      border-radius: 12px;
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;

      mat-icon {
        color: white;
        font-size: 24px;
        width: 24px;
        height: 24px;
      }

      &.bg-danger { background: linear-gradient(135deg, var(--danger) 0%, #c73e37 100%); }
      &.bg-warning { background: linear-gradient(135deg, var(--warning) 0%, #b8840a 100%); mat-icon { color: black; } }
      &.bg-success { background: linear-gradient(135deg, var(--success) 0%, #2d9a40 100%); mat-icon { color: black; } }
      &.bg-info { background: linear-gradient(135deg, var(--info) 0%, #3d8bd9 100%); }
      &.bg-accent { background: linear-gradient(135deg, var(--accent) 0%, #2d7dd2 100%); }
    }

    .stat-content {
      display: flex;
      flex-direction: column;
      flex: 1;
      min-width: 0;
    }

    .stat-value {
      font-family: var(--font-display);
      font-size: 28px;
      font-weight: 700;
      color: var(--text-primary);
      line-height: 1;
    }

    .stat-label {
      font-size: 13px;
      color: var(--text-secondary);
      margin-top: 4px;
    }

    .stat-subtitle {
      font-size: 11px;
      color: var(--text-muted);
      margin-top: 2px;
    }

    .stat-trend {
      display: flex;
      align-items: center;
      gap: 2px;
      font-size: 12px;
      font-weight: 500;
      padding: 4px 8px;
      border-radius: 8px;
      background: var(--bg-tertiary);

      mat-icon {
        font-size: 16px;
        width: 16px;
        height: 16px;
      }

      &.positive {
        color: var(--danger);
        mat-icon { color: var(--danger); }
      }

      &.negative {
        color: var(--success);
        mat-icon { color: var(--success); }
      }
    }
  `]
})
export class StatsPanelComponent {
  stats = input.required<StatCard[]>();

  formatNumber(value: number): string {
    if (value >= 1000000) {
      return (value / 1000000).toFixed(1) + 'M';
    } else if (value >= 1000) {
      return (value / 1000).toFixed(1) + 'K';
    }
    return value.toLocaleString();
  }
}
