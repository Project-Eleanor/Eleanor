import { Injectable, signal, computed, OnDestroy, inject, Injector, runInInjectionContext } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Router } from '@angular/router';
import { Observable, tap, catchError, throwError, BehaviorSubject, filter, take, switchMap, of } from 'rxjs';
import { User, TokenResponse, LoginRequest } from '../../shared/models';
import { AppConfigService } from '../config/app-config.service';
import { RbacService } from '../api/rbac.service';
import { LoggingService } from '../services/logging.service';

const TOKEN_KEY = 'eleanor_token';
const TOKEN_EXPIRY_KEY = 'eleanor_token_expiry';
const USER_KEY = 'eleanor_user';

@Injectable({
  providedIn: 'root'
})
export class AuthService implements OnDestroy {
  private readonly config = inject(AppConfigService);
  private readonly injector = inject(Injector);
  private readonly logger = inject(LoggingService);
  private get apiUrl(): string { return this.config.apiUrl; }
  private get refreshThreshold(): number { return this.config.auth.tokenRefreshThreshold; }

  private tokenSignal = signal<string | null>(this.getStoredToken());
  private userSignal = signal<User | null>(this.getStoredUser());

  // For coordinating refresh across multiple concurrent requests
  private isRefreshing = false;
  private refreshTokenSubject = new BehaviorSubject<string | null>(null);

  // Timer for proactive refresh
  private refreshTimer: ReturnType<typeof setTimeout> | null = null;

  readonly token = this.tokenSignal.asReadonly();
  readonly user = this.userSignal.asReadonly();
  readonly currentUser$ = new BehaviorSubject<User | null>(this.getStoredUser());
  readonly isAuthenticated = computed(() => !!this.tokenSignal() && !this.isTokenExpired());
  readonly isAdmin = computed(() => this.userSignal()?.is_admin ?? false);

  constructor(
    private http: HttpClient,
    private router: Router
  ) {
    this.checkTokenOnInit();
  }

  ngOnDestroy(): void {
    this.cancelRefreshTimer();
  }

  private checkTokenOnInit(): void {
    if (this.tokenSignal()) {
      if (this.isTokenExpired()) {
        this.clearAuth();
      } else {
        // Schedule proactive refresh
        this.scheduleTokenRefresh();
      }
    }
  }

  private getStoredToken(): string | null {
    if (typeof localStorage === 'undefined') return null;
    return localStorage.getItem(TOKEN_KEY);
  }

  private getStoredUser(): User | null {
    if (typeof localStorage === 'undefined') return null;
    const userJson = localStorage.getItem(USER_KEY);
    return userJson ? JSON.parse(userJson) : null;
  }

  private isTokenExpired(): boolean {
    if (typeof localStorage === 'undefined') return true;
    const expiry = localStorage.getItem(TOKEN_EXPIRY_KEY);
    if (!expiry) return true;
    return Date.now() > parseInt(expiry, 10);
  }

  login(credentials: LoginRequest): Observable<TokenResponse> {
    const formData = new URLSearchParams();
    formData.set('username', credentials.username);
    formData.set('password', credentials.password);

    const headers = new HttpHeaders({
      'Content-Type': 'application/x-www-form-urlencoded'
    });

    return this.http.post<TokenResponse>(
      `${this.apiUrl}/auth/login`,
      formData.toString(),
      { headers }
    ).pipe(
      tap(response => {
        this.setToken(response.access_token, response.expires_in);
        this.loadCurrentUser();
      }),
      catchError(error => {
        this.logger.error('Login failed', error, { component: 'AuthService' });
        return throwError(() => error);
      })
    );
  }

  private setToken(token: string, expiresIn: number): void {
    const expiryTime = Date.now() + (expiresIn * 1000);
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(TOKEN_EXPIRY_KEY, expiryTime.toString());
    this.tokenSignal.set(token);
    this.scheduleTokenRefresh();
  }

  loadCurrentUser(): void {
    this.http.get<User>(`${this.apiUrl}/auth/me`).pipe(
      tap(user => {
        localStorage.setItem(USER_KEY, JSON.stringify(user));
        this.userSignal.set(user);
        this.currentUser$.next(user);
        // Load user permissions
        this.loadPermissions();
      }),
      catchError(error => {
        this.logger.error('Failed to load user', error, { component: 'AuthService' });
        return throwError(() => error);
      })
    ).subscribe();
  }

  private loadPermissions(): void {
    // Lazy inject RbacService to avoid circular dependency
    runInInjectionContext(this.injector, () => {
      const rbacService = inject(RbacService);
      rbacService.getMyPermissions().subscribe({
        error: (err) => this.logger.error('Failed to load permissions', err, { component: 'AuthService' })
      });
    });
  }

  private clearPermissions(): void {
    runInInjectionContext(this.injector, () => {
      const rbacService = inject(RbacService);
      rbacService.clearPermissions();
    });
  }

  refreshToken(): Observable<TokenResponse> {
    return this.http.post<TokenResponse>(`${this.apiUrl}/auth/refresh`, {}).pipe(
      tap(response => {
        this.setToken(response.access_token, response.expires_in);
        this.scheduleTokenRefresh();
      }),
      catchError(error => {
        this.logout();
        return throwError(() => error);
      })
    );
  }

  /**
   * Handle token refresh for concurrent requests.
   * Returns existing refresh observable if refresh is in progress.
   */
  handleTokenRefresh(): Observable<string> {
    if (!this.isRefreshing) {
      this.isRefreshing = true;
      this.refreshTokenSubject.next(null);

      return this.refreshToken().pipe(
        switchMap(response => {
          this.isRefreshing = false;
          this.refreshTokenSubject.next(response.access_token);
          return of(response.access_token);
        }),
        catchError(error => {
          this.isRefreshing = false;
          return throwError(() => error);
        })
      );
    }

    // Wait for the in-progress refresh to complete
    return this.refreshTokenSubject.pipe(
      filter(token => token !== null),
      take(1),
      switchMap(token => of(token!))
    );
  }

  /**
   * Schedule proactive token refresh before expiry.
   */
  private scheduleTokenRefresh(): void {
    this.cancelRefreshTimer();

    const expiryTime = this.getTokenExpiryTime();
    if (!expiryTime) return;

    const now = Date.now();
    const timeUntilExpiry = expiryTime - now;
    const refreshTime = timeUntilExpiry - this.refreshThreshold;

    if (refreshTime <= 0) {
      // Token expires soon, refresh immediately
      this.handleTokenRefresh().subscribe();
    } else {
      // Schedule refresh
      this.refreshTimer = setTimeout(() => {
        this.handleTokenRefresh().subscribe();
      }, refreshTime);
    }
  }

  private cancelRefreshTimer(): void {
    if (this.refreshTimer) {
      clearTimeout(this.refreshTimer);
      this.refreshTimer = null;
    }
  }

  private getTokenExpiryTime(): number | null {
    if (typeof localStorage === 'undefined') return null;
    const expiry = localStorage.getItem(TOKEN_EXPIRY_KEY);
    return expiry ? parseInt(expiry, 10) : null;
  }

  logout(): void {
    this.http.post(`${this.apiUrl}/auth/logout`, {}).subscribe({
      complete: () => {
        this.clearAuth();
        this.router.navigate(['/login']);
      },
      error: () => {
        this.clearAuth();
        this.router.navigate(['/login']);
      }
    });
  }

  private clearAuth(): void {
    this.cancelRefreshTimer();
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(TOKEN_EXPIRY_KEY);
    localStorage.removeItem(USER_KEY);
    this.tokenSignal.set(null);
    this.userSignal.set(null);
    this.currentUser$.next(null);
    this.clearPermissions();
  }

  getToken(): string | null {
    return this.tokenSignal();
  }
}
