import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { environment } from '../../../environments/environment';
import { Environment } from '../../../environments/environment.interface';
import { catchError, of, tap } from 'rxjs';

/**
 * Runtime configuration that can be loaded from config.json.
 * Only includes fields that should be configurable at runtime.
 */
export interface RuntimeConfig {
  apiUrl?: string;
  wsUrl?: string;
  features?: Partial<Environment['features']>;
  timeouts?: Partial<Environment['timeouts']>;
  refreshIntervals?: Partial<Environment['refreshIntervals']>;
  auth?: Partial<Environment['auth']>;
  logging?: Partial<Environment['logging']>;
}

@Injectable({
  providedIn: 'root'
})
export class AppConfigService {
  private config: Environment = { ...environment };
  private loaded = false;

  private readonly http = inject(HttpClient);

  /**
   * Load runtime configuration from config.json.
   * Falls back to environment defaults if file not found.
   */
  load(): Promise<void> {
    return new Promise(resolve => {
      this.http.get<RuntimeConfig>('/assets/config.json').pipe(
        tap(runtimeConfig => {
          this.mergeConfig(runtimeConfig);
          console.log('Runtime config loaded:', runtimeConfig);
        }),
        catchError(error => {
          console.log('No runtime config found, using defaults');
          return of(null);
        })
      ).subscribe(() => {
        this.loaded = true;
        resolve();
      });
    });
  }

  private mergeConfig(runtimeConfig: RuntimeConfig): void {
    if (runtimeConfig.apiUrl) {
      this.config.apiUrl = runtimeConfig.apiUrl;
    }

    if (runtimeConfig.wsUrl) {
      this.config.wsUrl = runtimeConfig.wsUrl;
    }

    if (runtimeConfig.features) {
      this.config.features = { ...this.config.features, ...runtimeConfig.features };
    }

    if (runtimeConfig.timeouts) {
      this.config.timeouts = { ...this.config.timeouts, ...runtimeConfig.timeouts };
    }

    if (runtimeConfig.refreshIntervals) {
      this.config.refreshIntervals = { ...this.config.refreshIntervals, ...runtimeConfig.refreshIntervals };
    }

    if (runtimeConfig.auth) {
      this.config.auth = { ...this.config.auth, ...runtimeConfig.auth };
    }

    if (runtimeConfig.logging) {
      this.config.logging = { ...this.config.logging, ...runtimeConfig.logging };
    }
  }

  get apiUrl(): string {
    return this.config.apiUrl;
  }

  get wsUrl(): string {
    if (this.config.wsUrl) {
      return this.config.wsUrl;
    }
    // Compute from window.location if not specified
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    return `${protocol}//${window.location.host}${this.config.apiUrl}/ws`;
  }

  get features(): Environment['features'] {
    return this.config.features;
  }

  get timeouts(): Environment['timeouts'] {
    return this.config.timeouts;
  }

  get refreshIntervals(): Environment['refreshIntervals'] {
    return this.config.refreshIntervals;
  }

  get auth(): Environment['auth'] {
    return this.config.auth;
  }

  get logging(): Environment['logging'] {
    return this.config.logging;
  }

  get appName(): string {
    return this.config.appName;
  }

  get appVersion(): string {
    return this.config.appVersion;
  }

  get production(): boolean {
    return this.config.production;
  }

  isFeatureEnabled(feature: keyof Environment['features']): boolean {
    return this.config.features[feature];
  }
}
