import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterModule, Router } from '@angular/router';
import { MatCardModule } from '@angular/material/card';
import { MatTableModule } from '@angular/material/table';
import { MatPaginatorModule, PageEvent } from '@angular/material/paginator';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatChipsModule } from '@angular/material/chips';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatMenuModule } from '@angular/material/menu';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { MatDividerModule } from '@angular/material/divider';
import { HttpClient } from '@angular/common/http';
import { EvidenceService } from '../../core/api/evidence.service';
import { Evidence, EvidenceType } from '../../shared/models';
import { environment } from '../../../environments/environment';

interface CustodyEvent {
  id: string;
  evidence_id: string;
  action: string;
  actor_id: string | null;
  actor_name: string | null;
  ip_address: string | null;
  user_agent: string | null;
  details: Record<string, unknown>;
  created_at: string;
}

@Component({
  selector: 'app-evidence-browser',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    RouterModule,
    MatCardModule,
    MatTableModule,
    MatPaginatorModule,
    MatButtonModule,
    MatIconModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    MatChipsModule,
    MatProgressSpinnerModule,
    MatMenuModule,
    MatTooltipModule,
    MatSnackBarModule,
    MatDividerModule
  ],
  template: `
    <div class="evidence-browser">
      <div class="page-header">
        <h1>Evidence</h1>
        <button mat-flat-button color="accent" (click)="uploadEvidence()">
          <mat-icon>upload_file</mat-icon>
          Upload Evidence
        </button>
      </div>

      <!-- Filters -->
      <mat-card class="filter-card">
        <div class="filters">
          <mat-form-field appearance="outline" class="search-field">
            <mat-icon matPrefix>search</mat-icon>
            <input matInput [(ngModel)]="searchQuery"
                   placeholder="Search evidence..."
                   (keyup.enter)="applyFilters()">
          </mat-form-field>

          <mat-form-field appearance="outline">
            <mat-label>Type</mat-label>
            <mat-select [(ngModel)]="typeFilter" (selectionChange)="applyFilters()">
              <mat-option [value]="null">All Types</mat-option>
              <mat-option value="disk_image">Disk Images</mat-option>
              <mat-option value="memory">Memory Dumps</mat-option>
              <mat-option value="logs">Logs</mat-option>
              <mat-option value="triage">Triage</mat-option>
              <mat-option value="pcap">Network Captures</mat-option>
              <mat-option value="artifact">Artifacts</mat-option>
              <mat-option value="document">Documents</mat-option>
              <mat-option value="malware">Malware Samples</mat-option>
              <mat-option value="other">Other</mat-option>
            </mat-select>
          </mat-form-field>

          <button mat-icon-button (click)="clearFilters()" matTooltip="Clear filters">
            <mat-icon>filter_alt_off</mat-icon>
          </button>
        </div>
      </mat-card>

      <!-- Evidence Table -->
      @if (isLoading()) {
        <div class="loading">
          <mat-spinner diameter="40"></mat-spinner>
        </div>
      } @else {
        <div class="table-container">
          <table mat-table [dataSource]="evidence()">
            <!-- Icon -->
            <ng-container matColumnDef="icon">
              <th mat-header-cell *matHeaderCellDef></th>
              <td mat-cell *matCellDef="let row">
                <mat-icon class="file-icon" [class]="'type-' + row.evidence_type">
                  {{ getFileIcon(row.evidence_type, row.mime_type) }}
                </mat-icon>
              </td>
            </ng-container>

            <!-- Filename -->
            <ng-container matColumnDef="filename">
              <th mat-header-cell *matHeaderCellDef>Filename</th>
              <td mat-cell *matCellDef="let row">
                <div class="file-info">
                  <span class="filename">{{ row.original_filename }}</span>
                  <span class="meta">{{ formatFileSize(row.file_size) }}</span>
                </div>
              </td>
            </ng-container>

            <!-- Type -->
            <ng-container matColumnDef="type">
              <th mat-header-cell *matHeaderCellDef>Type</th>
              <td mat-cell *matCellDef="let row">
                <mat-chip class="type-chip">{{ row.evidence_type }}</mat-chip>
              </td>
            </ng-container>

            <!-- Status -->
            <ng-container matColumnDef="status">
              <th mat-header-cell *matHeaderCellDef>Status</th>
              <td mat-cell *matCellDef="let row">
                <span class="status-badge" [class]="'status-' + row.status">
                  {{ row.status | titlecase }}
                </span>
              </td>
            </ng-container>

            <!-- Hash -->
            <ng-container matColumnDef="hash">
              <th mat-header-cell *matHeaderCellDef>SHA256</th>
              <td mat-cell *matCellDef="let row">
                <span class="hash" [matTooltip]="row.sha256">
                  {{ row.sha256?.substring(0, 16) }}...
                </span>
              </td>
            </ng-container>

            <!-- Created -->
            <ng-container matColumnDef="created">
              <th mat-header-cell *matHeaderCellDef>Uploaded</th>
              <td mat-cell *matCellDef="let row">
                {{ row.uploaded_at | date:'short' }}
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
                  <button mat-menu-item (click)="viewDetails(row)">
                    <mat-icon>visibility</mat-icon>
                    <span>View Details</span>
                  </button>
                  <button mat-menu-item (click)="downloadEvidence(row)">
                    <mat-icon>download</mat-icon>
                    <span>Download</span>
                  </button>
                  <button mat-menu-item (click)="verifyIntegrity(row)">
                    <mat-icon>verified</mat-icon>
                    <span>Verify Integrity</span>
                  </button>
                  <mat-divider></mat-divider>
                  <button mat-menu-item class="danger" (click)="deleteEvidence(row)">
                    <mat-icon>delete</mat-icon>
                    <span>Delete</span>
                  </button>
                </mat-menu>
              </td>
            </ng-container>

            <tr mat-header-row *matHeaderRowDef="displayedColumns"></tr>
            <tr mat-row *matRowDef="let row; columns: displayedColumns;"
                (click)="viewDetails(row)">
            </tr>
          </table>
        </div>

        <mat-paginator [length]="totalEvidence()"
                       [pageSize]="pageSize"
                       [pageIndex]="currentPage()"
                       [pageSizeOptions]="[20, 50, 100]"
                       (page)="onPageChange($event)">
        </mat-paginator>
      }

      <!-- Detail Panel -->
      @if (selectedEvidence()) {
        <div class="detail-panel">
          <div class="panel-header">
            <h3>Evidence Details</h3>
            <button mat-icon-button (click)="closeDetails()">
              <mat-icon>close</mat-icon>
            </button>
          </div>

          <div class="panel-content">
            <div class="detail-section">
              <h4>File Information</h4>
              <div class="detail-grid">
                <div class="detail-item">
                  <span class="label">Filename</span>
                  <span class="value">{{ selectedEvidence()!.original_filename }}</span>
                </div>
                <div class="detail-item">
                  <span class="label">Size</span>
                  <span class="value">{{ formatFileSize(selectedEvidence()!.file_size) }}</span>
                </div>
                <div class="detail-item">
                  <span class="label">Type</span>
                  <span class="value">{{ selectedEvidence()!.evidence_type }}</span>
                </div>
                <div class="detail-item">
                  <span class="label">MIME Type</span>
                  <span class="value">{{ selectedEvidence()!.mime_type || 'Unknown' }}</span>
                </div>
              </div>
            </div>

            <div class="detail-section">
              <h4>Hashes</h4>
              <div class="hash-list">
                <div class="hash-item">
                  <span class="label">MD5</span>
                  <code>{{ selectedEvidence()!.md5 || 'N/A' }}</code>
                </div>
                <div class="hash-item">
                  <span class="label">SHA1</span>
                  <code>{{ selectedEvidence()!.sha1 || 'N/A' }}</code>
                </div>
                <div class="hash-item">
                  <span class="label">SHA256</span>
                  <code>{{ selectedEvidence()!.sha256 || 'N/A' }}</code>
                </div>
              </div>
            </div>

            <div class="detail-section">
              <h4>Chain of Custody</h4>
              @if (custodyEvents().length === 0) {
                <p class="empty">No custody entries</p>
              } @else {
                <div class="custody-timeline">
                  @for (entry of custodyEvents(); track entry.id) {
                    <div class="custody-entry">
                      <div class="custody-marker"></div>
                      <div class="custody-content">
                        <div class="custody-header">
                          <span class="action">{{ entry.action | titlecase }}</span>
                          <span class="time">{{ entry.created_at | date:'medium' }}</span>
                        </div>
                        <div class="custody-user">{{ entry.actor_name || 'System' }}</div>
                      </div>
                    </div>
                  }
                </div>
              }
            </div>
          </div>
        </div>
      }
    </div>
  `,
  styles: [`
    .evidence-browser {
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

    .filter-card {
      margin-bottom: 16px;
      background: var(--bg-card);
    }

    .filters {
      display: flex;
      gap: 16px;
      align-items: center;
    }

    .search-field {
      flex: 1;
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

    .mat-mdc-row {
      cursor: pointer;

      &:hover {
        background: rgba(255, 255, 255, 0.02);
      }
    }

    .file-icon {
      font-size: 24px;
      width: 24px;
      height: 24px;
      color: var(--text-secondary);

      &.type-file { color: var(--info); }
      &.type-image { color: var(--success); }
      &.type-log { color: var(--text-secondary); }
      &.type-memory { color: var(--warning); }
      &.type-network { color: var(--accent); }
    }

    .file-info {
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

    .type-chip {
      font-size: 11px;
      min-height: 24px !important;
    }

    .status-badge {
      padding: 4px 12px;
      border-radius: 12px;
      font-size: 12px;

      &.status-pending { background: var(--text-muted); color: white; }
      &.status-uploading { background: var(--info); color: white; }
      &.status-processing { background: var(--warning); color: black; }
      &.status-ready { background: var(--success); color: black; }
      &.status-failed { background: var(--danger); color: white; }
      &.status-quarantined { background: #7c3aed; color: white; }
    }

    .hash {
      font-family: monospace;
      font-size: 12px;
      color: var(--text-secondary);
    }

    .danger {
      color: var(--danger) !important;
    }

    .detail-panel {
      position: fixed;
      top: 0;
      right: 0;
      width: 450px;
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

    .detail-section {
      margin-bottom: 24px;

      h4 {
        font-size: 12px;
        color: var(--text-secondary);
        text-transform: uppercase;
        margin-bottom: 12px;
      }
    }

    .detail-grid {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 12px;
    }

    .detail-item {
      display: flex;
      flex-direction: column;
      gap: 2px;

      .label {
        font-size: 11px;
        color: var(--text-muted);
      }

      .value {
        font-size: 13px;
      }
    }

    .hash-list {
      display: flex;
      flex-direction: column;
      gap: 8px;
    }

    .hash-item {
      .label {
        font-size: 11px;
        color: var(--text-muted);
        display: block;
        margin-bottom: 2px;
      }

      code {
        font-size: 11px;
        background: var(--bg-surface);
        padding: 4px 8px;
        border-radius: 4px;
        word-break: break-all;
      }
    }

    .custody-timeline {
      position: relative;
      padding-left: 20px;

      &::before {
        content: '';
        position: absolute;
        left: 4px;
        top: 0;
        bottom: 0;
        width: 2px;
        background: var(--border-color);
      }
    }

    .custody-entry {
      position: relative;
      padding-bottom: 16px;
    }

    .custody-marker {
      position: absolute;
      left: -20px;
      top: 4px;
      width: 10px;
      height: 10px;
      border-radius: 50%;
      background: var(--accent);
    }

    .custody-content {
      .custody-header {
        display: flex;
        justify-content: space-between;
        margin-bottom: 4px;

        .action {
          font-weight: 500;
        }

        .time {
          font-size: 11px;
          color: var(--text-secondary);
        }
      }

      .custody-user {
        font-size: 13px;
        color: var(--text-secondary);
      }

      .custody-notes {
        font-size: 12px;
        color: var(--text-muted);
        margin-top: 4px;
      }
    }

    .empty {
      color: var(--text-muted);
      font-style: italic;
    }
  `]
})
export class EvidenceBrowserComponent implements OnInit {
  displayedColumns = ['icon', 'filename', 'type', 'status', 'hash', 'created', 'actions'];

  evidence = signal<Evidence[]>([]);
  totalEvidence = signal(0);
  currentPage = signal(0);
  pageSize = 20;
  isLoading = signal(true);

  searchQuery = '';
  typeFilter: EvidenceType | null = null;

  selectedEvidence = signal<Evidence | null>(null);
  custodyEvents = signal<CustodyEvent[]>([]);

  constructor(
    private evidenceService: EvidenceService,
    private http: HttpClient,
    private router: Router,
    private snackBar: MatSnackBar
  ) {}

  ngOnInit(): void {
    this.loadEvidence();
  }

  loadEvidence(): void {
    this.isLoading.set(true);

    this.evidenceService.list({
      page: this.currentPage() + 1,
      page_size: this.pageSize,
      evidence_type: this.typeFilter || undefined,
      search: this.searchQuery || undefined
    }).subscribe({
      next: (response) => {
        this.evidence.set(response.items);
        this.totalEvidence.set(response.total);
        this.isLoading.set(false);
      },
      error: () => this.isLoading.set(false)
    });
  }

  applyFilters(): void {
    this.currentPage.set(0);
    this.loadEvidence();
  }

  clearFilters(): void {
    this.searchQuery = '';
    this.typeFilter = null;
    this.applyFilters();
  }

  onPageChange(event: PageEvent): void {
    this.currentPage.set(event.pageIndex);
    this.pageSize = event.pageSize;
    this.loadEvidence();
  }

  viewDetails(item: Evidence): void {
    this.selectedEvidence.set(item);
    this.loadCustodyEvents(item.id);
  }

  loadCustodyEvents(evidenceId: string): void {
    this.http.get<CustodyEvent[]>(`${environment.apiUrl}/evidence/${evidenceId}/custody`)
      .subscribe({
        next: (events) => this.custodyEvents.set(events),
        error: () => this.custodyEvents.set([])
      });
  }

  closeDetails(): void {
    this.selectedEvidence.set(null);
    this.custodyEvents.set([]);
  }

  uploadEvidence(): void {
    this.snackBar.open('Upload feature coming soon', 'Dismiss', { duration: 3000 });
  }

  downloadEvidence(item: Evidence): void {
    this.evidenceService.download(item.id).subscribe({
      next: (blob) => {
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = item.original_filename || item.filename;
        a.click();
        URL.revokeObjectURL(url);
      }
    });
  }

  verifyIntegrity(item: Evidence): void {
    this.evidenceService.verify(item.id).subscribe({
      next: (result) => {
        const message = result.integrity_valid ? 'Integrity verified' : 'Integrity check failed';
        this.snackBar.open(message, 'Dismiss', { duration: 3000 });
      }
    });
  }

  deleteEvidence(item: Evidence): void {
    if (confirm(`Delete ${item.original_filename}?`)) {
      this.evidenceService.delete(item.id).subscribe({
        next: () => this.loadEvidence()
      });
    }
  }

  getFileIcon(type: EvidenceType, mimeType: string | null): string {
    const icons: Record<EvidenceType, string> = {
      disk_image: 'storage',
      memory: 'memory',
      logs: 'description',
      triage: 'fact_check',
      pcap: 'lan',
      artifact: 'folder_special',
      document: 'article',
      malware: 'bug_report',
      other: 'help'
    };
    return icons[type] || 'insert_drive_file';
  }

  formatFileSize(bytes: number | null): string {
    if (bytes === null || bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  }
}
