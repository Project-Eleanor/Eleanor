import { Environment } from './environment.interface';

export const environment: Environment = {
  production: true,

  // API Configuration - relative URL, works with reverse proxy
  apiUrl: '/api/v1',
  wsUrl: undefined, // Will be computed from window.location

  // App Info
  appName: 'Eleanor',
  appVersion: '1.0.0',

  // Feature Flags
  features: {
    webSocket: true,
    threatIntel: true,
    analytics: true,
    automation: true,
    mitreAttack: true,
  },

  // Timeouts (ms)
  timeouts: {
    api: 30000,
    search: 120000,
    upload: 600000,
  },

  // Refresh intervals (ms)
  refreshIntervals: {
    dashboard: 60000,
    incidents: 30000,
    integrations: 120000,
  },

  // Authentication
  auth: {
    tokenRefreshThreshold: 5 * 60 * 1000, // 5 minutes before expiry
    sessionTimeout: 60 * 60 * 1000, // 60 minutes of inactivity
  },

  // Logging
  logging: {
    level: 'warn',
    sendToServer: true,
  },
};
