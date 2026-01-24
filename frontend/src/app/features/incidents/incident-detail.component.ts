import { Component, OnInit, signal, computed } from '@angular/core';
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

interface Entity {
  id: string;
  type: 'ip' | 'user' | 'host' | 'file' | 'url' | 'email';
  value: string;
  risk_score?: number;
  first_seen?: string;
  last_seen?: string;
}

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
      <div class="incident-detail-sentinel">
        <!-- Header Bar -->
        <div class="incident-header">
          <div class="header-left">
            <button mat-icon-button (click)="goBack()" class="back-btn">
              <mat-icon>arrow_back</mat-icon>
            </button>
            <div class="header-title">
              <span class="incident-number">{{ caseData()!.case_number }}</span>
              <h1>{{ caseData()!.title }}</h1>
            </div>
          </div>
          <div class="header-actions">
            <button mat-stroked-button (click)="refresh()">
              <mat-icon>refresh</mat-icon>
              Refresh
            </button>
            <button mat-stroked-button [matMenuTriggerFor]="moreMenu">
              <mat-icon>more_horiz</mat-icon>
            </button>
            <mat-menu #moreMenu="matMenu">
              <button mat-menu-item>
                <mat-icon>delete</mat-icon>
                <span>Delete incident</span>
              </button>
              <button mat-menu-item>
                <mat-icon>list</mat-icon>
                <span>View logs</span>
              </button>
              <button mat-menu-item>
                <mat-icon>assignment</mat-icon>
                <span>Tasks</span>
              </button>
              <button mat-menu-item>
                <mat-icon>history</mat-icon>
                <span>Activity log</span>
              </button>
            </mat-menu>
          </div>
        </div>

        <!-- Status Bar -->
        <div class="status-bar">
          <div class="status-item">
            <span class="status-label">Severity</span>
            <mat-form-field appearance="outline" class="status-select">
              <mat-select [(value)]="severity" (selectionChange)="updateSeverity($event.value)">
                <mat-option value="critical">
                  <span class="severity-option critical">Critical</span>
                </mat-option>
                <mat-option value="high">
                  <span class="severity-option high">High</span>
                </mat-option>
                <mat-option value="medium">
                  <span class="severity-option medium">Medium</span>
                </mat-option>
                <mat-option value="low">
                  <span class="severity-option low">Low</span>
                </mat-option>
                <mat-option value="info">
                  <span class="severity-option info">Informational</span>
                </mat-option>
              </mat-select>
            </mat-form-field>
          </div>

          <div class="status-item">
            <span class="status-label">Status</span>
            <mat-form-field appearance="outline" class="status-select">
              <mat-select [(value)]="status" (selectionChange)="updateStatus($event.value)">
                <mat-option value="open">Open</mat-option>
                <mat-option value="in_progress">In Progress</mat-option>
                <mat-option value="pending">Pending</mat-option>
                <mat-option value="closed">Closed</mat-option>
              </mat-select>
            </mat-form-field>
          </div>

          <div class="status-item">
            <span class="status-label">Owner</span>
            <mat-form-field appearance="outline" class="status-select owner-select">
              <mat-select [(value)]="owner">
                <mat-option value="">Unassigned</mat-option>
                <mat-option value="admin">Admin</mat-option>
                <mat-option value="analyst1">Analyst 1</mat-option>
                <mat-option value="analyst2">Analyst 2</mat-option>
              </mat-select>
            </mat-form-field>
          </div>

          <div class="status-spacer"></div>

          <button mat-flat-button color="primary" [matMenuTriggerFor]="actionMenu">
            <mat-icon>play_arrow</mat-icon>
            Actions
          </button>
          <mat-menu #actionMenu="matMenu">
            <button mat-menu-item routerLink="/response" [queryParams]="{case: caseData()!.id}">
              <mat-icon>security</mat-icon>
              Response Actions
            </button>
            <button mat-menu-item routerLink="/hunting" [queryParams]="{case: caseData()!.id}">
              <mat-icon>manage_search</mat-icon>
              Hunt
            </button>
            <button mat-menu-item>
              <mat-icon>ios_share</mat-icon>
              Export Report
            </button>
          </mat-menu>
        </div>

        <!-- Three-Panel Layout -->
        <div class="three-panel-layout">
          <!-- Left Panel: Metadata -->
          <aside class="left-panel">
            <div class="panel-section">
              <h3>Description</h3>
              <p class="description-text">
                {{ caseData()!.description || 'No description provided.' }}
              </p>
            </div>

            <mat-divider></mat-divider>

            <div class="panel-section">
              <h3>Details</h3>
              <div class="detail-grid">
                <div class="detail-item">
                  <span class="detail-label">Created</span>
                  <span class="detail-value">{{ caseData()!.created_at | date:'medium' }}</span>
                </div>
                <div class="detail-item">
                  <span class="detail-label">Created by</span>
                  <span class="detail-value">{{ caseData()!.created_by_name || 'System' }}</span>
                </div>
                <div class="detail-item">
                  <span class="detail-label">Last updated</span>
                  <span class="detail-value">{{ caseData()!.updated_at | date:'medium' }}</span>
                </div>
                @if (caseData()!.closed_at) {
                  <div class="detail-item">
                    <span class="detail-label">Closed</span>
                    <span class="detail-value">{{ caseData()!.closed_at | date:'medium' }}</span>
                  </div>
                }
                <div class="detail-item">
                  <span class="detail-label">Priority</span>
                  <span class="detail-value">{{ caseData()!.priority }}</span>
                </div>
              </div>
            </div>

            <mat-divider></mat-divider>

            <div class="panel-section">
              <h3>Evidence ({{ evidence().length }})</h3>
              @if (evidence().length === 0) {
                <p class="empty-text">No evidence attached</p>
              } @else {
                <div class="evidence-mini-list">
                  @for (item of evidence().slice(0, 5); track item.id) {
                    <div class="evidence-mini-item" [routerLink]="['/evidence', item.id]">
                      <mat-icon>insert_drive_file</mat-icon>
                      <span class="filename">{{ item.original_filename }}</span>
                    </div>
                  }
                  @if (evidence().length > 5) {
                    <a class="view-all-link" routerLink="/evidence" [queryParams]="{case: caseData()!.id}">
                      View all {{ evidence().length }} items
                    </a>
                  }
                </div>
              }
            </div>

            <mat-divider></mat-divider>

            @if (caseData()!.tags.length > 0) {
              <div class="panel-section">
                <h3>Tags</h3>
                <div class="tags-list">
                  @for (tag of caseData()!.tags; track tag) {
                    <mat-chip>{{ tag }}</mat-chip>
                  }
                </div>
              </div>
              <mat-divider></mat-divider>
            }

            @if (caseData()!.mitre_techniques.length > 0) {
              <div class="panel-section">
                <h3>MITRE ATT&CK</h3>
                <div class="mitre-list">
                  @for (technique of caseData()!.mitre_techniques; track technique) {
                    <a class="mitre-item" [routerLink]="['/mitre']" [queryParams]="{highlight: technique}">
                      {{ technique }}
                    </a>
                  }
                </div>
              </div>
            }
          </aside>

          <!-- Center Panel: Timeline -->
          <main class="center-panel">
            <mat-tab-group animationDuration="200ms">
              <mat-tab>
                <ng-template mat-tab-label>
                  <mat-icon>timeline</mat-icon>
                  <span>Timeline ({{ timeline().length }})</span>
                </ng-template>

                <div class="timeline-container">
                  <div class="timeline-toolbar">
                    <div class="timeline-search">
                      <mat-icon>search</mat-icon>
                      <input type="text" placeholder="Search timeline..." [(ngModel)]="timelineSearch">
                    </div>
                    <button mat-stroked-button>
                      <mat-icon>filter_list</mat-icon>
                      Add filter
                    </button>
                  </div>

                  @if (filteredTimeline().length === 0) {
                    <div class="empty-state">
                      <mat-icon>timeline</mat-icon>
                      <p>No timeline events</p>
                    </div>
                  } @else {
                    <div class="timeline">
                      @for (event of filteredTimeline(); track event.id) {
                        <div class="timeline-item">
                          <div class="timeline-line"></div>
                          <div class="timeline-marker" [class]="'marker-' + (event.category || 'default')"></div>
                          <div class="timeline-content">
                            <div class="timeline-header">
                              <span class="timeline-time">
                                {{ event.timestamp | date:'MMM d, y h:mm a' }}
                              </span>
                              @if (event.category) {
                                <span class="timeline-category">{{ event.category }}</span>
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

              <mat-tab>
                <ng-template mat-tab-label>
                  <mat-icon>description</mat-icon>
                  <span>Notes</span>
                </ng-template>

                <div class="notes-container">
                  <mat-form-field appearance="outline" class="notes-field">
                    <mat-label>Add a note</mat-label>
                    <textarea matInput rows="3" placeholder="Type your note here..."></textarea>
                  </mat-form-field>
                  <button mat-flat-button color="primary">Add Note</button>
                </div>
              </mat-tab>

              <mat-tab>
                <ng-template mat-tab-label>
                  <mat-icon>security</mat-icon>
                  <span>IOCs</span>
                </ng-template>

                <div class="iocs-container">
                  <div class="empty-state">
                    <mat-icon>security</mat-icon>
                    <p>No IOCs extracted</p>
                    <button mat-stroked-button>Extract IOCs from Evidence</button>
                  </div>
                </div>
              </mat-tab>
            </mat-tab-group>
          </main>

          <!-- Right Panel: Entities -->
          <aside class="right-panel">
            <div class="panel-header">
              <h3>Entities</h3>
              <span class="entity-count">{{ entities().length }}</span>
            </div>

            <div class="entity-search">
              <mat-icon>search</mat-icon>
              <input type="text" placeholder="Search entities..." [(ngModel)]="entitySearch">
            </div>

            <mat-form-field appearance="outline" class="entity-type-filter">
              <mat-select [(value)]="entityTypeFilter" placeholder="Type: All">
                <mat-option value="">All types</mat-option>
                <mat-option value="ip">IP Address</mat-option>
                <mat-option value="user">User Account</mat-option>
                <mat-option value="host">Host</mat-option>
                <mat-option value="file">File</mat-option>
                <mat-option value="url">URL</mat-option>
              </mat-select>
            </mat-form-field>

            <div class="entities-list">
              @if (filteredEntities().length === 0) {
                <div class="empty-state-small">
                  <mat-icon>account_tree</mat-icon>
                  <p>No entities found</p>
                </div>
              } @else {
                @for (entity of filteredEntities(); track entity.id) {
                  <div class="entity-card" [routerLink]="['/entities', entity.type, entity.value]">
                    <div class="entity-icon" [class]="'entity-' + entity.type">
                      <mat-icon>{{ getEntityIcon(entity.type) }}</mat-icon>
                    </div>
                    <div class="entity-info">
                      <span class="entity-type">{{ entity.type | uppercase }}</span>
                      <span class="entity-value">{{ entity.value }}</span>
                    </div>
                    @if (entity.risk_score !== undefined) {
                      <div class="entity-risk" [class]="getRiskClass(entity.risk_score)">
                        {{ entity.risk_score }}
                      </div>
                    }
                  </div>
                }
              }
            </div>
          </aside>
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

    .incident-detail-sentinel {
      display: flex;
      flex-direction: column;
      height: calc(100vh - 112px);
      margin: -24px;
    }

    /* Header */
    .incident-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 16px 24px;
      background: var(--bg-secondary);
      border-bottom: 1px solid var(--border-color);
    }

    .header-left {
      display: flex;
      align-items: center;
      gap: 16px;
    }

    .back-btn {
      color: var(--text-secondary);
    }

    .header-title {
      display: flex;
      flex-direction: column;
    }

    .incident-number {
      font-size: 12px;
      font-family: monospace;
      color: var(--text-secondary);
    }

    h1 {
      font-size: 18px;
      font-weight: 600;
      margin: 0;
      color: var(--text-primary);
    }

    .header-actions {
      display: flex;
      gap: 8px;
    }

    /* Status Bar */
    .status-bar {
      display: flex;
      align-items: center;
      gap: 24px;
      padding: 12px 24px;
      background: var(--bg-card);
      border-bottom: 1px solid var(--border-color);
    }

    .status-item {
      display: flex;
      flex-direction: column;
      gap: 4px;
    }

    .status-label {
      font-size: 11px;
      text-transform: uppercase;
      color: var(--text-muted);
      font-weight: 500;
    }

    .status-select {
      width: 150px;

      ::ng-deep .mat-mdc-form-field-subscript-wrapper {
        display: none;
      }

      ::ng-deep .mat-mdc-text-field-wrapper {
        padding: 0 8px !important;
      }

      ::ng-deep .mat-mdc-form-field-infix {
        padding: 8px 0 !important;
        min-height: 36px;
      }
    }

    .owner-select {
      width: 180px;
    }

    .severity-option {
      &.critical { color: var(--danger); }
      &.high { color: #f97316; }
      &.medium { color: var(--warning); }
      &.low { color: var(--info); }
      &.info { color: var(--text-secondary); }
    }

    .status-spacer {
      flex: 1;
    }

    /* Three-Panel Layout */
    .three-panel-layout {
      display: flex;
      flex: 1;
      overflow: hidden;
    }

    /* Left Panel */
    .left-panel {
      width: 300px;
      flex-shrink: 0;
      background: var(--bg-secondary);
      border-right: 1px solid var(--border-color);
      overflow-y: auto;
    }

    .panel-section {
      padding: 16px;

      h3 {
        font-size: 12px;
        font-weight: 600;
        text-transform: uppercase;
        color: var(--text-muted);
        margin: 0 0 12px 0;
      }
    }

    .description-text {
      font-size: 14px;
      line-height: 1.6;
      color: var(--text-secondary);
      margin: 0;
      white-space: pre-wrap;
    }

    .detail-grid {
      display: flex;
      flex-direction: column;
      gap: 12px;
    }

    .detail-item {
      display: flex;
      flex-direction: column;
      gap: 2px;
    }

    .detail-label {
      font-size: 11px;
      color: var(--text-muted);
    }

    .detail-value {
      font-size: 13px;
      color: var(--text-primary);
    }

    .evidence-mini-list {
      display: flex;
      flex-direction: column;
      gap: 8px;
    }

    .evidence-mini-item {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 8px;
      background: var(--bg-tertiary);
      border-radius: 4px;
      cursor: pointer;
      transition: background 0.15s ease;

      &:hover {
        background: rgba(88, 166, 255, 0.2);
      }

      mat-icon {
        font-size: 18px;
        width: 18px;
        height: 18px;
        color: var(--text-secondary);
      }

      .filename {
        font-size: 13px;
        color: var(--text-primary);
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
    }

    .view-all-link {
      font-size: 13px;
      color: var(--accent);
      text-decoration: none;
      padding: 8px 0;

      &:hover {
        text-decoration: underline;
      }
    }

    .empty-text {
      font-size: 13px;
      color: var(--text-muted);
      margin: 0;
    }

    .tags-list {
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
      font-size: 13px;
      color: var(--accent);
      text-decoration: none;

      &:hover {
        text-decoration: underline;
      }
    }

    /* Center Panel */
    .center-panel {
      flex: 1;
      display: flex;
      flex-direction: column;
      overflow: hidden;
      background: var(--bg-primary);
    }

    .timeline-container {
      padding: 16px;
      flex: 1;
      overflow-y: auto;
    }

    .timeline-toolbar {
      display: flex;
      gap: 12px;
      margin-bottom: 16px;
    }

    .timeline-search {
      flex: 1;
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 8px 16px;
      background: var(--bg-card);
      border: 1px solid var(--border-color);
      border-radius: 4px;

      mat-icon {
        color: var(--text-muted);
        font-size: 20px;
        width: 20px;
        height: 20px;
      }

      input {
        flex: 1;
        background: transparent;
        border: none;
        outline: none;
        color: var(--text-primary);
        font-size: 14px;

        &::placeholder {
          color: var(--text-muted);
        }
      }
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
    }

    .timeline {
      position: relative;
    }

    .timeline-item {
      position: relative;
      padding-left: 32px;
      padding-bottom: 24px;
    }

    .timeline-line {
      position: absolute;
      left: 7px;
      top: 0;
      bottom: 0;
      width: 2px;
      background: var(--border-color);
    }

    .timeline-marker {
      position: absolute;
      left: 0;
      top: 4px;
      width: 16px;
      height: 16px;
      border-radius: 50%;
      background: var(--accent);
      border: 3px solid var(--bg-primary);

      &.marker-alert { background: var(--danger); }
      &.marker-action { background: var(--success); }
      &.marker-note { background: var(--warning); }
    }

    .timeline-content {
      background: var(--bg-card);
      border: 1px solid var(--border-color);
      border-radius: 8px;
      padding: 12px 16px;

      h4 {
        margin: 4px 0;
        font-size: 14px;
        font-weight: 500;
        color: var(--text-primary);
      }

      p {
        margin: 0;
        font-size: 13px;
        color: var(--text-secondary);
        line-height: 1.5;
      }
    }

    .timeline-header {
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .timeline-time {
      font-size: 11px;
      color: var(--text-muted);
    }

    .timeline-category {
      font-size: 10px;
      padding: 2px 6px;
      border-radius: 4px;
      background: var(--bg-tertiary);
      color: var(--text-secondary);
      text-transform: uppercase;
    }

    .notes-container {
      padding: 16px;
      display: flex;
      flex-direction: column;
      gap: 12px;
    }

    .notes-field {
      width: 100%;
    }

    .iocs-container {
      padding: 16px;
    }

    /* Right Panel */
    .right-panel {
      width: 320px;
      flex-shrink: 0;
      background: var(--bg-secondary);
      border-left: 1px solid var(--border-color);
      display: flex;
      flex-direction: column;
    }

    .panel-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 16px;
      border-bottom: 1px solid var(--border-color);

      h3 {
        margin: 0;
        font-size: 14px;
        font-weight: 600;
        color: var(--text-primary);
      }
    }

    .entity-count {
      font-size: 12px;
      padding: 2px 8px;
      border-radius: 12px;
      background: var(--bg-tertiary);
      color: var(--text-secondary);
    }

    .entity-search {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 8px 16px;
      margin: 12px 16px 8px;
      background: var(--bg-tertiary);
      border-radius: 4px;

      mat-icon {
        color: var(--text-muted);
        font-size: 18px;
        width: 18px;
        height: 18px;
      }

      input {
        flex: 1;
        background: transparent;
        border: none;
        outline: none;
        color: var(--text-primary);
        font-size: 13px;

        &::placeholder {
          color: var(--text-muted);
        }
      }
    }

    .entity-type-filter {
      margin: 0 16px 8px;

      ::ng-deep .mat-mdc-form-field-subscript-wrapper {
        display: none;
      }
    }

    .entities-list {
      flex: 1;
      overflow-y: auto;
      padding: 0 16px 16px;
    }

    .empty-state-small {
      display: flex;
      flex-direction: column;
      align-items: center;
      padding: 32px;
      color: var(--text-muted);

      mat-icon {
        font-size: 32px;
        width: 32px;
        height: 32px;
        margin-bottom: 8px;
      }

      p {
        margin: 0;
        font-size: 13px;
      }
    }

    .entity-card {
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 12px;
      background: var(--bg-tertiary);
      border-radius: 8px;
      margin-bottom: 8px;
      cursor: pointer;
      transition: all 0.15s ease;

      &:hover {
        background: rgba(88, 166, 255, 0.2);
      }
    }

    .entity-icon {
      width: 36px;
      height: 36px;
      border-radius: 8px;
      display: flex;
      align-items: center;
      justify-content: center;
      background: var(--bg-card);

      mat-icon {
        font-size: 20px;
        width: 20px;
        height: 20px;
      }

      &.entity-ip mat-icon { color: #3b82f6; }
      &.entity-user mat-icon { color: #8b5cf6; }
      &.entity-host mat-icon { color: #10b981; }
      &.entity-file mat-icon { color: #f59e0b; }
      &.entity-url mat-icon { color: #ec4899; }
      &.entity-email mat-icon { color: #06b6d4; }
    }

    .entity-info {
      flex: 1;
      display: flex;
      flex-direction: column;
      gap: 2px;
      overflow: hidden;
    }

    .entity-type {
      font-size: 10px;
      color: var(--text-muted);
      font-weight: 500;
    }

    .entity-value {
      font-size: 13px;
      color: var(--text-primary);
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .entity-risk {
      width: 28px;
      height: 28px;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 11px;
      font-weight: 600;

      &.risk-high {
        background: var(--danger);
        color: white;
      }

      &.risk-medium {
        background: var(--warning);
        color: black;
      }

      &.risk-low {
        background: var(--success);
        color: black;
      }
    }
  `]
})
export class IncidentDetailComponent implements OnInit {
  caseData = signal<Case | null>(null);
  timeline = signal<TimelineEvent[]>([]);
  evidence = signal<Evidence[]>([]);
  entities = signal<Entity[]>([]);
  isLoading = signal(true);

  severity = 'medium';
  status = 'open';
  owner = '';

  timelineSearch = '';
  entitySearch = '';
  entityTypeFilter = '';

  filteredTimeline = computed(() => {
    const events = this.timeline();
    if (!this.timelineSearch) return events;
    const search = this.timelineSearch.toLowerCase();
    return events.filter(e =>
      e.title.toLowerCase().includes(search) ||
      (e.description?.toLowerCase().includes(search) ?? false)
    );
  });

  filteredEntities = computed(() => {
    let entities = this.entities();

    if (this.entitySearch) {
      const search = this.entitySearch.toLowerCase();
      entities = entities.filter(e => e.value.toLowerCase().includes(search));
    }

    if (this.entityTypeFilter) {
      entities = entities.filter(e => e.type === this.entityTypeFilter);
    }

    return entities;
  });

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
        this.severity = data.severity;
        this.status = data.status;
        this.owner = data.assignee_name || '';
        this.isLoading.set(false);
        this.loadTimeline(id);
        this.loadEvidence(id);
        this.loadEntities(id);
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

  private loadEntities(caseId: string): void {
    // Mock entities - in production this would come from API
    this.entities.set([
      { id: '1', type: 'ip', value: '192.168.1.100', risk_score: 85 },
      { id: '2', type: 'ip', value: '10.0.0.15', risk_score: 45 },
      { id: '3', type: 'user', value: 'john.doe@company.com', risk_score: 72 },
      { id: '4', type: 'host', value: 'WORKSTATION-001', risk_score: 60 },
      { id: '5', type: 'file', value: 'malware.exe', risk_score: 95 },
      { id: '6', type: 'url', value: 'http://malicious-site.com/payload', risk_score: 90 }
    ]);
  }

  goBack(): void {
    this.router.navigate(['/incidents']);
  }

  refresh(): void {
    const id = this.caseData()?.id;
    if (id) {
      this.loadCase(id);
    }
  }

  updateSeverity(severity: string): void {
    const id = this.caseData()?.id;
    if (!id) return;

    this.caseService.update(id, { severity: severity as Case['severity'] }).subscribe({
      next: (updated) => this.caseData.set(updated)
    });
  }

  updateStatus(status: CaseStatus): void {
    const id = this.caseData()?.id;
    if (!id) return;

    this.caseService.update(id, { status }).subscribe({
      next: (updated) => this.caseData.set(updated)
    });
  }

  getEntityIcon(type: string): string {
    const icons: Record<string, string> = {
      ip: 'router',
      user: 'person',
      host: 'computer',
      file: 'description',
      url: 'link',
      email: 'email'
    };
    return icons[type] || 'help';
  }

  getRiskClass(score: number): string {
    if (score >= 70) return 'risk-high';
    if (score >= 40) return 'risk-medium';
    return 'risk-low';
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
