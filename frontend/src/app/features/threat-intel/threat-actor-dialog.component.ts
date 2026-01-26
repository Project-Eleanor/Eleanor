import { Component, Inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MAT_DIALOG_DATA, MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatChipsModule } from '@angular/material/chips';
import { MatDividerModule } from '@angular/material/divider';
import { MatTooltipModule } from '@angular/material/tooltip';
import { ThreatActor } from '../../core/api/enrichment.service';

@Component({
  selector: 'app-threat-actor-dialog',
  standalone: true,
  imports: [
    CommonModule,
    MatDialogModule,
    MatButtonModule,
    MatIconModule,
    MatChipsModule,
    MatDividerModule,
    MatTooltipModule
  ],
  template: `
    <div class="dialog-header">
      <div class="header-content">
        <div class="actor-avatar">
          <mat-icon>person_search</mat-icon>
        </div>
        <div class="header-text">
          <h2 mat-dialog-title>{{ data.name }}</h2>
          @if (data.aliases.length > 0) {
            <div class="aliases">
              AKA: {{ data.aliases.join(', ') }}
            </div>
          }
        </div>
      </div>
      <button mat-icon-button (click)="onClose()" matTooltip="Close">
        <mat-icon>close</mat-icon>
      </button>
    </div>

    <mat-dialog-content>
      <!-- Key Attributes -->
      <div class="attributes-grid">
        @if (data.motivation) {
          <div class="attribute-card">
            <mat-icon>psychology</mat-icon>
            <div class="attribute-content">
              <span class="attribute-label">Motivation</span>
              <span class="attribute-value">{{ data.motivation }}</span>
            </div>
          </div>
        }

        @if (data.sophistication) {
          <div class="attribute-card">
            <mat-icon>speed</mat-icon>
            <div class="attribute-content">
              <span class="attribute-label">Sophistication</span>
              <span class="attribute-value sophistication" [class]="getSophisticationClass()">
                {{ data.sophistication }}
              </span>
            </div>
          </div>
        }

        @if (data.first_seen) {
          <div class="attribute-card">
            <mat-icon>visibility</mat-icon>
            <div class="attribute-content">
              <span class="attribute-label">First Seen</span>
              <span class="attribute-value">{{ data.first_seen | date:'mediumDate' }}</span>
            </div>
          </div>
        }

        @if (data.last_seen) {
          <div class="attribute-card">
            <mat-icon>update</mat-icon>
            <div class="attribute-content">
              <span class="attribute-label">Last Seen</span>
              <span class="attribute-value">{{ data.last_seen | date:'mediumDate' }}</span>
            </div>
          </div>
        }
      </div>

      <mat-divider></mat-divider>

      <!-- Description -->
      <div class="description-section">
        <h4>Description</h4>
        <p class="description">{{ data.description || 'No description available.' }}</p>
      </div>

      <!-- Aliases -->
      @if (data.aliases.length > 0) {
        <mat-divider></mat-divider>
        <div class="aliases-section">
          <h4>Known Aliases</h4>
          <div class="aliases-list">
            @for (alias of data.aliases; track alias) {
              <mat-chip>{{ alias }}</mat-chip>
            }
          </div>
        </div>
      }

      <!-- Activity Timeline -->
      @if (data.first_seen || data.last_seen) {
        <mat-divider></mat-divider>
        <div class="timeline-section">
          <h4>Activity Timeline</h4>
          <div class="timeline">
            <div class="timeline-bar">
              <div class="timeline-start" [matTooltip]="'First seen: ' + (data.first_seen | date:'mediumDate')">
                <mat-icon>flag</mat-icon>
              </div>
              <div class="timeline-line"></div>
              <div class="timeline-end" [matTooltip]="'Last seen: ' + (data.last_seen | date:'mediumDate')">
                <mat-icon>{{ isRecentlyActive() ? 'radio_button_checked' : 'radio_button_unchecked' }}</mat-icon>
              </div>
            </div>
            <div class="timeline-labels">
              <span>{{ data.first_seen | date:'MMM yyyy' }}</span>
              <span class="activity-status" [class.active]="isRecentlyActive()">
                {{ isRecentlyActive() ? 'Currently Active' : 'Last Active: ' + (data.last_seen | date:'MMM yyyy') }}
              </span>
            </div>
          </div>
        </div>
      }
    </mat-dialog-content>

    <mat-dialog-actions align="end">
      <button mat-button (click)="searchForActor()">
        <mat-icon>search</mat-icon>
        Search Intel
      </button>
      <button mat-button (click)="huntForActor()">
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

    .actor-avatar {
      width: 56px;
      height: 56px;
      border-radius: 50%;
      background: linear-gradient(135deg, var(--accent), #7c3aed);
      display: flex;
      align-items: center;
      justify-content: center;

      mat-icon {
        font-size: 28px;
        width: 28px;
        height: 28px;
        color: white;
      }
    }

    .header-text {
      h2 {
        margin: 0 0 4px 0;
        font-size: 22px;
        font-weight: 600;
      }
    }

    .aliases {
      font-size: 13px;
      color: var(--text-secondary);
      font-style: italic;
    }

    mat-dialog-content {
      min-width: 550px;
      max-width: 700px;
    }

    .attributes-grid {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 16px;
      padding: 20px 0;
    }

    .attribute-card {
      display: flex;
      align-items: flex-start;
      gap: 12px;
      padding: 16px;
      background: var(--bg-tertiary);
      border-radius: 8px;

      mat-icon {
        color: var(--accent);
        flex-shrink: 0;
      }
    }

    .attribute-content {
      display: flex;
      flex-direction: column;
      gap: 4px;
    }

    .attribute-label {
      font-size: 11px;
      text-transform: uppercase;
      color: var(--text-muted);
      letter-spacing: 0.5px;
    }

    .attribute-value {
      font-size: 15px;
      color: var(--text-primary);
      font-weight: 500;

      &.sophistication {
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 12px;

        &.high {
          background: var(--danger);
          color: white;
        }
        &.medium {
          background: var(--warning);
          color: black;
        }
        &.low {
          background: var(--success);
          color: black;
        }
      }
    }

    .description-section, .aliases-section, .timeline-section {
      padding: 20px 0;

      h4 {
        font-size: 12px;
        font-weight: 600;
        color: var(--text-secondary);
        margin: 0 0 12px 0;
        text-transform: uppercase;
        letter-spacing: 0.5px;
      }
    }

    .description {
      color: var(--text-primary);
      line-height: 1.7;
      margin: 0;
      font-size: 14px;
    }

    .aliases-list {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }

    .timeline {
      padding: 16px;
      background: var(--bg-tertiary);
      border-radius: 8px;
    }

    .timeline-bar {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 12px;
    }

    .timeline-start, .timeline-end {
      width: 32px;
      height: 32px;
      border-radius: 50%;
      background: var(--bg-card);
      border: 2px solid var(--accent);
      display: flex;
      align-items: center;
      justify-content: center;

      mat-icon {
        font-size: 16px;
        width: 16px;
        height: 16px;
        color: var(--accent);
      }
    }

    .timeline-line {
      flex: 1;
      height: 3px;
      background: linear-gradient(90deg, var(--accent), var(--text-muted));
      border-radius: 2px;
    }

    .timeline-labels {
      display: flex;
      justify-content: space-between;
      font-size: 12px;
      color: var(--text-secondary);
    }

    .activity-status {
      &.active {
        color: var(--success);
        font-weight: 500;
      }
    }
  `]
})
export class ThreatActorDialogComponent {
  constructor(
    @Inject(MAT_DIALOG_DATA) public data: ThreatActor,
    private dialogRef: MatDialogRef<ThreatActorDialogComponent>
  ) {}

  getSophisticationClass(): string {
    const soph = this.data.sophistication?.toLowerCase() || '';
    if (soph.includes('high') || soph.includes('advanced') || soph.includes('expert')) {
      return 'high';
    }
    if (soph.includes('medium') || soph.includes('intermediate')) {
      return 'medium';
    }
    return 'low';
  }

  isRecentlyActive(): boolean {
    if (!this.data.last_seen) return false;
    const lastSeen = new Date(this.data.last_seen);
    const sixMonthsAgo = new Date();
    sixMonthsAgo.setMonth(sixMonthsAgo.getMonth() - 6);
    return lastSeen > sixMonthsAgo;
  }

  searchForActor(): void {
    // Navigate back and search for this actor
    this.dialogRef.close({ action: 'search', query: this.data.name });
  }

  huntForActor(): void {
    window.location.href = `/hunting?q=${encodeURIComponent(this.data.name)}`;
  }

  onClose(): void {
    this.dialogRef.close();
  }
}
