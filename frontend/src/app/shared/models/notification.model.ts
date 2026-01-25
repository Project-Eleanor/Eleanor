/**
 * Notification models for Eleanor.
 */

export type NotificationType =
  | 'case_created'
  | 'case_updated'
  | 'case_assigned'
  | 'case_closed'
  | 'evidence_uploaded'
  | 'evidence_processed'
  | 'workflow_started'
  | 'workflow_completed'
  | 'workflow_failed'
  | 'approval_required'
  | 'approval_granted'
  | 'approval_denied'
  | 'detection_hit'
  | 'alert_triggered'
  | 'system_alert'
  | 'integration_error'
  | 'scheduled_task'
  | 'mention'
  | 'comment';

export type NotificationSeverity = 'info' | 'success' | 'warning' | 'error' | 'critical';

export interface Notification {
  id: string;
  type: NotificationType;
  severity: NotificationSeverity;
  title: string;
  body: string | null;
  link: string | null;
  icon: string | null;
  data: Record<string, unknown> | null;
  read: boolean;
  read_at: string | null;
  created_at: string;
}

export interface NotificationListResponse {
  items: Notification[];
  total: number;
  unread_count: number;
  page: number;
  page_size: number;
}

export interface NotificationPreferences {
  email_enabled: boolean;
  push_enabled: boolean;
  in_app_enabled: boolean;
  type_preferences: Record<NotificationType, boolean>;
  quiet_hours_enabled: boolean;
  quiet_hours_start: string | null;
  quiet_hours_end: string | null;
}

export interface NotificationPreferenceUpdate {
  email_enabled?: boolean;
  push_enabled?: boolean;
  in_app_enabled?: boolean;
  type_preferences?: Record<string, boolean>;
  quiet_hours_enabled?: boolean;
  quiet_hours_start?: string | null;
  quiet_hours_end?: string | null;
}
