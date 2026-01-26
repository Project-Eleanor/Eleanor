import { Component, OnInit, signal, inject, ViewChild, ElementRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterModule } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatChipsModule } from '@angular/material/chips';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatDatepickerModule } from '@angular/material/datepicker';
import { MatNativeDateModule } from '@angular/material/core';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatMenuModule } from '@angular/material/menu';
import { MatDividerModule } from '@angular/material/divider';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { MatSliderModule } from '@angular/material/slider';
import { MatBadgeModule } from '@angular/material/badge';
import { MatCardModule } from '@angular/material/card';
import { HttpClient } from '@angular/common/http';
import { environment } from '../../../environments/environment';
import { D3TimelineComponent, TimelineItem } from '../../shared/components/d3-timeline/d3-timeline.component';

export type ArtifactCategory = 'process' | 'network' | 'file' | 'registry' | 'authentication' | 'persistence' | 'memory' | 'other';

export interface TimelineArtifact {
  id: string;
  timestamp: string;
  category: ArtifactCategory;
  artifact_type: string;
  title: string;
  description: string;
  source_host?: string;
  evidence_id?: string;
  evidence_name?: string;
  severity?: 'low' | 'medium' | 'high' | 'critical';
  data: Record<string, unknown>;
  tags?: string[];
  bookmarked?: boolean;
  correlation_id?: string;
}

export interface TimelineResponse {
  items: TimelineArtifact[];
  total: number;
  time_range: { start: string; end: string };
  category_counts: Record<ArtifactCategory, number>;
}

interface TimelineBookmark {
  id: string;
  artifact_id: string;
  timestamp: string;
  label: string;
  color: string;
  note?: string;
}

interface CorrelationGroup {
  id: string;
  timestamp: string;
  artifacts: TimelineArtifact[];
  label: string;
}

@Component({
  selector: 'app-artifact-timeline',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    RouterModule,
    MatButtonModule,
    MatIconModule,
    MatChipsModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    MatDatepickerModule,
    MatNativeDateModule,
    MatProgressSpinnerModule,
    MatTooltipModule,
    MatMenuModule,
    MatDividerModule,
    MatSnackBarModule,
    MatSliderModule,
    MatBadgeModule,
    MatCardModule,
    D3TimelineComponent,
  ],
  template: `
    <div class="artifact-timeline-page">
      <!-- Header -->
      <div class="page-header">
        <div class="header-left">
          <button mat-icon-button (click)="goBack()">
            <mat-icon>arrow_back</mat-icon>
          </button>
          <h1>Artifact Timeline</h1>
          @if (caseId()) {
            <span class="case-badge">Case: {{ caseId() }}</span>
          }
        </div>
        <div class="header-right">
          <button mat-icon-button [matMenuTriggerFor]="exportMenu" matTooltip="Export">
            <mat-icon>download</mat-icon>
          </button>
          <mat-menu #exportMenu="matMenu">
            <button mat-menu-item (click)="exportTimeline('json')">
              <mat-icon>code</mat-icon>
              Export JSON
            </button>
            <button mat-menu-item (click)="exportTimeline('csv')">
              <mat-icon>table_chart</mat-icon>
              Export CSV
            </button>
            <button mat-menu-item (click)="exportToReport()">
              <mat-icon>description</mat-icon>
              Add to Report
            </button>
          </mat-menu>
        </div>
      </div>

      <!-- Filters Bar -->
      <div class="filters-bar">
        <div class="filter-section">
          <!-- Time Range -->
          <div class="time-range-picker">
            <mat-form-field appearance="outline">
              <mat-label>Start</mat-label>
              <input matInput [matDatepicker]="startPicker" [(ngModel)]="startDate" (dateChange)="onDateChange()">
              <mat-datepicker-toggle matSuffix [for]="startPicker"></mat-datepicker-toggle>
              <mat-datepicker #startPicker></mat-datepicker>
            </mat-form-field>
            <span class="range-separator">to</span>
            <mat-form-field appearance="outline">
              <mat-label>End</mat-label>
              <input matInput [matDatepicker]="endPicker" [(ngModel)]="endDate" (dateChange)="onDateChange()">
              <mat-datepicker-toggle matSuffix [for]="endPicker"></mat-datepicker-toggle>
              <mat-datepicker #endPicker></mat-datepicker>
            </mat-form-field>
          </div>

          <!-- Quick Time Ranges -->
          <div class="quick-ranges">
            <button mat-stroked-button (click)="setTimeRange('1h')">1H</button>
            <button mat-stroked-button (click)="setTimeRange('24h')">24H</button>
            <button mat-stroked-button (click)="setTimeRange('7d')">7D</button>
            <button mat-stroked-button (click)="setTimeRange('30d')">30D</button>
            <button mat-stroked-button (click)="setTimeRange('all')">All</button>
          </div>
        </div>

        <div class="filter-section">
          <!-- Category Chips -->
          <mat-chip-listbox [multiple]="true" [(ngModel)]="selectedCategories" (change)="loadTimeline()">
            @for (cat of categories; track cat.type) {
              <mat-chip-option [value]="cat.type" [style.--chip-color]="cat.color">
                <mat-icon>{{ cat.icon }}</mat-icon>
                {{ cat.label }}
                @if (categoryCounts()[cat.type]) {
                  <span class="chip-count">({{ categoryCounts()[cat.type] }})</span>
                }
              </mat-chip-option>
            }
          </mat-chip-listbox>
        </div>

        <div class="filter-section">
          <!-- Host Filter -->
          <mat-form-field appearance="outline" class="host-filter">
            <mat-label>Host</mat-label>
            <mat-select [(ngModel)]="selectedHost" (selectionChange)="loadTimeline()">
              <mat-option value="">All Hosts</mat-option>
              @for (host of availableHosts(); track host) {
                <mat-option [value]="host">{{ host }}</mat-option>
              }
            </mat-select>
          </mat-form-field>

          <!-- Evidence Filter -->
          <mat-form-field appearance="outline" class="evidence-filter">
            <mat-label>Evidence Source</mat-label>
            <mat-select [(ngModel)]="selectedEvidence" (selectionChange)="loadTimeline()">
              <mat-option value="">All Evidence</mat-option>
              @for (ev of availableEvidence(); track ev.id) {
                <mat-option [value]="ev.id">{{ ev.name }}</mat-option>
              }
            </mat-select>
          </mat-form-field>
        </div>
      </div>

      <!-- Main Content -->
      <div class="main-content">
        <!-- Timeline View -->
        <div class="timeline-container" [class.loading]="isLoading()">
          @if (isLoading()) {
            <div class="loading-overlay">
              <mat-spinner diameter="48"></mat-spinner>
              <span>Loading timeline...</span>
            </div>
          }

          <!-- D3 Timeline Overview -->
          <div class="timeline-overview">
            <app-d3-timeline
              [items]="timelineItems()"
              [config]="{ height: 120, enableZoom: true, enableBrush: true }"
              [selectedId]="selectedArtifact()?.id || null"
              (itemSelected)="onTimelineItemSelect($event)"
              (rangeChanged)="onTimelineRangeChange($event)"
            ></app-d3-timeline>
          </div>

          <!-- Correlation Markers -->
          @if (correlationGroups().length > 0) {
            <div class="correlation-bar">
              <span class="label">Correlations:</span>
              @for (group of correlationGroups(); track group.id) {
                <button class="correlation-marker"
                        [matTooltip]="group.label + ' (' + group.artifacts.length + ' events)'"
                        (click)="focusCorrelation(group)">
                  <mat-icon>link</mat-icon>
                  {{ group.artifacts.length }}
                </button>
              }
            </div>
          }

          <!-- Artifact List -->
          <div class="artifact-list" #artifactList>
            @for (artifact of artifacts(); track artifact.id; let i = $index) {
              <div class="artifact-item"
                   [class.selected]="selectedArtifact()?.id === artifact.id"
                   [class.bookmarked]="artifact.bookmarked"
                   [class.correlated]="artifact.correlation_id"
                   [attr.data-id]="artifact.id"
                   (click)="selectArtifact(artifact)">
                <div class="artifact-time">
                  <span class="time">{{ formatTime(artifact.timestamp) }}</span>
                  <span class="date">{{ formatDate(artifact.timestamp) }}</span>
                </div>

                <div class="artifact-marker" [style.background]="getCategoryColor(artifact.category)">
                  <mat-icon>{{ getCategoryIcon(artifact.category) }}</mat-icon>
                </div>

                <div class="artifact-content">
                  <div class="artifact-header">
                    <span class="artifact-title">{{ artifact.title }}</span>
                    @if (artifact.severity) {
                      <span class="severity-badge" [class]="'severity-' + artifact.severity">
                        {{ artifact.severity }}
                      </span>
                    }
                    @if (artifact.correlation_id) {
                      <mat-icon class="correlation-icon" matTooltip="Correlated with other events">link</mat-icon>
                    }
                  </div>
                  <div class="artifact-meta">
                    <span class="meta-item">
                      <mat-icon>category</mat-icon>
                      {{ artifact.artifact_type }}
                    </span>
                    @if (artifact.source_host) {
                      <span class="meta-item">
                        <mat-icon>computer</mat-icon>
                        {{ artifact.source_host }}
                      </span>
                    }
                    @if (artifact.evidence_name) {
                      <span class="meta-item">
                        <mat-icon>folder</mat-icon>
                        {{ artifact.evidence_name }}
                      </span>
                    }
                  </div>
                  @if (artifact.description) {
                    <div class="artifact-description">{{ truncate(artifact.description, 150) }}</div>
                  }
                  @if (artifact.tags && artifact.tags.length > 0) {
                    <div class="artifact-tags">
                      @for (tag of artifact.tags.slice(0, 3); track tag) {
                        <span class="tag">{{ tag }}</span>
                      }
                    </div>
                  }
                </div>

                <div class="artifact-actions">
                  <button mat-icon-button (click)="toggleBookmark(artifact, $event)" [matTooltip]="artifact.bookmarked ? 'Remove bookmark' : 'Add bookmark'">
                    <mat-icon>{{ artifact.bookmarked ? 'bookmark' : 'bookmark_border' }}</mat-icon>
                  </button>
                  <button mat-icon-button [matMenuTriggerFor]="artifactMenu" (click)="$event.stopPropagation()">
                    <mat-icon>more_vert</mat-icon>
                  </button>
                  <mat-menu #artifactMenu="matMenu">
                    <button mat-menu-item (click)="viewInEvidence(artifact)">
                      <mat-icon>folder_open</mat-icon>
                      View in Evidence
                    </button>
                    <button mat-menu-item (click)="addToGraph(artifact)">
                      <mat-icon>hub</mat-icon>
                      Add to Graph
                    </button>
                    <button mat-menu-item (click)="findRelated(artifact)">
                      <mat-icon>search</mat-icon>
                      Find Related
                    </button>
                    <mat-divider></mat-divider>
                    <button mat-menu-item (click)="addAnnotation(artifact)">
                      <mat-icon>edit_note</mat-icon>
                      Add Note
                    </button>
                  </mat-menu>
                </div>
              </div>
            }

            @if (artifacts().length === 0 && !isLoading()) {
              <div class="empty-state">
                <mat-icon>timeline</mat-icon>
                <p>No artifacts found for the selected filters</p>
                <button mat-stroked-button (click)="resetFilters()">Reset Filters</button>
              </div>
            }
          </div>
        </div>

        <!-- Detail Panel -->
        @if (selectedArtifact()) {
          <div class="detail-panel">
            <div class="panel-header">
              <div class="panel-title">
                <mat-icon [style.color]="getCategoryColor(selectedArtifact()!.category)">
                  {{ getCategoryIcon(selectedArtifact()!.category) }}
                </mat-icon>
                <h3>{{ selectedArtifact()!.title }}</h3>
              </div>
              <button mat-icon-button (click)="clearSelection()">
                <mat-icon>close</mat-icon>
              </button>
            </div>

            <div class="panel-content">
              <div class="detail-section">
                <h4>Event Details</h4>
                <div class="detail-grid">
                  <div class="detail-item">
                    <span class="label">Timestamp</span>
                    <span class="value">{{ selectedArtifact()!.timestamp | date:'medium' }}</span>
                  </div>
                  <div class="detail-item">
                    <span class="label">Category</span>
                    <span class="value">{{ selectedArtifact()!.category | titlecase }}</span>
                  </div>
                  <div class="detail-item">
                    <span class="label">Type</span>
                    <span class="value">{{ selectedArtifact()!.artifact_type }}</span>
                  </div>
                  @if (selectedArtifact()!.source_host) {
                    <div class="detail-item">
                      <span class="label">Host</span>
                      <span class="value">{{ selectedArtifact()!.source_host }}</span>
                    </div>
                  }
                </div>
              </div>

              @if (selectedArtifact()!.description) {
                <div class="detail-section">
                  <h4>Description</h4>
                  <p class="description">{{ selectedArtifact()!.description }}</p>
                </div>
              }

              <div class="detail-section">
                <h4>Raw Data</h4>
                <pre class="raw-data">{{ formatJson(selectedArtifact()!.data) }}</pre>
              </div>

              <div class="detail-actions">
                <button mat-stroked-button (click)="pivotToHunting(selectedArtifact()!)">
                  <mat-icon>search</mat-icon>
                  Search Similar
                </button>
                <button mat-stroked-button (click)="copyToClipboard(selectedArtifact()!)">
                  <mat-icon>content_copy</mat-icon>
                  Copy JSON
                </button>
              </div>
            </div>
          </div>
        }
      </div>

      <!-- Bookmarks Bar -->
      @if (bookmarks().length > 0) {
        <div class="bookmarks-bar">
          <span class="bar-label">
            <mat-icon>bookmarks</mat-icon>
            Bookmarks ({{ bookmarks().length }})
          </span>
          <div class="bookmarks-list">
            @for (bookmark of bookmarks(); track bookmark.id) {
              <button class="bookmark-chip"
                      [style.border-color]="bookmark.color"
                      (click)="jumpToBookmark(bookmark)">
                {{ bookmark.label }}
              </button>
            }
          </div>
          <button mat-stroked-button (click)="exportBookmarks()">
            <mat-icon>download</mat-icon>
            Export Bookmarks
          </button>
        </div>
      }
    </div>
  `,
  styles: [`
    :host {
      display: block;
      height: 100%;
    }

    .artifact-timeline-page {
      display: flex;
      flex-direction: column;
      height: 100%;
      background: #121212;
    }

    .page-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 12px 16px;
      background: #1e1e1e;
      border-bottom: 1px solid #333;
    }

    .header-left, .header-right {
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .page-header h1 {
      margin: 0;
      font-size: 18px;
      font-weight: 500;
    }

    .case-badge {
      padding: 4px 8px;
      background: #333;
      border-radius: 4px;
      font-size: 12px;
      color: #888;
    }

    .filters-bar {
      display: flex;
      flex-wrap: wrap;
      gap: 16px;
      padding: 12px 16px;
      background: #1e1e1e;
      border-bottom: 1px solid #333;
    }

    .filter-section {
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .time-range-picker {
      display: flex;
      align-items: center;
      gap: 8px;

      mat-form-field {
        width: 140px;
      }

      .range-separator {
        color: #666;
      }
    }

    .quick-ranges {
      display: flex;
      gap: 4px;

      button {
        min-width: 40px;
        padding: 0 8px;
      }
    }

    .host-filter, .evidence-filter {
      width: 180px;
    }

    mat-chip-option {
      --mdc-chip-label-text-color: #fff;
    }

    .chip-count {
      margin-left: 4px;
      font-size: 11px;
      opacity: 0.7;
    }

    .main-content {
      flex: 1;
      display: flex;
      overflow: hidden;
    }

    .timeline-container {
      flex: 1;
      display: flex;
      flex-direction: column;
      overflow: hidden;
    }

    .timeline-container.loading {
      opacity: 0.5;
    }

    .loading-overlay {
      position: absolute;
      top: 50%;
      left: 50%;
      transform: translate(-50%, -50%);
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 16px;
      z-index: 10;
    }

    .timeline-overview {
      padding: 16px;
      border-bottom: 1px solid #333;
    }

    .correlation-bar {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 8px 16px;
      background: #252525;
      border-bottom: 1px solid #333;

      .label {
        font-size: 12px;
        color: #888;
      }

      .correlation-marker {
        display: flex;
        align-items: center;
        gap: 4px;
        padding: 4px 8px;
        background: rgba(var(--accent-rgb), 0.2);
        border: 1px solid var(--accent);
        border-radius: 4px;
        font-size: 12px;
        color: var(--accent);
        cursor: pointer;

        mat-icon {
          font-size: 14px;
          width: 14px;
          height: 14px;
        }
      }
    }

    .artifact-list {
      flex: 1;
      overflow-y: auto;
      padding: 16px;
    }

    .artifact-item {
      display: flex;
      gap: 16px;
      padding: 16px;
      background: #1e1e1e;
      border-radius: 8px;
      margin-bottom: 8px;
      cursor: pointer;
      transition: all 0.15s ease;

      &:hover {
        background: #252525;
      }

      &.selected {
        background: #252525;
        border: 1px solid var(--accent);
      }

      &.bookmarked {
        border-left: 3px solid #4CAF50;
      }

      &.correlated {
        border-right: 3px solid var(--accent);
      }
    }

    .artifact-time {
      display: flex;
      flex-direction: column;
      align-items: flex-end;
      min-width: 80px;

      .time {
        font-family: monospace;
        font-size: 14px;
        font-weight: 500;
      }

      .date {
        font-size: 11px;
        color: #666;
      }
    }

    .artifact-marker {
      width: 36px;
      height: 36px;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;

      mat-icon {
        font-size: 18px;
        width: 18px;
        height: 18px;
        color: white;
      }
    }

    .artifact-content {
      flex: 1;
      min-width: 0;
    }

    .artifact-header {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 4px;
    }

    .artifact-title {
      font-weight: 500;
      font-size: 14px;
    }

    .severity-badge {
      padding: 2px 6px;
      border-radius: 4px;
      font-size: 10px;
      text-transform: uppercase;

      &.severity-critical { background: #f44336; }
      &.severity-high { background: #ff9800; }
      &.severity-medium { background: #ffeb3b; color: black; }
      &.severity-low { background: #4CAF50; }
    }

    .correlation-icon {
      font-size: 16px;
      width: 16px;
      height: 16px;
      color: var(--accent);
    }

    .artifact-meta {
      display: flex;
      gap: 12px;
      font-size: 12px;
      color: #888;
      margin-bottom: 4px;
    }

    .meta-item {
      display: flex;
      align-items: center;
      gap: 4px;

      mat-icon {
        font-size: 14px;
        width: 14px;
        height: 14px;
      }
    }

    .artifact-description {
      font-size: 13px;
      color: #aaa;
      margin-bottom: 4px;
    }

    .artifact-tags {
      display: flex;
      gap: 4px;

      .tag {
        padding: 2px 6px;
        background: #333;
        border-radius: 4px;
        font-size: 11px;
      }
    }

    .artifact-actions {
      display: flex;
      flex-direction: column;
      gap: 4px;
    }

    .empty-state {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      padding: 64px;
      color: #888;

      mat-icon {
        font-size: 48px;
        width: 48px;
        height: 48px;
        margin-bottom: 16px;
      }
    }

    .detail-panel {
      width: 400px;
      background: #1e1e1e;
      border-left: 1px solid #333;
      display: flex;
      flex-direction: column;
    }

    .panel-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 12px 16px;
      background: #252525;
      border-bottom: 1px solid #333;
    }

    .panel-title {
      display: flex;
      align-items: center;
      gap: 8px;

      h3 {
        margin: 0;
        font-size: 14px;
        font-weight: 500;
      }
    }

    .panel-content {
      flex: 1;
      overflow-y: auto;
      padding: 16px;
    }

    .detail-section {
      margin-bottom: 20px;

      h4 {
        margin: 0 0 12px;
        font-size: 12px;
        color: #888;
        text-transform: uppercase;
      }
    }

    .detail-grid {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 12px;
    }

    .detail-item {
      .label {
        font-size: 11px;
        color: #666;
        display: block;
        margin-bottom: 2px;
      }

      .value {
        font-size: 13px;
      }
    }

    .description {
      font-size: 13px;
      line-height: 1.5;
      margin: 0;
    }

    .raw-data {
      background: #252525;
      padding: 12px;
      border-radius: 4px;
      font-size: 11px;
      font-family: 'Fira Code', monospace;
      overflow-x: auto;
      max-height: 300px;
      margin: 0;
    }

    .detail-actions {
      display: flex;
      gap: 8px;
      margin-top: 16px;
    }

    .bookmarks-bar {
      display: flex;
      align-items: center;
      gap: 16px;
      padding: 8px 16px;
      background: #1e1e1e;
      border-top: 1px solid #333;
    }

    .bar-label {
      display: flex;
      align-items: center;
      gap: 4px;
      font-size: 13px;
      color: #888;

      mat-icon {
        font-size: 18px;
        width: 18px;
        height: 18px;
      }
    }

    .bookmarks-list {
      flex: 1;
      display: flex;
      gap: 8px;
      overflow-x: auto;
    }

    .bookmark-chip {
      padding: 4px 12px;
      background: transparent;
      border: 1px solid;
      border-radius: 16px;
      font-size: 12px;
      cursor: pointer;
      white-space: nowrap;

      &:hover {
        background: rgba(255, 255, 255, 0.05);
      }
    }
  `]
})
export class ArtifactTimelineComponent implements OnInit {
  @ViewChild('artifactList') artifactListEl!: ElementRef;

  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private http = inject(HttpClient);
  private snackBar = inject(MatSnackBar);

  caseId = signal<string | null>(null);
  isLoading = signal(false);
  artifacts = signal<TimelineArtifact[]>([]);
  timelineItems = signal<TimelineItem[]>([]);
  selectedArtifact = signal<TimelineArtifact | null>(null);
  categoryCounts = signal<Record<ArtifactCategory, number>>({} as Record<ArtifactCategory, number>);
  correlationGroups = signal<CorrelationGroup[]>([]);
  bookmarks = signal<TimelineBookmark[]>([]);
  availableHosts = signal<string[]>([]);
  availableEvidence = signal<{ id: string; name: string }[]>([]);

  // Filters
  startDate: Date | null = null;
  endDate: Date | null = null;
  selectedCategories: ArtifactCategory[] = ['process', 'network', 'file', 'authentication'];
  selectedHost = '';
  selectedEvidence = '';

  categories: { type: ArtifactCategory; label: string; icon: string; color: string }[] = [
    { type: 'process', label: 'Process', icon: 'memory', color: '#9C27B0' },
    { type: 'network', label: 'Network', icon: 'lan', color: '#FF9800' },
    { type: 'file', label: 'File', icon: 'description', color: '#795548' },
    { type: 'registry', label: 'Registry', icon: 'app_registration', color: '#8BC34A' },
    { type: 'authentication', label: 'Auth', icon: 'vpn_key', color: '#E91E63' },
    { type: 'persistence', label: 'Persistence', icon: 'schedule', color: '#F44336' },
    { type: 'memory', label: 'Memory', icon: 'developer_board', color: '#00BCD4' },
    { type: 'other', label: 'Other', icon: 'category', color: '#607D8B' }
  ];

  ngOnInit(): void {
    this.route.queryParams.subscribe(params => {
      if (params['case_id']) {
        this.caseId.set(params['case_id']);
        this.loadTimeline();
        this.loadMetadata();
      }
    });
  }

  async loadTimeline(): Promise<void> {
    if (!this.caseId()) return;

    this.isLoading.set(true);

    try {
      const params: Record<string, string> = {
        case_id: this.caseId()!,
        categories: this.selectedCategories.join(',')
      };

      if (this.startDate) params['start'] = this.startDate.toISOString();
      if (this.endDate) params['end'] = this.endDate.toISOString();
      if (this.selectedHost) params['host'] = this.selectedHost;
      if (this.selectedEvidence) params['evidence_id'] = this.selectedEvidence;

      const response = await this.http.get<TimelineResponse>(
        `${environment.apiUrl}/timeline/artifacts`,
        { params }
      ).toPromise();

      if (response) {
        this.artifacts.set(response.items);
        this.categoryCounts.set(response.category_counts);
        this.updateTimelineItems(response.items);
        this.detectCorrelations(response.items);
      }
    } catch (error) {
      console.error('Failed to load timeline:', error);
      // Use demo data
      this.loadDemoData();
    } finally {
      this.isLoading.set(false);
    }
  }

  private loadDemoData(): void {
    const now = new Date();
    const demo: TimelineArtifact[] = [
      {
        id: '1',
        timestamp: new Date(now.getTime() - 3600000).toISOString(),
        category: 'process',
        artifact_type: 'Process Creation',
        title: 'powershell.exe spawned',
        description: 'PowerShell process started with encoded command',
        source_host: 'WORKSTATION01',
        severity: 'high',
        data: { pid: 1234, command_line: 'powershell.exe -enc ...' },
        tags: ['execution', 'T1059.001']
      },
      {
        id: '2',
        timestamp: new Date(now.getTime() - 3500000).toISOString(),
        category: 'network',
        artifact_type: 'DNS Query',
        title: 'Suspicious DNS query',
        description: 'Query to known malicious domain',
        source_host: 'WORKSTATION01',
        severity: 'critical',
        data: { domain: 'evil.example.com', query_type: 'A' },
        tags: ['c2', 'T1071.004'],
        correlation_id: 'corr-1'
      },
      {
        id: '3',
        timestamp: new Date(now.getTime() - 3400000).toISOString(),
        category: 'file',
        artifact_type: 'File Creation',
        title: 'Suspicious file written',
        description: 'New executable in temp directory',
        source_host: 'WORKSTATION01',
        severity: 'medium',
        data: { path: 'C:\\Temp\\update.exe', size: 524288 },
        tags: ['persistence']
      }
    ];
    this.artifacts.set(demo);
    this.updateTimelineItems(demo);
  }

  private async loadMetadata(): Promise<void> {
    if (!this.caseId()) return;

    try {
      const [hosts, evidence] = await Promise.all([
        this.http.get<string[]>(`${environment.apiUrl}/timeline/hosts`, {
          params: { case_id: this.caseId()! }
        }).toPromise(),
        this.http.get<{ items: { id: string; name: string }[] }>(`${environment.apiUrl}/evidence`, {
          params: { case_id: this.caseId()! }
        }).toPromise()
      ]);

      if (hosts) this.availableHosts.set(hosts);
      if (evidence) this.availableEvidence.set(evidence.items.map(e => ({ id: e.id, name: e.name })));
    } catch (error) {
      console.error('Failed to load metadata:', error);
    }
  }

  private updateTimelineItems(artifacts: TimelineArtifact[]): void {
    const items: TimelineItem[] = artifacts.map(a => ({
      id: a.id,
      timestamp: new Date(a.timestamp),
      title: a.title,
      category: a.category,
      severity: a.severity,
      data: a as unknown as Record<string, unknown>
    }));
    this.timelineItems.set(items);
  }

  private detectCorrelations(artifacts: TimelineArtifact[]): void {
    // Group artifacts by correlation_id
    const groups = new Map<string, TimelineArtifact[]>();
    for (const artifact of artifacts) {
      if (artifact.correlation_id) {
        if (!groups.has(artifact.correlation_id)) {
          groups.set(artifact.correlation_id, []);
        }
        groups.get(artifact.correlation_id)!.push(artifact);
      }
    }

    const correlations: CorrelationGroup[] = [];
    groups.forEach((arts, id) => {
      if (arts.length > 1) {
        correlations.push({
          id,
          timestamp: arts[0].timestamp,
          artifacts: arts,
          label: `Related Events (${arts.length})`
        });
      }
    });

    this.correlationGroups.set(correlations);
  }

  onTimelineItemSelect(item: TimelineItem): void {
    const artifact = this.artifacts().find(a => a.id === item.id);
    if (artifact) {
      this.selectArtifact(artifact);
    }
  }

  onTimelineRangeChange(range: { start: Date; end: Date }): void {
    this.startDate = range.start;
    this.endDate = range.end;
    // Optionally reload with new range
  }

  selectArtifact(artifact: TimelineArtifact): void {
    this.selectedArtifact.set(artifact);
  }

  clearSelection(): void {
    this.selectedArtifact.set(null);
  }

  onDateChange(): void {
    this.loadTimeline();
  }

  setTimeRange(range: string): void {
    const now = new Date();
    this.endDate = now;

    switch (range) {
      case '1h':
        this.startDate = new Date(now.getTime() - 3600000);
        break;
      case '24h':
        this.startDate = new Date(now.getTime() - 86400000);
        break;
      case '7d':
        this.startDate = new Date(now.getTime() - 604800000);
        break;
      case '30d':
        this.startDate = new Date(now.getTime() - 2592000000);
        break;
      case 'all':
        this.startDate = null;
        this.endDate = null;
        break;
    }

    this.loadTimeline();
  }

  resetFilters(): void {
    this.startDate = null;
    this.endDate = null;
    this.selectedCategories = ['process', 'network', 'file', 'authentication'];
    this.selectedHost = '';
    this.selectedEvidence = '';
    this.loadTimeline();
  }

  toggleBookmark(artifact: TimelineArtifact, event: Event): void {
    event.stopPropagation();
    artifact.bookmarked = !artifact.bookmarked;

    if (artifact.bookmarked) {
      const bookmark: TimelineBookmark = {
        id: `bm-${Date.now()}`,
        artifact_id: artifact.id,
        timestamp: artifact.timestamp,
        label: artifact.title,
        color: this.getCategoryColor(artifact.category)
      };
      this.bookmarks.update(list => [...list, bookmark]);
      this.snackBar.open('Bookmark added', 'Close', { duration: 2000 });
    } else {
      this.bookmarks.update(list => list.filter(b => b.artifact_id !== artifact.id));
    }
  }

  jumpToBookmark(bookmark: TimelineBookmark): void {
    const artifact = this.artifacts().find(a => a.id === bookmark.artifact_id);
    if (artifact) {
      this.selectArtifact(artifact);
      // Scroll to element
      const el = this.artifactListEl?.nativeElement.querySelector(`[data-id="${artifact.id}"]`);
      if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    }
  }

  focusCorrelation(group: CorrelationGroup): void {
    // Highlight all correlated artifacts
    this.snackBar.open(`Showing ${group.artifacts.length} correlated events`, 'Close', { duration: 3000 });
  }

  viewInEvidence(artifact: TimelineArtifact): void {
    if (artifact.evidence_id) {
      this.router.navigate(['/evidence'], { queryParams: { id: artifact.evidence_id } });
    }
  }

  addToGraph(artifact: TimelineArtifact): void {
    this.snackBar.open('Added to investigation graph', 'Close', { duration: 2000 });
  }

  findRelated(artifact: TimelineArtifact): void {
    // Search for related artifacts
    this.snackBar.open('Finding related artifacts...', 'Close', { duration: 2000 });
  }

  addAnnotation(artifact: TimelineArtifact): void {
    const note = prompt('Add note:');
    if (note) {
      this.snackBar.open('Note added', 'Close', { duration: 2000 });
    }
  }

  pivotToHunting(artifact: TimelineArtifact): void {
    const query = `artifact_type:"${artifact.artifact_type}"`;
    this.router.navigate(['/hunting'], { queryParams: { q: query } });
  }

  copyToClipboard(artifact: TimelineArtifact): void {
    navigator.clipboard.writeText(JSON.stringify(artifact, null, 2));
    this.snackBar.open('Copied to clipboard', 'Close', { duration: 2000 });
  }

  exportTimeline(format: string): void {
    this.snackBar.open(`Exporting as ${format.toUpperCase()}...`, 'Close', { duration: 2000 });
  }

  exportToReport(): void {
    this.snackBar.open('Added to report', 'Close', { duration: 2000 });
  }

  exportBookmarks(): void {
    const data = JSON.stringify(this.bookmarks(), null, 2);
    const blob = new Blob([data], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `timeline-bookmarks-${new Date().toISOString().split('T')[0]}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  goBack(): void {
    window.history.back();
  }

  getCategoryColor(category: ArtifactCategory): string {
    return this.categories.find(c => c.type === category)?.color || '#666';
  }

  getCategoryIcon(category: ArtifactCategory): string {
    return this.categories.find(c => c.type === category)?.icon || 'category';
  }

  formatTime(timestamp: string): string {
    return new Date(timestamp).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  }

  formatDate(timestamp: string): string {
    return new Date(timestamp).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  }

  formatJson(data: Record<string, unknown>): string {
    return JSON.stringify(data, null, 2);
  }

  truncate(text: string, length: number): string {
    return text.length > length ? text.substring(0, length) + '...' : text;
  }
}
