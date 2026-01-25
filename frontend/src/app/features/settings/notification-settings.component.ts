import { Component, OnInit, inject, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatSlideToggleModule } from '@angular/material/slide-toggle';
import { MatDividerModule } from '@angular/material/divider';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { RouterModule } from '@angular/router';
import { NotificationService } from '../../core/services/notification.service';
import { NotificationPreferences, NotificationType } from '../../shared/models';

@Component({
  selector: 'app-notification-settings',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    RouterModule,
    MatCardModule,
    MatButtonModule,
    MatIconModule,
    MatSlideToggleModule,
    MatDividerModule,
    MatProgressSpinnerModule,
    MatFormFieldModule,
    MatInputModule,
    MatSnackBarModule
  ],
  template: `
    <div class="notification-settings">
      <div class="page-header">
        <a mat-button routerLink="/settings">
          <mat-icon>arrow_back</mat-icon>
          Back to Settings
        </a>
        <h1>Notification Settings</h1>
      </div>

      @if (loading()) {
        <div class="loading">
          <mat-spinner diameter="40"></mat-spinner>
        </div>
      } @else if (preferences()) {
        <!-- Delivery Channels -->
        <mat-card class="settings-card">
          <mat-card-header>
            <mat-icon mat-card-avatar>send</mat-icon>
            <mat-card-title>Delivery Channels</mat-card-title>
            <mat-card-subtitle>Choose how you receive notifications</mat-card-subtitle>
          </mat-card-header>
          <mat-card-content>
            <div class="preference-row">
              <div class="preference-info">
                <span class="preference-label">In-App Notifications</span>
                <span class="preference-desc">Show notifications in the app notification center</span>
              </div>
              <mat-slide-toggle
                [checked]="preferences()!.in_app_enabled"
                (change)="updatePreference('in_app_enabled', $event.checked)">
              </mat-slide-toggle>
            </div>
            <mat-divider></mat-divider>
            <div class="preference-row">
              <div class="preference-info">
                <span class="preference-label">Email Notifications</span>
                <span class="preference-desc">Receive notifications via email</span>
              </div>
              <mat-slide-toggle
                [checked]="preferences()!.email_enabled"
                (change)="updatePreference('email_enabled', $event.checked)">
              </mat-slide-toggle>
            </div>
            <mat-divider></mat-divider>
            <div class="preference-row">
              <div class="preference-info">
                <span class="preference-label">Push Notifications</span>
                <span class="preference-desc">Receive browser push notifications</span>
              </div>
              <mat-slide-toggle
                [checked]="preferences()!.push_enabled"
                (change)="updatePreference('push_enabled', $event.checked)">
              </mat-slide-toggle>
            </div>
          </mat-card-content>
        </mat-card>

        <!-- Quiet Hours -->
        <mat-card class="settings-card">
          <mat-card-header>
            <mat-icon mat-card-avatar>do_not_disturb</mat-icon>
            <mat-card-title>Quiet Hours</mat-card-title>
            <mat-card-subtitle>Pause notifications during specific hours</mat-card-subtitle>
          </mat-card-header>
          <mat-card-content>
            <div class="preference-row">
              <div class="preference-info">
                <span class="preference-label">Enable Quiet Hours</span>
                <span class="preference-desc">Suppress notifications during the specified time range</span>
              </div>
              <mat-slide-toggle
                [checked]="preferences()!.quiet_hours_enabled"
                (change)="updatePreference('quiet_hours_enabled', $event.checked)">
              </mat-slide-toggle>
            </div>
            @if (preferences()!.quiet_hours_enabled) {
              <mat-divider></mat-divider>
              <div class="time-range">
                <mat-form-field>
                  <mat-label>Start Time</mat-label>
                  <input matInput type="time"
                         [ngModel]="preferences()!.quiet_hours_start || '22:00'"
                         (ngModelChange)="updatePreference('quiet_hours_start', $event)">
                </mat-form-field>
                <span class="time-separator">to</span>
                <mat-form-field>
                  <mat-label>End Time</mat-label>
                  <input matInput type="time"
                         [ngModel]="preferences()!.quiet_hours_end || '07:00'"
                         (ngModelChange)="updatePreference('quiet_hours_end', $event)">
                </mat-form-field>
              </div>
            }
          </mat-card-content>
        </mat-card>

        <!-- Notification Types -->
        <mat-card class="settings-card">
          <mat-card-header>
            <mat-icon mat-card-avatar>tune</mat-icon>
            <mat-card-title>Notification Types</mat-card-title>
            <mat-card-subtitle>Choose which notifications you want to receive</mat-card-subtitle>
          </mat-card-header>
          <mat-card-content>
            @for (category of notificationCategories; track category.label) {
              <div class="category-header">{{ category.label }}</div>
              @for (type of category.types; track type.type; let last = $last) {
                <div class="preference-row indent">
                  <div class="preference-info">
                    <span class="preference-label">{{ type.label }}</span>
                    <span class="preference-desc">{{ type.description }}</span>
                  </div>
                  <mat-slide-toggle
                    [checked]="isTypeEnabled(type.type)"
                    (change)="updateTypePreference(type.type, $event.checked)">
                  </mat-slide-toggle>
                </div>
                @if (!last) {
                  <mat-divider></mat-divider>
                }
              }
              <mat-divider class="category-divider"></mat-divider>
            }
          </mat-card-content>
        </mat-card>

        <!-- Notification History -->
        <mat-card class="settings-card">
          <mat-card-header>
            <mat-icon mat-card-avatar>history</mat-icon>
            <mat-card-title>Notification History</mat-card-title>
            <mat-card-subtitle>View all your notifications</mat-card-subtitle>
          </mat-card-header>
          <mat-card-content>
            <div class="notification-list">
              @for (notification of recentNotifications(); track notification.id) {
                <div class="notification-item" [class.unread]="!notification.read">
                  <mat-icon [class]="'severity-' + notification.severity">
                    {{ getNotificationIcon(notification.type) }}
                  </mat-icon>
                  <div class="notification-body">
                    <span class="notification-title">{{ notification.title }}</span>
                    @if (notification.body) {
                      <span class="notification-text">{{ notification.body }}</span>
                    }
                    <span class="notification-time">{{ formatTime(notification.created_at) }}</span>
                  </div>
                </div>
              } @empty {
                <div class="empty-state">
                  <mat-icon>notifications_none</mat-icon>
                  <span>No notifications yet</span>
                </div>
              }
            </div>
          </mat-card-content>
          <mat-card-actions>
            <button mat-button color="accent" (click)="markAllRead()">Mark All as Read</button>
          </mat-card-actions>
        </mat-card>
      }
    </div>
  `,
  styles: [`
    .notification-settings {
      max-width: 800px;
      margin: 0 auto;
    }

    .page-header {
      margin-bottom: 24px;

      a {
        margin-bottom: 8px;
        color: var(--text-secondary);
      }

      h1 {
        font-size: 24px;
        margin: 8px 0 0;
      }
    }

    .loading {
      display: flex;
      justify-content: center;
      padding: 48px;
    }

    .settings-card {
      margin-bottom: 24px;
      background: var(--bg-card);

      mat-card-avatar {
        font-size: 24px;
        width: 40px;
        height: 40px;
        display: flex;
        align-items: center;
        justify-content: center;
        color: var(--accent);
      }
    }

    .preference-row {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 16px 0;

      &.indent {
        padding-left: 16px;
      }
    }

    .preference-info {
      display: flex;
      flex-direction: column;
      gap: 4px;
    }

    .preference-label {
      font-weight: 500;
    }

    .preference-desc {
      font-size: 12px;
      color: var(--text-secondary);
    }

    .time-range {
      display: flex;
      align-items: center;
      gap: 16px;
      padding: 16px 0;

      mat-form-field {
        width: 150px;
      }
    }

    .time-separator {
      color: var(--text-secondary);
    }

    .category-header {
      font-size: 12px;
      font-weight: 600;
      text-transform: uppercase;
      color: var(--accent);
      padding: 16px 0 8px;
      letter-spacing: 0.5px;
    }

    .category-divider {
      margin: 8px 0 !important;
    }

    .notification-list {
      max-height: 400px;
      overflow-y: auto;
    }

    .notification-item {
      display: flex;
      gap: 12px;
      padding: 12px 0;
      border-bottom: 1px solid var(--border-color);

      &:last-child {
        border-bottom: none;
      }

      &.unread {
        background: rgba(88, 166, 255, 0.05);
        margin: 0 -16px;
        padding: 12px 16px;
      }

      mat-icon {
        flex-shrink: 0;

        &.severity-info { color: var(--info); }
        &.severity-success { color: var(--success); }
        &.severity-warning { color: var(--warning); }
        &.severity-error, &.severity-critical { color: var(--danger); }
      }
    }

    .notification-body {
      display: flex;
      flex-direction: column;
      gap: 2px;
      min-width: 0;
    }

    .notification-title {
      font-weight: 500;
      font-size: 13px;
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
    }
  `]
})
export class NotificationSettingsComponent implements OnInit {
  private readonly notificationService = inject(NotificationService);
  private readonly snackBar = inject(MatSnackBar);

  readonly loading = signal(true);
  readonly preferences = signal<NotificationPreferences | null>(null);
  readonly recentNotifications = this.notificationService.notifications;

  readonly notificationCategories = [
    {
      label: 'Cases',
      types: [
        { type: 'case_created' as NotificationType, label: 'Case Created', description: 'When a new case is created' },
        { type: 'case_updated' as NotificationType, label: 'Case Updated', description: 'When a case is modified' },
        { type: 'case_assigned' as NotificationType, label: 'Case Assigned', description: 'When a case is assigned to you' },
        { type: 'case_closed' as NotificationType, label: 'Case Closed', description: 'When a case is closed' }
      ]
    },
    {
      label: 'Evidence',
      types: [
        { type: 'evidence_uploaded' as NotificationType, label: 'Evidence Uploaded', description: 'When new evidence is uploaded' },
        { type: 'evidence_processed' as NotificationType, label: 'Evidence Processed', description: 'When evidence processing completes' }
      ]
    },
    {
      label: 'Workflows',
      types: [
        { type: 'workflow_started' as NotificationType, label: 'Workflow Started', description: 'When a workflow execution begins' },
        { type: 'workflow_completed' as NotificationType, label: 'Workflow Completed', description: 'When a workflow completes successfully' },
        { type: 'workflow_failed' as NotificationType, label: 'Workflow Failed', description: 'When a workflow execution fails' },
        { type: 'approval_required' as NotificationType, label: 'Approval Required', description: 'When a workflow needs your approval' }
      ]
    },
    {
      label: 'Detections',
      types: [
        { type: 'detection_hit' as NotificationType, label: 'Detection Hit', description: 'When a detection rule triggers' },
        { type: 'alert_triggered' as NotificationType, label: 'Alert Triggered', description: 'When a security alert is raised' }
      ]
    },
    {
      label: 'System',
      types: [
        { type: 'system_alert' as NotificationType, label: 'System Alerts', description: 'Important system notifications' },
        { type: 'integration_error' as NotificationType, label: 'Integration Errors', description: 'When an integration fails' }
      ]
    },
    {
      label: 'Collaboration',
      types: [
        { type: 'mention' as NotificationType, label: 'Mentions', description: 'When someone mentions you' },
        { type: 'comment' as NotificationType, label: 'Comments', description: 'When someone comments on your items' }
      ]
    }
  ];

  ngOnInit(): void {
    this.loadPreferences();
    this.loadNotifications();
  }

  private loadPreferences(): void {
    this.notificationService.getPreferences().subscribe({
      next: (prefs) => {
        this.preferences.set(prefs);
        this.loading.set(false);
      },
      error: () => {
        // Set defaults if loading fails
        this.preferences.set({
          email_enabled: false,
          push_enabled: false,
          in_app_enabled: true,
          type_preferences: {
            case_created: true,
            case_updated: true,
            case_assigned: true,
            case_closed: true,
            evidence_uploaded: true,
            evidence_processed: true,
            workflow_started: true,
            workflow_completed: true,
            workflow_failed: true,
            approval_required: true,
            approval_granted: true,
            approval_denied: true,
            detection_hit: true,
            alert_triggered: true,
            system_alert: true,
            integration_error: true,
            scheduled_task: true,
            mention: true,
            comment: true
          },
          quiet_hours_enabled: false,
          quiet_hours_start: null,
          quiet_hours_end: null
        });
        this.loading.set(false);
      }
    });
  }

  private loadNotifications(): void {
    this.notificationService.list({ page_size: 20 }).subscribe();
  }

  updatePreference(key: string, value: boolean | string): void {
    const updates = { [key]: value };
    this.notificationService.updatePreferences(updates).subscribe({
      next: (prefs) => {
        this.preferences.set(prefs);
        this.snackBar.open('Preferences updated', 'Dismiss', { duration: 2000 });
      },
      error: () => {
        this.snackBar.open('Failed to update preferences', 'Dismiss', { duration: 3000 });
      }
    });
  }

  isTypeEnabled(type: NotificationType): boolean {
    const prefs = this.preferences();
    if (!prefs) return true;
    return prefs.type_preferences[type] !== false;
  }

  updateTypePreference(type: NotificationType, enabled: boolean): void {
    const prefs = this.preferences();
    if (!prefs) return;

    const updates = {
      type_preferences: {
        ...prefs.type_preferences,
        [type]: enabled
      }
    };

    this.notificationService.updatePreferences(updates).subscribe({
      next: (newPrefs) => {
        this.preferences.set(newPrefs);
        this.snackBar.open('Preferences updated', 'Dismiss', { duration: 2000 });
      },
      error: () => {
        this.snackBar.open('Failed to update preferences', 'Dismiss', { duration: 3000 });
      }
    });
  }

  markAllRead(): void {
    this.notificationService.markAllAsRead().subscribe({
      next: () => {
        this.snackBar.open('All notifications marked as read', 'Dismiss', { duration: 2000 });
      }
    });
  }

  getNotificationIcon(type: NotificationType): string {
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
    return iconMap[type] || 'notifications';
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
