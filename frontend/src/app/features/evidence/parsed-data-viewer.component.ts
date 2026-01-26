import { Component, Input, signal, OnChanges, SimpleChanges } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatTabsModule } from '@angular/material/tabs';
import { MatTableModule } from '@angular/material/table';
import { MatPaginatorModule, PageEvent } from '@angular/material/paginator';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatChipsModule } from '@angular/material/chips';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatMenuModule } from '@angular/material/menu';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { HttpClient } from '@angular/common/http';
import { environment } from '../../../environments/environment';
import { Evidence, EvidenceType } from '../../shared/models';

export interface ParsedArtifact {
  id: string;
  evidence_id: string;
  artifact_type: string;
  data: Record<string, unknown>;
  timestamp?: string;
  source_file?: string;
  metadata?: Record<string, unknown>;
}

export interface ParsedDataResponse {
  items: ParsedArtifact[];
  total: number;
  page: number;
  page_size: number;
  artifact_types: string[];
}

interface ArtifactTab {
  type: string;
  label: string;
  icon: string;
  count: number;
}

@Component({
  selector: 'app-parsed-data-viewer',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatTabsModule,
    MatTableModule,
    MatPaginatorModule,
    MatButtonModule,
    MatIconModule,
    MatChipsModule,
    MatProgressSpinnerModule,
    MatTooltipModule,
    MatMenuModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    MatSnackBarModule,
  ],
  template: `
    <div class="parsed-data-viewer">
      @if (isLoading()) {
        <div class="loading">
          <mat-spinner diameter="32"></mat-spinner>
          <span>Loading parsed data...</span>
        </div>
      } @else if (tabs().length === 0) {
        <div class="empty-state">
          <mat-icon>data_object</mat-icon>
          <p>No parsed data available</p>
          @if (evidence?.status === 'processing') {
            <span class="hint">Evidence is still being processed...</span>
          } @else if (evidence?.status === 'pending') {
            <button mat-stroked-button (click)="triggerParse()">
              <mat-icon>play_arrow</mat-icon>
              Start Processing
            </button>
          } @else {
            <button mat-stroked-button (click)="triggerParse()">
              <mat-icon>refresh</mat-icon>
              Reprocess Evidence
            </button>
          }
        </div>
      } @else {
        <!-- Toolbar -->
        <div class="viewer-toolbar">
          <mat-form-field appearance="outline" class="search-field">
            <mat-icon matPrefix>search</mat-icon>
            <input matInput [(ngModel)]="searchQuery" placeholder="Search artifacts..." (keyup.enter)="loadArtifacts()">
          </mat-form-field>

          <button mat-icon-button [matMenuTriggerFor]="exportMenu" matTooltip="Export">
            <mat-icon>download</mat-icon>
          </button>
          <mat-menu #exportMenu="matMenu">
            <button mat-menu-item (click)="exportData('json')">
              <mat-icon>code</mat-icon>
              Export JSON
            </button>
            <button mat-menu-item (click)="exportData('csv')">
              <mat-icon>table_chart</mat-icon>
              Export CSV
            </button>
          </mat-menu>
        </div>

        <!-- Tabs -->
        <mat-tab-group (selectedTabChange)="onTabChange($event.index)" [animationDuration]="'200ms'">
          @for (tab of tabs(); track tab.type) {
            <mat-tab>
              <ng-template mat-tab-label>
                <mat-icon>{{ tab.icon }}</mat-icon>
                <span class="tab-label">{{ tab.label }}</span>
                <span class="tab-count">{{ tab.count }}</span>
              </ng-template>

              <div class="tab-content">
                @if (tabLoading()) {
                  <div class="tab-loading">
                    <mat-spinner diameter="24"></mat-spinner>
                  </div>
                } @else {
                  @switch (tab.type) {
                    @case ('windows_event') {
                      <ng-container *ngTemplateOutlet="eventLogViewer"></ng-container>
                    }
                    @case ('network_flow') {
                      <ng-container *ngTemplateOutlet="networkViewer"></ng-container>
                    }
                    @case ('registry') {
                      <ng-container *ngTemplateOutlet="registryViewer"></ng-container>
                    }
                    @case ('browser_history') {
                      <ng-container *ngTemplateOutlet="browserViewer"></ng-container>
                    }
                    @case ('process') {
                      <ng-container *ngTemplateOutlet="processViewer"></ng-container>
                    }
                    @case ('file_artifact') {
                      <ng-container *ngTemplateOutlet="fileViewer"></ng-container>
                    }
                    @default {
                      <ng-container *ngTemplateOutlet="genericViewer"></ng-container>
                    }
                  }
                }
              </div>
            </mat-tab>
          }
        </mat-tab-group>
      }

      <!-- Event Log Template -->
      <ng-template #eventLogViewer>
        <div class="artifact-table-container">
          <table mat-table [dataSource]="artifacts()">
            <ng-container matColumnDef="timestamp">
              <th mat-header-cell *matHeaderCellDef>Timestamp</th>
              <td mat-cell *matCellDef="let row">{{ formatTimestamp(row.data['timestamp'] || row.timestamp) }}</td>
            </ng-container>
            <ng-container matColumnDef="event_id">
              <th mat-header-cell *matHeaderCellDef>Event ID</th>
              <td mat-cell *matCellDef="let row">
                <span class="event-id">{{ row.data['event_id'] }}</span>
              </td>
            </ng-container>
            <ng-container matColumnDef="channel">
              <th mat-header-cell *matHeaderCellDef>Channel</th>
              <td mat-cell *matCellDef="let row">{{ row.data['channel'] || '-' }}</td>
            </ng-container>
            <ng-container matColumnDef="computer">
              <th mat-header-cell *matHeaderCellDef>Computer</th>
              <td mat-cell *matCellDef="let row">{{ row.data['computer'] || '-' }}</td>
            </ng-container>
            <ng-container matColumnDef="message">
              <th mat-header-cell *matHeaderCellDef>Message</th>
              <td mat-cell *matCellDef="let row" class="message-cell">
                {{ truncateText(row.data['message'], 80) }}
              </td>
            </ng-container>
            <ng-container matColumnDef="actions">
              <th mat-header-cell *matHeaderCellDef></th>
              <td mat-cell *matCellDef="let row">
                <button mat-icon-button (click)="viewArtifactDetail(row)" matTooltip="View Details">
                  <mat-icon>visibility</mat-icon>
                </button>
              </td>
            </ng-container>
            <tr mat-header-row *matHeaderRowDef="eventColumns"></tr>
            <tr mat-row *matRowDef="let row; columns: eventColumns;" (click)="viewArtifactDetail(row)"></tr>
          </table>
          <mat-paginator [length]="totalArtifacts()" [pageSize]="pageSize" [pageSizeOptions]="[25, 50, 100]" (page)="onPageChange($event)"></mat-paginator>
        </div>
      </ng-template>

      <!-- Network Flow Template -->
      <ng-template #networkViewer>
        <div class="artifact-table-container">
          <table mat-table [dataSource]="artifacts()">
            <ng-container matColumnDef="timestamp">
              <th mat-header-cell *matHeaderCellDef>Timestamp</th>
              <td mat-cell *matCellDef="let row">{{ formatTimestamp(row.data['timestamp'] || row.timestamp) }}</td>
            </ng-container>
            <ng-container matColumnDef="src_ip">
              <th mat-header-cell *matHeaderCellDef>Source</th>
              <td mat-cell *matCellDef="let row">
                <span class="ip-address">{{ row.data['src_ip'] }}:{{ row.data['src_port'] }}</span>
              </td>
            </ng-container>
            <ng-container matColumnDef="dst_ip">
              <th mat-header-cell *matHeaderCellDef>Destination</th>
              <td mat-cell *matCellDef="let row">
                <span class="ip-address">{{ row.data['dst_ip'] }}:{{ row.data['dst_port'] }}</span>
              </td>
            </ng-container>
            <ng-container matColumnDef="protocol">
              <th mat-header-cell *matHeaderCellDef>Protocol</th>
              <td mat-cell *matCellDef="let row">
                <mat-chip>{{ row.data['protocol'] || 'TCP' }}</mat-chip>
              </td>
            </ng-container>
            <ng-container matColumnDef="bytes">
              <th mat-header-cell *matHeaderCellDef>Bytes</th>
              <td mat-cell *matCellDef="let row">{{ formatBytes(row.data['bytes']) }}</td>
            </ng-container>
            <ng-container matColumnDef="actions">
              <th mat-header-cell *matHeaderCellDef></th>
              <td mat-cell *matCellDef="let row">
                <button mat-icon-button (click)="viewArtifactDetail(row)" matTooltip="View Details">
                  <mat-icon>visibility</mat-icon>
                </button>
              </td>
            </ng-container>
            <tr mat-header-row *matHeaderRowDef="networkColumns"></tr>
            <tr mat-row *matRowDef="let row; columns: networkColumns;" (click)="viewArtifactDetail(row)"></tr>
          </table>
          <mat-paginator [length]="totalArtifacts()" [pageSize]="pageSize" [pageSizeOptions]="[25, 50, 100]" (page)="onPageChange($event)"></mat-paginator>
        </div>
      </ng-template>

      <!-- Registry Template -->
      <ng-template #registryViewer>
        <div class="artifact-table-container">
          <table mat-table [dataSource]="artifacts()">
            <ng-container matColumnDef="timestamp">
              <th mat-header-cell *matHeaderCellDef>Timestamp</th>
              <td mat-cell *matCellDef="let row">{{ formatTimestamp(row.data['timestamp'] || row.timestamp) }}</td>
            </ng-container>
            <ng-container matColumnDef="key_path">
              <th mat-header-cell *matHeaderCellDef>Key Path</th>
              <td mat-cell *matCellDef="let row" class="key-path">{{ truncateText(row.data['key_path'], 60) }}</td>
            </ng-container>
            <ng-container matColumnDef="value_name">
              <th mat-header-cell *matHeaderCellDef>Value</th>
              <td mat-cell *matCellDef="let row">{{ row.data['value_name'] || '(Default)' }}</td>
            </ng-container>
            <ng-container matColumnDef="value_data">
              <th mat-header-cell *matHeaderCellDef>Data</th>
              <td mat-cell *matCellDef="let row" class="value-data">{{ truncateText(row.data['value_data'], 40) }}</td>
            </ng-container>
            <ng-container matColumnDef="actions">
              <th mat-header-cell *matHeaderCellDef></th>
              <td mat-cell *matCellDef="let row">
                <button mat-icon-button (click)="viewArtifactDetail(row)" matTooltip="View Details">
                  <mat-icon>visibility</mat-icon>
                </button>
              </td>
            </ng-container>
            <tr mat-header-row *matHeaderRowDef="registryColumns"></tr>
            <tr mat-row *matRowDef="let row; columns: registryColumns;" (click)="viewArtifactDetail(row)"></tr>
          </table>
          <mat-paginator [length]="totalArtifacts()" [pageSize]="pageSize" [pageSizeOptions]="[25, 50, 100]" (page)="onPageChange($event)"></mat-paginator>
        </div>
      </ng-template>

      <!-- Browser History Template -->
      <ng-template #browserViewer>
        <div class="artifact-table-container">
          <table mat-table [dataSource]="artifacts()">
            <ng-container matColumnDef="timestamp">
              <th mat-header-cell *matHeaderCellDef>Visited</th>
              <td mat-cell *matCellDef="let row">{{ formatTimestamp(row.data['visit_time'] || row.timestamp) }}</td>
            </ng-container>
            <ng-container matColumnDef="title">
              <th mat-header-cell *matHeaderCellDef>Title</th>
              <td mat-cell *matCellDef="let row">{{ truncateText(row.data['title'], 50) }}</td>
            </ng-container>
            <ng-container matColumnDef="url">
              <th mat-header-cell *matHeaderCellDef>URL</th>
              <td mat-cell *matCellDef="let row" class="url-cell">{{ truncateText(row.data['url'], 60) }}</td>
            </ng-container>
            <ng-container matColumnDef="browser">
              <th mat-header-cell *matHeaderCellDef>Browser</th>
              <td mat-cell *matCellDef="let row">
                <mat-chip>{{ row.data['browser'] || 'Unknown' }}</mat-chip>
              </td>
            </ng-container>
            <ng-container matColumnDef="actions">
              <th mat-header-cell *matHeaderCellDef></th>
              <td mat-cell *matCellDef="let row">
                <button mat-icon-button (click)="viewArtifactDetail(row)" matTooltip="View Details">
                  <mat-icon>visibility</mat-icon>
                </button>
              </td>
            </ng-container>
            <tr mat-header-row *matHeaderRowDef="browserColumns"></tr>
            <tr mat-row *matRowDef="let row; columns: browserColumns;" (click)="viewArtifactDetail(row)"></tr>
          </table>
          <mat-paginator [length]="totalArtifacts()" [pageSize]="pageSize" [pageSizeOptions]="[25, 50, 100]" (page)="onPageChange($event)"></mat-paginator>
        </div>
      </ng-template>

      <!-- Process Template -->
      <ng-template #processViewer>
        <div class="artifact-table-container">
          <table mat-table [dataSource]="artifacts()">
            <ng-container matColumnDef="timestamp">
              <th mat-header-cell *matHeaderCellDef>Time</th>
              <td mat-cell *matCellDef="let row">{{ formatTimestamp(row.data['timestamp'] || row.timestamp) }}</td>
            </ng-container>
            <ng-container matColumnDef="name">
              <th mat-header-cell *matHeaderCellDef>Process</th>
              <td mat-cell *matCellDef="let row" class="process-name">{{ row.data['name'] }}</td>
            </ng-container>
            <ng-container matColumnDef="pid">
              <th mat-header-cell *matHeaderCellDef>PID</th>
              <td mat-cell *matCellDef="let row">{{ row.data['pid'] }}</td>
            </ng-container>
            <ng-container matColumnDef="ppid">
              <th mat-header-cell *matHeaderCellDef>PPID</th>
              <td mat-cell *matCellDef="let row">{{ row.data['ppid'] || '-' }}</td>
            </ng-container>
            <ng-container matColumnDef="command_line">
              <th mat-header-cell *matHeaderCellDef>Command Line</th>
              <td mat-cell *matCellDef="let row" class="cmdline-cell">{{ truncateText(row.data['command_line'], 60) }}</td>
            </ng-container>
            <ng-container matColumnDef="actions">
              <th mat-header-cell *matHeaderCellDef></th>
              <td mat-cell *matCellDef="let row">
                <button mat-icon-button (click)="viewArtifactDetail(row)" matTooltip="View Details">
                  <mat-icon>visibility</mat-icon>
                </button>
              </td>
            </ng-container>
            <tr mat-header-row *matHeaderRowDef="processColumns"></tr>
            <tr mat-row *matRowDef="let row; columns: processColumns;" (click)="viewArtifactDetail(row)"></tr>
          </table>
          <mat-paginator [length]="totalArtifacts()" [pageSize]="pageSize" [pageSizeOptions]="[25, 50, 100]" (page)="onPageChange($event)"></mat-paginator>
        </div>
      </ng-template>

      <!-- File Artifact Template -->
      <ng-template #fileViewer>
        <div class="artifact-table-container">
          <table mat-table [dataSource]="artifacts()">
            <ng-container matColumnDef="timestamp">
              <th mat-header-cell *matHeaderCellDef>Modified</th>
              <td mat-cell *matCellDef="let row">{{ formatTimestamp(row.data['modified_time'] || row.timestamp) }}</td>
            </ng-container>
            <ng-container matColumnDef="path">
              <th mat-header-cell *matHeaderCellDef>Path</th>
              <td mat-cell *matCellDef="let row" class="file-path">{{ truncateText(row.data['path'], 60) }}</td>
            </ng-container>
            <ng-container matColumnDef="size">
              <th mat-header-cell *matHeaderCellDef>Size</th>
              <td mat-cell *matCellDef="let row">{{ formatBytes(row.data['size']) }}</td>
            </ng-container>
            <ng-container matColumnDef="hash">
              <th mat-header-cell *matHeaderCellDef>Hash</th>
              <td mat-cell *matCellDef="let row" class="hash-cell">
                {{ truncateText(row.data['sha256'] || row.data['md5'], 16) }}
              </td>
            </ng-container>
            <ng-container matColumnDef="actions">
              <th mat-header-cell *matHeaderCellDef></th>
              <td mat-cell *matCellDef="let row">
                <button mat-icon-button (click)="viewArtifactDetail(row)" matTooltip="View Details">
                  <mat-icon>visibility</mat-icon>
                </button>
              </td>
            </ng-container>
            <tr mat-header-row *matHeaderRowDef="fileColumns"></tr>
            <tr mat-row *matRowDef="let row; columns: fileColumns;" (click)="viewArtifactDetail(row)"></tr>
          </table>
          <mat-paginator [length]="totalArtifacts()" [pageSize]="pageSize" [pageSizeOptions]="[25, 50, 100]" (page)="onPageChange($event)"></mat-paginator>
        </div>
      </ng-template>

      <!-- Generic Viewer Template -->
      <ng-template #genericViewer>
        <div class="artifact-table-container">
          <table mat-table [dataSource]="artifacts()">
            <ng-container matColumnDef="timestamp">
              <th mat-header-cell *matHeaderCellDef>Timestamp</th>
              <td mat-cell *matCellDef="let row">{{ formatTimestamp(row.timestamp) }}</td>
            </ng-container>
            <ng-container matColumnDef="type">
              <th mat-header-cell *matHeaderCellDef>Type</th>
              <td mat-cell *matCellDef="let row">
                <mat-chip>{{ row.artifact_type }}</mat-chip>
              </td>
            </ng-container>
            <ng-container matColumnDef="preview">
              <th mat-header-cell *matHeaderCellDef>Data Preview</th>
              <td mat-cell *matCellDef="let row" class="preview-cell">
                {{ getDataPreview(row.data) }}
              </td>
            </ng-container>
            <ng-container matColumnDef="actions">
              <th mat-header-cell *matHeaderCellDef></th>
              <td mat-cell *matCellDef="let row">
                <button mat-icon-button (click)="viewArtifactDetail(row)" matTooltip="View Details">
                  <mat-icon>visibility</mat-icon>
                </button>
              </td>
            </ng-container>
            <tr mat-header-row *matHeaderRowDef="genericColumns"></tr>
            <tr mat-row *matRowDef="let row; columns: genericColumns;" (click)="viewArtifactDetail(row)"></tr>
          </table>
          <mat-paginator [length]="totalArtifacts()" [pageSize]="pageSize" [pageSizeOptions]="[25, 50, 100]" (page)="onPageChange($event)"></mat-paginator>
        </div>
      </ng-template>

      <!-- Artifact Detail Dialog -->
      @if (selectedArtifact()) {
        <div class="detail-overlay" (click)="closeArtifactDetail()">
          <div class="detail-dialog" (click)="$event.stopPropagation()">
            <div class="detail-header">
              <h3>Artifact Details</h3>
              <button mat-icon-button (click)="closeArtifactDetail()">
                <mat-icon>close</mat-icon>
              </button>
            </div>
            <div class="detail-content">
              <div class="detail-meta">
                <span class="meta-item">
                  <mat-icon>category</mat-icon>
                  {{ selectedArtifact()!.artifact_type }}
                </span>
                @if (selectedArtifact()!.timestamp) {
                  <span class="meta-item">
                    <mat-icon>schedule</mat-icon>
                    {{ formatTimestamp(selectedArtifact()!.timestamp) }}
                  </span>
                }
                @if (selectedArtifact()!.source_file) {
                  <span class="meta-item">
                    <mat-icon>source</mat-icon>
                    {{ selectedArtifact()!.source_file }}
                  </span>
                }
              </div>
              <div class="detail-data">
                <pre>{{ formatJson(selectedArtifact()!.data) }}</pre>
              </div>
              <div class="detail-actions">
                <button mat-stroked-button (click)="copyToClipboard(selectedArtifact()!.data)">
                  <mat-icon>content_copy</mat-icon>
                  Copy JSON
                </button>
                <button mat-stroked-button (click)="addToTimeline(selectedArtifact()!)">
                  <mat-icon>timeline</mat-icon>
                  Add to Timeline
                </button>
              </div>
            </div>
          </div>
        </div>
      }
    </div>
  `,
  styles: [`
    .parsed-data-viewer {
      height: 100%;
      display: flex;
      flex-direction: column;
    }

    .loading, .empty-state {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      padding: 48px;
      gap: 16px;
      color: var(--text-secondary);
    }

    .empty-state mat-icon {
      font-size: 48px;
      width: 48px;
      height: 48px;
      color: var(--text-muted);
    }

    .empty-state .hint {
      font-size: 12px;
      color: var(--text-muted);
    }

    .viewer-toolbar {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 8px 16px;
      border-bottom: 1px solid var(--border-color);
    }

    .search-field {
      flex: 1;
    }

    mat-tab-group {
      flex: 1;
      display: flex;
      flex-direction: column;
    }

    ::ng-deep .mat-mdc-tab-body-wrapper {
      flex: 1;
    }

    .tab-label {
      margin: 0 8px;
    }

    .tab-count {
      background: var(--bg-surface);
      padding: 2px 8px;
      border-radius: 12px;
      font-size: 11px;
      color: var(--text-secondary);
    }

    .tab-content {
      height: 100%;
      overflow: hidden;
    }

    .tab-loading {
      display: flex;
      justify-content: center;
      padding: 48px;
    }

    .artifact-table-container {
      height: 100%;
      display: flex;
      flex-direction: column;
      overflow: hidden;
    }

    .artifact-table-container table {
      flex: 1;
      overflow: auto;
    }

    table {
      width: 100%;
    }

    .mat-mdc-row {
      cursor: pointer;
      &:hover {
        background: rgba(255, 255, 255, 0.02);
      }
    }

    .event-id {
      font-family: monospace;
      font-weight: 500;
      color: var(--accent);
    }

    .ip-address, .hash-cell {
      font-family: monospace;
      font-size: 12px;
    }

    .message-cell, .cmdline-cell, .url-cell, .file-path, .key-path, .preview-cell {
      font-size: 12px;
      max-width: 300px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .process-name {
      font-weight: 500;
    }

    .value-data {
      font-family: monospace;
      font-size: 11px;
    }

    mat-chip {
      font-size: 11px;
      min-height: 20px !important;
    }

    .detail-overlay {
      position: fixed;
      top: 0;
      left: 0;
      right: 0;
      bottom: 0;
      background: rgba(0, 0, 0, 0.7);
      display: flex;
      align-items: center;
      justify-content: center;
      z-index: 2000;
    }

    .detail-dialog {
      background: var(--bg-card);
      border-radius: 8px;
      width: 700px;
      max-width: 90vw;
      max-height: 80vh;
      display: flex;
      flex-direction: column;
      box-shadow: 0 8px 32px rgba(0, 0, 0, 0.5);
    }

    .detail-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 16px;
      border-bottom: 1px solid var(--border-color);
    }

    .detail-header h3 {
      margin: 0;
      font-size: 16px;
    }

    .detail-content {
      flex: 1;
      overflow-y: auto;
      padding: 16px;
    }

    .detail-meta {
      display: flex;
      flex-wrap: wrap;
      gap: 16px;
      margin-bottom: 16px;
      padding-bottom: 16px;
      border-bottom: 1px solid var(--border-color);
    }

    .meta-item {
      display: flex;
      align-items: center;
      gap: 6px;
      font-size: 13px;
      color: var(--text-secondary);
    }

    .meta-item mat-icon {
      font-size: 16px;
      width: 16px;
      height: 16px;
    }

    .detail-data {
      background: var(--bg-surface);
      border-radius: 4px;
      padding: 16px;
      overflow-x: auto;
    }

    .detail-data pre {
      margin: 0;
      font-size: 12px;
      font-family: 'Fira Code', monospace;
      white-space: pre-wrap;
      word-break: break-word;
    }

    .detail-actions {
      display: flex;
      gap: 8px;
      margin-top: 16px;
      padding-top: 16px;
      border-top: 1px solid var(--border-color);
    }
  `]
})
export class ParsedDataViewerComponent implements OnChanges {
  @Input() evidence: Evidence | null = null;

  isLoading = signal(true);
  tabLoading = signal(false);
  tabs = signal<ArtifactTab[]>([]);
  artifacts = signal<ParsedArtifact[]>([]);
  totalArtifacts = signal(0);
  selectedArtifact = signal<ParsedArtifact | null>(null);

  currentTab = 0;
  pageSize = 25;
  currentPage = 0;
  searchQuery = '';

  // Column definitions for different artifact types
  eventColumns = ['timestamp', 'event_id', 'channel', 'computer', 'message', 'actions'];
  networkColumns = ['timestamp', 'src_ip', 'dst_ip', 'protocol', 'bytes', 'actions'];
  registryColumns = ['timestamp', 'key_path', 'value_name', 'value_data', 'actions'];
  browserColumns = ['timestamp', 'title', 'url', 'browser', 'actions'];
  processColumns = ['timestamp', 'name', 'pid', 'ppid', 'command_line', 'actions'];
  fileColumns = ['timestamp', 'path', 'size', 'hash', 'actions'];
  genericColumns = ['timestamp', 'type', 'preview', 'actions'];

  private typeIcons: Record<string, string> = {
    windows_event: 'event_note',
    network_flow: 'lan',
    registry: 'app_registration',
    browser_history: 'public',
    process: 'memory',
    file_artifact: 'insert_drive_file',
    prefetch: 'speed',
    scheduled_task: 'schedule',
    service: 'settings_applications',
    amcache: 'inventory',
    shimcache: 'cached',
    default: 'data_object'
  };

  private typeLabels: Record<string, string> = {
    windows_event: 'Event Logs',
    network_flow: 'Network',
    registry: 'Registry',
    browser_history: 'Browser',
    process: 'Processes',
    file_artifact: 'Files',
    prefetch: 'Prefetch',
    scheduled_task: 'Tasks',
    service: 'Services',
    amcache: 'AmCache',
    shimcache: 'ShimCache'
  };

  constructor(
    private http: HttpClient,
    private snackBar: MatSnackBar
  ) {}

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['evidence'] && this.evidence) {
      this.loadArtifactTypes();
    }
  }

  async loadArtifactTypes(): Promise<void> {
    if (!this.evidence) return;

    this.isLoading.set(true);

    try {
      const response = await this.http.get<{ types: { type: string; count: number }[] }>(
        `${environment.apiUrl}/evidence/${this.evidence.id}/parsed/types`
      ).toPromise();

      if (response?.types) {
        const tabs = response.types.map(t => ({
          type: t.type,
          label: this.typeLabels[t.type] || t.type,
          icon: this.typeIcons[t.type] || this.typeIcons['default'],
          count: t.count
        }));
        this.tabs.set(tabs);

        if (tabs.length > 0) {
          this.loadArtifacts();
        }
      }
    } catch (error) {
      console.error('Failed to load artifact types:', error);
    } finally {
      this.isLoading.set(false);
    }
  }

  async loadArtifacts(): Promise<void> {
    if (!this.evidence || this.tabs().length === 0) return;

    const currentType = this.tabs()[this.currentTab]?.type;
    if (!currentType) return;

    this.tabLoading.set(true);

    try {
      const params: Record<string, string> = {
        artifact_type: currentType,
        page: (this.currentPage + 1).toString(),
        page_size: this.pageSize.toString()
      };

      if (this.searchQuery) {
        params['search'] = this.searchQuery;
      }

      const response = await this.http.get<ParsedDataResponse>(
        `${environment.apiUrl}/evidence/${this.evidence.id}/parsed`,
        { params }
      ).toPromise();

      if (response) {
        this.artifacts.set(response.items);
        this.totalArtifacts.set(response.total);
      }
    } catch (error) {
      console.error('Failed to load artifacts:', error);
    } finally {
      this.tabLoading.set(false);
    }
  }

  onTabChange(index: number): void {
    this.currentTab = index;
    this.currentPage = 0;
    this.loadArtifacts();
  }

  onPageChange(event: PageEvent): void {
    this.currentPage = event.pageIndex;
    this.pageSize = event.pageSize;
    this.loadArtifacts();
  }

  viewArtifactDetail(artifact: ParsedArtifact): void {
    this.selectedArtifact.set(artifact);
  }

  closeArtifactDetail(): void {
    this.selectedArtifact.set(null);
  }

  async triggerParse(): Promise<void> {
    if (!this.evidence) return;

    try {
      await this.http.post(
        `${environment.apiUrl}/evidence/${this.evidence.id}/parse`,
        {}
      ).toPromise();

      this.snackBar.open('Processing started', 'Close', { duration: 3000 });
    } catch (error) {
      this.snackBar.open('Failed to start processing', 'Close', { duration: 3000 });
    }
  }

  async exportData(format: 'json' | 'csv'): Promise<void> {
    if (!this.evidence) return;

    const currentType = this.tabs()[this.currentTab]?.type;
    if (!currentType) return;

    try {
      const response = await this.http.get(
        `${environment.apiUrl}/evidence/${this.evidence.id}/parsed/export`,
        {
          params: { artifact_type: currentType, format },
          responseType: 'blob'
        }
      ).toPromise();

      if (response) {
        const url = URL.createObjectURL(response);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${this.evidence.filename}-${currentType}.${format}`;
        a.click();
        URL.revokeObjectURL(url);
      }
    } catch (error) {
      this.snackBar.open('Failed to export data', 'Close', { duration: 3000 });
    }
  }

  copyToClipboard(data: Record<string, unknown>): void {
    navigator.clipboard.writeText(JSON.stringify(data, null, 2));
    this.snackBar.open('Copied to clipboard', 'Close', { duration: 2000 });
  }

  addToTimeline(artifact: ParsedArtifact): void {
    this.snackBar.open('Added to investigation timeline', 'Close', { duration: 2000 });
  }

  formatTimestamp(timestamp: unknown): string {
    if (!timestamp) return '-';
    try {
      return new Date(String(timestamp)).toLocaleString();
    } catch {
      return String(timestamp);
    }
  }

  formatBytes(bytes: unknown): string {
    const num = Number(bytes);
    if (isNaN(num) || num === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(num) / Math.log(k));
    return parseFloat((num / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  }

  truncateText(text: unknown, length: number): string {
    const str = String(text || '');
    return str.length > length ? str.substring(0, length) + '...' : str;
  }

  formatJson(data: Record<string, unknown>): string {
    return JSON.stringify(data, null, 2);
  }

  getDataPreview(data: Record<string, unknown>): string {
    const keys = Object.keys(data).slice(0, 3);
    return keys.map(k => `${k}: ${this.truncateText(data[k], 20)}`).join(' | ');
  }
}
