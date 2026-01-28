import { Component, OnInit, signal, computed, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatTableModule } from '@angular/material/table';
import { MatChipsModule } from '@angular/material/chips';
import { MatMenuModule } from '@angular/material/menu';
import { MatDialogModule, MatDialog } from '@angular/material/dialog';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatTabsModule } from '@angular/material/tabs';
import { MatCardModule } from '@angular/material/card';
import { MatBadgeModule } from '@angular/material/badge';
import { MatDividerModule } from '@angular/material/divider';
import {
  ConnectorsService,
  DataConnector,
  ConnectorType,
  ConnectorStatus,
  ConnectorHealth,
  ConnectorsStats,
  ConnectorCreate
} from '../../core/api/connectors.service';
import { ConnectorDialogComponent } from './connector-dialog.component';

@Component({
  selector: 'app-connectors',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatButtonModule,
    MatIconModule,
    MatTableModule,
    MatChipsModule,
    MatMenuModule,
    MatDialogModule,
    MatProgressSpinnerModule,
    MatTooltipModule,
    MatSnackBarModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    MatTabsModule,
    MatCardModule,
    MatBadgeModule,
    MatDividerModule,
  ],
  template: `
    <div class="connectors-page">
      <!-- Header -->
      <div class="page-header">
        <div class="header-title">
          <h1>Data Connectors</h1>
          <p class="subtitle">Manage data ingestion sources and integrations</p>
        </div>
        <div class="header-actions">
          <button mat-stroked-button (click)="refreshConnectors()">
            <mat-icon>refresh</mat-icon>
            Refresh
          </button>
          <button mat-flat-button color="primary" (click)="openAddConnector()">
            <mat-icon>add</mat-icon>
            Add Connector
          </button>
        </div>
      </div>

      <!-- Stats Cards -->
      <div class="stats-grid">
        <div class="stat-card">
          <div class="stat-icon total">
            <mat-icon>hub</mat-icon>
          </div>
          <div class="stat-content">
            <span class="stat-value">{{ stats()?.total_connectors || 0 }}</span>
            <span class="stat-label">Total Connectors</span>
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-icon healthy">
            <mat-icon>check_circle</mat-icon>
          </div>
          <div class="stat-content">
            <span class="stat-value">{{ stats()?.by_health?.['healthy'] || 0 }}</span>
            <span class="stat-label">Healthy</span>
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-icon degraded">
            <mat-icon>warning</mat-icon>
          </div>
          <div class="stat-content">
            <span class="stat-value">{{ stats()?.by_health?.['degraded'] || 0 }}</span>
            <span class="stat-label">Degraded</span>
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-icon unhealthy">
            <mat-icon>error</mat-icon>
          </div>
          <div class="stat-content">
            <span class="stat-value">{{ stats()?.by_health?.['unhealthy'] || 0 }}</span>
            <span class="stat-label">Unhealthy</span>
          </div>
        </div>
        <div class="stat-card wide">
          <div class="stat-icon events">
            <mat-icon>analytics</mat-icon>
          </div>
          <div class="stat-content">
            <span class="stat-value">{{ formatNumber(stats()?.total_events_processed || 0) }}</span>
            <span class="stat-label">Events Processed</span>
          </div>
          <div class="stat-secondary">
            <span class="secondary-value">{{ formatBytes(stats()?.total_bytes_received || 0) }}</span>
            <span class="secondary-label">Data Received</span>
          </div>
        </div>
      </div>

      <!-- Filters -->
      <div class="filters-bar">
        <mat-form-field appearance="outline" class="search-field">
          <mat-icon matPrefix>search</mat-icon>
          <input matInput placeholder="Search connectors..." [(ngModel)]="searchQuery" (ngModelChange)="onSearch()">
        </mat-form-field>

        <mat-form-field appearance="outline" class="filter-field">
          <mat-label>Type</mat-label>
          <mat-select [(ngModel)]="filterType" (ngModelChange)="loadConnectors()">
            <mat-option [value]="null">All Types</mat-option>
            @for (type of connectorTypes; track type) {
              <mat-option [value]="type">{{ getTypeLabel(type) }}</mat-option>
            }
          </mat-select>
        </mat-form-field>

        <mat-form-field appearance="outline" class="filter-field">
          <mat-label>Status</mat-label>
          <mat-select [(ngModel)]="filterStatus" (ngModelChange)="loadConnectors()">
            <mat-option [value]="null">All Status</mat-option>
            <mat-option value="enabled">Enabled</mat-option>
            <mat-option value="disabled">Disabled</mat-option>
            <mat-option value="error">Error</mat-option>
            <mat-option value="configuring">Configuring</mat-option>
          </mat-select>
        </mat-form-field>

        <mat-form-field appearance="outline" class="filter-field">
          <mat-label>Health</mat-label>
          <mat-select [(ngModel)]="filterHealth" (ngModelChange)="loadConnectors()">
            <mat-option [value]="null">All Health</mat-option>
            <mat-option value="healthy">Healthy</mat-option>
            <mat-option value="degraded">Degraded</mat-option>
            <mat-option value="unhealthy">Unhealthy</mat-option>
            <mat-option value="unknown">Unknown</mat-option>
          </mat-select>
        </mat-form-field>
      </div>

      <!-- Connectors List -->
      @if (loading()) {
        <div class="loading-container">
          <mat-spinner diameter="48"></mat-spinner>
          <span>Loading connectors...</span>
        </div>
      } @else if (connectors().length === 0) {
        <div class="empty-state">
          <mat-icon>cable</mat-icon>
          <h3>No Data Connectors</h3>
          <p>Add your first connector to start ingesting data</p>
          <button mat-flat-button color="primary" (click)="openAddConnector()">
            <mat-icon>add</mat-icon>
            Add Connector
          </button>
        </div>
      } @else {
        <div class="connectors-grid">
          @for (connector of connectors(); track connector.id) {
            <div class="connector-card" [class]="'health-' + connector.health">
              <div class="card-header">
                <div class="connector-icon" [class]="connector.connector_type">
                  <mat-icon>{{ getTypeIcon(connector.connector_type) }}</mat-icon>
                </div>
                <div class="connector-info">
                  <h3>{{ connector.name }}</h3>
                  <span class="connector-type">{{ getTypeLabel(connector.connector_type) }}</span>
                </div>
                <button mat-icon-button [matMenuTriggerFor]="connectorMenu">
                  <mat-icon>more_vert</mat-icon>
                </button>
                <mat-menu #connectorMenu="matMenu">
                  <button mat-menu-item (click)="editConnector(connector)">
                    <mat-icon>edit</mat-icon>
                    <span>Edit</span>
                  </button>
                  <button mat-menu-item (click)="testConnector(connector)">
                    <mat-icon>play_arrow</mat-icon>
                    <span>Test Connection</span>
                  </button>
                  @if (connector.status === 'enabled') {
                    <button mat-menu-item (click)="disableConnector(connector)">
                      <mat-icon>pause</mat-icon>
                      <span>Disable</span>
                    </button>
                  } @else {
                    <button mat-menu-item (click)="enableConnector(connector)">
                      <mat-icon>play_arrow</mat-icon>
                      <span>Enable</span>
                    </button>
                  }
                  <mat-divider></mat-divider>
                  <button mat-menu-item class="delete-action" (click)="deleteConnector(connector)">
                    <mat-icon>delete</mat-icon>
                    <span>Delete</span>
                  </button>
                </mat-menu>
              </div>

              <div class="card-body">
                @if (connector.description) {
                  <p class="description">{{ connector.description }}</p>
                }

                <div class="status-row">
                  <div class="status-chip" [class]="connector.status">
                    <span class="status-dot"></span>
                    {{ connector.status | titlecase }}
                  </div>
                  <div class="health-chip" [class]="connector.health">
                    <mat-icon>{{ getHealthIcon(connector.health) }}</mat-icon>
                    {{ connector.health | titlecase }}
                  </div>
                </div>

                <div class="metrics-grid">
                  <div class="metric">
                    <span class="metric-value">{{ formatNumber(connector.events_processed) }}</span>
                    <span class="metric-label">Events</span>
                  </div>
                  <div class="metric">
                    <span class="metric-value">{{ formatBytes(connector.bytes_received) }}</span>
                    <span class="metric-label">Data</span>
                  </div>
                  <div class="metric">
                    <span class="metric-value" [class.error]="connector.events_failed > 0">
                      {{ connector.events_failed }}
                    </span>
                    <span class="metric-label">Failed</span>
                  </div>
                </div>

                @if (connector.last_event_at) {
                  <div class="last-event">
                    <mat-icon>schedule</mat-icon>
                    Last event: {{ formatRelativeTime(connector.last_event_at) }}
                  </div>
                }

                @if (connector.last_error_message) {
                  <div class="error-message">
                    <mat-icon>error_outline</mat-icon>
                    {{ connector.last_error_message }}
                  </div>
                }
              </div>

              <div class="card-footer">
                @if (connector.target_index) {
                  <span class="index-tag">
                    <mat-icon>storage</mat-icon>
                    {{ connector.target_index }}
                  </span>
                }
                @if (connector.data_type) {
                  <span class="type-tag">{{ connector.data_type }}</span>
                }
              </div>
            </div>
          }
        </div>
      }
    </div>
  `,
  styles: [`
    .connectors-page {
      padding: 24px;
      max-width: 1600px;
      margin: 0 auto;
    }

    .page-header {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      margin-bottom: 24px;
    }

    .header-title h1 {
      margin: 0;
      font-size: 28px;
      font-weight: 500;
    }

    .subtitle {
      margin: 4px 0 0;
      color: #888;
      font-size: 14px;
    }

    .header-actions {
      display: flex;
      gap: 12px;
    }

    /* Stats Grid */
    .stats-grid {
      display: grid;
      grid-template-columns: repeat(5, 1fr);
      gap: 16px;
      margin-bottom: 24px;
    }

    .stat-card {
      background: rgba(20, 26, 36, 0.6);
      backdrop-filter: blur(12px);
      -webkit-backdrop-filter: blur(12px);
      border: 1px solid rgba(74, 158, 255, 0.1);
      border-radius: 12px;
      padding: 16px;
      display: flex;
      align-items: center;
      gap: 16px;
      transition: border-color 0.2s ease, background-color 0.2s ease;
    }

    .stat-card:hover {
      border-color: rgba(74, 158, 255, 0.25);
      background: rgba(20, 26, 36, 0.75);
    }

    .stat-card.wide {
      grid-column: span 1;
    }

    .stat-icon {
      width: 48px;
      height: 48px;
      border-radius: 8px;
      display: flex;
      align-items: center;
      justify-content: center;
    }

    .stat-icon.total { background: rgba(33, 150, 243, 0.15); color: #2196F3; }
    .stat-icon.healthy { background: rgba(76, 175, 80, 0.15); color: #4CAF50; }
    .stat-icon.degraded { background: rgba(255, 152, 0, 0.15); color: #FF9800; }
    .stat-icon.unhealthy { background: rgba(244, 67, 54, 0.15); color: #F44336; }
    .stat-icon.events { background: rgba(156, 39, 176, 0.15); color: #9C27B0; }

    .stat-content {
      display: flex;
      flex-direction: column;
    }

    .stat-value {
      font-size: 24px;
      font-weight: 600;
    }

    .stat-label {
      font-size: 12px;
      color: #888;
    }

    .stat-secondary {
      margin-left: auto;
      text-align: right;
    }

    .secondary-value {
      font-size: 18px;
      font-weight: 500;
      color: #aaa;
    }

    .secondary-label {
      font-size: 11px;
      color: #666;
      display: block;
    }

    /* Filters */
    .filters-bar {
      display: flex;
      gap: 16px;
      margin-bottom: 24px;
      flex-wrap: wrap;
    }

    .search-field {
      flex: 1;
      min-width: 250px;
    }

    .filter-field {
      width: 150px;
    }

    /* Loading & Empty States */
    .loading-container, .empty-state {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      padding: 80px 24px;
      color: #888;
      gap: 16px;
    }

    .empty-state mat-icon {
      font-size: 64px;
      width: 64px;
      height: 64px;
      opacity: 0.5;
    }

    .empty-state h3 {
      margin: 0;
      font-size: 20px;
      color: #ccc;
    }

    .empty-state p {
      margin: 0;
    }

    /* Connectors Grid */
    .connectors-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
      gap: 20px;
    }

    .connector-card {
      background: rgba(20, 26, 36, 0.6);
      backdrop-filter: blur(12px);
      -webkit-backdrop-filter: blur(12px);
      border: 1px solid rgba(74, 158, 255, 0.1);
      border-radius: 12px;
      overflow: hidden;
      transition: border-color 0.2s ease, background-color 0.2s ease, box-shadow 0.3s ease;
    }

    .connector-card:hover {
      border-color: rgba(74, 158, 255, 0.25);
      background: rgba(20, 26, 36, 0.75);
      box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3), 0 0 20px rgba(74, 158, 255, 0.1);
    }

    .connector-card.health-healthy { border-left: 3px solid #4CAF50; }
    .connector-card.health-degraded { border-left: 3px solid #FF9800; }
    .connector-card.health-unhealthy { border-left: 3px solid #F44336; }
    .connector-card.health-unknown { border-left: 3px solid #666; }

    .card-header {
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 16px;
      border-bottom: 1px solid rgba(74, 158, 255, 0.08);
      background: rgba(255, 255, 255, 0.02);
    }

    .connector-icon {
      width: 40px;
      height: 40px;
      border-radius: 8px;
      display: flex;
      align-items: center;
      justify-content: center;
      background: #2a2a2a;
    }

    .connector-icon.syslog { background: rgba(0, 188, 212, 0.15); color: #00BCD4; }
    .connector-icon.windows_event { background: rgba(33, 150, 243, 0.15); color: #2196F3; }
    .connector-icon.cloud_trail { background: rgba(255, 152, 0, 0.15); color: #FF9800; }
    .connector-icon.azure_ad { background: rgba(0, 120, 212, 0.15); color: #0078D4; }
    .connector-icon.office_365 { background: rgba(235, 59, 90, 0.15); color: #EB3B5A; }
    .connector-icon.aws_s3 { background: rgba(255, 153, 0, 0.15); color: #FF9900; }
    .connector-icon.beats { background: rgba(0, 191, 178, 0.15); color: #00BFB2; }
    .connector-icon.kafka { background: rgba(0, 0, 0, 0.15); color: #fff; }
    .connector-icon.webhook { background: rgba(156, 39, 176, 0.15); color: #9C27B0; }
    .connector-icon.api_polling { background: rgba(76, 175, 80, 0.15); color: #4CAF50; }
    .connector-icon.file_upload { background: rgba(121, 85, 72, 0.15); color: #795548; }
    .connector-icon.custom { background: rgba(158, 158, 158, 0.15); color: #9E9E9E; }
    /* Phase 4 connector types */
    .connector-icon.gcp_cloud_logging { background: rgba(66, 133, 244, 0.15); color: #4285F4; }
    .connector-icon.aws_security_hub { background: rgba(255, 153, 0, 0.15); color: #FF9900; }
    .connector-icon.azure_event_hub { background: rgba(0, 120, 212, 0.15); color: #0078D4; }
    .connector-icon.fluentd { background: rgba(0, 150, 136, 0.15); color: #009688; }
    .connector-icon.wef { background: rgba(33, 150, 243, 0.15); color: #2196F3; }
    .connector-icon.okta { background: rgba(0, 123, 255, 0.15); color: #007BFF; }
    .connector-icon.crowdstrike_fdr { background: rgba(244, 67, 54, 0.15); color: #F44336; }
    .connector-icon.splunk_hec { background: rgba(139, 195, 74, 0.15); color: #8BC34A; }

    .connector-info {
      flex: 1;
      min-width: 0;
    }

    .connector-info h3 {
      margin: 0;
      font-size: 16px;
      font-weight: 500;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    .connector-type {
      font-size: 12px;
      color: #888;
    }

    .card-body {
      padding: 16px;
    }

    .description {
      margin: 0 0 12px;
      font-size: 13px;
      color: #aaa;
      line-height: 1.4;
    }

    .status-row {
      display: flex;
      gap: 12px;
      margin-bottom: 16px;
    }

    .status-chip, .health-chip {
      display: flex;
      align-items: center;
      gap: 6px;
      padding: 4px 10px;
      border-radius: 4px;
      font-size: 12px;
      font-weight: 500;
    }

    .status-chip {
      background: #2a2a2a;
    }

    .status-dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
    }

    .status-chip.enabled .status-dot { background: #4CAF50; }
    .status-chip.disabled .status-dot { background: #666; }
    .status-chip.error .status-dot { background: #F44336; }
    .status-chip.configuring .status-dot { background: #FF9800; }

    .health-chip mat-icon {
      font-size: 16px;
      width: 16px;
      height: 16px;
    }

    .health-chip.healthy { background: rgba(76, 175, 80, 0.15); color: #4CAF50; }
    .health-chip.degraded { background: rgba(255, 152, 0, 0.15); color: #FF9800; }
    .health-chip.unhealthy { background: rgba(244, 67, 54, 0.15); color: #F44336; }
    .health-chip.unknown { background: rgba(158, 158, 158, 0.15); color: #9E9E9E; }

    .metrics-grid {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 12px;
      margin-bottom: 12px;
    }

    .metric {
      text-align: center;
      padding: 8px;
      background: #252525;
      border-radius: 6px;
    }

    .metric-value {
      display: block;
      font-size: 18px;
      font-weight: 600;
    }

    .metric-value.error {
      color: #F44336;
    }

    .metric-label {
      font-size: 11px;
      color: #888;
    }

    .last-event {
      display: flex;
      align-items: center;
      gap: 6px;
      font-size: 12px;
      color: #888;
    }

    .last-event mat-icon {
      font-size: 14px;
      width: 14px;
      height: 14px;
    }

    .error-message {
      display: flex;
      align-items: flex-start;
      gap: 6px;
      margin-top: 12px;
      padding: 8px;
      background: rgba(244, 67, 54, 0.1);
      border-radius: 4px;
      font-size: 12px;
      color: #F44336;
    }

    .error-message mat-icon {
      font-size: 16px;
      width: 16px;
      height: 16px;
      flex-shrink: 0;
    }

    .card-footer {
      display: flex;
      gap: 8px;
      padding: 12px 16px;
      background: rgba(0, 0, 0, 0.2);
      border-top: 1px solid rgba(74, 158, 255, 0.08);
      flex-wrap: wrap;
    }

    .index-tag, .type-tag {
      display: flex;
      align-items: center;
      gap: 4px;
      padding: 2px 8px;
      background: #2a2a2a;
      border-radius: 4px;
      font-size: 11px;
      color: #aaa;
    }

    .index-tag mat-icon {
      font-size: 12px;
      width: 12px;
      height: 12px;
    }

    .delete-action {
      color: #F44336;
    }

    @media (max-width: 1200px) {
      .stats-grid {
        grid-template-columns: repeat(3, 1fr);
      }
      .stat-card.wide {
        grid-column: span 1;
      }
    }

    @media (max-width: 768px) {
      .stats-grid {
        grid-template-columns: repeat(2, 1fr);
      }
      .connectors-grid {
        grid-template-columns: 1fr;
      }
    }
  `]
})
export class ConnectorsComponent implements OnInit {
  private connectorsService = inject(ConnectorsService);
  private dialog = inject(MatDialog);
  private snackBar = inject(MatSnackBar);

  connectors = signal<DataConnector[]>([]);
  stats = signal<ConnectorsStats | null>(null);
  loading = signal(true);

  searchQuery = '';
  filterType: ConnectorType | null = null;
  filterStatus: ConnectorStatus | null = null;
  filterHealth: ConnectorHealth | null = null;

  connectorTypes: ConnectorType[] = [
    'syslog', 'windows_event', 'cloud_trail', 'azure_ad', 'office_365',
    'aws_s3', 'beats', 'kafka', 'webhook', 'api_polling', 'file_upload', 'custom',
    // Phase 4 connector types
    'gcp_cloud_logging', 'aws_security_hub', 'azure_event_hub', 'fluentd',
    'wef', 'okta', 'crowdstrike_fdr', 'splunk_hec'
  ];

  ngOnInit(): void {
    this.loadConnectors();
    this.loadStats();
  }

  loadConnectors(): void {
    this.loading.set(true);
    this.connectorsService.list({
      type: this.filterType || undefined,
      status: this.filterStatus || undefined,
      health: this.filterHealth || undefined,
      search: this.searchQuery || undefined,
      page_size: 100
    }).subscribe({
      next: (response) => {
        this.connectors.set(response.items);
        this.loading.set(false);
      },
      error: (err) => {
        console.error('Failed to load connectors:', err);
        this.loading.set(false);
        this.snackBar.open('Failed to load connectors', 'Dismiss', { duration: 3000 });
      }
    });
  }

  loadStats(): void {
    this.connectorsService.getStats().subscribe({
      next: (stats) => this.stats.set(stats),
      error: (err) => console.error('Failed to load stats:', err)
    });
  }

  refreshConnectors(): void {
    this.loadConnectors();
    this.loadStats();
  }

  onSearch(): void {
    this.loadConnectors();
  }

  openAddConnector(): void {
    const dialogRef = this.dialog.open(ConnectorDialogComponent, {
      width: '600px',
      maxHeight: '85vh',
      data: { mode: 'create' },
      panelClass: 'centered-dialog',
      position: { top: '50px' }
    });

    dialogRef.afterClosed().subscribe(result => {
      if (result) {
        this.loadConnectors();
        this.loadStats();
      }
    });
  }

  editConnector(connector: DataConnector): void {
    const dialogRef = this.dialog.open(ConnectorDialogComponent, {
      width: '600px',
      maxHeight: '85vh',
      data: { mode: 'edit', connector },
      panelClass: 'centered-dialog',
      position: { top: '50px' }
    });

    dialogRef.afterClosed().subscribe(result => {
      if (result) {
        this.loadConnectors();
        this.loadStats();
      }
    });
  }

  testConnector(connector: DataConnector): void {
    this.snackBar.open('Testing connection...', '', { duration: 0 });
    this.connectorsService.test(connector.id).subscribe({
      next: (result) => {
        if (result.success) {
          this.snackBar.open(`Connection successful (${result.latency_ms}ms)`, 'OK', { duration: 5000 });
        } else {
          this.snackBar.open(`Connection failed: ${result.message}`, 'Dismiss', { duration: 5000 });
        }
      },
      error: (err) => {
        this.snackBar.open('Test failed: ' + (err.error?.detail || 'Unknown error'), 'Dismiss', { duration: 5000 });
      }
    });
  }

  enableConnector(connector: DataConnector): void {
    this.connectorsService.enable(connector.id).subscribe({
      next: () => {
        this.snackBar.open('Connector enabled', 'OK', { duration: 3000 });
        this.loadConnectors();
        this.loadStats();
      },
      error: (err) => {
        this.snackBar.open('Failed to enable connector', 'Dismiss', { duration: 3000 });
      }
    });
  }

  disableConnector(connector: DataConnector): void {
    this.connectorsService.disable(connector.id).subscribe({
      next: () => {
        this.snackBar.open('Connector disabled', 'OK', { duration: 3000 });
        this.loadConnectors();
        this.loadStats();
      },
      error: (err) => {
        this.snackBar.open('Failed to disable connector', 'Dismiss', { duration: 3000 });
      }
    });
  }

  deleteConnector(connector: DataConnector): void {
    if (confirm(`Delete connector "${connector.name}"? This cannot be undone.`)) {
      this.connectorsService.delete(connector.id).subscribe({
        next: () => {
          this.snackBar.open('Connector deleted', 'OK', { duration: 3000 });
          this.loadConnectors();
          this.loadStats();
        },
        error: (err) => {
          this.snackBar.open('Failed to delete connector', 'Dismiss', { duration: 3000 });
        }
      });
    }
  }

  getTypeLabel(type: ConnectorType): string {
    const labels: Record<ConnectorType, string> = {
      syslog: 'Syslog',
      windows_event: 'Windows Events',
      cloud_trail: 'AWS CloudTrail',
      azure_ad: 'Azure AD',
      office_365: 'Office 365',
      aws_s3: 'AWS S3',
      beats: 'Elastic Beats',
      kafka: 'Apache Kafka',
      webhook: 'Webhook',
      api_polling: 'API Polling',
      file_upload: 'File Upload',
      custom: 'Custom',
      // Phase 4 connector types
      gcp_cloud_logging: 'GCP Cloud Logging',
      aws_security_hub: 'AWS Security Hub',
      azure_event_hub: 'Azure Event Hub',
      fluentd: 'Fluentd/Fluent Bit',
      wef: 'Windows Event Forwarding',
      okta: 'Okta',
      crowdstrike_fdr: 'CrowdStrike FDR',
      splunk_hec: 'Splunk HEC'
    };
    return labels[type] || type;
  }

  getTypeIcon(type: ConnectorType): string {
    const icons: Record<ConnectorType, string> = {
      syslog: 'terminal',
      windows_event: 'desktop_windows',
      cloud_trail: 'cloud',
      azure_ad: 'account_circle',
      office_365: 'mail',
      aws_s3: 'cloud_upload',
      beats: 'sensors',
      kafka: 'stream',
      webhook: 'webhook',
      api_polling: 'sync',
      file_upload: 'upload_file',
      custom: 'extension',
      // Phase 4 connector types
      gcp_cloud_logging: 'cloud_queue',
      aws_security_hub: 'security',
      azure_event_hub: 'hub',
      fluentd: 'route',
      wef: 'dns',
      okta: 'fingerprint',
      crowdstrike_fdr: 'radar',
      splunk_hec: 'data_exploration'
    };
    return icons[type] || 'cable';
  }

  getHealthIcon(health: ConnectorHealth): string {
    const icons: Record<ConnectorHealth, string> = {
      healthy: 'check_circle',
      degraded: 'warning',
      unhealthy: 'error',
      unknown: 'help'
    };
    return icons[health] || 'help';
  }

  formatNumber(num: number): string {
    if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
    if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
    return num.toString();
  }

  formatBytes(bytes: number): string {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  }

  formatRelativeTime(dateStr: string): string {
    const date = new Date(dateStr);
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const seconds = Math.floor(diff / 1000);
    const minutes = Math.floor(seconds / 60);
    const hours = Math.floor(minutes / 60);
    const days = Math.floor(hours / 24);

    if (days > 0) return `${days}d ago`;
    if (hours > 0) return `${hours}h ago`;
    if (minutes > 0) return `${minutes}m ago`;
    return 'Just now';
  }
}
