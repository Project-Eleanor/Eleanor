import { Environment } from './environment.interface';

export const environment: Environment = {
  production: false,

  // API Configuration
  apiUrl: '/api/v1',
  wsUrl: 'ws://localhost:8000/api/v1/ws',

  // App Info
  appName: 'Eleanor',
  appVersion: '1.0.0-dev',

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
    search: 60000,
    upload: 300000,
  },

  // Refresh intervals (ms)
  refreshIntervals: {
    dashboard: 30000,
    incidents: 15000,
    integrations: 60000,
  },

  // Authentication
  auth: {
    tokenRefreshThreshold: 5 * 60 * 1000, // 5 minutes before expiry
    sessionTimeout: 30 * 60 * 1000, // 30 minutes of inactivity
  },

  // Logging
  logging: {
    level: 'debug',
    sendToServer: false,
  },
};
