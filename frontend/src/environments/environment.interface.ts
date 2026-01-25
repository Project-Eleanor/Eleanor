/**
 * Environment configuration interface for type safety.
 */
export interface Environment {
  production: boolean;

  // API Configuration
  apiUrl: string;
  wsUrl?: string;

  // App Info
  appName: string;
  appVersion: string;

  // Feature Flags
  features: {
    webSocket: boolean;
    threatIntel: boolean;
    analytics: boolean;
    automation: boolean;
    mitreAttack: boolean;
  };

  // Timeouts (ms)
  timeouts: {
    api: number;
    search: number;
    upload: number;
  };

  // Refresh intervals (ms)
  refreshIntervals: {
    dashboard: number;
    incidents: number;
    integrations: number;
  };

  // Authentication
  auth: {
    tokenRefreshThreshold: number; // ms before expiry to refresh
    sessionTimeout: number; // ms of inactivity before logout
  };

  // Logging
  logging: {
    level: 'debug' | 'info' | 'warn' | 'error';
    sendToServer: boolean;
  };
}
