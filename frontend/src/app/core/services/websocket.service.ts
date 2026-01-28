import { Injectable, OnDestroy, inject } from '@angular/core';
import { BehaviorSubject, Observable, Subject, filter, map } from 'rxjs';
import { AppConfigService } from '../config/app-config.service';
import { LoggingService } from './logging.service';

export interface WebSocketMessage {
  id: string;
  type: string;
  data: Record<string, unknown>;
  timestamp: string;
}

export type ConnectionStatus = 'disconnected' | 'connecting' | 'connected' | 'error';

/**
 * PATTERN: Reconnecting WebSocket Service
 *
 * Provides a robust WebSocket connection with automatic reconnection,
 * topic-based subscriptions, and keep-alive ping mechanism.
 *
 * ## Reconnection Strategy
 * Uses exponential backoff for reconnection attempts:
 * - Base delay: 1000ms (configurable via reconnectDelay)
 * - Formula: delay = baseDelay * 2^(attemptNumber - 1)
 * - Example: 1s, 2s, 4s, 8s, 16s
 * - Maximum attempts: 5 (configurable via maxReconnectAttempts)
 *
 * ## State Machine
 * ```
 * disconnected -> connecting -> connected
 *                      |            |
 *                      v            v
 *                   error    disconnected (close event)
 *                      |            |
 *                      +-----+------+
 *                            |
 *                            v
 *                    [reconnect after delay]
 * ```
 *
 * ## Token Lifetime Considerations
 * - Token is passed during connect() and used for initial authentication
 * - On reconnection, the same token is reused; if the token expires during
 *   disconnection, reconnection will fail with auth error
 * - Callers should listen to status$ and handle 'error' state by obtaining
 *   a fresh token and calling connect() again
 *
 * ## Subscription Persistence
 * Topic subscriptions are stored and automatically resubscribed on reconnection.
 * This ensures no messages are missed after a brief disconnect.
 */
@Injectable({
  providedIn: 'root'
})
export class WebSocketService implements OnDestroy {
  private readonly config = inject(AppConfigService);
  private readonly logger = inject(LoggingService);

  private socket: WebSocket | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  /** Base delay for exponential backoff (milliseconds) */
  private reconnectDelay = 1000;
  private pingInterval: ReturnType<typeof setInterval> | null = null;

  private messagesSubject = new Subject<WebSocketMessage>();
  private statusSubject = new BehaviorSubject<ConnectionStatus>('disconnected');
  /** Tracks active topic subscriptions for auto-resubscribe on reconnect */
  private subscriptions = new Set<string>();

  messages$ = this.messagesSubject.asObservable();
  status$ = this.statusSubject.asObservable();

  connect(token?: string): void {
    if (this.socket?.readyState === WebSocket.OPEN) {
      return;
    }

    this.statusSubject.next('connecting');

    const wsUrl = this.buildWebSocketUrl(token);
    this.socket = new WebSocket(wsUrl);

    this.socket.onopen = () => {
      this.logger.info('WebSocket connected', { component: 'WebSocketService' });
      this.statusSubject.next('connected');
      this.reconnectAttempts = 0;

      // Resubscribe to previous topics
      this.subscriptions.forEach(topic => {
        this.sendAction('subscribe', topic);
      });

      // Start ping interval
      this.startPingInterval();
    };

    this.socket.onmessage = (event) => {
      try {
        const message: WebSocketMessage = JSON.parse(event.data);
        this.messagesSubject.next(message);
      } catch (e) {
        this.logger.error('Failed to parse WebSocket message', e as Error, { component: 'WebSocketService' });
      }
    };

    this.socket.onerror = (error) => {
      this.logger.error('WebSocket error', undefined, { component: 'WebSocketService' });
      this.statusSubject.next('error');
    };

    this.socket.onclose = (event) => {
      this.logger.info('WebSocket closed', { component: 'WebSocketService', code: event.code, reason: event.reason });
      this.statusSubject.next('disconnected');
      this.stopPingInterval();

      // Attempt reconnection
      if (this.reconnectAttempts < this.maxReconnectAttempts) {
        this.reconnectAttempts++;
        const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);
        this.logger.debug(`Reconnecting in ${delay}ms`, { component: 'WebSocketService', attempt: this.reconnectAttempts });
        setTimeout(() => this.connect(token), delay);
      }
    };
  }

  disconnect(): void {
    this.stopPingInterval();
    if (this.socket) {
      this.socket.close();
      this.socket = null;
    }
    this.statusSubject.next('disconnected');
  }

  subscribe(topic: string): void {
    this.subscriptions.add(topic);
    if (this.socket?.readyState === WebSocket.OPEN) {
      this.sendAction('subscribe', topic);
    }
  }

  unsubscribe(topic: string): void {
    this.subscriptions.delete(topic);
    if (this.socket?.readyState === WebSocket.OPEN) {
      this.sendAction('unsubscribe', topic);
    }
  }

  /**
   * Get messages filtered by event type
   */
  onEvent(eventType: string): Observable<WebSocketMessage> {
    return this.messages$.pipe(
      filter(msg => msg.type === eventType)
    );
  }

  /**
   * Get messages filtered by multiple event types
   */
  onEvents(...eventTypes: string[]): Observable<WebSocketMessage> {
    return this.messages$.pipe(
      filter(msg => eventTypes.includes(msg.type))
    );
  }

  /**
   * Get case-related events
   */
  onCaseEvents(caseId?: string): Observable<WebSocketMessage> {
    const caseEvents = ['case_created', 'case_updated', 'case_deleted', 'case_assigned'];
    return this.messages$.pipe(
      filter(msg => caseEvents.includes(msg.type)),
      filter(msg => !caseId || msg.data['case_id'] === caseId)
    );
  }

  /**
   * Get workflow-related events
   */
  onWorkflowEvents(workflowId?: string): Observable<WebSocketMessage> {
    const workflowEvents = ['workflow_started', 'workflow_completed', 'workflow_failed', 'approval_required', 'approval_resolved'];
    return this.messages$.pipe(
      filter(msg => workflowEvents.includes(msg.type)),
      filter(msg => !workflowId || msg.data['workflow_id'] === workflowId)
    );
  }

  /**
   * Get notification events
   */
  onNotifications(): Observable<WebSocketMessage> {
    return this.onEvents('notification', 'system_alert');
  }

  /**
   * Get alert events
   */
  onAlerts(): Observable<WebSocketMessage> {
    return this.onEvents('alert_created', 'detection_hit');
  }

  ngOnDestroy(): void {
    this.disconnect();
    this.messagesSubject.complete();
    this.statusSubject.complete();
  }

  private buildWebSocketUrl(token?: string): string {
    let wsUrl = this.config.wsUrl;

    if (token) {
      wsUrl += `?token=${encodeURIComponent(token)}`;
    }

    return wsUrl;
  }

  private sendAction(action: string, topic?: string): void {
    if (this.socket?.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify({ action, topic }));
    }
  }

  private startPingInterval(): void {
    this.stopPingInterval();
    this.pingInterval = setInterval(() => {
      this.sendAction('ping');
    }, 30000); // Ping every 30 seconds
  }

  private stopPingInterval(): void {
    if (this.pingInterval) {
      clearInterval(this.pingInterval);
      this.pingInterval = null;
    }
  }
}
