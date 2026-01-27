import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatTableModule } from '@angular/material/table';
import { MatPaginatorModule, PageEvent } from '@angular/material/paginator';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatDialogModule, MatDialog } from '@angular/material/dialog';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatChipsModule } from '@angular/material/chips';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { MatSelectModule } from '@angular/material/select';
import { ResponseService, ResponseAction, IsolationStatus, ResponseActionResult } from '../../core/api/response.service';
import { IsolateDialogComponent } from './isolate-dialog.component';
import { ReleaseDialogComponent } from './release-dialog.component';

interface Endpoint {
  client_id: string;
  hostname: string;
  os: string;
  last_seen: string;
  online: boolean;
  isolation_status?: IsolationStatus;
}

@Component({
  selector: 'app-endpoint-isolation',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatCardModule,
    MatButtonModule,
    MatIconModule,
    MatInputModule,
    MatFormFieldModule,
    MatTableModule,
    MatPaginatorModule,
    MatProgressSpinnerModule,
    MatDialogModule,
    MatTooltipModule,
    MatChipsModule,
    MatSnackBarModule,
    MatSelectModule
  ],
  template: `
    <div class="endpoint-isolation">
      <header class="page-header">
        <h1>Endpoint Isolation</h1>
        <p class="subtitle">Manage network isolation for endpoints</p>
      </header>

      <!-- Filters -->
      <mat-card class="filters-card">
        <div class="filters">
          <mat-form-field appearance="outline">
            <mat-label>Search endpoints</mat-label>
            <input matInput [(ngModel)]="searchQuery" (keyup.enter)="search()" placeholder="Hostname or IP">
            <mat-icon matSuffix>search</mat-icon>
          </mat-form-field>

          <mat-form-field appearance="outline">
            <mat-label>Status</mat-label>
            <mat-select [(ngModel)]="statusFilter" (selectionChange)="applyFilters()">
              <mat-option value="all">All</mat-option>
              <mat-option value="isolated">Isolated</mat-option>
              <mat-option value="online">Online</mat-option>
              <mat-option value="offline">Offline</mat-option>
            </mat-select>
          </mat-form-field>

          <button mat-stroked-button (click)="refresh()">
            <mat-icon>refresh</mat-icon>
            Refresh
          </button>
        </div>
      </mat-card>

      <!-- Endpoints Table -->
      <mat-card class="endpoints-card">
        @if (isLoading()) {
          <div class="loading">
            <mat-spinner diameter="40"></mat-spinner>
          </div>
        } @else if (endpoints().length === 0) {
          <div class="empty-state">
            <mat-icon>devices</mat-icon>
            <p>No endpoints found</p>
            <span class="hint">Ensure Velociraptor is connected and endpoints are enrolled</span>
          </div>
        } @else {
          <table mat-table [dataSource]="endpoints()">
            <!-- Hostname -->
            <ng-container matColumnDef="hostname">
              <th mat-header-cell *matHeaderCellDef>Hostname</th>
              <td mat-cell *matCellDef="let row">
                <div class="hostname-cell">
                  <mat-icon [class.online]="row.online" [class.offline]="!row.online">
                    {{ row.online ? 'computer' : 'computer_off' }}
                  </mat-icon>
                  <div class="hostname-info">
                    <span class="hostname">{{ row.hostname }}</span>
                    <span class="client-id">{{ row.client_id }}</span>
                  </div>
                </div>
              </td>
            </ng-container>

            <!-- OS -->
            <ng-container matColumnDef="os">
              <th mat-header-cell *matHeaderCellDef>OS</th>
              <td mat-cell *matCellDef="let row">{{ row.os || 'Unknown' }}</td>
            </ng-container>

            <!-- Last Seen -->
            <ng-container matColumnDef="last_seen">
              <th mat-header-cell *matHeaderCellDef>Last Seen</th>
              <td mat-cell *matCellDef="let row">
                {{ row.last_seen | date:'short' }}
              </td>
            </ng-container>

            <!-- Isolation Status -->
            <ng-container matColumnDef="isolation">
              <th mat-header-cell *matHeaderCellDef>Isolation Status</th>
              <td mat-cell *matCellDef="let row">
                @if (row.isolation_status?.is_isolated) {
                  <mat-chip class="isolated-chip">
                    <mat-icon>block</mat-icon>
                    Isolated
                  </mat-chip>
                } @else {
                  <mat-chip class="normal-chip">
                    <mat-icon>check_circle</mat-icon>
                    Normal
                  </mat-chip>
                }
              </td>
            </ng-container>

            <!-- Actions -->
            <ng-container matColumnDef="actions">
              <th mat-header-cell *matHeaderCellDef>Actions</th>
              <td mat-cell *matCellDef="let row">
                <div class="action-buttons">
                  @if (row.isolation_status?.is_isolated) {
                    <button mat-flat-button color="primary" (click)="releaseEndpoint(row)">
                      <mat-icon>lock_open</mat-icon>
                      Release
                    </button>
                  } @else {
                    <button mat-flat-button color="warn" (click)="isolateEndpoint(row)">
                      <mat-icon>block</mat-icon>
                      Isolate
                    </button>
                  }
                  <button mat-icon-button matTooltip="View History" (click)="viewHistory(row)">
                    <mat-icon>history</mat-icon>
                  </button>
                </div>
              </td>
            </ng-container>

            <tr mat-header-row *matHeaderRowDef="displayedColumns"></tr>
            <tr mat-row *matRowDef="let row; columns: displayedColumns;"></tr>
          </table>

          <mat-paginator
            [length]="totalEndpoints()"
            [pageSize]="pageSize"
            [pageSizeOptions]="[10, 25, 50, 100]"
            (page)="onPageChange($event)">
          </mat-paginator>
        }
      </mat-card>

      <!-- Action History -->
      <mat-card class="history-card">
        <mat-card-header>
          <mat-card-title>Recent Actions</mat-card-title>
        </mat-card-header>
        <mat-card-content>
          @if (actionHistory().length === 0) {
            <div class="empty-history">
              <p>No recent isolation actions</p>
            </div>
          } @else {
            <div class="history-list">
              @for (action of actionHistory(); track action.id) {
                <div class="history-item" [class]="'status-' + action.status">
                  <div class="action-icon">
                    <mat-icon>{{ action.action_type === 'isolate' ? 'block' : 'lock_open' }}</mat-icon>
                  </div>
                  <div class="action-details">
                    <span class="action-type">{{ action.action_type | titlecase }}</span>
                    <span class="action-target">{{ action.hostname || action.client_id }}</span>
                    <span class="action-reason" *ngIf="action.reason">{{ action.reason }}</span>
                  </div>
                  <div class="action-meta">
                    <span class="status-badge" [class]="'status-' + action.status">
                      {{ action.status | titlecase }}
                    </span>
                    <span class="timestamp">{{ action.created_at | date:'short' }}</span>
                  </div>
                </div>
              }
            </div>
          }
        </mat-card-content>
      </mat-card>
    </div>
  `,
  styles: [`
    .endpoint-isolation {
      max-width: 1400px;
      margin: 0 auto;
    }

    .page-header {
      margin-bottom: 24px;

      h1 {
        font-size: 24px;
        margin: 0;
      }

      .subtitle {
        color: var(--text-secondary);
        margin: 4px 0 0;
      }
    }

    .filters-card {
      margin-bottom: 16px;
      padding: 16px;
    }

    .filters {
      display: flex;
      gap: 16px;
      align-items: flex-start;

      mat-form-field {
        flex: 1;
        max-width: 300px;
      }
    }

    .endpoints-card {
      margin-bottom: 16px;

      table {
        width: 100%;
      }
    }

    .loading {
      display: flex;
      justify-content: center;
      padding: 48px;
    }

    .empty-state {
      display: flex;
      flex-direction: column;
      align-items: center;
      padding: 48px;
      color: var(--text-muted);

      mat-icon {
        font-size: 48px;
        width: 48px;
        height: 48px;
        margin-bottom: 16px;
      }

      .hint {
        font-size: 13px;
        margin-top: 8px;
      }
    }

    .hostname-cell {
      display: flex;
      align-items: center;
      gap: 12px;

      mat-icon {
        font-size: 24px;
        width: 24px;
        height: 24px;

        &.online { color: var(--success); }
        &.offline { color: var(--text-muted); }
      }
    }

    .hostname-info {
      display: flex;
      flex-direction: column;

      .hostname {
        font-weight: 500;
      }

      .client-id {
        font-size: 11px;
        color: var(--text-muted);
        font-family: monospace;
      }
    }

    .isolated-chip {
      background: var(--danger) !important;
      color: white !important;

      mat-icon {
        font-size: 16px;
        width: 16px;
        height: 16px;
        margin-right: 4px;
      }
    }

    .normal-chip {
      background: var(--success) !important;
      color: black !important;

      mat-icon {
        font-size: 16px;
        width: 16px;
        height: 16px;
        margin-right: 4px;
      }
    }

    .action-buttons {
      display: flex;
      gap: 8px;
      align-items: center;
    }

    .history-card {
      mat-card-content {
        padding: 0;
      }
    }

    .empty-history {
      padding: 24px;
      text-align: center;
      color: var(--text-muted);
    }

    .history-list {
      max-height: 400px;
      overflow-y: auto;
    }

    .history-item {
      display: flex;
      align-items: center;
      gap: 16px;
      padding: 12px 16px;
      border-bottom: 1px solid var(--border-color);

      &:last-child {
        border-bottom: none;
      }

      &.status-failed {
        background: rgba(var(--danger-rgb), 0.1);
      }
    }

    .action-icon {
      width: 40px;
      height: 40px;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      background: var(--bg-secondary);

      mat-icon {
        font-size: 20px;
        width: 20px;
        height: 20px;
      }
    }

    .action-details {
      flex: 1;
      display: flex;
      flex-direction: column;

      .action-type {
        font-weight: 500;
      }

      .action-target {
        font-family: monospace;
        font-size: 13px;
        color: var(--text-secondary);
      }

      .action-reason {
        font-size: 12px;
        color: var(--text-muted);
        margin-top: 4px;
      }
    }

    .action-meta {
      display: flex;
      flex-direction: column;
      align-items: flex-end;
      gap: 4px;
    }

    .status-badge {
      padding: 4px 12px;
      border-radius: 12px;
      font-size: 11px;

      &.status-pending { background: var(--text-muted); color: white; }
      &.status-in_progress { background: var(--info); color: white; }
      &.status-completed { background: var(--success); color: black; }
      &.status-failed { background: var(--danger); color: white; }
    }

    .timestamp {
      font-size: 12px;
      color: var(--text-muted);
    }
  `]
})
export class EndpointIsolationComponent implements OnInit {
  endpoints = signal<Endpoint[]>([]);
  actionHistory = signal<ResponseAction[]>([]);
  totalEndpoints = signal(0);
  isLoading = signal(false);

  searchQuery = '';
  statusFilter = 'all';
  pageSize = 25;
  currentPage = 0;

  displayedColumns = ['hostname', 'os', 'last_seen', 'isolation', 'actions'];

  constructor(
    private responseService: ResponseService,
    private dialog: MatDialog,
    private snackBar: MatSnackBar
  ) {}

  ngOnInit(): void {
    this.loadEndpoints();
    this.loadActionHistory();
  }

  loadEndpoints(): void {
    this.isLoading.set(true);
    this.responseService.getEndpoints({
      search: this.searchQuery || undefined,
      limit: this.pageSize,
      offset: this.currentPage * this.pageSize
    }).subscribe({
      next: async (endpoints) => {
        // Load isolation status for each endpoint
        const endpointsWithStatus = await Promise.all(
          endpoints.map(async (e) => {
            try {
              const status = await this.responseService.getIsolationStatus(e.client_id).toPromise();
              return { ...e, isolation_status: status };
            } catch {
              return e;
            }
          })
        );
        this.endpoints.set(endpointsWithStatus);
        this.isLoading.set(false);
      },
      error: () => {
        this.isLoading.set(false);
        this.snackBar.open('Failed to load endpoints', 'Dismiss', { duration: 3000 });
      }
    });
  }

  loadActionHistory(): void {
    this.responseService.getActions({
      action_type: undefined,
      limit: 20
    }).subscribe({
      next: (actions) => this.actionHistory.set(actions),
      error: () => {}
    });
  }

  search(): void {
    this.currentPage = 0;
    this.loadEndpoints();
  }

  applyFilters(): void {
    this.currentPage = 0;
    this.loadEndpoints();
  }

  refresh(): void {
    this.loadEndpoints();
    this.loadActionHistory();
  }

  onPageChange(event: PageEvent): void {
    this.currentPage = event.pageIndex;
    this.pageSize = event.pageSize;
    this.loadEndpoints();
  }

  isolateEndpoint(endpoint: Endpoint): void {
    const dialogRef = this.dialog.open(IsolateDialogComponent, {
      width: '500px',
      data: { endpoint }
    });

    dialogRef.afterClosed().subscribe((result) => {
      if (result) {
        this.responseService.isolateHost({
          client_id: endpoint.client_id,
          hostname: endpoint.hostname,
          reason: result.reason,
          case_id: result.caseId
        }).subscribe({
          next: (response) => {
            if (response.success) {
              this.snackBar.open('Host isolation initiated', 'Dismiss', { duration: 3000 });
              this.refresh();
            } else {
              this.snackBar.open('Isolation failed', 'Dismiss', { duration: 3000 });
            }
          },
          error: (error) => {
            const message = error.error?.detail || 'Isolation failed';
            this.snackBar.open(message, 'Dismiss', { duration: 5000 });
          }
        });
      }
    });
  }

  releaseEndpoint(endpoint: Endpoint): void {
    const dialogRef = this.dialog.open(ReleaseDialogComponent, {
      width: '500px',
      data: { endpoint }
    });

    dialogRef.afterClosed().subscribe((result) => {
      if (result) {
        this.responseService.releaseHost({
          client_id: endpoint.client_id,
          reason: result.reason,
          case_id: result.caseId
        }).subscribe({
          next: (response) => {
            if (response.success) {
              this.snackBar.open('Host release initiated', 'Dismiss', { duration: 3000 });
              this.refresh();
            } else {
              this.snackBar.open('Release failed', 'Dismiss', { duration: 3000 });
            }
          },
          error: (error) => {
            const message = error.error?.detail || 'Release failed';
            this.snackBar.open(message, 'Dismiss', { duration: 5000 });
          }
        });
      }
    });
  }

  viewHistory(endpoint: Endpoint): void {
    this.responseService.getClientActions(endpoint.client_id).subscribe({
      next: (actions) => {
        // Could open a dialog to show endpoint-specific history
        console.log('Endpoint actions:', actions);
      }
    });
  }
}
