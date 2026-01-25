import { Injectable, OnDestroy } from '@angular/core';
import { MatSnackBar } from '@angular/material/snack-bar';
import { BehaviorSubject, Subject, takeUntil } from 'rxjs';
import { WebSocketService, WebSocketMessage } from './websocket.service';
import { AuthService } from '../auth/auth.service';

export interface Notification {
  id: string;
  title: string;
  body: string;
  severity: 'info' | 'success' | 'warning' | 'error';
  timestamp: Date;
  read: boolean;
  link?: string;
}

@Injectable({
  providedIn: 'root'
})
export class NotificationsService implements OnDestroy {
  private destroy$ = new Subject<void>();
  private notificationsSubject = new BehaviorSubject<Notification[]>([]);

  notifications$ = this.notificationsSubject.asObservable();
  unreadCount$ = this.notifications$.pipe();

  constructor(
    private wsService: WebSocketService,
    private authService: AuthService,
    private snackBar: MatSnackBar
  ) {
    // Connect WebSocket when user is authenticated
    this.authService.currentUser$.pipe(
      takeUntil(this.destroy$)
    ).subscribe(user => {
      if (user) {
        const token = localStorage.getItem('access_token');
        this.wsService.connect(token || undefined);
        this.subscribeToTopics();
      } else {
        this.wsService.disconnect();
      }
    });

    // Listen for notifications
    this.wsService.onNotifications().pipe(
      takeUntil(this.destroy$)
    ).subscribe(msg => this.handleNotification(msg));

    // Listen for case events
    this.wsService.onCaseEvents().pipe(
      takeUntil(this.destroy$)
    ).subscribe(msg => this.handleCaseEvent(msg));

    // Listen for workflow events
    this.wsService.onWorkflowEvents().pipe(
      takeUntil(this.destroy$)
    ).subscribe(msg => this.handleWorkflowEvent(msg));

    // Listen for alerts
    this.wsService.onAlerts().pipe(
      takeUntil(this.destroy$)
    ).subscribe(msg => this.handleAlert(msg));
  }

  private subscribeToTopics(): void {
    this.wsService.subscribe('cases');
    this.wsService.subscribe('workflows');
    this.wsService.subscribe('alerts');
  }

  private handleNotification(msg: WebSocketMessage): void {
    const data = msg.data as { title: string; body: string; severity: string; link?: string };

    const notification: Notification = {
      id: msg.id,
      title: data.title,
      body: data.body,
      severity: (data.severity as Notification['severity']) || 'info',
      timestamp: new Date(msg.timestamp),
      read: false,
      link: data.link
    };

    this.addNotification(notification);
    this.showSnackBar(notification);
  }

  private handleCaseEvent(msg: WebSocketMessage): void {
    const data = msg.data as { case_id: string; title?: string; status?: string };

    let title = 'Case Update';
    let body = '';

    switch (msg.type) {
      case 'case_created':
        title = 'New Case Created';
        body = data.title || `Case ${data.case_id} was created`;
        break;
      case 'case_updated':
        title = 'Case Updated';
        body = data.title || `Case ${data.case_id} was updated`;
        break;
      case 'case_assigned':
        title = 'Case Assigned';
        body = data.title || `Case ${data.case_id} was assigned to you`;
        break;
      case 'case_deleted':
        title = 'Case Deleted';
        body = data.title || `Case ${data.case_id} was deleted`;
        break;
    }

    const notification: Notification = {
      id: msg.id,
      title,
      body,
      severity: 'info',
      timestamp: new Date(msg.timestamp),
      read: false,
      link: `/incidents/${data.case_id}`
    };

    this.addNotification(notification);
  }

  private handleWorkflowEvent(msg: WebSocketMessage): void {
    const data = msg.data as { workflow_id: string; execution_id: string; workflow_name?: string; status?: string };

    let title = 'Workflow Update';
    let body = '';
    let severity: Notification['severity'] = 'info';

    switch (msg.type) {
      case 'workflow_started':
        title = 'Workflow Started';
        body = `${data.workflow_name || 'Workflow'} has started`;
        break;
      case 'workflow_completed':
        title = 'Workflow Completed';
        body = `${data.workflow_name || 'Workflow'} completed successfully`;
        severity = 'success';
        break;
      case 'workflow_failed':
        title = 'Workflow Failed';
        body = `${data.workflow_name || 'Workflow'} failed`;
        severity = 'error';
        break;
      case 'approval_required':
        title = 'Approval Required';
        body = `${data.workflow_name || 'Workflow'} requires your approval`;
        severity = 'warning';
        break;
      case 'approval_resolved':
        title = 'Approval Resolved';
        body = `Approval for ${data.workflow_name || 'workflow'} was resolved`;
        break;
    }

    const notification: Notification = {
      id: msg.id,
      title,
      body,
      severity,
      timestamp: new Date(msg.timestamp),
      read: false,
      link: `/automation`
    };

    this.addNotification(notification);

    // Show snackbar for important workflow events
    if (['workflow_failed', 'approval_required'].includes(msg.type)) {
      this.showSnackBar(notification);
    }
  }

  private handleAlert(msg: WebSocketMessage): void {
    const data = msg.data as { rule_name?: string; severity?: string; description?: string };

    const notification: Notification = {
      id: msg.id,
      title: data.rule_name || 'Detection Alert',
      body: data.description || 'A detection rule triggered',
      severity: (data.severity as Notification['severity']) || 'warning',
      timestamp: new Date(msg.timestamp),
      read: false,
      link: '/analytics'
    };

    this.addNotification(notification);
    this.showSnackBar(notification);
  }

  private addNotification(notification: Notification): void {
    const current = this.notificationsSubject.value;
    this.notificationsSubject.next([notification, ...current].slice(0, 100)); // Keep last 100
  }

  private showSnackBar(notification: Notification): void {
    const panelClass = `snackbar-${notification.severity}`;
    this.snackBar.open(
      `${notification.title}: ${notification.body}`,
      'Dismiss',
      {
        duration: 5000,
        horizontalPosition: 'right',
        verticalPosition: 'top',
        panelClass: [panelClass]
      }
    );
  }

  markAsRead(notificationId: string): void {
    const current = this.notificationsSubject.value;
    const updated = current.map(n =>
      n.id === notificationId ? { ...n, read: true } : n
    );
    this.notificationsSubject.next(updated);
  }

  markAllAsRead(): void {
    const current = this.notificationsSubject.value;
    const updated = current.map(n => ({ ...n, read: true }));
    this.notificationsSubject.next(updated);
  }

  clearAll(): void {
    this.notificationsSubject.next([]);
  }

  getUnreadCount(): number {
    return this.notificationsSubject.value.filter(n => !n.read).length;
  }

  ngOnDestroy(): void {
    this.destroy$.next();
    this.destroy$.complete();
  }
}
