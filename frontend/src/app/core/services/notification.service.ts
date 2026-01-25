import { Injectable, inject, signal, computed } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, tap, interval, switchMap, filter, startWith, takeUntil, Subject } from 'rxjs';
import { AppConfigService } from '../config/app-config.service';
import { WebSocketService, WebSocketMessage } from './websocket.service';
import { AuthService } from '../auth/auth.service';
import {
  Notification,
  NotificationListResponse,
  NotificationPreferences,
  NotificationPreferenceUpdate,
  NotificationSeverity
} from '../../shared/models';

@Injectable({
  providedIn: 'root'
})
export class NotificationService {
  private readonly config = inject(AppConfigService);
  private readonly http = inject(HttpClient);
  private readonly webSocketService = inject(WebSocketService);
  private readonly authService = inject(AuthService);

  private get apiUrl(): string {
    return `${this.config.apiUrl}/notifications`;
  }

  private readonly destroy$ = new Subject<void>();

  // Signals for reactive state
  private readonly notificationsSignal = signal<Notification[]>([]);
  private readonly unreadCountSignal = signal<number>(0);
  private readonly loadingSignal = signal<boolean>(false);
  private readonly totalSignal = signal<number>(0);

  readonly notifications = this.notificationsSignal.asReadonly();
  readonly unreadCount = this.unreadCountSignal.asReadonly();
  readonly loading = this.loadingSignal.asReadonly();
  readonly total = this.totalSignal.asReadonly();

  readonly hasUnread = computed(() => this.unreadCountSignal() > 0);

  // Real-time notifications from WebSocket
  private readonly realtimeNotifications = signal<Notification[]>([]);

  constructor() {
    this.setupWebSocketListener();
    this.setupPolling();
  }

  private setupWebSocketListener(): void {
    this.webSocketService.onNotifications()
      .pipe(takeUntil(this.destroy$))
      .subscribe(message => {
        this.handleRealtimeNotification(message);
      });
  }

  private setupPolling(): void {
    // Poll for unread count every 60 seconds as fallback
    interval(60000)
      .pipe(
        startWith(0),
        filter(() => this.authService.isAuthenticated()),
        switchMap(() => this.getUnreadCount()),
        takeUntil(this.destroy$)
      )
      .subscribe();
  }

  private handleRealtimeNotification(message: WebSocketMessage): void {
    const notification: Notification = {
      id: message.id,
      type: message.data['type'] as any,
      severity: (message.data['severity'] || 'info') as NotificationSeverity,
      title: message.data['title'] as string || 'New Notification',
      body: message.data['body'] as string || null,
      link: message.data['link'] as string || null,
      icon: null,
      data: message.data,
      read: false,
      read_at: null,
      created_at: message.timestamp
    };

    // Add to realtime notifications
    this.realtimeNotifications.update(list => [notification, ...list]);

    // Increment unread count
    this.unreadCountSignal.update(count => count + 1);

    // Add to main list if loaded
    this.notificationsSignal.update(list => [notification, ...list]);
  }

  // ==========================================================================
  // API Methods
  // ==========================================================================

  /**
   * List notifications with pagination.
   */
  list(params: {
    page?: number;
    page_size?: number;
    unread_only?: boolean;
    notification_type?: string;
  } = {}): Observable<NotificationListResponse> {
    this.loadingSignal.set(true);

    return this.http.get<NotificationListResponse>(this.apiUrl, { params: params as any }).pipe(
      tap(response => {
        this.notificationsSignal.set(response.items);
        this.unreadCountSignal.set(response.unread_count);
        this.totalSignal.set(response.total);
        this.loadingSignal.set(false);
      })
    );
  }

  /**
   * Get a specific notification.
   */
  get(notificationId: string): Observable<Notification> {
    return this.http.get<Notification>(`${this.apiUrl}/${notificationId}`);
  }

  /**
   * Get unread count.
   */
  getUnreadCount(): Observable<{ unread_count: number }> {
    return this.http.get<{ unread_count: number }>(`${this.apiUrl}/unread-count`).pipe(
      tap(response => this.unreadCountSignal.set(response.unread_count))
    );
  }

  /**
   * Mark a notification as read.
   */
  markAsRead(notificationId: string): Observable<{ success: boolean }> {
    return this.http.post<{ success: boolean }>(`${this.apiUrl}/${notificationId}/read`, {}).pipe(
      tap(() => {
        // Update local state
        this.notificationsSignal.update(list =>
          list.map(n => n.id === notificationId ? { ...n, read: true, read_at: new Date().toISOString() } : n)
        );
        this.unreadCountSignal.update(count => Math.max(0, count - 1));
      })
    );
  }

  /**
   * Mark multiple notifications as read.
   */
  markMultipleAsRead(notificationIds: string[]): Observable<{ success: boolean; count: number }> {
    return this.http.post<{ success: boolean; count: number }>(`${this.apiUrl}/mark-read`, {
      notification_ids: notificationIds
    }).pipe(
      tap(response => {
        this.notificationsSignal.update(list =>
          list.map(n => notificationIds.includes(n.id) ? { ...n, read: true, read_at: new Date().toISOString() } : n)
        );
        this.unreadCountSignal.update(count => Math.max(0, count - response.count));
      })
    );
  }

  /**
   * Mark all notifications as read.
   */
  markAllAsRead(): Observable<{ success: boolean; count: number }> {
    return this.http.post<{ success: boolean; count: number }>(`${this.apiUrl}/mark-all-read`, {}).pipe(
      tap(() => {
        this.notificationsSignal.update(list =>
          list.map(n => ({ ...n, read: true, read_at: new Date().toISOString() }))
        );
        this.unreadCountSignal.set(0);
      })
    );
  }

  /**
   * Dismiss a notification.
   */
  dismiss(notificationId: string): Observable<{ success: boolean }> {
    return this.http.delete<{ success: boolean }>(`${this.apiUrl}/${notificationId}`).pipe(
      tap(() => {
        this.notificationsSignal.update(list => list.filter(n => n.id !== notificationId));
        // Decrement unread if it was unread
        const notification = this.notificationsSignal().find(n => n.id === notificationId);
        if (notification && !notification.read) {
          this.unreadCountSignal.update(count => Math.max(0, count - 1));
        }
      })
    );
  }

  // ==========================================================================
  // Preferences
  // ==========================================================================

  /**
   * Get notification preferences.
   */
  getPreferences(): Observable<NotificationPreferences> {
    return this.http.get<NotificationPreferences>(`${this.apiUrl}/preferences`);
  }

  /**
   * Update notification preferences.
   */
  updatePreferences(updates: NotificationPreferenceUpdate): Observable<NotificationPreferences> {
    return this.http.patch<NotificationPreferences>(`${this.apiUrl}/preferences`, updates);
  }

  // ==========================================================================
  // Cleanup
  // ==========================================================================

  /**
   * Clear all local state (call on logout).
   */
  clear(): void {
    this.notificationsSignal.set([]);
    this.unreadCountSignal.set(0);
    this.realtimeNotifications.set([]);
    this.totalSignal.set(0);
  }

  ngOnDestroy(): void {
    this.destroy$.next();
    this.destroy$.complete();
  }
}
