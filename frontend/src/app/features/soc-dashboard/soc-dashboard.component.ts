import { Component, OnInit, OnDestroy, computed, signal, effect, DestroyRef, inject } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { MatCardModule } from '@angular/material/card';
import { MatIconModule } from '@angular/material/icon';
import { MatButtonModule } from '@angular/material/button';
import { MatButtonToggleModule } from '@angular/material/button-toggle';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatChipsModule } from '@angular/material/chips';
import { MatMenuModule } from '@angular/material/menu';
import { FormsModule } from '@angular/forms';

import {
  RealtimeDashboardService,
  TimeRange,
  TimelineInterval,
  TopRule
} from '../../core/services/realtime-dashboard.service';
import { WebSocketService } from '../../core/services/websocket.service';
import { StatsPanelComponent, StatCard } from './stats-panel.component';
import { AlertFeedComponent } from './alert-feed.component';
import { EventTickerComponent } from './event-ticker.component';
import { DetectionChartComponent } from './detection-chart.component';

@Component({
  selector: 'app-soc-dashboard',
  standalone: true,
  imports: [
    CommonModule,
    RouterModule,
    MatCardModule,
    MatIconModule,
    MatButtonModule,
    MatButtonToggleModule,
    MatProgressSpinnerModule,
    MatTooltipModule,
    MatChipsModule,
    MatMenuModule,
    FormsModule,
    StatsPanelComponent,
    AlertFeedComponent,
    EventTickerComponent,
    DetectionChartComponent
  ],
  template: `
    <div class="soc-dashboard">
      <!-- Header -->
      <header class="dashboard-header">
        <div class="header-left">
          <h1 class="dashboard-title">
            <mat-icon>security</mat-icon>
            SOC Dashboard
          </h1>
          <div class="connection-status" [class]="wsStatus()">
            <span class="status-dot"></span>
            <span>{{ wsStatus() | titlecase }}</span>
          </div>
        </div>
        <div class="header-right">
          <mat-button-toggle-group [value]="timeRange()" (change)="onTimeRangeChange($event.value)">
            <mat-button-toggle value="1h">1 Hour</mat-button-toggle>
            <mat-button-toggle value="24h">24 Hours</mat-button-toggle>
            <mat-button-toggle value="7d">7 Days</mat-button-toggle>
            <mat-button-toggle value="30d">30 Days</mat-button-toggle>
          </mat-button-toggle-group>
          <button mat-icon-button
                  matTooltip="Refresh"
                  (click)="refresh()">
            <mat-icon>refresh</mat-icon>
          </button>
          @if (lastUpdated()) {
            <span class="last-updated">
              Updated {{ formatLastUpdated() }}
            </span>
          }
        </div>
      </header>

      <!-- Event Ticker -->
      <section class="ticker-section">
        <app-event-ticker [events]="liveEvents()" />
      </section>

      <!-- Loading State -->
      @if (isLoading()) {
        <div class="loading-overlay">
          <mat-spinner diameter="48"></mat-spinner>
          <span>Loading dashboard...</span>
        </div>
      }

      <!-- Error State -->
      @if (error()) {
        <div class="error-banner">
          <mat-icon>error_outline</mat-icon>
          <span>{{ error() }}</span>
          <button mat-button (click)="refresh()">Retry</button>
        </div>
      }

      <!-- Stats Panel -->
      <section class="stats-section">
        <app-stats-panel [stats]="statCards()" />
      </section>

      <!-- Main Content Grid -->
      <div class="dashboard-grid">
        <!-- Alert Timeline Chart -->
        <section class="chart-section">
          <app-detection-chart
            [timeline]="timeline()"
            [interval]="timelineInterval()"
            (intervalChange)="onIntervalChange($event)" />
        </section>

        <!-- Live Alert Feed -->
        <section class="feed-section">
          <app-alert-feed
            [alerts]="liveAlerts()"
            (dismiss)="dismissAlert($event)"
            (clearAll)="clearAlerts()"
            (alertClicked)="onAlertClick($event)" />
        </section>
      </div>

      <!-- Bottom Row -->
      <div class="bottom-grid">
        <!-- Top Rules -->
        <section class="rules-section">
          <mat-card class="rules-card">
            <div class="card-header">
              <div class="card-title">
                <mat-icon>rule</mat-icon>
                <span>Top Triggering Rules</span>
              </div>
              <button mat-button color="accent" routerLink="/analytics">View All</button>
            </div>
            <div class="rules-list">
              @if (topRules().length === 0) {
                <div class="empty-state">
                  <mat-icon>playlist_add_check</mat-icon>
                  <p>No rule triggers in this period</p>
                </div>
              } @else {
                @for (rule of topRules(); track rule.id) {
                  <div class="rule-item" [routerLink]="['/analytics']" [queryParams]="{rule: rule.id}">
                    <div class="rule-info">
                      <span class="rule-name">{{ rule.name }}</span>
                      <div class="rule-meta">
                        <span class="severity-badge" [class]="rule.severity">
                          {{ rule.severity | uppercase }}
                        </span>
                        @for (technique of rule.mitre_techniques.slice(0, 2); track technique) {
                          <span class="mitre-badge">{{ technique }}</span>
                        }
                      </div>
                    </div>
                    <div class="rule-stats">
                      <span class="hit-count">{{ rule.hit_count }}</span>
                      <span class="hit-label">hits</span>
                    </div>
                  </div>
                }
              }
            </div>
          </mat-card>
        </section>

        <!-- Severity Distribution -->
        <section class="severity-section">
          <mat-card class="severity-card">
            <div class="card-header">
              <div class="card-title">
                <mat-icon>pie_chart</mat-icon>
                <span>Severity Distribution</span>
              </div>
            </div>
            <div class="severity-content">
              @if (hasSeverityData()) {
                <div class="severity-bars">
                  @for (item of severityItems(); track item.label) {
                    <div class="severity-row">
                      <span class="severity-label" [class]="item.key">{{ item.label }}</span>
                      <div class="severity-bar-container">
                        <div class="severity-bar"
                             [class]="item.key"
                             [style.width.%]="item.percent">
                        </div>
                      </div>
                      <span class="severity-count">{{ item.count }}</span>
                    </div>
                  }
                </div>
                <div class="severity-total">
                  <span>Total Alerts</span>
                  <strong>{{ totalSeverityCount() }}</strong>
                </div>
              } @else {
                <div class="empty-state">
                  <mat-icon>donut_large</mat-icon>
                  <p>No severity data</p>
                </div>
              }
            </div>
          </mat-card>
        </section>

        <!-- Quick Actions -->
        <section class="actions-section">
          <mat-card class="actions-card">
            <div class="card-header">
              <div class="card-title">
                <mat-icon>flash_on</mat-icon>
                <span>Quick Actions</span>
              </div>
            </div>
            <div class="actions-grid">
              <button mat-stroked-button routerLink="/incidents">
                <mat-icon>add_task</mat-icon>
                New Case
              </button>
              <button mat-stroked-button routerLink="/hunting">
                <mat-icon>search</mat-icon>
                Hunt
              </button>
              <button mat-stroked-button routerLink="/analytics">
                <mat-icon>rule</mat-icon>
                Rules
              </button>
              <button mat-stroked-button routerLink="/automation">
                <mat-icon>play_circle</mat-icon>
                Playbooks
              </button>
            </div>
          </mat-card>
        </section>
      </div>
    </div>
  `,
  styles: [`
    .soc-dashboard {
      max-width: 1600px;
      margin: 0 auto;
      padding: 0 16px;
      animation: fadeIn 0.3s ease-out;
    }

    @keyframes fadeIn {
      from { opacity: 0; transform: translateY(8px); }
      to { opacity: 1; transform: translateY(0); }
    }

    /* Header */
    .dashboard-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 24px;
      padding: 16px 0;
      border-bottom: 1px solid var(--border-color);
    }

    .header-left {
      display: flex;
      align-items: center;
      gap: 16px;
    }

    .dashboard-title {
      display: flex;
      align-items: center;
      gap: 12px;
      font-family: var(--font-display);
      font-size: 24px;
      font-weight: 700;
      margin: 0;
      color: var(--text-primary);

      mat-icon {
        font-size: 28px;
        width: 28px;
        height: 28px;
        color: var(--accent);
      }
    }

    .connection-status {
      display: flex;
      align-items: center;
      gap: 6px;
      font-size: 12px;
      padding: 4px 12px;
      border-radius: 12px;
      background: var(--bg-tertiary);

      .status-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background: var(--text-muted);
      }

      &.connected {
        .status-dot {
          background: var(--success);
          animation: pulse 2s infinite;
        }
      }

      &.connecting {
        .status-dot {
          background: var(--warning);
          animation: pulse 0.5s infinite;
        }
      }

      &.error, &.disconnected {
        .status-dot {
          background: var(--danger);
        }
      }
    }

    @keyframes pulse {
      0%, 100% { opacity: 1; }
      50% { opacity: 0.5; }
    }

    .header-right {
      display: flex;
      align-items: center;
      gap: 12px;
    }

    mat-button-toggle-group {
      height: 36px;
      border: 1px solid var(--border-color);

      ::ng-deep .mat-button-toggle {
        background: var(--bg-card);

        &.mat-button-toggle-checked {
          background: var(--accent);
          color: white;
        }

        .mat-button-toggle-label-content {
          font-size: 12px;
          line-height: 34px;
          padding: 0 16px;
        }
      }
    }

    .last-updated {
      font-size: 11px;
      color: var(--text-muted);
      font-family: var(--font-mono);
    }

    /* Sections */
    .ticker-section {
      margin-bottom: 24px;
    }

    .stats-section {
      margin-bottom: 24px;
    }

    .loading-overlay {
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 16px;
      padding: 64px;
      color: var(--text-secondary);
    }

    .error-banner {
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 12px 16px;
      margin-bottom: 24px;
      background: rgba(248, 81, 73, 0.1);
      border: 1px solid var(--danger);
      border-radius: 8px;
      color: var(--danger);

      mat-icon {
        font-size: 20px;
      }

      span {
        flex: 1;
      }
    }

    /* Dashboard Grid */
    .dashboard-grid {
      display: grid;
      grid-template-columns: 1fr 400px;
      gap: 24px;
      margin-bottom: 24px;
    }

    .bottom-grid {
      display: grid;
      grid-template-columns: 1fr 1fr 300px;
      gap: 24px;
    }

    @media (max-width: 1200px) {
      .dashboard-grid {
        grid-template-columns: 1fr;
      }

      .bottom-grid {
        grid-template-columns: 1fr 1fr;
      }
    }

    @media (max-width: 768px) {
      .bottom-grid {
        grid-template-columns: 1fr;
      }
    }

    /* Cards */
    .rules-card, .severity-card, .actions-card {
      background: var(--bg-card);
      border: 1px solid var(--border-color);
      height: 100%;
    }

    .card-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 16px;
      border-bottom: 1px solid var(--border-color);
    }

    .card-title {
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

    /* Rules List */
    .rules-list {
      max-height: 300px;
      overflow-y: auto;
    }

    .rule-item {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 12px 16px;
      border-bottom: 1px solid var(--border-color);
      cursor: pointer;
      transition: background 0.2s ease;

      &:hover {
        background: var(--bg-secondary);
      }

      &:last-child {
        border-bottom: none;
      }
    }

    .rule-info {
      min-width: 0;
    }

    .rule-name {
      font-size: 13px;
      font-weight: 500;
      color: var(--text-primary);
      display: block;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .rule-meta {
      display: flex;
      gap: 6px;
      margin-top: 4px;
    }

    .severity-badge {
      font-size: 10px;
      font-weight: 600;
      padding: 2px 6px;
      border-radius: 4px;
      text-transform: uppercase;

      &.critical { background: var(--severity-critical); color: white; }
      &.high { background: var(--severity-high); color: white; }
      &.medium { background: var(--severity-medium); color: black; }
      &.low { background: var(--severity-low); color: white; }
    }

    .mitre-badge {
      font-size: 10px;
      font-family: var(--font-mono);
      color: var(--accent);
      background: rgba(74, 158, 255, 0.1);
      padding: 2px 6px;
      border-radius: 4px;
    }

    .rule-stats {
      text-align: right;
    }

    .hit-count {
      font-family: var(--font-display);
      font-size: 20px;
      font-weight: 700;
      color: var(--text-primary);
      display: block;
    }

    .hit-label {
      font-size: 11px;
      color: var(--text-muted);
    }

    /* Severity Distribution */
    .severity-content {
      padding: 16px;
    }

    .severity-bars {
      display: flex;
      flex-direction: column;
      gap: 12px;
    }

    .severity-row {
      display: flex;
      align-items: center;
      gap: 12px;
    }

    .severity-label {
      width: 70px;
      font-size: 12px;
      font-weight: 500;

      &.critical { color: var(--severity-critical); }
      &.high { color: var(--severity-high); }
      &.medium { color: var(--severity-medium); }
      &.low { color: var(--severity-low); }
      &.info { color: var(--severity-info); }
    }

    .severity-bar-container {
      flex: 1;
      height: 8px;
      background: var(--bg-tertiary);
      border-radius: 4px;
      overflow: hidden;
    }

    .severity-bar {
      height: 100%;
      border-radius: 4px;
      transition: width 0.5s ease;

      &.critical { background: var(--severity-critical); }
      &.high { background: var(--severity-high); }
      &.medium { background: var(--severity-medium); }
      &.low { background: var(--severity-low); }
      &.info { background: var(--severity-info); }
    }

    .severity-count {
      width: 50px;
      text-align: right;
      font-size: 12px;
      font-family: var(--font-mono);
      color: var(--text-secondary);
    }

    .severity-total {
      display: flex;
      justify-content: space-between;
      margin-top: 16px;
      padding-top: 16px;
      border-top: 1px solid var(--border-color);
      font-size: 13px;
      color: var(--text-secondary);

      strong {
        font-family: var(--font-mono);
        color: var(--text-primary);
      }
    }

    /* Quick Actions */
    .actions-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
      padding: 16px;

      button {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 8px;
        padding: 20px 16px;
        height: auto;
        border-color: var(--border-color);

        mat-icon {
          font-size: 24px;
          width: 24px;
          height: 24px;
          color: var(--accent);
        }

        &:hover {
          border-color: var(--accent);
          background: rgba(74, 158, 255, 0.05);
        }
      }
    }

    /* Empty State */
    .empty-state {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      padding: 32px;
      color: var(--text-muted);

      mat-icon {
        font-size: 36px;
        width: 36px;
        height: 36px;
        opacity: 0.3;
        margin-bottom: 8px;
      }

      p {
        margin: 0;
        font-size: 13px;
      }
    }
  `]
})
export class SocDashboardComponent implements OnInit, OnDestroy {
  // Services
  private dashboardService: RealtimeDashboardService;
  private wsService: WebSocketService;

  // State from service
  isLoading = computed(() => this.dashboardService.isLoading());
  error = computed(() => this.dashboardService.error());
  lastUpdated = computed(() => this.dashboardService.lastUpdated());
  timeRange = computed(() => this.dashboardService.timeRange());
  timelineInterval = computed(() => this.dashboardService.timelineInterval());
  timeline = computed(() => this.dashboardService.timeline());
  topRules = computed(() => this.dashboardService.topRules());
  severityDistribution = computed(() => this.dashboardService.severityDistribution());
  liveAlerts = computed(() => this.dashboardService.liveAlerts());
  liveEvents = computed(() => this.dashboardService.liveEvents());

  // WebSocket status
  wsStatus = signal<string>('disconnected');

  // Computed stat cards
  statCards = computed<StatCard[]>(() => {
    const stats = this.dashboardService.stats();
    if (!stats) return [];

    return [
      {
        label: 'Total Alerts',
        value: stats.alerts.total,
        icon: 'warning',
        color: 'info',
        subtitle: `${stats.alerts.open} open`
      },
      {
        label: 'Critical',
        value: stats.alerts.critical,
        icon: 'priority_high',
        color: 'danger'
      },
      {
        label: 'High Priority',
        value: stats.alerts.high,
        icon: 'arrow_upward',
        color: 'warning'
      },
      {
        label: 'Active Cases',
        value: stats.cases.active,
        icon: 'folder_open',
        color: 'accent',
        subtitle: `of ${stats.cases.total} total`
      },
      {
        label: 'Enabled Rules',
        value: stats.rules.enabled,
        icon: 'rule',
        color: 'success',
        subtitle: `of ${stats.rules.total} total`
      },
      {
        label: 'Events',
        value: stats.events.total,
        icon: 'event_note',
        color: 'info',
        subtitle: this.formatTimeRange()
      }
    ];
  });

  // Severity items for bar chart
  severityItems = computed(() => {
    const dist = this.severityDistribution();
    const total = this.totalSeverityCount();
    if (total === 0) return [];

    const items = [
      { key: 'critical', label: 'Critical', count: dist['critical'] || 0 },
      { key: 'high', label: 'High', count: dist['high'] || 0 },
      { key: 'medium', label: 'Medium', count: dist['medium'] || 0 },
      { key: 'low', label: 'Low', count: dist['low'] || 0 },
      { key: 'info', label: 'Info', count: dist['info'] || 0 }
    ];

    return items.map(item => ({
      ...item,
      percent: (item.count / total) * 100
    }));
  });

  totalSeverityCount = computed(() => {
    const dist = this.severityDistribution();
    return Object.values(dist).reduce((sum, count) => sum + count, 0);
  });

  hasSeverityData = computed(() => this.totalSeverityCount() > 0);

  private destroyRef = inject(DestroyRef);

  constructor(
    dashboardService: RealtimeDashboardService,
    wsService: WebSocketService
  ) {
    this.dashboardService = dashboardService;
    this.wsService = wsService;

    // Track WebSocket status with proper cleanup
    this.wsService.status$
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe(status => {
        this.wsStatus.set(status);
      });
  }

  ngOnInit(): void {
    // Start polling and load initial data
    this.dashboardService.startPolling(30000);

    // Ensure WebSocket is connected
    this.wsService.connect();
  }

  ngOnDestroy(): void {
    this.dashboardService.stopPolling();
  }

  onTimeRangeChange(range: TimeRange): void {
    this.dashboardService.setTimeRange(range);
  }

  onIntervalChange(interval: TimelineInterval): void {
    this.dashboardService.setTimelineInterval(interval);
  }

  refresh(): void {
    this.dashboardService.refresh();
  }

  dismissAlert(alertId: string): void {
    this.dashboardService.dismissAlert(alertId);
  }

  clearAlerts(): void {
    this.dashboardService.clearLiveAlerts();
  }

  onAlertClick(alert: any): void {
    // Navigate to alert details or open dialog
    console.log('Alert clicked:', alert);
  }

  formatLastUpdated(): string {
    const date = this.lastUpdated();
    if (!date) return '';

    const now = new Date();
    const diff = now.getTime() - date.getTime();

    if (diff < 60000) {
      return 'just now';
    } else if (diff < 3600000) {
      const mins = Math.floor(diff / 60000);
      return `${mins}m ago`;
    } else {
      return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }
  }

  formatTimeRange(): string {
    const range = this.timeRange();
    const labels: Record<TimeRange, string> = {
      '1h': 'last hour',
      '24h': 'last 24h',
      '7d': 'last 7 days',
      '30d': 'last 30 days'
    };
    return labels[range];
  }
}
