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
            <img src="assets/logo.jpg" alt="Eleanor" class="logo-img">
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
          <div class="integration-status" [matTooltip]="'Integration Status'" matTooltipPosition="right">
            <mat-icon [class]="integrationStatusClass()">{{ integrationStatusIcon() }}</mat-icon>
            @if (!sidebarCollapsed()) {
              <span>{{ healthyCount() }}/{{ totalCount() }} Healthy</span>
            }
          </div>
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
    .shell-container {
      display: flex;
      height: 100vh;
      width: 100vw;
      overflow: hidden;
    }

    /* Sidebar */
    .sidebar {
      width: 240px;
      min-width: 240px;
      background: var(--bg-secondary);
      border-right: 1px solid var(--border-color);
      display: flex;
      flex-direction: column;
      transition: width 0.2s ease, min-width 0.2s ease;

      &.collapsed {
        width: 64px;
        min-width: 64px;
      }
    }

    .sidebar-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 16px;
      height: 64px;
    }

    .logo {
      display: flex;
      align-items: center;
      gap: 12px;

      &.collapsed {
        justify-content: center;
      }
    }

    .logo-img {
      width: 32px;
      height: 32px;
      object-fit: contain;
      border-radius: 4px;
    }

    .logo-text {
      font-size: 20px;
      font-weight: 700;
      color: var(--text-primary);
    }

    .collapse-btn {
      color: var(--text-secondary);
    }

    .nav-list {
      flex: 1;
      padding: 8px;
      overflow-y: auto;
    }

    .nav-group {
      margin-bottom: 8px;
    }

    .nav-group-label {
      display: block;
      font-size: 11px;
      font-weight: 600;
      text-transform: uppercase;
      color: var(--text-muted);
      padding: 12px 16px 6px;
      letter-spacing: 0.5px;
    }

    .nav-item {
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 12px 16px;
      margin-bottom: 4px;
      border-radius: 8px;
      color: var(--text-secondary);
      text-decoration: none;
      transition: all 0.15s ease;

      &:hover {
        background: rgba(255, 255, 255, 0.05);
        color: var(--text-primary);
      }

      &.active {
        background: var(--bg-tertiary);
        color: var(--accent);

        mat-icon {
          color: var(--accent);
        }
      }

      mat-icon {
        color: inherit;
      }
    }

    .nav-label {
      font-size: 14px;
      font-weight: 500;
    }

    .sidebar-footer {
      padding: 16px;
    }

    .integration-status {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 8px;
      font-size: 12px;
      color: var(--text-secondary);

      mat-icon {
        font-size: 20px;
        width: 20px;
        height: 20px;
      }

      .status-healthy {
        color: var(--success);
      }

      .status-partial {
        color: var(--warning);
      }

      .status-unhealthy {
        color: var(--danger);
      }
    }

    /* Main Area */
    .main-area {
      flex: 1;
      display: flex;
      flex-direction: column;
      overflow: hidden;
    }

    /* Header */
    .header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      height: 64px;
      padding: 0 24px;
      background: var(--bg-secondary);
      border-bottom: 1px solid var(--border-color);
    }

    .header-left {
      display: flex;
      align-items: center;
      gap: 16px;
    }

    .page-title {
      font-size: 18px;
      font-weight: 600;
      color: var(--text-primary);
    }

    .header-right {
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .quick-search {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 8px 16px;
      background: var(--bg-surface);
      border: 1px solid var(--border-color);
      border-radius: 20px;
      margin-right: 16px;

      mat-icon {
        color: var(--text-secondary);
        font-size: 20px;
        width: 20px;
        height: 20px;
      }

      input {
        background: transparent;
        border: none;
        outline: none;
        color: var(--text-primary);
        width: 200px;

        &::placeholder {
          color: var(--text-muted);
        }
      }
    }

    /* Content */
    .content {
      flex: 1;
      padding: 24px;
      overflow-y: auto;
      background: var(--bg-primary);
    }

    /* Menu Styles */
    .user-info {
      display: flex;
      flex-direction: column;
      padding: 12px 16px;

      strong {
        color: var(--text-primary);
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
