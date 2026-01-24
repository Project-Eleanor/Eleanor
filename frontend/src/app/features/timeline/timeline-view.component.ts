import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute } from '@angular/router';
import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatDatepickerModule } from '@angular/material/datepicker';
import { MatNativeDateModule } from '@angular/material/core';
import { MatChipsModule } from '@angular/material/chips';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatTooltipModule } from '@angular/material/tooltip';
import { CaseService } from '../../core/api/case.service';
import { TimelineEvent } from '../../shared/models';

@Component({
  selector: 'app-timeline-view',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatCardModule,
    MatButtonModule,
    MatIconModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    MatDatepickerModule,
    MatNativeDateModule,
    MatChipsModule,
    MatProgressSpinnerModule,
    MatTooltipModule
  ],
  template: `
    <div class="timeline-view">
      <div class="page-header">
        <h1>Timeline Analysis</h1>
        <div class="header-actions">
          <button mat-stroked-button>
            <mat-icon>file_download</mat-icon>
            Export
          </button>
          <button mat-flat-button color="accent">
            <mat-icon>add</mat-icon>
            Add Event
          </button>
        </div>
      </div>

      <!-- Filters -->
      <mat-card class="filter-card">
        <div class="filters">
          <mat-form-field appearance="outline">
            <mat-label>Case</mat-label>
            <mat-select [(ngModel)]="selectedCaseId" (selectionChange)="loadTimeline()">
              <mat-option [value]="null">All Cases</mat-option>
              @for (c of cases(); track c.id) {
                <mat-option [value]="c.id">{{ c.case_number }}</mat-option>
              }
            </mat-select>
          </mat-form-field>

          <mat-form-field appearance="outline">
            <mat-label>Date Range</mat-label>
            <mat-date-range-input [rangePicker]="picker">
              <input matStartDate placeholder="Start" [(ngModel)]="startDate">
              <input matEndDate placeholder="End" [(ngModel)]="endDate">
            </mat-date-range-input>
            <mat-datepicker-toggle matSuffix [for]="picker"></mat-datepicker-toggle>
            <mat-date-range-picker #picker></mat-date-range-picker>
          </mat-form-field>

          <mat-form-field appearance="outline">
            <mat-label>Category</mat-label>
            <mat-select [(ngModel)]="categoryFilter" multiple>
              <mat-option value="process">Process</mat-option>
              <mat-option value="network">Network</mat-option>
              <mat-option value="file">File</mat-option>
              <mat-option value="authentication">Authentication</mat-option>
              <mat-option value="persistence">Persistence</mat-option>
            </mat-select>
          </mat-form-field>

          <button mat-flat-button color="accent" (click)="loadTimeline()">
            <mat-icon>search</mat-icon>
            Filter
          </button>
        </div>
      </mat-card>

      <!-- Timeline -->
      @if (isLoading()) {
        <div class="loading">
          <mat-spinner diameter="40"></mat-spinner>
        </div>
      } @else if (events().length === 0) {
        <div class="empty-state">
          <mat-icon>timeline</mat-icon>
          <h3>No Timeline Events</h3>
          <p>Select a case or adjust filters to view timeline events</p>
        </div>
      } @else {
        <div class="timeline-container">
          <!-- Timeline Chart Area -->
          <div class="timeline-chart">
            <div class="chart-header">
              <span class="range-label">
                {{ getTimeRange() }}
              </span>
              <div class="zoom-controls">
                <button mat-icon-button (click)="zoomIn()">
                  <mat-icon>zoom_in</mat-icon>
                </button>
                <button mat-icon-button (click)="zoomOut()">
                  <mat-icon>zoom_out</mat-icon>
                </button>
              </div>
            </div>

            <div class="chart-area">
              <!-- Simple timeline visualization -->
              <div class="timeline-track">
                @for (event of events(); track event.id) {
                  <div class="event-marker"
                       [class]="'category-' + event.category"
                       [style.left.%]="getEventPosition(event)"
                       [matTooltip]="event.title"
                       (click)="selectEvent(event)">
                  </div>
                }
              </div>
            </div>
          </div>

          <!-- Event List -->
          <div class="event-list">
            @for (event of events(); track event.id) {
              <mat-card class="event-card"
                        [class.selected]="selectedEvent()?.id === event.id"
                        (click)="selectEvent(event)">
                <div class="event-time">
                  {{ event.timestamp | date:'medium' }}
                </div>
                <div class="event-content">
                  <div class="event-header">
                    <h4>{{ event.title }}</h4>
                    @if (event.category) {
                      <mat-chip class="mini-chip" [class]="'category-' + event.category">
                        {{ event.category }}
                      </mat-chip>
                    }
                  </div>
                  @if (event.description) {
                    <p class="event-description">{{ event.description }}</p>
                  }
                  @if (event.source) {
                    <span class="event-source">Source: {{ event.source }}</span>
                  }
                </div>
              </mat-card>
            }
          </div>
        </div>
      }

      <!-- Event Detail Panel -->
      @if (selectedEvent()) {
        <div class="detail-panel">
          <div class="panel-header">
            <h3>Event Details</h3>
            <button mat-icon-button (click)="clearSelection()">
              <mat-icon>close</mat-icon>
            </button>
          </div>
          <div class="panel-content">
            <div class="detail-row">
              <span class="label">Timestamp</span>
              <span class="value">{{ selectedEvent()!.timestamp | date:'full' }}</span>
            </div>
            <div class="detail-row">
              <span class="label">Title</span>
              <span class="value">{{ selectedEvent()!.title }}</span>
            </div>
            @if (selectedEvent()!.description) {
              <div class="detail-row">
                <span class="label">Description</span>
                <span class="value">{{ selectedEvent()!.description }}</span>
              </div>
            }
            @if (selectedEvent()!.category) {
              <div class="detail-row">
                <span class="label">Category</span>
                <span class="value">{{ selectedEvent()!.category }}</span>
              </div>
            }
            @if (selectedEvent()!.source) {
              <div class="detail-row">
                <span class="label">Source</span>
                <span class="value">{{ selectedEvent()!.source }}</span>
              </div>
            }

            @if (getEntityKeys(selectedEvent()!.entities).length > 0) {
              <div class="entities-section">
                <h4>Related Entities</h4>
                @for (entry of getEntityEntries(selectedEvent()!.entities); track entry[0]) {
                  <div class="entity-item">
                    <span class="entity-type">{{ entry[0] }}</span>
                    <span class="entity-value">{{ entry[1] }}</span>
                  </div>
                }
              </div>
            }

            @if (selectedEvent()!.tags.length > 0) {
              <div class="tags-section">
                <h4>Tags</h4>
                <div class="tags">
                  @for (tag of selectedEvent()!.tags; track tag) {
                    <mat-chip>{{ tag }}</mat-chip>
                  }
                </div>
              </div>
            }
          </div>
        </div>
      }
    </div>
  `,
  styles: [`
    .timeline-view {
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
        margin: 0;
      }
    }

    .header-actions {
      display: flex;
      gap: 8px;
    }

    .filter-card {
      margin-bottom: 16px;
      background: var(--bg-card);
    }

    .filters {
      display: flex;
      gap: 16px;
      align-items: center;
      flex-wrap: wrap;
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
      justify-content: center;
      padding: 64px;
      color: var(--text-muted);
      text-align: center;

      mat-icon {
        font-size: 64px;
        width: 64px;
        height: 64px;
        margin-bottom: 16px;
      }

      h3 {
        margin: 0 0 8px;
        color: var(--text-primary);
      }
    }

    .timeline-container {
      flex: 1;
      display: flex;
      flex-direction: column;
      min-height: 0;
    }

    .timeline-chart {
      background: var(--bg-card);
      border: 1px solid var(--border-color);
      border-radius: 8px;
      padding: 16px;
      margin-bottom: 16px;
    }

    .chart-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 16px;
    }

    .range-label {
      font-size: 14px;
      color: var(--text-secondary);
    }

    .chart-area {
      height: 60px;
      background: var(--bg-surface);
      border-radius: 4px;
      position: relative;
    }

    .timeline-track {
      position: absolute;
      top: 50%;
      left: 16px;
      right: 16px;
      height: 4px;
      background: var(--border-color);
      transform: translateY(-50%);
    }

    .event-marker {
      position: absolute;
      top: -8px;
      width: 20px;
      height: 20px;
      border-radius: 50%;
      background: var(--accent);
      cursor: pointer;
      transform: translateX(-50%);
      transition: transform 0.15s ease;

      &:hover {
        transform: translateX(-50%) scale(1.2);
      }

      &.category-process { background: var(--info); }
      &.category-network { background: var(--warning); }
      &.category-file { background: var(--success); }
      &.category-authentication { background: var(--accent); }
      &.category-persistence { background: var(--danger); }
    }

    .event-list {
      flex: 1;
      overflow-y: auto;
      display: flex;
      flex-direction: column;
      gap: 8px;
    }

    .event-card {
      padding: 12px 16px;
      background: var(--bg-card);
      cursor: pointer;
      display: flex;
      gap: 16px;

      &:hover {
        border-color: var(--accent);
      }

      &.selected {
        border-color: var(--accent);
        background: rgba(233, 69, 96, 0.1);
      }
    }

    .event-time {
      font-size: 12px;
      color: var(--text-secondary);
      white-space: nowrap;
      min-width: 150px;
    }

    .event-content {
      flex: 1;
    }

    .event-header {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 4px;

      h4 {
        margin: 0;
        font-size: 14px;
        font-weight: 500;
      }
    }

    .mini-chip {
      font-size: 10px;
      min-height: 20px !important;

      &.category-process { background: var(--info) !important; }
      &.category-network { background: var(--warning) !important; color: black !important; }
      &.category-file { background: var(--success) !important; color: black !important; }
      &.category-authentication { background: var(--accent) !important; }
      &.category-persistence { background: var(--danger) !important; }
    }

    .event-description {
      margin: 0;
      font-size: 13px;
      color: var(--text-secondary);
    }

    .event-source {
      font-size: 11px;
      color: var(--text-muted);
    }

    .detail-panel {
      position: fixed;
      top: 0;
      right: 0;
      width: 400px;
      height: 100vh;
      background: var(--bg-card);
      border-left: 1px solid var(--border-color);
      display: flex;
      flex-direction: column;
      z-index: 1000;
      box-shadow: -4px 0 16px rgba(0, 0, 0, 0.3);
    }

    .panel-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 16px;
      border-bottom: 1px solid var(--border-color);

      h3 {
        margin: 0;
      }
    }

    .panel-content {
      flex: 1;
      overflow-y: auto;
      padding: 16px;
    }

    .detail-row {
      margin-bottom: 16px;

      .label {
        display: block;
        font-size: 11px;
        color: var(--text-muted);
        text-transform: uppercase;
        margin-bottom: 4px;
      }

      .value {
        font-size: 14px;
      }
    }

    .entities-section, .tags-section {
      margin-top: 24px;

      h4 {
        font-size: 12px;
        color: var(--text-secondary);
        margin-bottom: 8px;
      }
    }

    .entity-item {
      display: flex;
      justify-content: space-between;
      padding: 8px 0;
      border-bottom: 1px solid var(--border-color);

      .entity-type {
        color: var(--text-secondary);
        font-size: 12px;
      }

      .entity-value {
        font-family: monospace;
        font-size: 12px;
      }
    }

    .tags {
      display: flex;
      flex-wrap: wrap;
      gap: 4px;
    }
  `]
})
export class TimelineViewComponent implements OnInit {
  events = signal<TimelineEvent[]>([]);
  cases = signal<{ id: string; case_number: string }[]>([]);
  isLoading = signal(false);
  selectedEvent = signal<TimelineEvent | null>(null);

  selectedCaseId: string | null = null;
  startDate: Date | null = null;
  endDate: Date | null = null;
  categoryFilter: string[] = [];

  constructor(
    private route: ActivatedRoute,
    private caseService: CaseService
  ) {}

  ngOnInit(): void {
    const caseId = this.route.snapshot.queryParams['case'];
    if (caseId) {
      this.selectedCaseId = caseId;
      this.loadTimeline();
    }

    this.loadCases();
  }

  private loadCases(): void {
    this.caseService.list({ page_size: 100 }).subscribe({
      next: (response) => {
        this.cases.set(response.items.map(c => ({ id: c.id, case_number: c.case_number })));
      }
    });
  }

  loadTimeline(): void {
    if (!this.selectedCaseId) {
      this.events.set([]);
      return;
    }

    this.isLoading.set(true);
    this.caseService.getTimeline(this.selectedCaseId).subscribe({
      next: (events) => {
        this.events.set(events);
        this.isLoading.set(false);
      },
      error: () => this.isLoading.set(false)
    });
  }

  selectEvent(event: TimelineEvent): void {
    this.selectedEvent.set(event);
  }

  clearSelection(): void {
    this.selectedEvent.set(null);
  }

  getEventPosition(event: TimelineEvent): number {
    const events = this.events();
    if (events.length <= 1) return 50;

    const timestamps = events.map(e => new Date(e.timestamp).getTime());
    const min = Math.min(...timestamps);
    const max = Math.max(...timestamps);
    const current = new Date(event.timestamp).getTime();

    return ((current - min) / (max - min)) * 100;
  }

  getTimeRange(): string {
    const events = this.events();
    if (events.length === 0) return 'No events';

    const timestamps = events.map(e => new Date(e.timestamp));
    const min = new Date(Math.min(...timestamps.map(d => d.getTime())));
    const max = new Date(Math.max(...timestamps.map(d => d.getTime())));

    return `${min.toLocaleDateString()} - ${max.toLocaleDateString()}`;
  }

  getEntityEntries(entities: Record<string, unknown>): [string, string][] {
    return Object.entries(entities).map(([k, v]) => [k, String(v)]);
  }

  getEntityKeys(entities: Record<string, unknown>): string[] {
    return Object.keys(entities);
  }

  zoomIn(): void {}
  zoomOut(): void {}
}
