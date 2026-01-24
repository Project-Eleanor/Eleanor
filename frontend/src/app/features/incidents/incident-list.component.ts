import { Component, OnInit, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule, Router } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { MatTableModule } from '@angular/material/table';
import { MatSortModule, Sort } from '@angular/material/sort';
import { MatPaginatorModule, PageEvent } from '@angular/material/paginator';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatChipsModule } from '@angular/material/chips';
import { MatMenuModule } from '@angular/material/menu';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatDialogModule, MatDialog } from '@angular/material/dialog';
import { MatTooltipModule } from '@angular/material/tooltip';
import { CaseService } from '../../core/api/case.service';
import { Case, CaseStatus, Severity } from '../../shared/models';
import { CreateCaseDialogComponent } from './create-case-dialog.component';

@Component({
  selector: 'app-incident-list',
  standalone: true,
  imports: [
    CommonModule,
    RouterModule,
    FormsModule,
    MatTableModule,
    MatSortModule,
    MatPaginatorModule,
    MatButtonModule,
    MatIconModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    MatChipsModule,
    MatMenuModule,
    MatProgressSpinnerModule,
    MatDialogModule,
    MatTooltipModule
  ],
  template: `
    <div class="incident-list">
      <!-- Header -->
      <div class="page-header">
        <h1>Incidents</h1>
        <button mat-flat-button color="accent" (click)="createCase()">
          <mat-icon>add</mat-icon>
          New Case
        </button>
      </div>

      <!-- Filters -->
      <div class="filters">
        <mat-form-field appearance="outline" class="search-field">
          <mat-icon matPrefix>search</mat-icon>
          <input matInput
                 placeholder="Search cases..."
                 [(ngModel)]="searchQuery"
                 (keyup.enter)="applyFilters()">
        </mat-form-field>

        <mat-form-field appearance="outline">
          <mat-label>Status</mat-label>
          <mat-select [(ngModel)]="statusFilter" (selectionChange)="applyFilters()">
            <mat-option [value]="null">All</mat-option>
            <mat-option value="open">Open</mat-option>
            <mat-option value="in_progress">In Progress</mat-option>
            <mat-option value="pending">Pending</mat-option>
            <mat-option value="closed">Closed</mat-option>
          </mat-select>
        </mat-form-field>

        <mat-form-field appearance="outline">
          <mat-label>Severity</mat-label>
          <mat-select [(ngModel)]="severityFilter" (selectionChange)="applyFilters()">
            <mat-option [value]="null">All</mat-option>
            <mat-option value="critical">Critical</mat-option>
            <mat-option value="high">High</mat-option>
            <mat-option value="medium">Medium</mat-option>
            <mat-option value="low">Low</mat-option>
            <mat-option value="info">Info</mat-option>
          </mat-select>
        </mat-form-field>

        <button mat-icon-button (click)="clearFilters()" matTooltip="Clear filters">
          <mat-icon>filter_alt_off</mat-icon>
        </button>
      </div>

      <!-- Table -->
      @if (isLoading()) {
        <div class="loading">
          <mat-spinner diameter="40"></mat-spinner>
        </div>
      } @else {
        <div class="table-container">
          <table mat-table [dataSource]="cases()" matSort (matSortChange)="sortData($event)">
            <!-- Case Number -->
            <ng-container matColumnDef="case_number">
              <th mat-header-cell *matHeaderCellDef mat-sort-header>Case #</th>
              <td mat-cell *matCellDef="let row">
                <span class="case-number">{{ row.case_number }}</span>
              </td>
            </ng-container>

            <!-- Title -->
            <ng-container matColumnDef="title">
              <th mat-header-cell *matHeaderCellDef mat-sort-header>Title</th>
              <td mat-cell *matCellDef="let row">
                <div class="title-cell">
                  <span class="title">{{ row.title }}</span>
                  @if (row.tags.length > 0) {
                    <div class="tags">
                      @for (tag of row.tags.slice(0, 2); track tag) {
                        <mat-chip class="mini-chip">{{ tag }}</mat-chip>
                      }
                      @if (row.tags.length > 2) {
                        <span class="more-tags">+{{ row.tags.length - 2 }}</span>
                      }
                    </div>
                  }
                </div>
              </td>
            </ng-container>

            <!-- Severity -->
            <ng-container matColumnDef="severity">
              <th mat-header-cell *matHeaderCellDef mat-sort-header>Severity</th>
              <td mat-cell *matCellDef="let row">
                <mat-chip [class]="'severity-' + row.severity">
                  {{ row.severity | uppercase }}
                </mat-chip>
              </td>
            </ng-container>

            <!-- Status -->
            <ng-container matColumnDef="status">
              <th mat-header-cell *matHeaderCellDef mat-sort-header>Status</th>
              <td mat-cell *matCellDef="let row">
                <span class="status-badge" [class]="'status-' + row.status">
                  {{ formatStatus(row.status) }}
                </span>
              </td>
            </ng-container>

            <!-- Assignee -->
            <ng-container matColumnDef="assignee">
              <th mat-header-cell *matHeaderCellDef>Assignee</th>
              <td mat-cell *matCellDef="let row">
                @if (row.assignee_name) {
                  <div class="assignee">
                    <mat-icon>person</mat-icon>
                    {{ row.assignee_name }}
                  </div>
                } @else {
                  <span class="unassigned">Unassigned</span>
                }
              </td>
            </ng-container>

            <!-- Created -->
            <ng-container matColumnDef="created_at">
              <th mat-header-cell *matHeaderCellDef mat-sort-header>Created</th>
              <td mat-cell *matCellDef="let row">
                {{ row.created_at | date:'short' }}
              </td>
            </ng-container>

            <!-- Actions -->
            <ng-container matColumnDef="actions">
              <th mat-header-cell *matHeaderCellDef></th>
              <td mat-cell *matCellDef="let row">
                <button mat-icon-button [matMenuTriggerFor]="actionMenu">
                  <mat-icon>more_vert</mat-icon>
                </button>
                <mat-menu #actionMenu="matMenu">
                  <button mat-menu-item [routerLink]="['/incidents', row.id]">
                    <mat-icon>visibility</mat-icon>
                    <span>View Details</span>
                  </button>
                  <button mat-menu-item (click)="updateStatus(row, 'in_progress')"
                          [disabled]="row.status === 'in_progress'">
                    <mat-icon>play_arrow</mat-icon>
                    <span>Start Investigation</span>
                  </button>
                  <button mat-menu-item (click)="updateStatus(row, 'closed')"
                          [disabled]="row.status === 'closed'">
                    <mat-icon>check_circle</mat-icon>
                    <span>Close Case</span>
                  </button>
                </mat-menu>
              </td>
            </ng-container>

            <tr mat-header-row *matHeaderRowDef="displayedColumns"></tr>
            <tr mat-row *matRowDef="let row; columns: displayedColumns;"
                class="case-row"
                (click)="viewCase(row)">
            </tr>
          </table>
        </div>

        <mat-paginator [length]="totalCases()"
                       [pageSize]="pageSize"
                       [pageIndex]="currentPage()"
                       [pageSizeOptions]="[10, 20, 50]"
                       (page)="onPageChange($event)">
        </mat-paginator>
      }
    </div>
  `,
  styles: [`
    .incident-list {
      height: 100%;
      display: flex;
      flex-direction: column;
    }

    .page-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 24px;

      h1 {
        font-size: 24px;
        font-weight: 600;
        margin: 0;
      }
    }

    .filters {
      display: flex;
      gap: 16px;
      margin-bottom: 16px;
      flex-wrap: wrap;

      mat-form-field {
        min-width: 150px;
      }

      .search-field {
        flex: 1;
        min-width: 300px;
      }
    }

    .loading {
      display: flex;
      justify-content: center;
      padding: 48px;
    }

    .table-container {
      flex: 1;
      overflow: auto;
      background: var(--bg-card);
      border: 1px solid var(--border-color);
      border-radius: 8px;
    }

    table {
      width: 100%;
    }

    .case-row {
      cursor: pointer;

      &:hover {
        background: rgba(255, 255, 255, 0.02);
      }
    }

    .case-number {
      font-family: monospace;
      font-size: 12px;
      color: var(--text-secondary);
    }

    .title-cell {
      display: flex;
      flex-direction: column;
      gap: 4px;

      .title {
        font-weight: 500;
      }

      .tags {
        display: flex;
        gap: 4px;
        align-items: center;
      }
    }

    .mini-chip {
      font-size: 10px;
      min-height: 20px !important;
      padding: 2px 8px !important;
    }

    .more-tags {
      font-size: 10px;
      color: var(--text-secondary);
    }

    .severity-critical { background: var(--severity-critical) !important; color: white !important; }
    .severity-high { background: var(--severity-high) !important; color: white !important; }
    .severity-medium { background: var(--severity-medium) !important; color: black !important; }
    .severity-low { background: var(--severity-low) !important; color: white !important; }
    .severity-info { background: var(--severity-info) !important; color: white !important; }

    .status-badge {
      display: inline-flex;
      align-items: center;
      padding: 4px 12px;
      border-radius: 12px;
      font-size: 12px;
      font-weight: 500;

      &.status-open { background: var(--info); color: white; }
      &.status-in_progress { background: var(--warning); color: black; }
      &.status-pending { background: var(--text-muted); color: white; }
      &.status-closed { background: var(--success); color: black; }
    }

    .assignee {
      display: flex;
      align-items: center;
      gap: 4px;
      font-size: 13px;

      mat-icon {
        font-size: 16px;
        width: 16px;
        height: 16px;
        color: var(--text-secondary);
      }
    }

    .unassigned {
      color: var(--text-muted);
      font-style: italic;
    }
  `]
})
export class IncidentListComponent implements OnInit {
  displayedColumns = ['case_number', 'title', 'severity', 'status', 'assignee', 'created_at', 'actions'];

  cases = signal<Case[]>([]);
  isLoading = signal(true);
  totalCases = signal(0);
  currentPage = signal(0);
  pageSize = 20;

  searchQuery = '';
  statusFilter: CaseStatus | null = null;
  severityFilter: Severity | null = null;

  constructor(
    private caseService: CaseService,
    private router: Router,
    private dialog: MatDialog
  ) {}

  ngOnInit(): void {
    this.loadCases();
  }

  loadCases(): void {
    this.isLoading.set(true);

    const params: Parameters<CaseService['list']>[0] = {
      page: this.currentPage() + 1,
      page_size: this.pageSize
    };

    if (this.searchQuery) params.search = this.searchQuery;
    if (this.statusFilter) params.status = this.statusFilter;
    if (this.severityFilter) params.severity = this.severityFilter;

    this.caseService.list(params).subscribe({
      next: (response) => {
        this.cases.set(response.items);
        this.totalCases.set(response.total);
        this.isLoading.set(false);
      },
      error: () => this.isLoading.set(false)
    });
  }

  applyFilters(): void {
    this.currentPage.set(0);
    this.loadCases();
  }

  clearFilters(): void {
    this.searchQuery = '';
    this.statusFilter = null;
    this.severityFilter = null;
    this.applyFilters();
  }

  sortData(sort: Sort): void {
    this.loadCases();
  }

  onPageChange(event: PageEvent): void {
    this.currentPage.set(event.pageIndex);
    this.pageSize = event.pageSize;
    this.loadCases();
  }

  viewCase(caseItem: Case): void {
    this.router.navigate(['/incidents', caseItem.id]);
  }

  createCase(): void {
    const dialogRef = this.dialog.open(CreateCaseDialogComponent, {
      width: '600px'
    });

    dialogRef.afterClosed().subscribe(result => {
      if (result) {
        this.loadCases();
      }
    });
  }

  updateStatus(caseItem: Case, newStatus: CaseStatus): void {
    this.caseService.update(caseItem.id, { status: newStatus }).subscribe({
      next: () => this.loadCases()
    });
  }

  formatStatus(status: string): string {
    return status.replace('_', ' ').split(' ')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ');
  }
}
