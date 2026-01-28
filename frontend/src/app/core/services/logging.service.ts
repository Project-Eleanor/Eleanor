/**
 * PATTERN: Singleton Service Pattern
 * Centralized logging with configurable levels and context.
 *
 * This service provides structured logging for the Eleanor frontend,
 * replacing raw console.log calls with context-aware logging that:
 * - Respects environment-based log levels
 * - Attaches consistent context (timestamp, component)
 * - Formats errors with stack traces
 * - Supports future server-side log aggregation
 */
import { Injectable, inject } from '@angular/core';
import { environment } from '../../../environments/environment';

/** Log severity levels */
export enum LogLevel {
  DEBUG = 0,
  INFO = 1,
  WARN = 2,
  ERROR = 3,
}

/** Context information attached to log entries */
export interface LogContext {
  component?: string;
  caseId?: string;
  userId?: string;
  [key: string]: unknown;
}

/** Structured log entry for potential server-side aggregation */
interface LogEntry {
  timestamp: string;
  level: keyof typeof LogLevel;
  message: string;
  context?: LogContext;
  error?: {
    name: string;
    message: string;
    stack?: string;
  };
}

@Injectable({
  providedIn: 'root'
})
export class LoggingService {
  /** Current log level based on environment configuration */
  private logLevel: LogLevel = this.parseLogLevel(environment.logging?.level || 'info');

  /** Whether to send logs to server (future feature) */
  private sendToServer = environment.logging?.sendToServer || false;

  /**
   * Parse string log level to enum value.
   */
  private parseLogLevel(level: string): LogLevel {
    const levels: Record<string, LogLevel> = {
      debug: LogLevel.DEBUG,
      info: LogLevel.INFO,
      warn: LogLevel.WARN,
      error: LogLevel.ERROR,
    };
    return levels[level.toLowerCase()] ?? LogLevel.INFO;
  }

  /**
   * Check if a log level should be output.
   */
  private shouldLog(level: LogLevel): boolean {
    return level >= this.logLevel;
  }

  /**
   * Format context object for console output.
   */
  private formatContext(context?: LogContext): string {
    if (!context || Object.keys(context).length === 0) {
      return '';
    }
    return ` | ${JSON.stringify(context)}`;
  }

  /**
   * Get ISO timestamp for log entry.
   */
  private getTimestamp(): string {
    return new Date().toISOString();
  }

  /**
   * Log a debug message.
   * Use for detailed diagnostic information during development.
   *
   * @param message - Log message
   * @param context - Optional context object with component/case info
   */
  debug(message: string, context?: LogContext): void {
    if (!this.shouldLog(LogLevel.DEBUG)) return;

    const timestamp = this.getTimestamp();
    const contextStr = this.formatContext(context);

    // eslint-disable-next-line no-console
    console.debug(`[${timestamp}] DEBUG: ${message}${contextStr}`);
  }

  /**
   * Log an informational message.
   * Use for general operational information.
   *
   * @param message - Log message
   * @param context - Optional context object with component/case info
   */
  info(message: string, context?: LogContext): void {
    if (!this.shouldLog(LogLevel.INFO)) return;

    const timestamp = this.getTimestamp();
    const contextStr = this.formatContext(context);

    // eslint-disable-next-line no-console
    console.info(`[${timestamp}] INFO: ${message}${contextStr}`);
  }

  /**
   * Log a warning message.
   * Use for potentially harmful situations that don't prevent operation.
   *
   * @param message - Log message
   * @param context - Optional context object with component/case info
   */
  warn(message: string, context?: LogContext): void {
    if (!this.shouldLog(LogLevel.WARN)) return;

    const timestamp = this.getTimestamp();
    const contextStr = this.formatContext(context);

    // eslint-disable-next-line no-console
    console.warn(`[${timestamp}] WARN: ${message}${contextStr}`);
  }

  /**
   * Log an error message with optional Error object.
   * Use for error conditions that may affect functionality.
   *
   * @param message - Log message
   * @param error - Optional Error object for stack trace
   * @param context - Optional context object with component/case info
   */
  error(message: string, error?: Error, context?: LogContext): void {
    if (!this.shouldLog(LogLevel.ERROR)) return;

    const timestamp = this.getTimestamp();
    const contextStr = this.formatContext(context);

    // eslint-disable-next-line no-console
    console.error(`[${timestamp}] ERROR: ${message}${contextStr}`);

    if (error) {
      // eslint-disable-next-line no-console
      console.error(error);
    }

    // Future: Send to server for aggregation
    if (this.sendToServer) {
      this.sendLogToServer({
        timestamp,
        level: 'ERROR',
        message,
        context,
        error: error ? {
          name: error.name,
          message: error.message,
          stack: error.stack,
        } : undefined,
      });
    }
  }

  /**
   * Set the log level dynamically.
   * Useful for runtime configuration changes.
   *
   * @param level - New log level
   */
  setLogLevel(level: LogLevel): void {
    this.logLevel = level;
  }

  /**
   * Send log entry to server (placeholder for future implementation).
   */
  private sendLogToServer(entry: LogEntry): void {
    // TODO: Implement server-side log aggregation
    // This could use a dedicated /api/v1/logs endpoint
    // or integrate with a service like Sentry
  }
}
