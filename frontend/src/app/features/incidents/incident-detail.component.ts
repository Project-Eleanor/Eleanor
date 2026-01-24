import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, Router, RouterModule } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatTabsModule } from '@angular/material/tabs';
import { MatChipsModule } from '@angular/material/chips';
import { MatMenuModule } from '@angular/material/menu';
import { MatDividerModule } from '@angular/material/divider';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatTooltipModule } from '@angular/material/tooltip';
import { CaseService } from '../../core/api/case.service';
import { EvidenceService } from '../../core/api/evidence.service';
import { Case, TimelineEvent, Evidence, CaseStatus } from '../../shared/models';

@Component({
  selector: 'app-incident-detail',
  standalone: true,
  imports: [
    CommonModule,
    RouterModule,
    FormsModule,
    MatCardModule,
    MatButtonModule,
    MatIconModule,
    MatTabsModule,
    MatChipsModule,
    MatMenuModule,
    MatDividerModule,
    MatProgressSpinnerModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    MatTooltipModule
  ],
  template: `
    @if (isLoading()) {
      <div class="loading">
        <mat-spinner></mat-spinner>
      </div>
    } @else if (caseData()) {
      <div class="case-detail">
        <!-- Header -->
        <div class="case-header">
          <button mat-icon-button (click)="goBack()">
            <mat-icon>arrow_back</mat-icon>
          </button>

          <div class="case-info">
            <div class="case-meta">
              <span class="case-number">{{ caseData()!.case_number }}</span>
              <mat-chip [class]="'severity-' + caseData()!.severity">
                {{ caseData()!.severity | uppercase }}
              </mat-chip>
              <span class="status-badge" [class]="'status-' + caseData()!.status">
                {{ formatStatus(caseData()!.status) }}
              </span>
            </div>
            <h1>{{ caseData()!.title }}</h1>
          </div>

          <div class="case-actions">
            <button mat-stroked-button [matMenuTriggerFor]="statusMenu">
              <mat-icon>swap_horiz</mat-icon>
              Change Status
            </button>
            <mat-menu #statusMenu="matMenu">
              <button mat-menu-item (click)="updateStatus('open')">
                <mat-icon>radio_button_checked</mat-icon> Open
              </button>
              <button mat-menu-item (click)="updateStatus('in_progress')">
                <mat-icon>pending</mat-icon> In Progress
              </button>
              <button mat-menu-item (click)="updateStatus('pending')">
                <mat-icon>pause_circle</mat-icon> Pending
              </button>
              <button mat-menu-item (click)="updateStatus('closed')">
                <mat-icon>check_circle</mat-icon> Closed
              </button>
            </mat-menu>

            <button mat-flat-button color="accent" [matMenuTriggerFor]="actionMenu">
              <mat-icon>play_arrow</mat-icon>
              Actions
            </button>
            <mat-menu #actionMenu="matMenu">
              <button mat-menu-item routerLink="/response" [queryParams]="{case: caseData()!.id}">
                <mat-icon>security</mat-icon> Response Actions
              </button>
              <button mat-menu-item routerLink="/hunting" [queryParams]="{case: caseData()!.id}">
                <mat-icon>search</mat-icon> Hunt
              </button>
              <button mat-menu-item>
                <mat-icon>ios_share</mat-icon> Export Report
              </button>
            </mat-menu>
          </div>
        </div>

        <!-- Content -->
        <div class="case-content">
          <!-- Sidebar -->
          <aside class="case-sidebar">
            <mat-card>
              <mat-card-header>
                <mat-card-title>Details</mat-card-title>
              </mat-card-header>
              <mat-card-content>
                <div class="detail-row">
                  <span class="label">Priority</span>
                  <span class="value">{{ caseData()!.priority }}</span>
                </div>
                <div class="detail-row">
                  <span class="label">Assignee</span>
                  <span class="value">{{ caseData()!.assignee_name || 'Unassigned' }}</span>
                </div>
                <div class="detail-row">
                  <span class="label">Created</span>
                  <span class="value">{{ caseData()!.created_at | date:'medium' }}</span>
                </div>
                <div class="detail-row">
                  <span class="label">Created By</span>
                  <span class="value">{{ caseData()!.created_by_name || 'System' }}</span>
                </div>
                <div class="detail-row">
                  <span class="label">Updated</span>
                  <span class="value">{{ caseData()!.updated_at | date:'medium' }}</span>
                </div>
                @if (caseData()!.closed_at) {
                  <div class="detail-row">
                    <span class="label">Closed</span>
                    <span class="value">{{ caseData()!.closed_at | date:'medium' }}</span>
                  </div>
                }
              </mat-card-content>
            </mat-card>

            @if (caseData()!.tags.length > 0) {
              <mat-card>
                <mat-card-header>
                  <mat-card-title>Tags</mat-card-title>
                </mat-card-header>
                <mat-card-content>
                  <div class="tags">
                    @for (tag of caseData()!.tags; track tag) {
                      <mat-chip>{{ tag }}</mat-chip>
                    }
                  </div>
                </mat-card-content>
              </mat-card>
            }

            @if (caseData()!.mitre_techniques.length > 0) {
              <mat-card>
                <mat-card-header>
                  <mat-card-title>MITRE ATT&CK</mat-card-title>
                </mat-card-header>
                <mat-card-content>
                  <div class="mitre-list">
                    @for (technique of caseData()!.mitre_techniques; track technique) {
                      <div class="mitre-item">{{ technique }}</div>
                    }
                  </div>
                </mat-card-content>
              </mat-card>
            }
          </aside>

          <!-- Main Area -->
          <main class="case-main">
            <mat-tab-group>
              <mat-tab label="Overview">
                <div class="tab-content">
                  <mat-card>
                    <mat-card-header>
                      <mat-card-title>Description</mat-card-title>
                    </mat-card-header>
                    <mat-card-content>
                      <p class="description">
                        {{ caseData()!.description || 'No description provided.' }}
                      </p>
                    </mat-card-content>
                  </mat-card>
                </div>
              </mat-tab>

              <mat-tab label="Timeline ({{ timeline().length }})">
                <div class="tab-content">
                  @if (timeline().length === 0) {
                    <div class="empty-state">
                      <mat-icon>timeline</mat-icon>
                      <p>No timeline events</p>
                    </div>
                  } @else {
                    <div class="timeline">
                      @for (event of timeline(); track event.id) {
                        <div class="timeline-item">
                          <div class="timeline-marker"></div>
                          <div class="timeline-content">
                            <div class="timeline-header">
                              <span class="timeline-time">
                                {{ event.timestamp | date:'medium' }}
                              </span>
                              @if (event.category) {
                                <mat-chip class="mini-chip">{{ event.category }}</mat-chip>
                              }
                            </div>
                            <h4>{{ event.title }}</h4>
                            @if (event.description) {
                              <p>{{ event.description }}</p>
                            }
                          </div>
                        </div>
                      }
                    </div>
                  }
                </div>
              </mat-tab>

              <mat-tab label="Evidence ({{ evidence().length }})">
                <div class="tab-content">
                  @if (evidence().length === 0) {
                    <div class="empty-state">
                      <mat-icon>folder_open</mat-icon>
                      <p>No evidence attached</p>
                    </div>
                  } @else {
                    <div class="evidence-list">
                      @for (item of evidence(); track item.id) {
                        <mat-card class="evidence-item" [routerLink]="['/evidence', item.id]">
                          <mat-icon class="file-icon">insert_drive_file</mat-icon>
                          <div class="evidence-info">
                            <span class="filename">{{ item.original_filename }}</span>
                            <span class="meta">
                              {{ item.evidence_type | titlecase }} • {{ formatFileSize(item.file_size) }}
                            </span>
                          </div>
                          <span class="status-badge" [class]="'status-' + item.status">
                            {{ item.status | titlecase }}
                          </span>
                        </mat-card>
                      }
                    </div>
                  }
                </div>
              </mat-tab>

              <mat-tab label="IOCs">
                <div class="tab-content">
                  <div class="empty-state">
                    <mat-icon>security</mat-icon>
                    <p>No IOCs extracted</p>
                  </div>
                </div>
              </mat-tab>
            </mat-tab-group>
          </main>
        </div>
      </div>
    }
  `,
  styles: [`
    .loading {
      display: flex;
      justify-content: center;
      padding: 48px;
    }

    .case-detail {
      height: 100%;
      display: flex;
      flex-direction: column;
    }

    .case-header {
      display: flex;
      align-items: flex-start;
      gap: 16px;
      margin-bottom: 24px;
      padding-bottom: 24px;
      border-bottom: 1px solid var(--border-color);
    }

    .case-info {
      flex: 1;
    }

    .case-meta {
      display: flex;
      align-items: center;
      gap: 12px;
      margin-bottom: 8px;
    }

    .case-number {
      font-family: monospace;
      font-size: 12px;
      color: var(--text-secondary);
    }

    h1 {
      font-size: 24px;
      font-weight: 600;
      margin: 0;
    }

    .case-actions {
      display: flex;
      gap: 8px;
    }

    .case-content {
      display: flex;
      gap: 24px;
      flex: 1;
      min-height: 0;
    }

    .case-sidebar {
      width: 280px;
      flex-shrink: 0;
      display: flex;
      flex-direction: column;
      gap: 16px;

      mat-card {
        background: var(--bg-card);
      }
    }

    .detail-row {
      display: flex;
      justify-content: space-between;
      padding: 8px 0;
      border-bottom: 1px solid var(--border-color);

      &:last-child {
        border-bottom: none;
      }

      .label {
        color: var(--text-secondary);
        font-size: 13px;
      }

      .value {
        font-weight: 500;
        font-size: 13px;
      }
    }

    .tags {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }

    .mitre-list {
      display: flex;
      flex-direction: column;
      gap: 4px;
    }

    .mitre-item {
      font-family: monospace;
      font-size: 12px;
      color: var(--accent);
    }

    .case-main {
      flex: 1;
      min-width: 0;
    }

    .tab-content {
      padding: 16px 0;
    }

    .description {
      color: var(--text-primary);
      line-height: 1.6;
      white-space: pre-wrap;
    }

    .empty-state {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      padding: 48px;
      color: var(--text-muted);

      mat-icon {
        font-size: 48px;
        width: 48px;
        height: 48px;
        margin-bottom: 16px;
      }
    }

    .timeline {
      position: relative;
      padding-left: 24px;

      &::before {
        content: '';
        position: absolute;
        left: 6px;
        top: 0;
        bottom: 0;
        width: 2px;
        background: var(--border-color);
      }
    }

    .timeline-item {
      position: relative;
      padding-bottom: 24px;
    }

    .timeline-marker {
      position: absolute;
      left: -24px;
      top: 4px;
      width: 14px;
      height: 14px;
      border-radius: 50%;
      background: var(--accent);
      border: 2px solid var(--bg-primary);
    }

    .timeline-content {
      background: var(--bg-card);
      border: 1px solid var(--border-color);
      border-radius: 8px;
      padding: 16px;

      h4 {
        margin: 8px 0 4px;
        font-weight: 500;
      }

      p {
        margin: 0;
        color: var(--text-secondary);
        font-size: 14px;
      }
    }

    .timeline-header {
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .timeline-time {
      font-size: 12px;
      color: var(--text-secondary);
    }

    .evidence-list {
      display: flex;
      flex-direction: column;
      gap: 8px;
    }

    .evidence-item {
      display: flex;
      align-items: center;
      gap: 16px;
      padding: 16px;
      cursor: pointer;
      background: var(--bg-card);

      &:hover {
        border-color: var(--accent);
      }
    }

    .file-icon {
      font-size: 32px;
      width: 32px;
      height: 32px;
      color: var(--text-secondary);
    }

    .evidence-info {
      flex: 1;
      display: flex;
      flex-direction: column;

      .filename {
        font-weight: 500;
      }

      .meta {
        font-size: 12px;
        color: var(--text-secondary);
      }
    }

    .severity-critical { background: var(--severity-critical) !important; color: white !important; }
    .severity-high { background: var(--severity-high) !important; color: white !important; }
    .severity-medium { background: var(--severity-medium) !important; color: black !important; }
    .severity-low { background: var(--severity-low) !important; color: white !important; }
    .severity-info { background: var(--severity-info) !important; color: white !important; }

    .status-badge {
      display: inline-flex;
      padding: 4px 12px;
      border-radius: 12px;
      font-size: 12px;
      font-weight: 500;

      &.status-open { background: var(--info); color: white; }
      &.status-in_progress { background: var(--warning); color: black; }
      &.status-pending, &.status-processing { background: var(--text-muted); color: white; }
      &.status-closed, &.status-analyzed { background: var(--success); color: black; }
    }

    .mini-chip {
      font-size: 10px;
      min-height: 20px !important;
      padding: 2px 8px !important;
    }
  `]
})
export class IncidentDetailComponent implements OnInit {
  caseData = signal<Case | null>(null);
  timeline = signal<TimelineEvent[]>([]);
  evidence = signal<Evidence[]>([]);
  isLoading = signal(true);

  constructor(
    private route: ActivatedRoute,
    private router: Router,
    private caseService: CaseService,
    private evidenceService: EvidenceService
  ) {}

  ngOnInit(): void {
    const id = this.route.snapshot.paramMap.get('id');
    if (id) {
      this.loadCase(id);
    }
  }

  private loadCase(id: string): void {
    this.caseService.get(id).subscribe({
      next: (data) => {
        this.caseData.set(data);
        this.isLoading.set(false);
        this.loadTimeline(id);
        this.loadEvidence(id);
      },
      error: () => {
        this.isLoading.set(false);
        this.router.navigate(['/incidents']);
      }
    });
  }

  private loadTimeline(caseId: string): void {
    this.caseService.getTimeline(caseId).subscribe({
      next: (events) => this.timeline.set(events)
    });
  }

  private loadEvidence(caseId: string): void {
    this.evidenceService.list({ case_id: caseId }).subscribe({
      next: (response) => this.evidence.set(response.items)
    });
  }

  goBack(): void {
    this.router.navigate(['/incidents']);
  }

  updateStatus(status: CaseStatus): void {
    const id = this.caseData()?.id;
    if (!id) return;

    this.caseService.update(id, { status }).subscribe({
      next: (updated) => this.caseData.set(updated)
    });
  }

  formatStatus(status: string): string {
    return status.replace('_', ' ').split(' ')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ');
  }

  formatFileSize(bytes: number): string {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  }
}
