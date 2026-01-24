import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatCardModule } from '@angular/material/card';
import { MatIconModule } from '@angular/material/icon';
import { MatButtonModule } from '@angular/material/button';
import { MatTabsModule } from '@angular/material/tabs';
import { MatTableModule } from '@angular/material/table';
import { MatPaginatorModule, PageEvent } from '@angular/material/paginator';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatChipsModule } from '@angular/material/chips';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatMenuModule } from '@angular/material/menu';
import { EnrichmentService, ThreatReport, ThreatActor } from '../../core/api/enrichment.service';
import { IOC } from '../../shared/models';

@Component({
  selector: 'app-threat-intel',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatCardModule,
    MatIconModule,
    MatButtonModule,
    MatTabsModule,
    MatTableModule,
    MatPaginatorModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    MatChipsModule,
    MatProgressSpinnerModule,
    MatTooltipModule,
    MatMenuModule
  ],
  template: `
    <div class="threat-intel">
      <!-- Header -->
      <div class="page-header">
        <div class="header-content">
          <h1>Threat Intelligence</h1>
          <p class="subtitle">Browse indicators, threat actors, and campaigns from OpenCTI</p>
        </div>
        <div class="header-actions">
          <button mat-stroked-button (click)="refresh()">
            <mat-icon>refresh</mat-icon>
            Refresh
          </button>
        </div>
      </div>

      <!-- Search Bar -->
      <mat-card class="search-card">
        <div class="search-container">
          <mat-icon>search</mat-icon>
          <input type="text"
                 placeholder="Search indicators, threat actors, campaigns..."
                 [(ngModel)]="searchQuery"
                 (keyup.enter)="search()">
          <button mat-flat-button color="primary" (click)="search()" [disabled]="!searchQuery">
            Search
          </button>
        </div>
      </mat-card>

      <!-- Tabs -->
      <mat-tab-group animationDuration="200ms" (selectedTabChange)="onTabChange($event.index)">
        <!-- Indicators Tab -->
        <mat-tab>
          <ng-template mat-tab-label>
            <mat-icon>security</mat-icon>
            <span>Indicators ({{ totalIndicators() }})</span>
          </ng-template>

          <div class="tab-content">
            <!-- Filters -->
            <div class="filters-row">
              <mat-form-field appearance="outline" class="filter-field">
                <mat-label>Type</mat-label>
                <mat-select [(value)]="indicatorTypeFilter" (selectionChange)="loadIndicators()">
                  <mat-option value="">All Types</mat-option>
                  <mat-option value="ip">IP Address</mat-option>
                  <mat-option value="domain">Domain</mat-option>
                  <mat-option value="url">URL</mat-option>
                  <mat-option value="hash">File Hash</mat-option>
                  <mat-option value="email">Email</mat-option>
                </mat-select>
              </mat-form-field>

              <mat-form-field appearance="outline" class="filter-field">
                <mat-label>Min Confidence</mat-label>
                <mat-select [(value)]="minConfidenceFilter" (selectionChange)="loadIndicators()">
                  <mat-option [value]="0">Any</mat-option>
                  <mat-option [value]="25">25%+</mat-option>
                  <mat-option [value]="50">50%+</mat-option>
                  <mat-option [value]="75">75%+</mat-option>
                  <mat-option [value]="90">90%+</mat-option>
                </mat-select>
              </mat-form-field>
            </div>

            @if (isLoadingIndicators()) {
              <div class="loading">
                <mat-spinner diameter="40"></mat-spinner>
              </div>
            } @else {
              <table mat-table [dataSource]="indicators()" class="indicators-table">
                <ng-container matColumnDef="value">
                  <th mat-header-cell *matHeaderCellDef>Indicator</th>
                  <td mat-cell *matCellDef="let ioc">
                    <div class="indicator-cell">
                      <mat-icon class="type-icon">{{ getIndicatorIcon(ioc.indicator_type) }}</mat-icon>
                      <span class="indicator-value">{{ ioc.value }}</span>
                    </div>
                  </td>
                </ng-container>

                <ng-container matColumnDef="type">
                  <th mat-header-cell *matHeaderCellDef>Type</th>
                  <td mat-cell *matCellDef="let ioc">
                    <span class="type-badge">{{ ioc.indicator_type | uppercase }}</span>
                  </td>
                </ng-container>

                <ng-container matColumnDef="confidence">
                  <th mat-header-cell *matHeaderCellDef>Confidence</th>
                  <td mat-cell *matCellDef="let ioc">
                    <div class="confidence-bar">
                      <div class="confidence-fill" [style.width.%]="ioc.confidence"
                           [class.high]="ioc.confidence >= 75"
                           [class.medium]="ioc.confidence >= 50 && ioc.confidence < 75"
                           [class.low]="ioc.confidence < 50"></div>
                    </div>
                    <span class="confidence-text">{{ ioc.confidence }}%</span>
                  </td>
                </ng-container>

                <ng-container matColumnDef="source">
                  <th mat-header-cell *matHeaderCellDef>Source</th>
                  <td mat-cell *matCellDef="let ioc">{{ ioc.source }}</td>
                </ng-container>

                <ng-container matColumnDef="first_seen">
                  <th mat-header-cell *matHeaderCellDef>First Seen</th>
                  <td mat-cell *matCellDef="let ioc">{{ ioc.first_seen | date:'mediumDate' }}</td>
                </ng-container>

                <ng-container matColumnDef="actions">
                  <th mat-header-cell *matHeaderCellDef></th>
                  <td mat-cell *matCellDef="let ioc">
                    <button mat-icon-button [matMenuTriggerFor]="iocMenu">
                      <mat-icon>more_vert</mat-icon>
                    </button>
                    <mat-menu #iocMenu="matMenu">
                      <button mat-menu-item (click)="enrichIndicator(ioc.value)">
                        <mat-icon>search</mat-icon>
                        <span>Enrich</span>
                      </button>
                      <button mat-menu-item (click)="copyToClipboard(ioc.value)">
                        <mat-icon>content_copy</mat-icon>
                        <span>Copy</span>
                      </button>
                      <button mat-menu-item (click)="huntForIndicator(ioc.value)">
                        <mat-icon>manage_search</mat-icon>
                        <span>Hunt</span>
                      </button>
                    </mat-menu>
                  </td>
                </ng-container>

                <tr mat-header-row *matHeaderRowDef="indicatorColumns"></tr>
                <tr mat-row *matRowDef="let row; columns: indicatorColumns;"></tr>
              </table>

              <mat-paginator [length]="totalIndicators()"
                             [pageSize]="20"
                             [pageSizeOptions]="[10, 20, 50]"
                             (page)="onIndicatorPageChange($event)">
              </mat-paginator>
            }
          </div>
        </mat-tab>

        <!-- Threat Actors Tab -->
        <mat-tab>
          <ng-template mat-tab-label>
            <mat-icon>groups</mat-icon>
            <span>Threat Actors ({{ threatActors().length }})</span>
          </ng-template>

          <div class="tab-content">
            @if (isLoadingActors()) {
              <div class="loading">
                <mat-spinner diameter="40"></mat-spinner>
              </div>
            } @else if (threatActors().length === 0) {
              <div class="empty-state">
                <mat-icon>groups</mat-icon>
                <h3>No Threat Actors Found</h3>
                <p>Search for threat intelligence to discover known threat actors</p>
              </div>
            } @else {
              <div class="actors-grid">
                @for (actor of threatActors(); track actor.id) {
                  <mat-card class="actor-card">
                    <mat-card-header>
                      <mat-icon mat-card-avatar class="actor-icon">person_search</mat-icon>
                      <mat-card-title>{{ actor.name }}</mat-card-title>
                      @if (actor.aliases.length > 0) {
                        <mat-card-subtitle>
                          AKA: {{ actor.aliases.slice(0, 3).join(', ') }}
                          @if (actor.aliases.length > 3) {
                            +{{ actor.aliases.length - 3 }} more
                          }
                        </mat-card-subtitle>
                      }
                    </mat-card-header>
                    <mat-card-content>
                      <p class="actor-description">{{ actor.description | slice:0:200 }}...</p>
                      <div class="actor-meta">
                        @if (actor.motivation) {
                          <div class="meta-item">
                            <span class="meta-label">Motivation</span>
                            <span class="meta-value">{{ actor.motivation }}</span>
                          </div>
                        }
                        @if (actor.sophistication) {
                          <div class="meta-item">
                            <span class="meta-label">Sophistication</span>
                            <span class="meta-value">{{ actor.sophistication }}</span>
                          </div>
                        }
                        @if (actor.first_seen) {
                          <div class="meta-item">
                            <span class="meta-label">Active Since</span>
                            <span class="meta-value">{{ actor.first_seen | date:'mediumDate' }}</span>
                          </div>
                        }
                      </div>
                    </mat-card-content>
                    <mat-card-actions align="end">
                      <button mat-button color="primary" (click)="viewActorDetails(actor)">
                        View Details
                      </button>
                    </mat-card-actions>
                  </mat-card>
                }
              </div>
            }
          </div>
        </mat-tab>

        <!-- Campaigns Tab -->
        <mat-tab>
          <ng-template mat-tab-label>
            <mat-icon>campaign</mat-icon>
            <span>Reports ({{ threatReports().length }})</span>
          </ng-template>

          <div class="tab-content">
            @if (isLoadingReports()) {
              <div class="loading">
                <mat-spinner diameter="40"></mat-spinner>
              </div>
            } @else if (threatReports().length === 0) {
              <div class="empty-state">
                <mat-icon>article</mat-icon>
                <h3>No Reports Found</h3>
                <p>Search for threat intelligence to discover threat reports</p>
              </div>
            } @else {
              <div class="reports-list">
                @for (report of threatReports(); track report.id) {
                  <mat-card class="report-card">
                    <div class="report-header">
                      <mat-icon>article</mat-icon>
                      <div class="report-info">
                        <h3>{{ report.name }}</h3>
                        <span class="report-source">{{ report.source }} - {{ report.published | date:'mediumDate' }}</span>
                      </div>
                    </div>
                    <p class="report-description">{{ report.description | slice:0:300 }}...</p>
                    @if (report.tags.length > 0) {
                      <div class="report-tags">
                        @for (tag of report.tags.slice(0, 5); track tag) {
                          <mat-chip>{{ tag }}</mat-chip>
                        }
                      </div>
                    }
                    <mat-card-actions align="end">
                      @if (report.url) {
                        <a mat-button color="primary" [href]="report.url" target="_blank">
                          <mat-icon>open_in_new</mat-icon>
                          View Report
                        </a>
                      }
                    </mat-card-actions>
                  </mat-card>
                }
              </div>
            }
          </div>
        </mat-tab>
      </mat-tab-group>
    </div>
  `,
  styles: [`
    .threat-intel {
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

    .search-card {
      padding: 16px;
      margin-bottom: 24px;
      background: var(--bg-card);
    }

    .search-container {
      display: flex;
      align-items: center;
      gap: 12px;

      mat-icon {
        color: var(--text-secondary);
      }

      input {
        flex: 1;
        background: transparent;
        border: none;
        outline: none;
        font-size: 16px;
        color: var(--text-primary);

        &::placeholder {
          color: var(--text-muted);
        }
      }
    }

    .tab-content {
      padding: 24px 0;
    }

    .filters-row {
      display: flex;
      gap: 16px;
      margin-bottom: 16px;
    }

    .filter-field {
      width: 200px;
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
      padding: 64px;
      color: var(--text-muted);

      mat-icon {
        font-size: 64px;
        width: 64px;
        height: 64px;
        margin-bottom: 16px;
      }

      h3 {
        margin: 0 0 8px 0;
        color: var(--text-primary);
      }

      p {
        margin: 0;
      }
    }

    /* Indicators Table */
    .indicators-table {
      width: 100%;
      background: transparent;
    }

    .indicator-cell {
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .type-icon {
      font-size: 18px;
      width: 18px;
      height: 18px;
      color: var(--accent);
    }

    .indicator-value {
      font-family: monospace;
      font-size: 13px;
    }

    .type-badge {
      display: inline-block;
      padding: 2px 8px;
      border-radius: 4px;
      font-size: 11px;
      font-weight: 500;
      background: var(--bg-tertiary);
      color: var(--text-secondary);
    }

    .confidence-bar {
      width: 60px;
      height: 6px;
      background: var(--bg-tertiary);
      border-radius: 3px;
      overflow: hidden;
      display: inline-block;
      margin-right: 8px;
    }

    .confidence-fill {
      height: 100%;
      border-radius: 3px;

      &.high { background: var(--success); }
      &.medium { background: var(--warning); }
      &.low { background: var(--danger); }
    }

    .confidence-text {
      font-size: 12px;
      color: var(--text-secondary);
    }

    /* Actors Grid */
    .actors-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
      gap: 16px;
    }

    .actor-card {
      background: var(--bg-card);
      border: 1px solid var(--border-color);
    }

    .actor-icon {
      color: var(--accent);
      background: var(--bg-tertiary);
      border-radius: 50%;
      padding: 8px;
    }

    .actor-description {
      color: var(--text-secondary);
      font-size: 14px;
      line-height: 1.5;
      margin-bottom: 16px;
    }

    .actor-meta {
      display: flex;
      flex-wrap: wrap;
      gap: 16px;
    }

    .meta-item {
      display: flex;
      flex-direction: column;
      gap: 2px;
    }

    .meta-label {
      font-size: 11px;
      text-transform: uppercase;
      color: var(--text-muted);
    }

    .meta-value {
      font-size: 13px;
      color: var(--text-primary);
    }

    /* Reports List */
    .reports-list {
      display: flex;
      flex-direction: column;
      gap: 16px;
    }

    .report-card {
      padding: 20px;
      background: var(--bg-card);
      border: 1px solid var(--border-color);
    }

    .report-header {
      display: flex;
      align-items: flex-start;
      gap: 16px;
      margin-bottom: 12px;

      mat-icon {
        font-size: 32px;
        width: 32px;
        height: 32px;
        color: var(--accent);
      }
    }

    .report-info h3 {
      margin: 0 0 4px 0;
      font-size: 16px;
      font-weight: 500;
    }

    .report-source {
      font-size: 12px;
      color: var(--text-secondary);
    }

    .report-description {
      color: var(--text-secondary);
      font-size: 14px;
      line-height: 1.5;
      margin: 0 0 12px 0;
    }

    .report-tags {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-bottom: 8px;
    }
  `]
})
export class ThreatIntelComponent implements OnInit {
  searchQuery = '';
  indicatorTypeFilter = '';
  minConfidenceFilter = 0;

  isLoadingIndicators = signal(false);
  isLoadingActors = signal(false);
  isLoadingReports = signal(false);

  indicators = signal<IOC[]>([]);
  totalIndicators = signal(0);
  threatActors = signal<ThreatActor[]>([]);
  threatReports = signal<ThreatReport[]>([]);

  indicatorColumns = ['value', 'type', 'confidence', 'source', 'first_seen', 'actions'];

  constructor(private enrichmentService: EnrichmentService) {}

  ngOnInit(): void {
    this.loadIndicators();
  }

  loadIndicators(page = 1, pageSize = 20): void {
    this.isLoadingIndicators.set(true);
    this.enrichmentService.getIOCs({
      indicator_type: this.indicatorTypeFilter || undefined,
      min_confidence: this.minConfidenceFilter || undefined,
      page,
      page_size: pageSize
    }).subscribe({
      next: (response) => {
        this.indicators.set(response.items);
        this.totalIndicators.set(response.total);
        this.isLoadingIndicators.set(false);
      },
      error: () => this.isLoadingIndicators.set(false)
    });
  }

  search(): void {
    if (!this.searchQuery.trim()) return;

    this.isLoadingIndicators.set(true);
    this.isLoadingActors.set(true);
    this.isLoadingReports.set(true);

    this.enrichmentService.searchThreatIntel(this.searchQuery).subscribe({
      next: (results) => {
        this.indicators.set(results.indicators);
        this.totalIndicators.set(results.indicators.length);
        this.threatActors.set(results.actors);
        this.threatReports.set(results.reports);
        this.isLoadingIndicators.set(false);
        this.isLoadingActors.set(false);
        this.isLoadingReports.set(false);
      },
      error: () => {
        this.isLoadingIndicators.set(false);
        this.isLoadingActors.set(false);
        this.isLoadingReports.set(false);
      }
    });
  }

  refresh(): void {
    this.loadIndicators();
  }

  onTabChange(index: number): void {
    // Tabs: 0=Indicators, 1=Actors, 2=Reports
    // Data is already loaded from search, no additional load needed
  }

  onIndicatorPageChange(event: PageEvent): void {
    this.loadIndicators(event.pageIndex + 1, event.pageSize);
  }

  getIndicatorIcon(type: string): string {
    const icons: Record<string, string> = {
      ip: 'router',
      domain: 'dns',
      url: 'link',
      hash: 'fingerprint',
      email: 'email'
    };
    return icons[type] || 'security';
  }

  enrichIndicator(value: string): void {
    this.enrichmentService.enrich(value).subscribe({
      next: (result) => {
        console.log('Enrichment result:', result);
        // Could open a dialog with enrichment details
      }
    });
  }

  copyToClipboard(value: string): void {
    navigator.clipboard.writeText(value);
  }

  huntForIndicator(value: string): void {
    // Navigate to hunting console with indicator
    window.location.href = `/hunting?q=${encodeURIComponent(value)}`;
  }

  viewActorDetails(actor: ThreatActor): void {
    // Could open a dialog with full actor details
    console.log('View actor:', actor);
  }
}
