import { Component, input, OnInit, OnDestroy, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MatIconModule } from '@angular/material/icon';
import { LiveEvent } from '../../core/services/realtime-dashboard.service';

@Component({
  selector: 'app-event-ticker',
  standalone: true,
  imports: [CommonModule, MatIconModule],
  template: `
    <div class="event-ticker" [class.paused]="isPaused()">
      <div class="ticker-label">
        <mat-icon>rss_feed</mat-icon>
        <span>Live</span>
      </div>
      <div class="ticker-content"
           (mouseenter)="pause()"
           (mouseleave)="resume()">
        @if (events().length === 0) {
          <span class="no-events">Waiting for events...</span>
        } @else {
          <div class="ticker-scroll" [style.animation-duration.s]="scrollDuration()">
            @for (event of displayEvents(); track event.id) {
              <span class="ticker-item">
                <span class="event-type" [class]="getEventTypeClass(event.type)">
                  {{ event.type }}
                </span>
                <span class="event-message">{{ event.message }}</span>
                <span class="event-time">{{ formatTime(event.timestamp) }}</span>
                @if (event.source) {
                  <span class="event-source">{{ event.source }}</span>
                }
              </span>
            }
          </div>
        }
      </div>
      <div class="ticker-stats">
        <span class="stat">
          <strong>{{ eventsPerMinute() }}</strong> events/min
        </span>
      </div>
    </div>
  `,
  styles: [`
    .event-ticker {
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 8px 16px;
      background: var(--bg-card);
      border: 1px solid var(--border-color);
      border-radius: 8px;
      overflow: hidden;
    }

    .ticker-label {
      display: flex;
      align-items: center;
      gap: 6px;
      flex-shrink: 0;
      padding: 4px 12px;
      background: var(--success);
      border-radius: 4px;
      font-size: 12px;
      font-weight: 600;
      color: black;

      mat-icon {
        font-size: 14px;
        width: 14px;
        height: 14px;
        animation: blink 1s infinite;
      }
    }

    @keyframes blink {
      0%, 100% { opacity: 1; }
      50% { opacity: 0.5; }
    }

    .ticker-content {
      flex: 1;
      overflow: hidden;
      position: relative;
      height: 24px;
    }

    .no-events {
      color: var(--text-muted);
      font-size: 12px;
      font-style: italic;
    }

    .ticker-scroll {
      display: flex;
      gap: 32px;
      animation: scroll linear infinite;
      white-space: nowrap;
      padding-left: 100%;

      .paused & {
        animation-play-state: paused;
      }
    }

    @keyframes scroll {
      0% {
        transform: translateX(0);
      }
      100% {
        transform: translateX(-100%);
      }
    }

    .ticker-item {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      font-size: 12px;
    }

    .event-type {
      font-family: var(--font-mono);
      font-size: 10px;
      font-weight: 500;
      padding: 2px 6px;
      border-radius: 4px;
      text-transform: uppercase;

      &.auth { background: var(--info); color: white; }
      &.network { background: var(--accent); color: white; }
      &.process { background: var(--warning); color: black; }
      &.file { background: var(--success); color: black; }
      &.registry { background: #9f7aea; color: white; }
      &.default { background: var(--bg-tertiary); color: var(--text-secondary); }
    }

    .event-message {
      color: var(--text-primary);
      max-width: 400px;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    .event-time {
      color: var(--text-muted);
      font-family: var(--font-mono);
    }

    .event-source {
      color: var(--text-secondary);
      font-family: var(--font-mono);
      background: var(--bg-tertiary);
      padding: 2px 6px;
      border-radius: 4px;
    }

    .ticker-stats {
      flex-shrink: 0;
      padding-left: 12px;
      border-left: 1px solid var(--border-color);
    }

    .stat {
      font-size: 11px;
      color: var(--text-secondary);

      strong {
        color: var(--text-primary);
        font-family: var(--font-mono);
      }
    }
  `]
})
export class EventTickerComponent implements OnInit, OnDestroy {
  events = input.required<LiveEvent[]>();

  isPaused = signal(false);
  eventsPerMinute = signal(0);

  private statsInterval?: ReturnType<typeof setInterval>;
  private eventTimestamps: number[] = [];

  ngOnInit(): void {
    this.statsInterval = setInterval(() => this.calculateEPM(), 5000);
  }

  ngOnDestroy(): void {
    if (this.statsInterval) {
      clearInterval(this.statsInterval);
    }
  }

  displayEvents(): LiveEvent[] {
    // Show last 20 events for ticker
    return this.events().slice(0, 20);
  }

  scrollDuration(): number {
    // Adjust scroll speed based on number of events
    const count = this.displayEvents().length;
    return Math.max(30, count * 3);
  }

  pause(): void {
    this.isPaused.set(true);
  }

  resume(): void {
    this.isPaused.set(false);
  }

  formatTime(timestamp: string): string {
    const date = new Date(timestamp);
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  }

  getEventTypeClass(type: string): string {
    const typeMap: Record<string, string> = {
      authentication: 'auth',
      login: 'auth',
      logout: 'auth',
      network: 'network',
      connection: 'network',
      dns: 'network',
      process: 'process',
      execution: 'process',
      file: 'file',
      registry: 'registry'
    };

    for (const [key, value] of Object.entries(typeMap)) {
      if (type.toLowerCase().includes(key)) {
        return value;
      }
    }
    return 'default';
  }

  private calculateEPM(): void {
    const now = Date.now();
    const oneMinuteAgo = now - 60000;

    // Add timestamps from new events
    const newTimestamps = this.events()
      .slice(0, 10)
      .map(e => new Date(e.timestamp).getTime())
      .filter(t => t > oneMinuteAgo);

    this.eventTimestamps = [
      ...this.eventTimestamps.filter(t => t > oneMinuteAgo),
      ...newTimestamps
    ];

    this.eventsPerMinute.set(this.eventTimestamps.length);
  }
}
