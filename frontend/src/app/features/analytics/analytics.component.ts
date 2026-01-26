import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatCardModule } from '@angular/material/card';
import { MatIconModule } from '@angular/material/icon';
import { MatButtonModule } from '@angular/material/button';
import { MatTableModule } from '@angular/material/table';
import { MatSlideToggleModule } from '@angular/material/slide-toggle';
import { MatChipsModule } from '@angular/material/chips';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatMenuModule } from '@angular/material/menu';
import { MatDialogModule, MatDialog } from '@angular/material/dialog';
import { MatDividerModule } from '@angular/material/divider';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { AnalyticsService, DetectionRule, RuleSeverity, RuleStatus } from '../../core/api/analytics.service';
import { RuleDetailDialogComponent } from './rule-detail-dialog.component';
import { RuleEditDialogComponent, RuleEditDialogData } from './rule-edit-dialog.component';
import { RuleTriggersDialogComponent } from './rule-triggers-dialog.component';

export interface AnalyticsRule {
  id: string;
  name: string;
  description: string;
  severity: 'critical' | 'high' | 'medium' | 'low' | 'informational';
  enabled: boolean;
  source: string;
  tactics: string[];
  techniques: string[];
  last_triggered: string | null;
  trigger_count: number;
  created_at: string;
  updated_at: string;
}

@Component({
  selector: 'app-analytics',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatCardModule,
    MatIconModule,
    MatButtonModule,
    MatTableModule,
    MatSlideToggleModule,
    MatChipsModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    MatProgressSpinnerModule,
    MatTooltipModule,
    MatMenuModule,
    MatDialogModule,
    MatDividerModule,
    MatSnackBarModule
  ],
  template: `
    <div class="analytics">
      <!-- Header -->
      <div class="page-header">
        <div class="header-content">
          <h1>Analytics Rules</h1>
          <p class="subtitle">View and manage detection rules for threat detection</p>
        </div>
        <div class="header-actions">
          <button mat-stroked-button (click)="refresh()">
            <mat-icon>refresh</mat-icon>
            Refresh
          </button>
          <button mat-flat-button color="primary" (click)="createRule()">
            <mat-icon>add</mat-icon>
            Create Rule
          </button>
        </div>
      </div>

      <!-- Stats Cards -->
      <div class="stats-row">
        <mat-card class="stat-card">
          <div class="stat-icon bg-info">
            <mat-icon>rule</mat-icon>
          </div>
          <div class="stat-content">
            <span class="stat-value">{{ totalRules() }}</span>
            <span class="stat-label">Total Rules</span>
          </div>
        </mat-card>

        <mat-card class="stat-card">
          <div class="stat-icon bg-success">
            <mat-icon>check_circle</mat-icon>
          </div>
          <div class="stat-content">
            <span class="stat-value">{{ enabledRules() }}</span>
            <span class="stat-label">Enabled</span>
          </div>
        </mat-card>

        <mat-card class="stat-card">
          <div class="stat-icon bg-warning">
            <mat-icon>notifications_active</mat-icon>
          </div>
          <div class="stat-content">
            <span class="stat-value">{{ totalTriggers() }}</span>
            <span class="stat-label">Triggers (24h)</span>
          </div>
        </mat-card>

        <mat-card class="stat-card">
          <div class="stat-icon bg-danger">
            <mat-icon>error</mat-icon>
          </div>
          <div class="stat-content">
            <span class="stat-value">{{ criticalRules() }}</span>
            <span class="stat-label">Critical Rules</span>
          </div>
        </mat-card>
      </div>

      <!-- Filters -->
      <mat-card class="filters-card">
        <div class="filters-row">
          <mat-form-field appearance="outline" class="search-field">
            <mat-label>Search rules</mat-label>
            <mat-icon matPrefix>search</mat-icon>
            <input matInput [(ngModel)]="searchQuery" (keyup)="filterRules()" placeholder="Search by name or description">
          </mat-form-field>

          <mat-form-field appearance="outline" class="filter-field">
            <mat-label>Severity</mat-label>
            <mat-select [(value)]="severityFilter" (selectionChange)="filterRules()">
              <mat-option value="">All</mat-option>
              <mat-option value="critical">Critical</mat-option>
              <mat-option value="high">High</mat-option>
              <mat-option value="medium">Medium</mat-option>
              <mat-option value="low">Low</mat-option>
              <mat-option value="informational">Info</mat-option>
            </mat-select>
          </mat-form-field>

          <mat-form-field appearance="outline" class="filter-field">
            <mat-label>Status</mat-label>
            <mat-select [(value)]="statusFilter" (selectionChange)="filterRules()">
              <mat-option value="">All</mat-option>
              <mat-option value="enabled">Enabled</mat-option>
              <mat-option value="disabled">Disabled</mat-option>
            </mat-select>
          </mat-form-field>

          <mat-form-field appearance="outline" class="filter-field">
            <mat-label>Source</mat-label>
            <mat-select [(value)]="sourceFilter" (selectionChange)="filterRules()">
              <mat-option value="">All</mat-option>
              <mat-option value="sigma">Sigma</mat-option>
              <mat-option value="elastic">Elastic</mat-option>
              <mat-option value="custom">Custom</mat-option>
            </mat-select>
          </mat-form-field>
        </div>
      </mat-card>

      <!-- Rules Table -->
      @if (isLoading()) {
        <div class="loading">
          <mat-spinner diameter="40"></mat-spinner>
        </div>
      } @else {
        <mat-card class="rules-card">
          <table mat-table [dataSource]="filteredRules()" class="rules-table">
            <ng-container matColumnDef="enabled">
              <th mat-header-cell *matHeaderCellDef>Status</th>
              <td mat-cell *matCellDef="let rule">
                <mat-slide-toggle [checked]="rule.enabled"
                                  (change)="toggleRule(rule)"
                                  color="primary">
                </mat-slide-toggle>
              </td>
            </ng-container>

            <ng-container matColumnDef="severity">
              <th mat-header-cell *matHeaderCellDef>Severity</th>
              <td mat-cell *matCellDef="let rule">
                <span class="severity-badge" [class]="'severity-' + rule.severity">
                  {{ rule.severity | uppercase }}
                </span>
              </td>
            </ng-container>

            <ng-container matColumnDef="name">
              <th mat-header-cell *matHeaderCellDef>Rule Name</th>
              <td mat-cell *matCellDef="let rule">
                <div class="rule-name-cell">
                  <span class="rule-name">{{ rule.name }}</span>
                  <span class="rule-description">{{ rule.description | slice:0:80 }}...</span>
                </div>
              </td>
            </ng-container>

            <ng-container matColumnDef="tactics">
              <th mat-header-cell *matHeaderCellDef>MITRE Tactics</th>
              <td mat-cell *matCellDef="let rule">
                <div class="tactics-list">
                  @for (tactic of rule.tactics.slice(0, 2); track tactic) {
                    <span class="tactic-badge">{{ tactic }}</span>
                  }
                  @if (rule.tactics.length > 2) {
                    <span class="more-badge">+{{ rule.tactics.length - 2 }}</span>
                  }
                </div>
              </td>
            </ng-container>

            <ng-container matColumnDef="source">
              <th mat-header-cell *matHeaderCellDef>Source</th>
              <td mat-cell *matCellDef="let rule">
                <span class="source-badge" [class]="'source-' + rule.source">
                  {{ rule.source }}
                </span>
              </td>
            </ng-container>

            <ng-container matColumnDef="triggers">
              <th mat-header-cell *matHeaderCellDef>Triggers</th>
              <td mat-cell *matCellDef="let rule">
                <div class="trigger-info">
                  <span class="trigger-count">{{ rule.trigger_count }}</span>
                  @if (rule.last_triggered) {
                    <span class="last-triggered">Last: {{ rule.last_triggered | date:'short' }}</span>
                  }
                </div>
              </td>
            </ng-container>

            <ng-container matColumnDef="actions">
              <th mat-header-cell *matHeaderCellDef></th>
              <td mat-cell *matCellDef="let rule">
                <button mat-icon-button [matMenuTriggerFor]="ruleMenu">
                  <mat-icon>more_vert</mat-icon>
                </button>
                <mat-menu #ruleMenu="matMenu">
                  <button mat-menu-item (click)="viewRule(rule)">
                    <mat-icon>visibility</mat-icon>
                    <span>View Details</span>
                  </button>
                  <button mat-menu-item (click)="editRule(rule)">
                    <mat-icon>edit</mat-icon>
                    <span>Edit Rule</span>
                  </button>
                  <button mat-menu-item (click)="duplicateRule(rule)">
                    <mat-icon>content_copy</mat-icon>
                    <span>Duplicate</span>
                  </button>
                  <button mat-menu-item (click)="viewTriggers(rule)">
                    <mat-icon>history</mat-icon>
                    <span>View Triggers</span>
                  </button>
                  <mat-divider></mat-divider>
                  <button mat-menu-item class="danger-item" (click)="deleteRule(rule)">
                    <mat-icon>delete</mat-icon>
                    <span>Delete</span>
                  </button>
                </mat-menu>
              </td>
            </ng-container>

            <tr mat-header-row *matHeaderRowDef="ruleColumns"></tr>
            <tr mat-row *matRowDef="let row; columns: ruleColumns;"
                [class.disabled-row]="!row.enabled"></tr>
          </table>
        </mat-card>
      }
    </div>
  `,
  styles: [`
    .analytics {
      max-width: 1400px;
      margin: 0 auto;
    }

    .page-header {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      margin-bottom: 24px;
    }

    .header-content h1 {
      font-size: 24px;
      font-weight: 600;
      margin: 0 0 4px 0;
    }

    .subtitle {
      color: var(--text-secondary);
      margin: 0;
    }

    .header-actions {
      display: flex;
      gap: 8px;
    }

    /* Stats Row */
    .stats-row {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
      gap: 16px;
      margin-bottom: 24px;
    }

    .stat-card {
      display: flex;
      align-items: center;
      gap: 16px;
      padding: 20px;
      background: var(--bg-card);
      border: 1px solid var(--border-color);
    }

    .stat-icon {
      width: 48px;
      height: 48px;
      border-radius: 12px;
      display: flex;
      align-items: center;
      justify-content: center;

      mat-icon {
        color: white;
        font-size: 24px;
        width: 24px;
        height: 24px;
      }

      &.bg-info { background: var(--info); }
      &.bg-success { background: var(--success); mat-icon { color: black; } }
      &.bg-warning { background: var(--warning); mat-icon { color: black; } }
      &.bg-danger { background: var(--danger); }
    }

    .stat-content {
      display: flex;
      flex-direction: column;
    }

    .stat-value {
      font-size: 28px;
      font-weight: 700;
      color: var(--text-primary);
    }

    .stat-label {
      font-size: 14px;
      color: var(--text-secondary);
    }

    /* Filters */
    .filters-card {
      padding: 16px;
      margin-bottom: 16px;
      background: var(--bg-card);
    }

    .filters-row {
      display: flex;
      gap: 16px;
      flex-wrap: wrap;
    }

    .search-field {
      flex: 1;
      min-width: 250px;
    }

    .filter-field {
      width: 150px;
    }

    /* Loading */
    .loading {
      display: flex;
      justify-content: center;
      padding: 48px;
    }

    /* Rules Table */
    .rules-card {
      background: var(--bg-card);
      border: 1px solid var(--border-color);
    }

    .rules-table {
      width: 100%;
      background: transparent;
    }

    .rule-name-cell {
      display: flex;
      flex-direction: column;
      gap: 4px;
    }

    .rule-name {
      font-weight: 500;
      color: var(--text-primary);
    }

    .rule-description {
      font-size: 12px;
      color: var(--text-secondary);
    }

    .severity-badge {
      display: inline-block;
      padding: 2px 8px;
      border-radius: 4px;
      font-size: 11px;
      font-weight: 600;

      &.severity-critical { background: var(--danger); color: white; }
      &.severity-high { background: #f97316; color: white; }
      &.severity-medium { background: var(--warning); color: black; }
      &.severity-low { background: var(--info); color: white; }
      &.severity-informational { background: var(--text-muted); color: white; }
    }

    .tactics-list {
      display: flex;
      flex-wrap: wrap;
      gap: 4px;
    }

    .tactic-badge {
      display: inline-block;
      padding: 2px 6px;
      border-radius: 4px;
      font-size: 10px;
      background: var(--bg-tertiary);
      color: var(--text-secondary);
    }

    .more-badge {
      display: inline-block;
      padding: 2px 6px;
      border-radius: 4px;
      font-size: 10px;
      background: var(--accent);
      color: white;
    }

    .source-badge {
      display: inline-block;
      padding: 2px 8px;
      border-radius: 4px;
      font-size: 11px;
      text-transform: capitalize;

      &.source-sigma { background: #7c3aed; color: white; }
      &.source-elastic { background: #059669; color: white; }
      &.source-custom { background: var(--accent); color: white; }
    }

    .trigger-info {
      display: flex;
      flex-direction: column;
      gap: 2px;
    }

    .trigger-count {
      font-weight: 600;
      color: var(--text-primary);
    }

    .last-triggered {
      font-size: 11px;
      color: var(--text-secondary);
    }

    .disabled-row {
      opacity: 0.5;
    }

    .danger-item {
      color: var(--danger);
    }
  `]
})
export class AnalyticsComponent implements OnInit {
  searchQuery = '';
  severityFilter = '';
  statusFilter = '';
  sourceFilter = '';

  isLoading = signal(true);
  rules = signal<AnalyticsRule[]>([]);
  filteredRules = signal<AnalyticsRule[]>([]);

  totalRules = signal(0);
  enabledRules = signal(0);
  totalTriggers = signal(0);
  criticalRules = signal(0);

  ruleColumns = ['enabled', 'severity', 'name', 'tactics', 'source', 'triggers', 'actions'];

  constructor(
    private dialog: MatDialog,
    private analyticsService: AnalyticsService,
    private snackBar: MatSnackBar
  ) {}

  ngOnInit(): void {
    this.loadRules();
    this.loadStats();
  }

  loadRules(): void {
    this.isLoading.set(true);

    const params: any = {};
    if (this.severityFilter) params.severity = this.severityFilter;
    if (this.statusFilter) params.status = this.statusFilter;
    if (this.searchQuery) params.search = this.searchQuery;

    this.analyticsService.listRules(params).subscribe({
      next: (response) => {
        const mappedRules = response.items.map(r => this.mapToAnalyticsRule(r));
        this.rules.set(mappedRules);
        this.filteredRules.set(mappedRules);
        this.totalRules.set(response.total);
        this.isLoading.set(false);
      },
      error: (err) => {
        console.error('Failed to load rules:', err);
        this.isLoading.set(false);
        this.snackBar.open('Failed to load rules', 'Dismiss', { duration: 3000 });
      }
    });
  }

  loadStats(): void {
    this.analyticsService.getStats().subscribe({
      next: (stats) => {
        this.totalRules.set(stats.total_rules);
        this.enabledRules.set(stats.by_status['enabled'] || 0);
        this.totalTriggers.set(stats.total_hits);
        this.criticalRules.set(stats.by_severity['critical'] || 0);
      },
      error: (err) => console.error('Failed to load stats:', err)
    });
  }

  mapToAnalyticsRule(rule: DetectionRule): AnalyticsRule {
    return {
      id: rule.id,
      name: rule.name,
      description: rule.description || '',
      severity: rule.severity as AnalyticsRule['severity'],
      enabled: rule.status === 'enabled',
      source: rule.category || rule.query_language,
      tactics: rule.mitre_tactics,
      techniques: rule.mitre_techniques,
      last_triggered: rule.last_run_at,
      trigger_count: rule.hit_count,
      created_at: rule.created_at,
      updated_at: rule.updated_at
    };
  }

  filterRules(): void {
    this.loadRules();
  }

  refresh(): void {
    this.loadRules();
    this.loadStats();
  }

  toggleRule(rule: AnalyticsRule): void {
    const action = rule.enabled
      ? this.analyticsService.disableRule(rule.id)
      : this.analyticsService.enableRule(rule.id);

    action.subscribe({
      next: (updated) => {
        rule.enabled = updated.status === 'enabled';
        this.rules.set([...this.rules()]);
        this.loadStats();
        this.snackBar.open(
          `Rule ${rule.enabled ? 'enabled' : 'disabled'}`,
          'Dismiss',
          { duration: 2000 }
        );
      },
      error: (err) => {
        console.error('Failed to toggle rule:', err);
        this.snackBar.open('Failed to update rule', 'Dismiss', { duration: 3000 });
      }
    });
  }

  createRule(): void {
    const dialogRef = this.dialog.open(RuleEditDialogComponent, {
      data: { mode: 'create' } as RuleEditDialogData,
      panelClass: 'dark-dialog'
    });

    dialogRef.afterClosed().subscribe(result => {
      if (result) {
        this.refresh();
        this.snackBar.open('Rule created successfully', 'Dismiss', { duration: 2000 });
      }
    });
  }

  viewRule(rule: AnalyticsRule): void {
    const dialogRef = this.dialog.open(RuleDetailDialogComponent, {
      data: rule,
      panelClass: 'dark-dialog'
    });

    dialogRef.afterClosed().subscribe(result => {
      if (result?.action === 'edit') {
        this.editRule(result.rule);
      }
    });
  }

  editRule(rule: AnalyticsRule): void {
    const dialogRef = this.dialog.open(RuleEditDialogComponent, {
      data: { rule, mode: 'edit' } as RuleEditDialogData,
      panelClass: 'dark-dialog'
    });

    dialogRef.afterClosed().subscribe(result => {
      if (result) {
        this.refresh();
        this.snackBar.open('Rule updated successfully', 'Dismiss', { duration: 2000 });
      }
    });
  }

  duplicateRule(rule: AnalyticsRule): void {
    const dialogRef = this.dialog.open(RuleEditDialogComponent, {
      data: { rule, mode: 'duplicate' } as RuleEditDialogData,
      panelClass: 'dark-dialog'
    });

    dialogRef.afterClosed().subscribe(result => {
      if (result) {
        this.refresh();
        this.snackBar.open('Rule duplicated successfully', 'Dismiss', { duration: 2000 });
      }
    });
  }

  viewTriggers(rule: AnalyticsRule): void {
    this.dialog.open(RuleTriggersDialogComponent, {
      data: rule,
      panelClass: 'dark-dialog'
    });
  }

  deleteRule(rule: AnalyticsRule): void {
    if (confirm(`Are you sure you want to delete "${rule.name}"?`)) {
      this.analyticsService.deleteRule(rule.id).subscribe({
        next: () => {
          this.rules.set(this.rules().filter(r => r.id !== rule.id));
          this.filteredRules.set(this.filteredRules().filter(r => r.id !== rule.id));
          this.loadStats();
          this.snackBar.open('Rule deleted', 'Dismiss', { duration: 2000 });
        },
        error: (err) => {
          console.error('Failed to delete rule:', err);
          this.snackBar.open('Failed to delete rule', 'Dismiss', { duration: 3000 });
        }
      });
    }
  }
}
