import { Component, signal, computed, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule, Router, NavigationEnd } from '@angular/router';
import { MatSidenavModule } from '@angular/material/sidenav';
import { MatToolbarModule } from '@angular/material/toolbar';
import { MatListModule } from '@angular/material/list';
import { MatIconModule } from '@angular/material/icon';
import { MatButtonModule } from '@angular/material/button';
import { MatMenuModule } from '@angular/material/menu';
import { MatBadgeModule } from '@angular/material/badge';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatDividerModule } from '@angular/material/divider';
import { filter } from 'rxjs/operators';
import { AuthService } from '../auth/auth.service';
import { IntegrationService } from '../api/integration.service';
import { NotificationBellComponent } from '../../shared/components/notification-bell/notification-bell.component';

interface NavItem {
  label: string;
  icon: string;
  route: string;
  badge?: number;
}

interface NavGroup {
  label: string;
  items: NavItem[];
}

@Component({
  selector: 'app-shell',
  standalone: true,
  imports: [
    CommonModule,
    RouterModule,
    MatSidenavModule,
    MatToolbarModule,
    MatListModule,
    MatIconModule,
    MatButtonModule,
    MatMenuModule,
    MatBadgeModule,
    MatTooltipModule,
    MatDividerModule,
    NotificationBellComponent
  ],
  template: `
    <div class="shell-container">
      <!-- Sidebar -->
      <aside class="sidebar" [class.collapsed]="sidebarCollapsed()">
        <div class="sidebar-header">
          <div class="logo" [class.collapsed]="sidebarCollapsed()">
            <img src="assets/logo.png" alt="Eleanor" class="logo-img">
            @if (!sidebarCollapsed()) {
              <span class="logo-text">Eleanor</span>
            }
          </div>
          <button mat-icon-button (click)="toggleSidebar()" class="collapse-btn">
            <mat-icon>{{ sidebarCollapsed() ? 'chevron_right' : 'chevron_left' }}</mat-icon>
          </button>
        </div>

        <nav class="nav-list">
          @for (group of navGroups; track group.label) {
            <div class="nav-group">
              @if (!sidebarCollapsed()) {
                <span class="nav-group-label">{{ group.label }}</span>
              }
              @for (item of group.items; track item.route) {
                <a class="nav-item"
                   [routerLink]="item.route"
                   routerLinkActive="active"
                   [matTooltip]="sidebarCollapsed() ? item.label : ''"
                   matTooltipPosition="right">
                  <div class="nav-indicator"></div>
                  <mat-icon [matBadge]="item.badge" matBadgeColor="accent" [matBadgeHidden]="!item.badge">
                    {{ item.icon }}
                  </mat-icon>
                  @if (!sidebarCollapsed()) {
                    <span class="nav-label">{{ item.label }}</span>
                  }
                </a>
              }
            </div>
          }
        </nav>

        <div class="sidebar-footer">
          <mat-divider></mat-divider>
          <a class="integration-status" routerLink="/connectors" [matTooltip]="'View Integration Status'" matTooltipPosition="right">
            <mat-icon [class]="integrationStatusClass()">{{ integrationStatusIcon() }}</mat-icon>
            @if (!sidebarCollapsed()) {
              <span>{{ healthyCount() }}/{{ totalCount() }} Healthy</span>
            }
          </a>
        </div>
      </aside>

      <!-- Main Content Area -->
      <div class="main-area">
        <!-- Header -->
        <header class="header">
          <div class="header-left">
            <span class="page-title">{{ pageTitle() }}</span>
          </div>

          <div class="header-right">
            <!-- Quick Search -->
            <div class="quick-search">
              <mat-icon>search</mat-icon>
              <input type="text" placeholder="Quick search..." (keyup.enter)="onQuickSearch($event)">
            </div>

            <!-- Notifications -->
            <app-notification-bell></app-notification-bell>

            <!-- User Menu -->
            <button mat-icon-button [matMenuTriggerFor]="userMenu" class="user-button">
              <mat-icon>account_circle</mat-icon>
            </button>
            <mat-menu #userMenu="matMenu">
              <div class="user-info">
                <strong>{{ user()?.display_name || user()?.username }}</strong>
                <span class="text-secondary">{{ user()?.email }}</span>
              </div>
              <mat-divider></mat-divider>
              <button mat-menu-item routerLink="/settings">
                <mat-icon>settings</mat-icon>
                <span>Settings</span>
              </button>
              @if (authService.isAdmin()) {
                <button mat-menu-item routerLink="/admin">
                  <mat-icon>admin_panel_settings</mat-icon>
                  <span>Administration</span>
                </button>
              }
              <mat-divider></mat-divider>
              <button mat-menu-item (click)="logout()">
                <mat-icon>logout</mat-icon>
                <span>Logout</span>
              </button>
            </mat-menu>
          </div>
        </header>

        <!-- Page Content -->
        <main class="content">
          <router-outlet></router-outlet>
        </main>
      </div>
    </div>
  `,
  styles: [`
    /*
     * DESIGN: Shell layout matching project-eleanor.com aesthetic
     * - Clean sidebar with subtle glow effects
     * - Understated hover interactions
     * - Refined border treatments
     */
    .shell-container {
      display: flex;
      height: 100vh;
      width: 100vw;
      overflow: hidden;
    }

    /* Sidebar - Enhanced Glassmorphism style */
    .sidebar {
      width: 240px;
      min-width: 240px;
      background: rgba(15, 20, 30, 0.6);
      backdrop-filter: blur(24px) saturate(180%);
      -webkit-backdrop-filter: blur(24px) saturate(180%);
      border-right: 1px solid rgba(255, 255, 255, 0.08);
      box-shadow:
        inset 0 0 0 1px rgba(255, 255, 255, 0.05),
        4px 0 24px rgba(0, 0, 0, 0.3);
      display: flex;
      flex-direction: column;
      transition: width 0.2s ease, min-width 0.2s ease;
      position: relative;

      /* Subtle top glow */
      &::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 200px;
        background: radial-gradient(ellipse at 50% 0%, var(--glow-accent) 0%, transparent 70%);
        pointer-events: none;
        opacity: 0.6;
      }

      &.collapsed {
        width: 68px;
        min-width: 68px;
      }
    }

    .sidebar-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 20px 16px;
      height: 68px;
      position: relative;
      z-index: 1;
    }

    .logo {
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 8px 14px;
      margin: -8px -14px;
      background: rgba(15, 20, 30, 0.4);
      backdrop-filter: blur(12px) saturate(180%);
      -webkit-backdrop-filter: blur(12px) saturate(180%);
      border: 1px solid rgba(255, 255, 255, 0.06);
      border-radius: 12px;
      box-shadow:
        0 4px 16px rgba(0, 0, 0, 0.2),
        inset 0 0 0 1px rgba(255, 255, 255, 0.03);
      transition: all 0.3s ease;

      &:hover {
        background: rgba(20, 26, 40, 0.5);
        border-color: rgba(255, 255, 255, 0.1);
        box-shadow:
          0 6px 20px rgba(0, 0, 0, 0.25),
          inset 0 0 0 1px rgba(255, 255, 255, 0.05),
          0 0 20px rgba(74, 158, 255, 0.1);
      }

      &.collapsed {
        justify-content: center;
        padding: 8px;
        margin: -8px;
      }
    }

    .logo-img {
      width: 32px;
      height: 32px;
      object-fit: contain;
      border-radius: 8px;
      filter: drop-shadow(0 0 12px var(--glow-accent));
      transition: filter 0.2s ease;

      &:hover {
        filter: drop-shadow(0 0 20px var(--glow-accent-strong));
      }
    }

    .logo-text {
      font-family: var(--font-display);
      font-size: 20px;
      font-weight: 700;
      letter-spacing: -0.5px;
      /* Silver-white for Elean, softer blue for or */
      background: linear-gradient(
        90deg,
        #c8d5e4 0%,      /* Silver */
        #c8d5e4 70%,     /* Silver through "Elean" */
        #7eb8e8 85%,     /* Transition to softer blue */
        #6aadd8 100%     /* Softer blue for "or" */
      );
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      background-clip: text;
      filter: drop-shadow(0 0 6px rgba(74, 158, 255, 0.2));
      transition: filter 0.3s ease;

      &:hover {
        filter: drop-shadow(0 0 10px rgba(74, 158, 255, 0.4));
      }
    }

    .collapse-btn {
      color: var(--text-muted);
      transition: color 0.2s ease;
      opacity: 0.7;

      &:hover {
        color: var(--text-primary);
        opacity: 1;
      }
    }

    .nav-list {
      flex: 1;
      padding: 12px;
      overflow-y: auto;
      position: relative;
      z-index: 1;
    }

    .nav-group {
      margin-bottom: 16px;
    }

    .nav-group-label {
      display: block;
      font-family: var(--font-body);
      font-size: 10px;
      font-weight: 600;
      text-transform: uppercase;
      color: var(--text-muted);
      padding: 8px 12px;
      letter-spacing: 0.8px;
    }

    .nav-item {
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 10px 12px;
      margin-bottom: 2px;
      border-radius: 8px;
      color: var(--text-secondary);
      text-decoration: none;
      transition: all 0.15s ease;
      position: relative;
      border: 1px solid transparent;

      .nav-indicator {
        position: absolute;
        left: 0;
        top: 50%;
        transform: translateY(-50%);
        width: 2px;
        height: 0;
        background: var(--accent);
        border-radius: 0 1px 1px 0;
        transition: height 0.2s ease;
      }

      &:hover {
        color: var(--text-primary);
        background: var(--glow-accent);
        border-color: var(--border-subtle);
      }

      &.active {
        color: var(--accent);
        background: var(--glow-accent);
        border-color: var(--border-hover);

        .nav-indicator {
          height: 20px;
        }

        mat-icon {
          color: var(--accent);
        }
      }

      mat-icon {
        color: inherit;
        font-size: 20px;
        width: 20px;
        height: 20px;
        transition: color 0.15s ease;
      }
    }

    .nav-label {
      font-size: 13px;
      font-weight: 500;
    }

    .sidebar-footer {
      padding: 16px;
      position: relative;
      z-index: 1;
      border-top: 1px solid var(--border-color);
    }

    .integration-status {
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 10px 12px;
      font-size: 12px;
      color: var(--text-secondary);
      border-radius: 8px;
      background: rgba(10, 14, 20, 0.6);
      backdrop-filter: blur(8px);
      -webkit-backdrop-filter: blur(8px);
      border: 1px solid rgba(74, 158, 255, 0.1);
      text-decoration: none;
      cursor: pointer;
      transition: all 0.2s ease;

      &:hover {
        background: rgba(10, 14, 20, 0.8);
        border-color: rgba(74, 158, 255, 0.25);
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.2), 0 0 12px rgba(74, 158, 255, 0.1);
      }

      mat-icon {
        font-size: 18px;
        width: 18px;
        height: 18px;
      }

      .status-healthy { color: var(--success); }
      .status-partial { color: var(--warning); }
      .status-unhealthy { color: var(--danger); }
    }

    /* Main Area */
    .main-area {
      flex: 1;
      display: flex;
      flex-direction: column;
      overflow: hidden;
      background: var(--bg-primary);
    }

    /* Header - Enhanced Glassmorphism style */
    .header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      height: 68px;
      padding: 0 28px;
      background: rgba(15, 20, 30, 0.6);
      backdrop-filter: blur(24px) saturate(180%);
      -webkit-backdrop-filter: blur(24px) saturate(180%);
      border-bottom: 1px solid rgba(255, 255, 255, 0.08);
      box-shadow: 0 4px 24px rgba(0, 0, 0, 0.2);
      position: relative;
    }

    .header-left {
      display: flex;
      align-items: center;
      gap: 16px;
    }

    .page-title {
      font-family: var(--font-display);
      font-size: 18px;
      font-weight: 600;
      color: var(--text-primary);
      letter-spacing: -0.3px;
    }

    .header-right {
      display: flex;
      align-items: center;
      gap: 12px;
    }

    .quick-search {
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 9px 16px;
      background: var(--bg-primary);
      border: 1px solid var(--border-color);
      border-radius: 8px;
      margin-right: 12px;
      transition: border-color 0.2s ease;

      &:focus-within {
        border-color: var(--border-hover);
        box-shadow: 0 0 20px var(--glow-accent);
      }

      mat-icon {
        color: var(--text-muted);
        font-size: 18px;
        width: 18px;
        height: 18px;
      }

      input {
        background: transparent;
        border: none;
        outline: none;
        color: var(--text-primary);
        width: 180px;
        font-family: var(--font-body);
        font-size: 13px;

        &::placeholder {
          color: var(--text-muted);
        }
      }
    }

    .user-button {
      color: var(--text-secondary);
      transition: color 0.2s ease;

      &:hover {
        color: var(--text-primary);
      }
    }

    /* Content */
    .content {
      flex: 1;
      padding: 28px;
      overflow-y: auto;
      background: var(--bg-primary);
      animation: fadeIn 0.4s ease-out;
    }

    @keyframes fadeIn {
      from { opacity: 0; transform: translateY(8px); }
      to { opacity: 1; transform: translateY(0); }
    }

    /* Menu Styles */
    .user-info {
      display: flex;
      flex-direction: column;
      padding: 14px 18px;
      gap: 4px;

      strong {
        color: var(--text-primary);
        font-size: 14px;
      }

      span {
        font-size: 12px;
      }
    }

    .status-healthy { color: var(--success); }
    .status-partial { color: var(--warning); }
    .status-unhealthy { color: var(--danger); }
  `]
})
export class ShellComponent implements OnInit {
  sidebarCollapsed = signal(false);
  pageTitle = signal('Dashboard');

  healthyCount = signal(0);
  totalCount = signal(0);

  navGroups: NavGroup[] = [
    {
      label: 'General',
      items: [
        { label: 'Dashboard', icon: 'dashboard', route: '/dashboard' },
        { label: 'Incidents', icon: 'warning_amber', route: '/incidents' }
      ]
    },
    {
      label: 'Threat Management',
      items: [
        { label: 'Hunting', icon: 'manage_search', route: '/hunting' },
        { label: 'Threat Intel', icon: 'policy', route: '/threat-intel' },
        { label: 'MITRE ATT&CK', icon: 'grid_view', route: '/mitre' }
      ]
    },
    {
      label: 'Configuration',
      items: [
        { label: 'Analytics', icon: 'analytics', route: '/analytics' },
        { label: 'Automation', icon: 'smart_toy', route: '/automation', badge: 2 },
        { label: 'Data Connectors', icon: 'cable', route: '/connectors' }
      ]
    },
    {
      label: 'Investigation',
      items: [
        { label: 'Entities', icon: 'account_tree', route: '/entities' },
        { label: 'Evidence', icon: 'folder_copy', route: '/evidence' },
        { label: 'Timeline', icon: 'timeline', route: '/timeline' }
      ]
    },
    {
      label: 'Settings',
      items: [
        { label: 'Settings', icon: 'settings', route: '/settings' }
      ]
    }
  ];

  user = this.authService.user;

  integrationStatusClass = computed(() => {
    const healthy = this.healthyCount();
    const total = this.totalCount();
    if (total === 0) return 'status-unhealthy';
    if (healthy === total) return 'status-healthy';
    if (healthy > 0) return 'status-partial';
    return 'status-unhealthy';
  });

  integrationStatusIcon = computed(() => {
    const healthy = this.healthyCount();
    const total = this.totalCount();
    if (total === 0) return 'cloud_off';
    if (healthy === total) return 'cloud_done';
    if (healthy > 0) return 'cloud_sync';
    return 'cloud_off';
  });

  constructor(
    public authService: AuthService,
    private integrationService: IntegrationService,
    private router: Router
  ) {}

  ngOnInit(): void {
    this.loadIntegrationStatus();
    this.setupRouterEvents();
  }

  private loadIntegrationStatus(): void {
    this.integrationService.getStatus().subscribe({
      next: (response) => {
        this.totalCount.set(response.integrations.length);
        this.healthyCount.set(response.summary['connected'] || 0);
      },
      error: () => {
        this.totalCount.set(0);
        this.healthyCount.set(0);
      }
    });
  }

  private setupRouterEvents(): void {
    this.router.events.pipe(
      filter(event => event instanceof NavigationEnd)
    ).subscribe(() => {
      this.updatePageTitle();
    });
    this.updatePageTitle();
  }

  private updatePageTitle(): void {
    const url = this.router.url;
    for (const group of this.navGroups) {
      const item = group.items.find(i => url.startsWith(i.route));
      if (item) {
        this.pageTitle.set(item.label);
        return;
      }
    }
    this.pageTitle.set('Eleanor');
  }

  toggleSidebar(): void {
    this.sidebarCollapsed.update(v => !v);
  }

  onQuickSearch(event: Event): void {
    const input = event.target as HTMLInputElement;
    if (input.value.trim()) {
      this.router.navigate(['/hunting'], { queryParams: { q: input.value } });
      input.value = '';
    }
  }

  logout(): void {
    this.authService.logout();
  }
}
