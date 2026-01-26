import { Component, Inject, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MAT_DIALOG_DATA, MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatTabsModule } from '@angular/material/tabs';
import { MatChipsModule } from '@angular/material/chips';
import { MatDividerModule } from '@angular/material/divider';
import { EnrichmentService, EnrichmentResult, EnrichmentSource } from '../../core/api/enrichment.service';

export interface EnrichmentDialogData {
  indicator: string;
  indicatorType?: string;
}

@Component({
  selector: 'app-enrichment-result-dialog',
  standalone: true,
  imports: [
    CommonModule,
    MatDialogModule,
    MatButtonModule,
    MatIconModule,
    MatProgressSpinnerModule,
    MatTooltipModule,
    MatTabsModule,
    MatChipsModule,
    MatDividerModule
  ],
  template: `
    <div class="dialog-header">
      <div class="header-content">
        <mat-icon class="indicator-icon">{{ getIndicatorIcon() }}</mat-icon>
        <div class="header-text">
          <h2 mat-dialog-title>Enrichment Results</h2>
          <code class="indicator-value">{{ data.indicator }}</code>
        </div>
      </div>
      <button mat-icon-button (click)="onClose()" matTooltip="Close">
        <mat-icon>close</mat-icon>
      </button>
    </div>

    <mat-dialog-content>
      @if (isLoading()) {
        <div class="loading">
          <mat-spinner diameter="40"></mat-spinner>
          <p>Enriching indicator...</p>
        </div>
      } @else if (error()) {
        <div class="error-state">
          <mat-icon>error_outline</mat-icon>
          <h3>Enrichment Failed</h3>
          <p>{{ error() }}</p>
          <button mat-stroked-button (click)="loadEnrichment()">
            <mat-icon>refresh</mat-icon>
            Retry
          </button>
        </div>
      } @else if (result()) {
        <!-- Summary Card -->
        <div class="summary-card" [class.malicious]="result()!.summary.is_malicious">
          <div class="risk-score" [class]="getRiskClass(result()!.summary.risk_score)">
            <span class="score-value">{{ result()!.summary.risk_score ?? 'N/A' }}</span>
            <span class="score-label">Risk Score</span>
          </div>
          <div class="summary-details">
            <div class="summary-row">
              <span class="summary-label">Type</span>
              <span class="summary-value type-badge">{{ result()!.indicator_type | uppercase }}</span>
            </div>
            @if (result()!.summary.category) {
              <div class="summary-row">
                <span class="summary-label">Category</span>
                <span class="summary-value">{{ result()!.summary.category }}</span>
              </div>
            }
            <div class="summary-row">
              <span class="summary-label">Status</span>
              <span class="summary-value" [class.malicious]="result()!.summary.is_malicious">
                <mat-icon>{{ result()!.summary.is_malicious ? 'dangerous' : 'verified' }}</mat-icon>
                {{ result()!.summary.is_malicious ? 'Malicious' : 'Clean' }}
              </span>
            </div>
          </div>
        </div>

        <!-- Tags -->
        @if (result()!.summary.tags.length > 0) {
          <div class="tags-section">
            <h4>Tags</h4>
            <div class="tags-list">
              @for (tag of result()!.summary.tags; track tag) {
                <mat-chip>{{ tag }}</mat-chip>
              }
            </div>
          </div>
        }

        <!-- Timeline -->
        <div class="timeline-section">
          <div class="timeline-item">
            <mat-icon>visibility</mat-icon>
            <div class="timeline-content">
              <span class="timeline-label">First Seen</span>
              <span class="timeline-value">
                {{ result()!.summary.first_seen ? (result()!.summary.first_seen | date:'medium') : 'Unknown' }}
              </span>
            </div>
          </div>
          <div class="timeline-item">
            <mat-icon>update</mat-icon>
            <div class="timeline-content">
              <span class="timeline-label">Last Seen</span>
              <span class="timeline-value">
                {{ result()!.summary.last_seen ? (result()!.summary.last_seen | date:'medium') : 'Unknown' }}
              </span>
            </div>
          </div>
        </div>

        <!-- Sources -->
        @if (result()!.sources.length > 0) {
          <mat-divider></mat-divider>
          <div class="sources-section">
            <h4>Sources ({{ result()!.sources.length }})</h4>
            <mat-tab-group>
              @for (source of result()!.sources; track source.name) {
                <mat-tab [label]="source.name">
                  <div class="source-content">
                    <div class="source-meta">
                      <span class="enriched-at">
                        Enriched: {{ source.enriched_at | date:'medium' }}
                      </span>
                    </div>
                    <div class="source-data">
                      @for (entry of getSourceEntries(source.data); track entry.key) {
                        <div class="data-row">
                          <span class="data-key">{{ entry.key }}</span>
                          <span class="data-value">{{ entry.value }}</span>
                        </div>
                      }
                    </div>
                  </div>
                </mat-tab>
              }
            </mat-tab-group>
          </div>
        }
      }
    </mat-dialog-content>

    <mat-dialog-actions align="end">
      <button mat-button (click)="copyToClipboard()">
        <mat-icon>content_copy</mat-icon>
        Copy Indicator
      </button>
      <button mat-button (click)="huntForIndicator()">
        <mat-icon>manage_search</mat-icon>
        Hunt
      </button>
      <button mat-flat-button color="primary" (click)="onClose()">Close</button>
    </mat-dialog-actions>
  `,
  styles: [`
    .dialog-header {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      padding: 16px 24px 0;
    }

    .header-content {
      display: flex;
      gap: 16px;
    }

    .indicator-icon {
      font-size: 32px;
      width: 32px;
      height: 32px;
      padding: 8px;
      border-radius: 8px;
      background: var(--bg-tertiary);
      color: var(--accent);
    }

    .header-text h2 {
      margin: 0 0 4px 0;
      font-size: 18px;
      font-weight: 600;
    }

    .indicator-value {
      font-family: 'Monaco', 'Menlo', monospace;
      font-size: 14px;
      color: var(--accent);
      background: var(--bg-tertiary);
      padding: 4px 8px;
      border-radius: 4px;
    }

    mat-dialog-content {
      min-width: 500px;
      max-width: 650px;
      min-height: 300px;
    }

    .loading {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      padding: 48px;
      gap: 16px;

      p {
        color: var(--text-secondary);
        margin: 0;
      }
    }

    .error-state {
      display: flex;
      flex-direction: column;
      align-items: center;
      padding: 48px;
      text-align: center;

      mat-icon {
        font-size: 48px;
        width: 48px;
        height: 48px;
        color: var(--danger);
        margin-bottom: 16px;
      }

      h3 {
        margin: 0 0 8px 0;
        color: var(--text-primary);
      }

      p {
        margin: 0 0 16px 0;
        color: var(--text-secondary);
      }
    }

    .summary-card {
      display: flex;
      gap: 24px;
      padding: 20px;
      background: var(--bg-tertiary);
      border-radius: 12px;
      margin-bottom: 20px;
      border: 1px solid var(--border-color);

      &.malicious {
        border-color: var(--danger);
        background: rgba(239, 68, 68, 0.05);
      }
    }

    .risk-score {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      width: 80px;
      height: 80px;
      border-radius: 50%;
      background: var(--bg-card);
      border: 3px solid var(--border-color);

      &.high {
        border-color: var(--danger);
        .score-value { color: var(--danger); }
      }
      &.medium {
        border-color: var(--warning);
        .score-value { color: var(--warning); }
      }
      &.low {
        border-color: var(--success);
        .score-value { color: var(--success); }
      }
    }

    .score-value {
      font-size: 24px;
      font-weight: 700;
    }

    .score-label {
      font-size: 10px;
      text-transform: uppercase;
      color: var(--text-muted);
    }

    .summary-details {
      flex: 1;
      display: flex;
      flex-direction: column;
      gap: 8px;
    }

    .summary-row {
      display: flex;
      justify-content: space-between;
      align-items: center;
    }

    .summary-label {
      font-size: 13px;
      color: var(--text-secondary);
    }

    .summary-value {
      font-size: 14px;
      color: var(--text-primary);
      display: flex;
      align-items: center;
      gap: 6px;

      mat-icon {
        font-size: 18px;
        width: 18px;
        height: 18px;
      }

      &.malicious {
        color: var(--danger);
      }
    }

    .type-badge {
      padding: 2px 8px;
      border-radius: 4px;
      font-size: 11px;
      font-weight: 500;
      background: var(--bg-card);
    }

    .tags-section, .sources-section {
      margin-bottom: 20px;

      h4 {
        font-size: 12px;
        font-weight: 600;
        color: var(--text-secondary);
        margin: 0 0 12px 0;
        text-transform: uppercase;
        letter-spacing: 0.5px;
      }
    }

    .tags-list {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }

    .timeline-section {
      display: flex;
      gap: 24px;
      margin-bottom: 20px;
    }

    .timeline-item {
      display: flex;
      align-items: center;
      gap: 12px;

      mat-icon {
        color: var(--text-muted);
      }
    }

    .timeline-content {
      display: flex;
      flex-direction: column;
      gap: 2px;
    }

    .timeline-label {
      font-size: 11px;
      text-transform: uppercase;
      color: var(--text-muted);
    }

    .timeline-value {
      font-size: 13px;
      color: var(--text-primary);
    }

    .source-content {
      padding: 16px 0;
    }

    .source-meta {
      margin-bottom: 16px;
    }

    .enriched-at {
      font-size: 12px;
      color: var(--text-muted);
    }

    .source-data {
      background: var(--bg-tertiary);
      border-radius: 8px;
      padding: 12px;
    }

    .data-row {
      display: flex;
      gap: 12px;
      padding: 6px 0;

      &:not(:last-child) {
        border-bottom: 1px solid var(--border-color);
      }
    }

    .data-key {
      min-width: 120px;
      font-size: 12px;
      color: var(--text-muted);
      text-transform: capitalize;
    }

    .data-value {
      font-size: 13px;
      color: var(--text-primary);
      font-family: monospace;
      word-break: break-all;
    }
  `]
})
export class EnrichmentResultDialogComponent implements OnInit {
  isLoading = signal(true);
  error = signal<string | null>(null);
  result = signal<EnrichmentResult | null>(null);

  constructor(
    @Inject(MAT_DIALOG_DATA) public data: EnrichmentDialogData,
    private dialogRef: MatDialogRef<EnrichmentResultDialogComponent>,
    private enrichmentService: EnrichmentService
  ) {}

  ngOnInit(): void {
    this.loadEnrichment();
  }

  loadEnrichment(): void {
    this.isLoading.set(true);
    this.error.set(null);

    this.enrichmentService.enrich(this.data.indicator, this.data.indicatorType).subscribe({
      next: (result) => {
        this.result.set(result);
        this.isLoading.set(false);
      },
      error: (err) => {
        this.error.set(err.error?.detail || 'Failed to enrich indicator');
        this.isLoading.set(false);
      }
    });
  }

  getIndicatorIcon(): string {
    const type = this.data.indicatorType?.toLowerCase() || this.result()?.indicator_type || '';
    const icons: Record<string, string> = {
      ip: 'router',
      domain: 'dns',
      url: 'link',
      hash: 'fingerprint',
      email: 'email'
    };
    return icons[type] || 'security';
  }

  getRiskClass(score: number | null): string {
    if (score === null) return '';
    if (score >= 70) return 'high';
    if (score >= 40) return 'medium';
    return 'low';
  }

  getSourceEntries(data: Record<string, unknown>): { key: string; value: string }[] {
    return Object.entries(data).map(([key, value]) => ({
      key: key.replace(/_/g, ' '),
      value: typeof value === 'object' ? JSON.stringify(value, null, 2) : String(value)
    }));
  }

  copyToClipboard(): void {
    navigator.clipboard.writeText(this.data.indicator);
  }

  huntForIndicator(): void {
    window.location.href = `/hunting?q=${encodeURIComponent(this.data.indicator)}`;
  }

  onClose(): void {
    this.dialogRef.close();
  }
}
