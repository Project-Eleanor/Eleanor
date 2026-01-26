import { Injectable, signal, computed, OnDestroy } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable, Subject, interval, takeUntil, switchMap, tap, catchError, of } from 'rxjs';
import { environment } from '../../../environments/environment';
import { WebSocketService, WebSocketMessage } from './websocket.service';

// =============================================================================
// Types
// =============================================================================

export interface AlertStats {
  total: number;
  open: number;
  critical: number;
  high: number;
}

export interface CaseStats {
  total: number;
  active: number;
}

export interface RuleStats {
  total: number;
  enabled: number;
}

export interface EventStats {
  total: number;
}

export interface OverviewStats {
  time_range: string;
  since: string;
  alerts: AlertStats;
  cases: CaseStats;
  rules: RuleStats;
  events: EventStats;
  generated_at: string;
}

export interface TimelineBucket {
  timestamp: string;
  count: number;
  by_severity: Record<string, number>;
}

export interface TopRule {
  id: string;
  name: string;
  severity: string;
  hit_count: number;
  last_run_at: string | null;
  mitre_techniques: string[];
}

export interface LiveAlert {
  id: string;
  title: string;
  severity: 'critical' | 'high' | 'medium' | 'low' | 'info';
  rule_name: string;
  timestamp: string;
  source_ip?: string;
  destination_ip?: string;
  mitre_techniques: string[];
}

export interface LiveEvent {
  id: string;
  type: string;
  message: string;
  timestamp: string;
  source?: string;
}

export type TimeRange = '1h' | '24h' | '7d' | '30d';
export type TimelineInterval = '15m' | '1h' | '4h' | '1d';

@Injectable({
  providedIn: 'root'
})
export class RealtimeDashboardService implements OnDestroy {
  private readonly apiUrl = `${environment.apiUrl}/realtime`;
  private readonly destroy$ = new Subject<void>();
  private pollingActive = false;

  // Reactive state
  private _stats = signal<OverviewStats | null>(null);
  private _timeline = signal<TimelineBucket[]>([]);
  private _topRules = signal<TopRule[]>([]);
  private _severityDistribution = signal<Record<string, number>>({});
  private _mitreHeatmap = signal<Record<string, number>>({});
  private _liveAlerts = signal<LiveAlert[]>([]);
  private _liveEvents = signal<LiveEvent[]>([]);
  private _isLoading = signal(true);
  private _error = signal<string | null>(null);
  private _lastUpdated = signal<Date | null>(null);
  private _timeRange = signal<TimeRange>('24h');
  private _timelineInterval = signal<TimelineInterval>('1h');

  // Public readable signals
  readonly stats = this._stats.asReadonly();
  readonly timeline = this._timeline.asReadonly();
  readonly topRules = this._topRules.asReadonly();
  readonly severityDistribution = this._severityDistribution.asReadonly();
  readonly mitreHeatmap = this._mitreHeatmap.asReadonly();
  readonly liveAlerts = this._liveAlerts.asReadonly();
  readonly liveEvents = this._liveEvents.asReadonly();
  readonly isLoading = this._isLoading.asReadonly();
  readonly error = this._error.asReadonly();
  readonly lastUpdated = this._lastUpdated.asReadonly();
  readonly timeRange = this._timeRange.asReadonly();
  readonly timelineInterval = this._timelineInterval.asReadonly();

  // Computed values
  readonly totalAlerts = computed(() => this._stats()?.alerts.total ?? 0);
  readonly openAlerts = computed(() => this._stats()?.alerts.open ?? 0);
  readonly criticalAlerts = computed(() => this._stats()?.alerts.critical ?? 0);
  readonly highAlerts = computed(() => this._stats()?.alerts.high ?? 0);
  readonly activeCases = computed(() => this._stats()?.cases.active ?? 0);
  readonly totalCases = computed(() => this._stats()?.cases.total ?? 0);
  readonly enabledRules = computed(() => this._stats()?.rules.enabled ?? 0);
  readonly totalEvents = computed(() => this._stats()?.events.total ?? 0);

  constructor(
    private http: HttpClient,
    private wsService: WebSocketService
  ) {
    this.setupWebSocketListeners();
  }

  ngOnDestroy(): void {
    this.destroy$.next();
    this.destroy$.complete();
    this.stopPolling();
  }

  // ==========================================================================
  // Time Range Configuration
  // ==========================================================================

  setTimeRange(range: TimeRange): void {
    this._timeRange.set(range);
    this.refresh();
  }

  setTimelineInterval(interval: TimelineInterval): void {
    this._timelineInterval.set(interval);
    this.loadTimeline();
  }

  // ==========================================================================
  // Data Loading
  // ==========================================================================

  refresh(): void {
    this._isLoading.set(true);
    this._error.set(null);

    // Load all data in parallel
    this.loadStats();
    this.loadTimeline();
    this.loadTopRules();
    this.loadSeverityDistribution();
    this.loadMitreHeatmap();
  }

  loadStats(): void {
    const params = new HttpParams().set('time_range', this._timeRange());

    this.http.get<OverviewStats>(`${this.apiUrl}/stats`, { params })
      .pipe(catchError(err => {
        this._error.set('Failed to load dashboard stats');
        return of(null);
      }))
      .subscribe(stats => {
        if (stats) {
          this._stats.set(stats);
          this._lastUpdated.set(new Date());
        }
        this._isLoading.set(false);
      });
  }

  loadTimeline(): void {
    const params = new HttpParams()
      .set('time_range', this._timeRange())
      .set('interval', this._timelineInterval());

    this.http.get<TimelineBucket[]>(`${this.apiUrl}/alerts/timeline`, { params })
      .pipe(catchError(() => of([])))
      .subscribe(timeline => {
        this._timeline.set(timeline);
      });
  }

  loadTopRules(limit = 10): void {
    const params = new HttpParams()
      .set('time_range', this._timeRange())
      .set('limit', limit.toString());

    this.http.get<TopRule[]>(`${this.apiUrl}/rules/top`, { params })
      .pipe(catchError(() => of([])))
      .subscribe(rules => {
        this._topRules.set(rules);
      });
  }

  loadSeverityDistribution(): void {
    const params = new HttpParams().set('time_range', this._timeRange());

    this.http.get<Record<string, number>>(`${this.apiUrl}/alerts/severity`, { params })
      .pipe(catchError(() => of({})))
      .subscribe(distribution => {
        this._severityDistribution.set(distribution);
      });
  }

  loadMitreHeatmap(): void {
    const params = new HttpParams().set('time_range', this._timeRange());

    this.http.get<Record<string, number>>(`${this.apiUrl}/mitre/heatmap`, { params })
      .pipe(catchError(() => of({})))
      .subscribe(heatmap => {
        this._mitreHeatmap.set(heatmap);
      });
  }

  // ==========================================================================
  // Live Data Management
  // ==========================================================================

  startPolling(intervalMs = 30000): void {
    if (this.pollingActive) return;
    this.pollingActive = true;

    // Initial load
    this.refresh();

    // Set up polling interval
    interval(intervalMs)
      .pipe(takeUntil(this.destroy$))
      .subscribe(() => {
        if (this.pollingActive) {
          this.loadStats();
        }
      });
  }

  stopPolling(): void {
    this.pollingActive = false;
  }

  private setupWebSocketListeners(): void {
    // Subscribe to dashboard topics
    this.wsService.subscribe('dashboard:alerts');
    this.wsService.subscribe('dashboard:events');
    this.wsService.subscribe('dashboard:stats');
    this.wsService.subscribe('dashboard:detections');

    // Handle alert events
    this.wsService.onEvents('alert_created', 'detection_hit')
      .pipe(takeUntil(this.destroy$))
      .subscribe(msg => this.handleAlertEvent(msg));

    // Handle event updates
    this.wsService.onEvent('event_ingested')
      .pipe(takeUntil(this.destroy$))
      .subscribe(msg => this.handleEventUpdate(msg));

    // Handle stats updates
    this.wsService.onEvent('stats_update')
      .pipe(takeUntil(this.destroy$))
      .subscribe(msg => this.handleStatsUpdate(msg));
  }

  private handleAlertEvent(msg: WebSocketMessage): void {
    const alert: LiveAlert = {
      id: msg.data['id'] as string,
      title: msg.data['title'] as string,
      severity: msg.data['severity'] as LiveAlert['severity'],
      rule_name: msg.data['rule_name'] as string,
      timestamp: msg.timestamp,
      source_ip: msg.data['source_ip'] as string | undefined,
      destination_ip: msg.data['destination_ip'] as string | undefined,
      mitre_techniques: (msg.data['mitre_techniques'] as string[]) || []
    };

    // Prepend new alert and keep last 50
    const alerts = [alert, ...this._liveAlerts()].slice(0, 50);
    this._liveAlerts.set(alerts);

    // Update stats incrementally
    const currentStats = this._stats();
    if (currentStats) {
      const updatedStats = {
        ...currentStats,
        alerts: {
          ...currentStats.alerts,
          total: currentStats.alerts.total + 1,
          open: currentStats.alerts.open + 1,
          critical: alert.severity === 'critical'
            ? currentStats.alerts.critical + 1
            : currentStats.alerts.critical,
          high: alert.severity === 'high'
            ? currentStats.alerts.high + 1
            : currentStats.alerts.high
        }
      };
      this._stats.set(updatedStats);
    }
  }

  private handleEventUpdate(msg: WebSocketMessage): void {
    const event: LiveEvent = {
      id: msg.id,
      type: msg.data['event_type'] as string,
      message: msg.data['message'] as string,
      timestamp: msg.timestamp,
      source: msg.data['source'] as string | undefined
    };

    // Prepend new event and keep last 100
    const events = [event, ...this._liveEvents()].slice(0, 100);
    this._liveEvents.set(events);

    // Update event count
    const currentStats = this._stats();
    if (currentStats) {
      this._stats.set({
        ...currentStats,
        events: {
          total: currentStats.events.total + 1
        }
      });
    }
  }

  private handleStatsUpdate(msg: WebSocketMessage): void {
    // Full stats update from server
    if (msg.data['stats']) {
      this._stats.set(msg.data['stats'] as OverviewStats);
      this._lastUpdated.set(new Date());
    }
  }

  // ==========================================================================
  // Alert Management
  // ==========================================================================

  clearLiveAlerts(): void {
    this._liveAlerts.set([]);
  }

  clearLiveEvents(): void {
    this._liveEvents.set([]);
  }

  dismissAlert(alertId: string): void {
    const alerts = this._liveAlerts().filter(a => a.id !== alertId);
    this._liveAlerts.set(alerts);
  }
}
