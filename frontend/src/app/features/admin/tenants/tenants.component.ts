import { Component, OnInit, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule, ReactiveFormsModule, FormBuilder, FormGroup, Validators } from '@angular/forms';
import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatTableModule } from '@angular/material/table';
import { MatChipsModule } from '@angular/material/chips';
import { MatMenuModule } from '@angular/material/menu';
import { MatDialogModule, MatDialog } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatTabsModule } from '@angular/material/tabs';
import { MatDividerModule } from '@angular/material/divider';
import { TenantService } from '../../../core/services/tenant.service';
import {
  Tenant,
  TenantCreate,
  TenantStatus,
  TenantPlan,
  TenantMembership,
  TenantAPIKey,
  TenantMembershipRole
} from '../../../shared/models';

@Component({
  selector: 'app-tenants',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    ReactiveFormsModule,
    MatCardModule,
    MatButtonModule,
    MatIconModule,
    MatTableModule,
    MatChipsModule,
    MatMenuModule,
    MatDialogModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    MatProgressSpinnerModule,
    MatSnackBarModule,
    MatTooltipModule,
    MatTabsModule,
    MatDividerModule
  ],
  template: `
    <div class="tenants-admin">
      <div class="header">
        <div class="title-section">
          <h1>Tenant Management</h1>
          <p class="subtitle">Manage organizations and multi-tenancy settings</p>
        </div>
        <button mat-raised-button color="primary" (click)="openCreateDialog()">
          <mat-icon>add</mat-icon>
          New Tenant
        </button>
      </div>

      <!-- Stats -->
      <div class="stats-row">
        <mat-card class="stat-card">
          <div class="stat-icon active">
            <mat-icon>business</mat-icon>
          </div>
          <div class="stat-info">
            <span class="stat-value">{{ activeTenants() }}</span>
            <span class="stat-label">Active Tenants</span>
          </div>
        </mat-card>
        <mat-card class="stat-card">
          <div class="stat-icon suspended">
            <mat-icon>pause_circle</mat-icon>
          </div>
          <div class="stat-info">
            <span class="stat-value">{{ suspendedTenants() }}</span>
            <span class="stat-label">Suspended</span>
          </div>
        </mat-card>
        <mat-card class="stat-card">
          <div class="stat-icon enterprise">
            <mat-icon>workspace_premium</mat-icon>
          </div>
          <div class="stat-info">
            <span class="stat-value">{{ enterpriseTenants() }}</span>
            <span class="stat-label">Enterprise</span>
          </div>
        </mat-card>
        <mat-card class="stat-card">
          <div class="stat-icon users">
            <mat-icon>group</mat-icon>
          </div>
          <div class="stat-info">
            <span class="stat-value">{{ totalMembers() }}</span>
            <span class="stat-label">Total Members</span>
          </div>
        </mat-card>
      </div>

      <!-- Search and filters -->
      <mat-card class="filter-card">
        <mat-form-field appearance="outline" class="search-field">
          <mat-label>Search tenants</mat-label>
          <input matInput [(ngModel)]="searchQuery" (ngModelChange)="loadTenants()" placeholder="Search by name or slug...">
          <mat-icon matPrefix>search</mat-icon>
        </mat-form-field>
        <mat-form-field appearance="outline">
          <mat-label>Status</mat-label>
          <mat-select [(ngModel)]="statusFilter" (ngModelChange)="loadTenants()">
            <mat-option value="">All</mat-option>
            <mat-option value="active">Active</mat-option>
            <mat-option value="suspended">Suspended</mat-option>
            <mat-option value="pending">Pending</mat-option>
          </mat-select>
        </mat-form-field>
        <mat-form-field appearance="outline">
          <mat-label>Plan</mat-label>
          <mat-select [(ngModel)]="planFilter" (ngModelChange)="loadTenants()">
            <mat-option value="">All</mat-option>
            <mat-option value="free">Free</mat-option>
            <mat-option value="professional">Professional</mat-option>
            <mat-option value="enterprise">Enterprise</mat-option>
          </mat-select>
        </mat-form-field>
      </mat-card>

      <!-- Tenants table -->
      <mat-card class="table-card">
        @if (isLoading()) {
          <div class="loading-overlay">
            <mat-spinner diameter="40"></mat-spinner>
          </div>
        }

        <table mat-table [dataSource]="tenants()" class="tenants-table">
          <!-- Name column -->
          <ng-container matColumnDef="name">
            <th mat-header-cell *matHeaderCellDef>Organization</th>
            <td mat-cell *matCellDef="let tenant">
              <div class="tenant-name-cell">
                <div class="tenant-avatar" [style.background-color]="getAvatarColor(tenant.slug)">
                  {{ tenant.name.charAt(0).toUpperCase() }}
                </div>
                <div class="tenant-info">
                  <span class="tenant-name">{{ tenant.name }}</span>
                  <span class="tenant-slug">{{ tenant.slug }}</span>
                </div>
              </div>
            </td>
          </ng-container>

          <!-- Status column -->
          <ng-container matColumnDef="status">
            <th mat-header-cell *matHeaderCellDef>Status</th>
            <td mat-cell *matCellDef="let tenant">
              <mat-chip [class]="'status-' + tenant.status">
                {{ tenant.status | titlecase }}
              </mat-chip>
            </td>
          </ng-container>

          <!-- Plan column -->
          <ng-container matColumnDef="plan">
            <th mat-header-cell *matHeaderCellDef>Plan</th>
            <td mat-cell *matCellDef="let tenant">
              <mat-chip [class]="'plan-' + tenant.plan">
                {{ tenant.plan | titlecase }}
              </mat-chip>
            </td>
          </ng-container>

          <!-- Members column -->
          <ng-container matColumnDef="members">
            <th mat-header-cell *matHeaderCellDef>Members</th>
            <td mat-cell *matCellDef="let tenant">
              <span class="member-count">{{ tenant.member_count }}</span>
            </td>
          </ng-container>

          <!-- Created column -->
          <ng-container matColumnDef="created">
            <th mat-header-cell *matHeaderCellDef>Created</th>
            <td mat-cell *matCellDef="let tenant">
              {{ tenant.created_at | date:'mediumDate' }}
            </td>
          </ng-container>

          <!-- Actions column -->
          <ng-container matColumnDef="actions">
            <th mat-header-cell *matHeaderCellDef></th>
            <td mat-cell *matCellDef="let tenant">
              <button mat-icon-button [matMenuTriggerFor]="actionMenu" matTooltip="Actions">
                <mat-icon>more_vert</mat-icon>
              </button>
              <mat-menu #actionMenu="matMenu">
                <button mat-menu-item (click)="selectTenant(tenant)">
                  <mat-icon>login</mat-icon>
                  <span>Switch to Tenant</span>
                </button>
                <button mat-menu-item (click)="viewTenantDetails(tenant)">
                  <mat-icon>visibility</mat-icon>
                  <span>View Details</span>
                </button>
                <button mat-menu-item (click)="editTenant(tenant)">
                  <mat-icon>edit</mat-icon>
                  <span>Edit</span>
                </button>
                <mat-divider></mat-divider>
                @if (tenant.status === 'active') {
                  <button mat-menu-item (click)="suspendTenant(tenant)" class="warn-action">
                    <mat-icon>pause_circle</mat-icon>
                    <span>Suspend</span>
                  </button>
                } @else {
                  <button mat-menu-item (click)="activateTenant(tenant)">
                    <mat-icon>play_circle</mat-icon>
                    <span>Activate</span>
                  </button>
                }
              </mat-menu>
            </td>
          </ng-container>

          <tr mat-header-row *matHeaderRowDef="displayedColumns"></tr>
          <tr mat-row *matRowDef="let row; columns: displayedColumns;"
              [class.selected]="selectedTenant()?.id === row.id"
              (click)="viewTenantDetails(row)"></tr>
        </table>

        @if (tenants().length === 0 && !isLoading()) {
          <div class="empty-state">
            <mat-icon>business</mat-icon>
            <h3>No tenants found</h3>
            <p>Create your first tenant to get started with multi-tenancy</p>
            <button mat-raised-button color="primary" (click)="openCreateDialog()">
              Create Tenant
            </button>
          </div>
        }
      </mat-card>

      <!-- Tenant details panel -->
      @if (selectedTenant()) {
        <mat-card class="details-panel">
          <mat-card-header>
            <div class="tenant-avatar large" [style.background-color]="getAvatarColor(selectedTenant()!.slug)">
              {{ selectedTenant()!.name.charAt(0).toUpperCase() }}
            </div>
            <mat-card-title>{{ selectedTenant()!.name }}</mat-card-title>
            <mat-card-subtitle>{{ selectedTenant()!.slug }}</mat-card-subtitle>
          </mat-card-header>

          <mat-tab-group>
            <mat-tab label="Overview">
              <div class="tab-content">
                <div class="detail-row">
                  <span class="label">Status</span>
                  <mat-chip [class]="'status-' + selectedTenant()!.status">
                    {{ selectedTenant()!.status | titlecase }}
                  </mat-chip>
                </div>
                <div class="detail-row">
                  <span class="label">Plan</span>
                  <mat-chip [class]="'plan-' + selectedTenant()!.plan">
                    {{ selectedTenant()!.plan | titlecase }}
                  </mat-chip>
                </div>
                <div class="detail-row">
                  <span class="label">Contact</span>
                  <span>{{ selectedTenant()!.contact_name || 'Not set' }}</span>
                </div>
                <div class="detail-row">
                  <span class="label">Email</span>
                  <span>{{ selectedTenant()!.contact_email || 'Not set' }}</span>
                </div>
                <div class="detail-row">
                  <span class="label">Domain</span>
                  <span>{{ selectedTenant()!.domain || 'Not configured' }}</span>
                </div>
                <div class="detail-row">
                  <span class="label">Created</span>
                  <span>{{ selectedTenant()!.created_at | date:'medium' }}</span>
                </div>
                <mat-divider></mat-divider>
                <h4>Features</h4>
                <div class="features-list">
                  @for (feature of selectedTenant()!.settings.features || []; track feature) {
                    <mat-chip>{{ feature }}</mat-chip>
                  }
                </div>
              </div>
            </mat-tab>

            <mat-tab label="Members ({{ tenantMembers().length }})">
              <div class="tab-content">
                <div class="members-list">
                  @for (member of tenantMembers(); track member.id) {
                    <div class="member-row">
                      <div class="member-info">
                        <mat-icon>person</mat-icon>
                        <div>
                          <span class="member-name">{{ member.user_display_name || member.user_email }}</span>
                          <span class="member-email">{{ member.user_email }}</span>
                        </div>
                      </div>
                      <mat-chip [class]="'role-' + member.role">{{ member.role }}</mat-chip>
                    </div>
                  }
                  @if (tenantMembers().length === 0) {
                    <div class="empty-members">No members yet</div>
                  }
                </div>
              </div>
            </mat-tab>

            <mat-tab label="API Keys ({{ tenantAPIKeys().length }})">
              <div class="tab-content">
                <button mat-stroked-button (click)="createAPIKey()" class="create-key-btn">
                  <mat-icon>add</mat-icon>
                  New API Key
                </button>
                <div class="api-keys-list">
                  @for (key of tenantAPIKeys(); track key.id) {
                    <div class="api-key-row">
                      <div class="key-info">
                        <span class="key-name">{{ key.name }}</span>
                        <span class="key-prefix">{{ key.key_prefix }}...</span>
                      </div>
                      <div class="key-meta">
                        <mat-chip [class]="key.is_active ? 'active' : 'inactive'">
                          {{ key.is_active ? 'Active' : 'Revoked' }}
                        </mat-chip>
                        @if (key.last_used_at) {
                          <span class="last-used">Last used: {{ key.last_used_at | date:'short' }}</span>
                        }
                      </div>
                      <button mat-icon-button (click)="revokeAPIKey(key)"
                              [disabled]="!key.is_active"
                              matTooltip="Revoke key">
                        <mat-icon>delete</mat-icon>
                      </button>
                    </div>
                  }
                </div>
              </div>
            </mat-tab>
          </mat-tab-group>
        </mat-card>
      }
    </div>
  `,
  styles: [`
    .tenants-admin {
      padding: 24px;
      max-width: 1600px;
      margin: 0 auto;
    }

    .header {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      margin-bottom: 24px;
    }

    .title-section h1 {
      margin: 0;
      font-size: 28px;
      font-weight: 500;
    }

    .subtitle {
      margin: 4px 0 0;
      color: var(--text-secondary);
    }

    .stats-row {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 16px;
      margin-bottom: 24px;
    }

    .stat-card {
      display: flex;
      align-items: center;
      gap: 16px;
      padding: 20px;
    }

    .stat-icon {
      width: 48px;
      height: 48px;
      border-radius: 12px;
      display: flex;
      align-items: center;
      justify-content: center;
    }

    .stat-icon.active { background: rgba(76, 175, 80, 0.1); color: #4caf50; }
    .stat-icon.suspended { background: rgba(255, 152, 0, 0.1); color: #ff9800; }
    .stat-icon.enterprise { background: rgba(156, 39, 176, 0.1); color: #9c27b0; }
    .stat-icon.users { background: rgba(33, 150, 243, 0.1); color: #2196f3; }

    .stat-info {
      display: flex;
      flex-direction: column;
    }

    .stat-value {
      font-size: 24px;
      font-weight: 600;
    }

    .stat-label {
      font-size: 12px;
      color: var(--text-secondary);
    }

    .filter-card {
      display: flex;
      gap: 16px;
      padding: 16px;
      margin-bottom: 24px;
    }

    .search-field {
      flex: 1;
    }

    .table-card {
      position: relative;
      min-height: 200px;
    }

    .loading-overlay {
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      bottom: 0;
      display: flex;
      align-items: center;
      justify-content: center;
      background: rgba(255, 255, 255, 0.8);
      z-index: 10;
    }

    .tenants-table {
      width: 100%;
    }

    .tenant-name-cell {
      display: flex;
      align-items: center;
      gap: 12px;
    }

    .tenant-avatar {
      width: 40px;
      height: 40px;
      border-radius: 8px;
      display: flex;
      align-items: center;
      justify-content: center;
      color: white;
      font-weight: 600;
      font-size: 16px;
    }

    .tenant-avatar.large {
      width: 48px;
      height: 48px;
      font-size: 20px;
    }

    .tenant-info {
      display: flex;
      flex-direction: column;
    }

    .tenant-name {
      font-weight: 500;
    }

    .tenant-slug {
      font-size: 12px;
      color: var(--text-secondary);
    }

    .status-active { background: rgba(76, 175, 80, 0.1) !important; color: #4caf50 !important; }
    .status-suspended { background: rgba(255, 152, 0, 0.1) !important; color: #ff9800 !important; }
    .status-pending { background: rgba(158, 158, 158, 0.1) !important; color: #9e9e9e !important; }

    .plan-free { background: rgba(158, 158, 158, 0.1) !important; color: #757575 !important; }
    .plan-professional { background: rgba(33, 150, 243, 0.1) !important; color: #2196f3 !important; }
    .plan-enterprise { background: rgba(156, 39, 176, 0.1) !important; color: #9c27b0 !important; }

    .role-owner { background: rgba(156, 39, 176, 0.1) !important; color: #9c27b0 !important; }
    .role-admin { background: rgba(244, 67, 54, 0.1) !important; color: #f44336 !important; }
    .role-member { background: rgba(33, 150, 243, 0.1) !important; color: #2196f3 !important; }
    .role-viewer { background: rgba(158, 158, 158, 0.1) !important; color: #757575 !important; }

    .member-count {
      font-weight: 500;
    }

    tr.mat-mdc-row:hover {
      background: var(--hover-bg);
      cursor: pointer;
    }

    tr.selected {
      background: var(--selected-bg);
    }

    .empty-state {
      text-align: center;
      padding: 60px 20px;
    }

    .empty-state mat-icon {
      font-size: 64px;
      width: 64px;
      height: 64px;
      color: var(--text-secondary);
      margin-bottom: 16px;
    }

    .empty-state h3 {
      margin: 0 0 8px;
    }

    .empty-state p {
      color: var(--text-secondary);
      margin-bottom: 24px;
    }

    .details-panel {
      margin-top: 24px;
    }

    .tab-content {
      padding: 24px;
    }

    .detail-row {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 12px 0;
      border-bottom: 1px solid var(--border-color);
    }

    .detail-row .label {
      color: var(--text-secondary);
    }

    .features-list {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 12px;
    }

    .members-list, .api-keys-list {
      display: flex;
      flex-direction: column;
      gap: 12px;
    }

    .member-row, .api-key-row {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 12px;
      background: var(--card-bg);
      border-radius: 8px;
    }

    .member-info {
      display: flex;
      align-items: center;
      gap: 12px;
    }

    .member-name {
      font-weight: 500;
    }

    .member-email {
      font-size: 12px;
      color: var(--text-secondary);
      display: block;
    }

    .key-info {
      display: flex;
      flex-direction: column;
    }

    .key-name {
      font-weight: 500;
    }

    .key-prefix {
      font-family: monospace;
      font-size: 12px;
      color: var(--text-secondary);
    }

    .key-meta {
      display: flex;
      align-items: center;
      gap: 12px;
    }

    .last-used {
      font-size: 12px;
      color: var(--text-secondary);
    }

    .create-key-btn {
      margin-bottom: 16px;
    }

    .empty-members {
      text-align: center;
      padding: 40px;
      color: var(--text-secondary);
    }

    .warn-action {
      color: var(--warn-color);
    }

    @media (max-width: 1200px) {
      .stats-row {
        grid-template-columns: repeat(2, 1fr);
      }
    }

    @media (max-width: 768px) {
      .stats-row {
        grid-template-columns: 1fr;
      }
      .filter-card {
        flex-direction: column;
      }
    }
  `]
})
export class TenantsComponent implements OnInit {
  tenants = signal<Tenant[]>([]);
  selectedTenant = signal<Tenant | null>(null);
  tenantMembers = signal<TenantMembership[]>([]);
  tenantAPIKeys = signal<TenantAPIKey[]>([]);
  isLoading = signal(true);

  searchQuery = '';
  statusFilter = '';
  planFilter = '';

  displayedColumns = ['name', 'status', 'plan', 'members', 'created', 'actions'];

  // Computed stats
  activeTenants = computed(() => this.tenants().filter(t => t.status === 'active').length);
  suspendedTenants = computed(() => this.tenants().filter(t => t.status === 'suspended').length);
  enterpriseTenants = computed(() => this.tenants().filter(t => t.plan === 'enterprise').length);
  totalMembers = computed(() => this.tenants().reduce((sum, t) => sum + t.member_count, 0));

  private avatarColors = [
    '#f44336', '#e91e63', '#9c27b0', '#673ab7', '#3f51b5',
    '#2196f3', '#03a9f4', '#00bcd4', '#009688', '#4caf50',
    '#8bc34a', '#cddc39', '#ffc107', '#ff9800', '#ff5722'
  ];

  constructor(
    private tenantService: TenantService,
    private snackBar: MatSnackBar,
    private dialog: MatDialog
  ) {}

  ngOnInit() {
    this.loadTenants();
  }

  loadTenants() {
    this.isLoading.set(true);
    this.tenantService.list({
      status: this.statusFilter as TenantStatus || undefined,
      plan: this.planFilter as TenantPlan || undefined,
      search: this.searchQuery || undefined
    }).subscribe({
      next: (tenants) => {
        this.tenants.set(tenants);
        this.isLoading.set(false);
      },
      error: (err) => {
        console.error('Failed to load tenants:', err);
        this.snackBar.open('Failed to load tenants', 'Dismiss', { duration: 3000 });
        this.isLoading.set(false);
      }
    });
  }

  getAvatarColor(slug: string): string {
    let hash = 0;
    for (let i = 0; i < slug.length; i++) {
      hash = slug.charCodeAt(i) + ((hash << 5) - hash);
    }
    return this.avatarColors[Math.abs(hash) % this.avatarColors.length];
  }

  selectTenant(tenant: Tenant) {
    this.tenantService.setCurrentTenant(tenant);
    this.snackBar.open(`Switched to ${tenant.name}`, 'Dismiss', { duration: 3000 });
  }

  viewTenantDetails(tenant: Tenant) {
    this.selectedTenant.set(tenant);
    this.loadTenantMembers(tenant.id);
    this.loadTenantAPIKeys(tenant.id);
  }

  loadTenantMembers(tenantId: string) {
    this.tenantService.listMembers(tenantId).subscribe({
      next: (members) => this.tenantMembers.set(members),
      error: (err) => console.error('Failed to load members:', err)
    });
  }

  loadTenantAPIKeys(tenantId: string) {
    this.tenantService.listAPIKeys(tenantId).subscribe({
      next: (keys) => this.tenantAPIKeys.set(keys),
      error: (err) => console.error('Failed to load API keys:', err)
    });
  }

  openCreateDialog() {
    // TODO: Implement create tenant dialog
    this.snackBar.open('Create tenant dialog coming soon', 'Dismiss', { duration: 3000 });
  }

  editTenant(tenant: Tenant) {
    // TODO: Implement edit tenant dialog
    this.snackBar.open('Edit tenant dialog coming soon', 'Dismiss', { duration: 3000 });
  }

  suspendTenant(tenant: Tenant) {
    this.tenantService.update(tenant.id, { status: 'suspended' }).subscribe({
      next: () => {
        this.snackBar.open(`${tenant.name} has been suspended`, 'Dismiss', { duration: 3000 });
        this.loadTenants();
      },
      error: (err) => {
        console.error('Failed to suspend tenant:', err);
        this.snackBar.open('Failed to suspend tenant', 'Dismiss', { duration: 3000 });
      }
    });
  }

  activateTenant(tenant: Tenant) {
    this.tenantService.update(tenant.id, { status: 'active' }).subscribe({
      next: () => {
        this.snackBar.open(`${tenant.name} has been activated`, 'Dismiss', { duration: 3000 });
        this.loadTenants();
      },
      error: (err) => {
        console.error('Failed to activate tenant:', err);
        this.snackBar.open('Failed to activate tenant', 'Dismiss', { duration: 3000 });
      }
    });
  }

  createAPIKey() {
    const tenant = this.selectedTenant();
    if (!tenant) return;

    // TODO: Implement API key creation dialog
    this.snackBar.open('API key creation coming soon', 'Dismiss', { duration: 3000 });
  }

  revokeAPIKey(key: TenantAPIKey) {
    const tenant = this.selectedTenant();
    if (!tenant) return;

    this.tenantService.revokeAPIKey(tenant.id, key.id).subscribe({
      next: () => {
        this.snackBar.open('API key revoked', 'Dismiss', { duration: 3000 });
        this.loadTenantAPIKeys(tenant.id);
      },
      error: (err) => {
        console.error('Failed to revoke API key:', err);
        this.snackBar.open('Failed to revoke API key', 'Dismiss', { duration: 3000 });
      }
    });
  }
}
