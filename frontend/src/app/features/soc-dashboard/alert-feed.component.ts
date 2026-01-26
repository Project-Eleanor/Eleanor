import { Component, input, output, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MatCardModule } from '@angular/material/card';
import { MatIconModule } from '@angular/material/icon';
import { MatButtonModule } from '@angular/material/button';
import { MatChipsModule } from '@angular/material/chips';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatBadgeModule } from '@angular/material/badge';
import { RouterModule } from '@angular/router';
import { LiveAlert } from '../../core/services/realtime-dashboard.service';

@Component({
  selector: 'app-alert-feed',
  standalone: true,
  imports: [
    CommonModule,
    RouterModule,
    MatCardModule,
    MatIconModule,
    MatButtonModule,
    MatChipsModule,
    MatTooltipModule,
    MatBadgeModule
  ],
  template: `
    <div class="alert-feed">
      <div class="feed-header">
        <div class="feed-title">
          <mat-icon>notifications_active</mat-icon>
          <span>Live Alerts</span>
          @if (alerts().length > 0) {
            <span class="alert-count">{{ alerts().length }}</span>
          }
        </div>
        <div class="feed-actions">
          @if (alerts().length > 0) {
            <button mat-icon-button
                    matTooltip="Clear all"
                    (click)="clearAll.emit()">
              <mat-icon>clear_all</mat-icon>
            </button>
          }
        </div>
      </div>

      <div class="feed-content">
        @if (alerts().length === 0) {
          <div class="empty-state">
            <mat-icon>shield</mat-icon>
            <p>No new alerts</p>
            <span>Alerts will appear here in real-time</span>
          </div>
        } @else {
          <div class="alerts-list">
            @for (alert of alerts(); track alert.id; let i = $index) {
              <div class="alert-item"
                   [class]="'severity-' + alert.severity"
                   [@slideIn]
                   (click)="alertClicked.emit(alert)">
                <div class="alert-severity">
                  <div class="severity-indicator" [class]="alert.severity"></div>
                </div>
                <div class="alert-content">
                  <div class="alert-header">
                    <span class="alert-title">{{ alert.title }}</span>
                    <button mat-icon-button
                            class="dismiss-btn"
                            (click)="$event.stopPropagation(); dismiss.emit(alert.id)">
                      <mat-icon>close</mat-icon>
                    </button>
                  </div>
                  <div class="alert-meta">
                    <span class="rule-name">{{ alert.rule_name }}</span>
                    <span class="alert-time">{{ formatTime(alert.timestamp) }}</span>
                  </div>
                  @if (alert.source_ip || alert.destination_ip) {
                    <div class="alert-ips">
                      @if (alert.source_ip) {
                        <span class="ip-badge" matTooltip="Source IP">
                          <mat-icon>arrow_upward</mat-icon>
                          {{ alert.source_ip }}
                        </span>
                      }
                      @if (alert.destination_ip) {
                        <span class="ip-badge" matTooltip="Destination IP">
                          <mat-icon>arrow_downward</mat-icon>
                          {{ alert.destination_ip }}
                        </span>
                      }
                    </div>
                  }
                  @if (alert.mitre_techniques.length > 0) {
                    <div class="mitre-tags">
                      @for (technique of alert.mitre_techniques.slice(0, 3); track technique) {
                        <span class="mitre-tag" [routerLink]="['/mitre']" [queryParams]="{technique: technique}">
                          {{ technique }}
                        </span>
                      }
                      @if (alert.mitre_techniques.length > 3) {
                        <span class="mitre-more">+{{ alert.mitre_techniques.length - 3 }}</span>
                      }
                    </div>
                  }
                </div>
              </div>
            }
          </div>
        }
      </div>
    </div>
  `,
  styles: [`
    .alert-feed {
      display: flex;
      flex-direction: column;
      height: 100%;
      background: var(--bg-card);
      border: 1px solid var(--border-color);
      border-radius: 8px;
      overflow: hidden;
    }

    .feed-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 16px;
      border-bottom: 1px solid var(--border-color);
      background: var(--bg-secondary);
    }

    .feed-title {
      display: flex;
      align-items: center;
      gap: 8px;
      font-family: var(--font-display);
      font-weight: 600;
      font-size: 14px;
      color: var(--text-primary);

      mat-icon {
        color: var(--warning);
        font-size: 20px;
        width: 20px;
        height: 20px;
      }
    }

    .alert-count {
      background: var(--danger);
      color: white;
      font-size: 11px;
      font-weight: 600;
      padding: 2px 8px;
      border-radius: 10px;
      min-width: 20px;
      text-align: center;
    }

    .feed-content {
      flex: 1;
      overflow-y: auto;
      min-height: 300px;
      max-height: 500px;
    }

    .empty-state {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      height: 100%;
      padding: 48px;
      color: var(--text-muted);

      mat-icon {
        font-size: 48px;
        width: 48px;
        height: 48px;
        opacity: 0.3;
        margin-bottom: 16px;
      }

      p {
        margin: 0;
        font-size: 14px;
        font-weight: 500;
      }

      span {
        font-size: 12px;
        margin-top: 4px;
      }
    }

    .alerts-list {
      display: flex;
      flex-direction: column;
    }

    .alert-item {
      display: flex;
      gap: 12px;
      padding: 12px 16px;
      border-bottom: 1px solid var(--border-color);
      cursor: pointer;
      transition: background 0.2s ease;
      animation: slideIn 0.3s ease-out;

      &:hover {
        background: var(--bg-secondary);

        .dismiss-btn {
          opacity: 1;
        }
      }

      &:last-child {
        border-bottom: none;
      }

      &.severity-critical {
        border-left: 3px solid var(--severity-critical);
        background: rgba(248, 81, 73, 0.05);
      }

      &.severity-high {
        border-left: 3px solid var(--severity-high);
        background: rgba(255, 123, 114, 0.05);
      }

      &.severity-medium {
        border-left: 3px solid var(--severity-medium);
      }

      &.severity-low {
        border-left: 3px solid var(--severity-low);
      }
    }

    @keyframes slideIn {
      from {
        opacity: 0;
        transform: translateX(-10px);
      }
      to {
        opacity: 1;
        transform: translateX(0);
      }
    }

    .alert-severity {
      flex-shrink: 0;
      padding-top: 4px;
    }

    .severity-indicator {
      width: 10px;
      height: 10px;
      border-radius: 50%;
      animation: pulse 2s infinite;

      &.critical { background: var(--severity-critical); }
      &.high { background: var(--severity-high); }
      &.medium { background: var(--severity-medium); }
      &.low { background: var(--severity-low); }
      &.info { background: var(--severity-info); }
    }

    @keyframes pulse {
      0% { opacity: 1; }
      50% { opacity: 0.5; }
      100% { opacity: 1; }
    }

    .alert-content {
      flex: 1;
      min-width: 0;
    }

    .alert-header {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 8px;
    }

    .alert-title {
      font-size: 13px;
      font-weight: 500;
      color: var(--text-primary);
      line-height: 1.4;
      overflow: hidden;
      text-overflow: ellipsis;
      display: -webkit-box;
      -webkit-line-clamp: 2;
      -webkit-box-orient: vertical;
    }

    .dismiss-btn {
      opacity: 0;
      transition: opacity 0.2s ease;
      margin: -8px;

      mat-icon {
        font-size: 16px;
        width: 16px;
        height: 16px;
      }
    }

    .alert-meta {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-top: 4px;
      font-size: 11px;
      color: var(--text-secondary);
    }

    .rule-name {
      font-family: var(--font-mono);
      background: var(--bg-tertiary);
      padding: 2px 6px;
      border-radius: 4px;
    }

    .alert-time {
      color: var(--text-muted);
    }

    .alert-ips {
      display: flex;
      gap: 8px;
      margin-top: 6px;
    }

    .ip-badge {
      display: inline-flex;
      align-items: center;
      gap: 2px;
      font-size: 11px;
      font-family: var(--font-mono);
      color: var(--text-secondary);
      background: var(--bg-tertiary);
      padding: 2px 6px;
      border-radius: 4px;

      mat-icon {
        font-size: 12px;
        width: 12px;
        height: 12px;
      }
    }

    .mitre-tags {
      display: flex;
      flex-wrap: wrap;
      gap: 4px;
      margin-top: 6px;
    }

    .mitre-tag {
      font-size: 10px;
      font-family: var(--font-mono);
      color: var(--accent);
      background: rgba(74, 158, 255, 0.1);
      padding: 2px 6px;
      border-radius: 4px;
      cursor: pointer;
      transition: background 0.2s ease;

      &:hover {
        background: rgba(74, 158, 255, 0.2);
      }
    }

    .mitre-more {
      font-size: 10px;
      color: var(--text-muted);
      padding: 2px 6px;
    }
  `]
})
export class AlertFeedComponent {
  alerts = input.required<LiveAlert[]>();

  dismiss = output<string>();
  clearAll = output<void>();
  alertClicked = output<LiveAlert>();

  formatTime(timestamp: string): string {
    const date = new Date(timestamp);
    const now = new Date();
    const diff = now.getTime() - date.getTime();

    if (diff < 60000) {
      return 'Just now';
    } else if (diff < 3600000) {
      const mins = Math.floor(diff / 60000);
      return `${mins}m ago`;
    } else if (diff < 86400000) {
      const hours = Math.floor(diff / 3600000);
      return `${hours}h ago`;
    } else {
      return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }
  }
}
