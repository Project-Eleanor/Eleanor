import { Component, Input, Output, EventEmitter } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatTableModule } from '@angular/material/table';
import { MatChipsModule } from '@angular/material/chips';
import { MatExpansionModule } from '@angular/material/expansion';
import { RuleBuilderConfig, ValidationResult, PreviewResult, CorrelationMatch } from './rule-builder.service';

@Component({
  selector: 'app-rule-preview',
  standalone: true,
  imports: [
    CommonModule,
    MatCardModule,
    MatButtonModule,
    MatIconModule,
    MatProgressSpinnerModule,
    MatTableModule,
    MatChipsModule,
    MatExpansionModule
  ],
  template: `
    <div class="rule-preview">
      <!-- Actions -->
      <div class="preview-actions">
        <button mat-raised-button (click)="validate.emit()" [disabled]="isValidating || !config">
          @if (isValidating) {
            <mat-spinner diameter="20"></mat-spinner>
          } @else {
            <mat-icon>check_circle</mat-icon>
          }
          Validate Configuration
        </button>
        <button mat-raised-button color="primary"
                (click)="preview.emit()"
                [disabled]="isPreviewing || !validationResult?.valid">
          @if (isPreviewing) {
            <mat-spinner diameter="20"></mat-spinner>
          } @else {
            <mat-icon>play_arrow</mat-icon>
          }
          Preview Matches (24h)
        </button>
      </div>

      <!-- Validation Result -->
      @if (validationResult) {
        <mat-card class="validation-result" [class.valid]="validationResult.valid" [class.invalid]="!validationResult.valid">
          <mat-card-header>
            <mat-icon mat-card-avatar>{{ validationResult.valid ? 'check_circle' : 'error' }}</mat-icon>
            <mat-card-title>{{ validationResult.valid ? 'Configuration Valid' : 'Validation Failed' }}</mat-card-title>
            <mat-card-subtitle>
              {{ validationResult.errors.length }} errors, {{ validationResult.warnings.length }} warnings
            </mat-card-subtitle>
          </mat-card-header>

          @if (validationResult.errors.length > 0 || validationResult.warnings.length > 0) {
            <mat-card-content>
              @for (error of validationResult.errors; track error.field) {
                <div class="message error">
                  <mat-icon>error</mat-icon>
                  <span><strong>{{ error.field }}:</strong> {{ error.message }}</span>
                </div>
              }
              @for (warning of validationResult.warnings; track warning.field) {
                <div class="message warning">
                  <mat-icon>warning</mat-icon>
                  <span>{{ warning.message }}</span>
                </div>
              }
            </mat-card-content>
          }
        </mat-card>
      }

      <!-- Preview Result -->
      @if (previewResult) {
        <mat-card class="preview-result">
          <mat-card-header>
            <mat-icon mat-card-avatar>insights</mat-icon>
            <mat-card-title>Preview Results</mat-card-title>
            <mat-card-subtitle>
              {{ previewResult.total_matches }} matches found in {{ previewResult.duration_ms }}ms
            </mat-card-subtitle>
          </mat-card-header>
          <mat-card-content>
            <div class="stats-row">
              <div class="stat">
                <span class="stat-value">{{ previewResult.total_matches }}</span>
                <span class="stat-label">Total Matches</span>
              </div>
              <div class="stat">
                <span class="stat-value">{{ previewResult.events_scanned | number }}</span>
                <span class="stat-label">Events Scanned</span>
              </div>
              <div class="stat">
                <span class="stat-value">{{ previewResult.duration_ms }}ms</span>
                <span class="stat-label">Duration</span>
              </div>
            </div>

            <div class="time-range">
              <mat-icon>schedule</mat-icon>
              <span>{{ previewResult.time_range_start | date:'short' }} - {{ previewResult.time_range_end | date:'short' }}</span>
            </div>

            @if (previewResult.matches.length > 0) {
              <h4>Sample Matches</h4>
              <div class="matches-list">
                @for (match of previewResult.matches.slice(0, 5); track match.entity_key) {
                  <mat-expansion-panel>
                    <mat-expansion-panel-header>
                      <mat-panel-title>
                        <span class="entity-key">{{ match.entity_key }}</span>
                      </mat-panel-title>
                      <mat-panel-description>
                        {{ match.total_events }} events
                        <span class="time-span">
                          {{ match.first_event_time | date:'shortTime' }} - {{ match.last_event_time | date:'shortTime' }}
                        </span>
                      </mat-panel-description>
                    </mat-expansion-panel-header>
                    <div class="match-details">
                      <div class="event-counts">
                        <h5>Event Counts</h5>
                        @for (item of getEventCounts(match); track item.eventId) {
                          <mat-chip>{{ item.eventId }}: {{ item.count }}</mat-chip>
                        }
                      </div>
                      <div class="sample-events">
                        <h5>Sample Events</h5>
                        @for (event of match.sample_events.slice(0, 3); track event.timestamp) {
                          <div class="sample-event">
                            <span class="event-time">{{ event.timestamp | date:'medium' }}</span>
                            <mat-chip>{{ event.event_id }}</mat-chip>
                            <pre class="event-doc">{{ event.document | json }}</pre>
                          </div>
                        }
                      </div>
                    </div>
                  </mat-expansion-panel>
                }
              </div>

              @if (previewResult.matches.length > 5) {
                <p class="more-matches">
                  ... and {{ previewResult.matches.length - 5 }} more matches
                </p>
              }
            } @else {
              <div class="no-matches">
                <mat-icon>search_off</mat-icon>
                <p>No matches found in the last 24 hours</p>
                <p class="hint">Try adjusting your conditions or time window</p>
              </div>
            }
          </mat-card-content>
        </mat-card>
      }
    </div>
  `,
  styles: [`
    .rule-preview {
      display: flex;
      flex-direction: column;
      gap: 16px;
    }

    .preview-actions {
      display: flex;
      gap: 12px;
    }

    .preview-actions button {
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .validation-result {
      &.valid {
        border-left: 4px solid #4caf50;
      }
      &.invalid {
        border-left: 4px solid #f44336;
      }
    }

    .validation-result mat-icon[mat-card-avatar] {
      color: inherit;
    }

    .validation-result.valid mat-icon[mat-card-avatar] {
      color: #4caf50;
    }

    .validation-result.invalid mat-icon[mat-card-avatar] {
      color: #f44336;
    }

    .message {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 8px 12px;
      border-radius: 4px;
      margin-bottom: 8px;
    }

    .message.error {
      background: rgba(244, 67, 54, 0.1);
      color: #f44336;
    }

    .message.warning {
      background: rgba(255, 152, 0, 0.1);
      color: #ff9800;
    }

    .message mat-icon {
      font-size: 18px;
      width: 18px;
      height: 18px;
    }

    .preview-result mat-icon[mat-card-avatar] {
      color: var(--primary-color);
    }

    .stats-row {
      display: flex;
      gap: 32px;
      margin-bottom: 16px;
    }

    .stat {
      display: flex;
      flex-direction: column;
    }

    .stat-value {
      font-size: 24px;
      font-weight: 600;
      color: var(--primary-color);
    }

    .stat-label {
      font-size: 12px;
      color: var(--text-secondary);
    }

    .time-range {
      display: flex;
      align-items: center;
      gap: 8px;
      color: var(--text-secondary);
      font-size: 13px;
      margin-bottom: 24px;
    }

    h4 {
      margin: 0 0 12px;
    }

    .matches-list {
      display: flex;
      flex-direction: column;
      gap: 8px;
    }

    .entity-key {
      font-family: monospace;
      font-size: 13px;
    }

    .time-span {
      margin-left: 12px;
      font-size: 12px;
      color: var(--text-secondary);
    }

    .match-details {
      padding: 16px 0;
    }

    .event-counts {
      margin-bottom: 16px;
    }

    .event-counts h5, .sample-events h5 {
      margin: 0 0 8px;
      font-size: 13px;
      color: var(--text-secondary);
    }

    .event-counts mat-chip {
      margin-right: 8px;
    }

    .sample-event {
      padding: 12px;
      background: var(--hover-bg);
      border-radius: 4px;
      margin-bottom: 8px;
    }

    .event-time {
      font-size: 12px;
      color: var(--text-secondary);
      margin-right: 12px;
    }

    .event-doc {
      margin-top: 8px;
      font-size: 11px;
      background: #1e1e1e;
      color: #d4d4d4;
      padding: 8px;
      border-radius: 4px;
      overflow-x: auto;
      max-height: 100px;
    }

    .more-matches {
      text-align: center;
      color: var(--text-secondary);
      margin-top: 16px;
    }

    .no-matches {
      text-align: center;
      padding: 40px;
    }

    .no-matches mat-icon {
      font-size: 48px;
      width: 48px;
      height: 48px;
      color: var(--text-secondary);
    }

    .no-matches p {
      margin: 8px 0 0;
    }

    .no-matches .hint {
      font-size: 12px;
      color: var(--text-secondary);
    }
  `]
})
export class RulePreviewComponent {
  @Input() config: RuleBuilderConfig | null = null;
  @Input() validationResult: ValidationResult | null = null;
  @Input() previewResult: PreviewResult | null = null;
  @Input() isValidating = false;
  @Input() isPreviewing = false;

  @Output() validate = new EventEmitter<void>();
  @Output() preview = new EventEmitter<void>();

  getEventCounts(match: CorrelationMatch): { eventId: string; count: number }[] {
    return Object.entries(match.event_counts).map(([eventId, count]) => ({
      eventId,
      count
    }));
  }
}
