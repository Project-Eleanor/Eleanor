import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatBadgeModule } from '@angular/material/badge';
import { MatMenuModule } from '@angular/material/menu';
import { MatDividerModule } from '@angular/material/divider';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { NotificationService } from '../../../core/services/notification.service';
import { Notification, NotificationSeverity } from '../../models';

@Component({
  selector: 'app-notification-bell',
  standalone: true,
  imports: [
    CommonModule,
    RouterModule,
    MatButtonModule,
    MatIconModule,
    MatBadgeModule,
    MatMenuModule,
    MatDividerModule,
    MatProgressSpinnerModule
  ],
  template: `
    <button mat-icon-button
            [matMenuTriggerFor]="notificationMenu"
            (menuOpened)="onMenuOpened()"
            class="notification-bell"
            [matBadge]="unreadCount()"
            [matBadgeHidden]="!hasUnread()"
            matBadgeColor="warn"
            matBadgeSize="small">
      <mat-icon>notifications</mat-icon>
    </button>

    <mat-menu #notificationMenu="matMenu" class="notification-menu" xPosition="before">
      <div class="notification-header" (click)="$event.stopPropagation()">
        <h3>Notifications</h3>
        @if (hasUnread()) {
          <button mat-button color="accent" (click)="markAllRead()">
            Mark all read
          </button>
        }
      </div>

      <mat-divider></mat-divider>

      <div class="notification-content" (click)="$event.stopPropagation()">
        @if (loading()) {
          <div class="loading">
            <mat-spinner diameter="24"></mat-spinner>
          </div>
        } @else if (notifications().length === 0) {
          <div class="empty-state">
            <mat-icon>notifications_none</mat-icon>
            <p>No notifications</p>
          </div>
        } @else {
          @for (notification of notifications(); track notification.id) {
            <div class="notification-item"
                 [class.unread]="!notification.read"
                 [class]="'severity-' + notification.severity"
                 (click)="onNotificationClick(notification)">
              <div class="notification-icon">
                <mat-icon>{{ getIcon(notification) }}</mat-icon>
              </div>
              <div class="notification-body">
                <div class="notification-title">{{ notification.title }}</div>
                @if (notification.body) {
                  <div class="notification-text">{{ notification.body }}</div>
                }
                <div class="notification-time">{{ formatTime(notification.created_at) }}</div>
              </div>
              <button mat-icon-button class="dismiss-btn" (click)="dismiss($event, notification.id)">
                <mat-icon>close</mat-icon>
              </button>
            </div>
          }
        }
      </div>

      <mat-divider></mat-divider>

      <div class="notification-footer">
        <a mat-button routerLink="/settings/notifications">
          View all notifications
        </a>
      </div>
    </mat-menu>
  `,
  styles: [`
    .notification-bell {
      position: relative;
    }

    ::ng-deep .notification-menu {
      width: 380px;
      max-width: 90vw;
    }

    .notification-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 12px 16px;

      h3 {
        margin: 0;
        font-size: 16px;
        font-weight: 500;
      }
    }

    .notification-content {
      max-height: 400px;
      overflow-y: auto;
    }

    .loading {
      display: flex;
      justify-content: center;
      padding: 32px;
    }

    .empty-state {
      display: flex;
      flex-direction: column;
      align-items: center;
      padding: 32px;
      color: var(--text-muted);

      mat-icon {
        font-size: 48px;
        width: 48px;
        height: 48px;
        margin-bottom: 8px;
      }

      p {
        margin: 0;
      }
    }

    .notification-item {
      display: flex;
      gap: 12px;
      padding: 12px 16px;
      cursor: pointer;
      transition: background-color 0.15s ease;
      position: relative;

      &:hover {
        background: var(--bg-tertiary);
      }

      &.unread {
        background: rgba(88, 166, 255, 0.1);

        &::before {
          content: '';
          position: absolute;
          left: 0;
          top: 0;
          bottom: 0;
          width: 3px;
          background: var(--accent);
        }
      }

      &.severity-warning {
        &::before {
          background: var(--warning);
        }
      }

      &.severity-error, &.severity-critical {
        &::before {
          background: var(--danger);
        }
      }

      &.severity-success {
        &::before {
          background: var(--success);
        }
      }
    }

    .notification-icon {
      flex-shrink: 0;
      width: 36px;
      height: 36px;
      border-radius: 50%;
      background: var(--bg-tertiary);
      display: flex;
      align-items: center;
      justify-content: center;

      mat-icon {
        font-size: 18px;
        width: 18px;
        height: 18px;
      }
    }

    .notification-body {
      flex: 1;
      min-width: 0;
    }

    .notification-title {
      font-weight: 500;
      font-size: 13px;
      margin-bottom: 2px;
    }

    .notification-text {
      font-size: 12px;
      color: var(--text-secondary);
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .notification-time {
      font-size: 11px;
      color: var(--text-muted);
      margin-top: 4px;
    }

    .dismiss-btn {
      opacity: 0;
      transition: opacity 0.15s ease;

      .notification-item:hover & {
        opacity: 1;
      }
    }

    .notification-footer {
      display: flex;
      justify-content: center;
      padding: 8px;
    }
  `]
})
export class NotificationBellComponent implements OnInit {
  private readonly notificationService = inject(NotificationService);

  readonly notifications = this.notificationService.notifications;
  readonly unreadCount = this.notificationService.unreadCount;
  readonly hasUnread = this.notificationService.hasUnread;
  readonly loading = this.notificationService.loading;

  ngOnInit(): void {
    // Initial load of unread count
    this.notificationService.getUnreadCount().subscribe();
  }

  onMenuOpened(): void {
    // Load notifications when menu opens
    this.notificationService.list({ page_size: 10 }).subscribe();
  }

  onNotificationClick(notification: Notification): void {
    if (!notification.read) {
      this.notificationService.markAsRead(notification.id).subscribe();
    }

    if (notification.link) {
      // Navigate to the link
      window.location.href = notification.link;
    }
  }

  markAllRead(): void {
    this.notificationService.markAllAsRead().subscribe();
  }

  dismiss(event: Event, notificationId: string): void {
    event.stopPropagation();
    this.notificationService.dismiss(notificationId).subscribe();
  }

  getIcon(notification: Notification): string {
    if (notification.icon) return notification.icon;

    // Default icons based on type
    const iconMap: Record<string, string> = {
      case_created: 'folder',
      case_updated: 'edit',
      case_assigned: 'person_add',
      case_closed: 'check_circle',
      evidence_uploaded: 'upload_file',
      evidence_processed: 'verified',
      workflow_started: 'play_circle',
      workflow_completed: 'task_alt',
      workflow_failed: 'error',
      approval_required: 'pending_actions',
      approval_granted: 'thumb_up',
      approval_denied: 'thumb_down',
      detection_hit: 'security',
      alert_triggered: 'warning',
      system_alert: 'info',
      integration_error: 'cloud_off',
      mention: 'alternate_email',
      comment: 'comment'
    };

    return iconMap[notification.type] || 'notifications';
  }

  formatTime(timestamp: string): string {
    const date = new Date(timestamp);
    const now = new Date();
    const diff = now.getTime() - date.getTime();

    const minutes = Math.floor(diff / 60000);
    const hours = Math.floor(diff / 3600000);
    const days = Math.floor(diff / 86400000);

    if (minutes < 1) return 'Just now';
    if (minutes < 60) return `${minutes}m ago`;
    if (hours < 24) return `${hours}h ago`;
    if (days < 7) return `${days}d ago`;

    return date.toLocaleDateString();
  }
}
