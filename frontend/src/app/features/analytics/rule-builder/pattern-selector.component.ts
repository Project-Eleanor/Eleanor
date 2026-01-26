import { Component, Input, Output, EventEmitter } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MatCardModule } from '@angular/material/card';
import { MatIconModule } from '@angular/material/icon';
import { MatChipsModule } from '@angular/material/chips';
import { MatTooltipModule } from '@angular/material/tooltip';
import { PatternDefinition } from './rule-builder.service';

@Component({
  selector: 'app-pattern-selector',
  standalone: true,
  imports: [
    CommonModule,
    MatCardModule,
    MatIconModule,
    MatChipsModule,
    MatTooltipModule
  ],
  template: `
    <div class="pattern-selector">
      <p class="selector-hint">Select a correlation pattern for your detection rule</p>
      <div class="patterns-grid">
        @for (pattern of patterns; track pattern.type) {
          <mat-card
            class="pattern-card"
            [class.selected]="selected?.type === pattern.type"
            (click)="selectPattern(pattern)">
            <mat-card-header>
              <mat-icon mat-card-avatar [class]="'pattern-icon-' + pattern.type">
                {{ getPatternIcon(pattern.type) }}
              </mat-icon>
              <mat-card-title>{{ pattern.name }}</mat-card-title>
            </mat-card-header>
            <mat-card-content>
              <p class="pattern-description">{{ pattern.description }}</p>
              <div class="use-cases">
                <span class="use-case-label">Use cases:</span>
                <ul>
                  @for (useCase of pattern.use_cases.slice(0, 2); track useCase) {
                    <li>{{ useCase }}</li>
                  }
                </ul>
              </div>
            </mat-card-content>
            @if (selected?.type === pattern.type) {
              <div class="selected-indicator">
                <mat-icon>check_circle</mat-icon>
              </div>
            }
          </mat-card>
        }
      </div>
    </div>
  `,
  styles: [`
    .pattern-selector {
      padding: 16px 0;
    }

    .selector-hint {
      color: var(--text-secondary);
      margin-bottom: 16px;
    }

    .patterns-grid {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 16px;
    }

    .pattern-card {
      cursor: pointer;
      transition: all 0.2s ease;
      position: relative;
      border: 2px solid transparent;
    }

    .pattern-card:hover {
      border-color: var(--primary-color);
      transform: translateY(-2px);
    }

    .pattern-card.selected {
      border-color: var(--primary-color);
      background: rgba(var(--primary-rgb), 0.05);
    }

    .pattern-icon-sequence { color: #2196f3; }
    .pattern-icon-temporal_join { color: #9c27b0; }
    .pattern-icon-aggregation { color: #ff9800; }
    .pattern-icon-spike { color: #f44336; }

    .pattern-description {
      font-size: 13px;
      color: var(--text-secondary);
      margin-bottom: 12px;
    }

    .use-cases {
      font-size: 12px;
    }

    .use-case-label {
      color: var(--text-secondary);
      font-weight: 500;
    }

    .use-cases ul {
      margin: 4px 0 0;
      padding-left: 20px;
    }

    .use-cases li {
      margin-bottom: 2px;
    }

    .selected-indicator {
      position: absolute;
      top: 12px;
      right: 12px;
      color: var(--primary-color);
    }

    @media (max-width: 768px) {
      .patterns-grid {
        grid-template-columns: 1fr;
      }
    }
  `]
})
export class PatternSelectorComponent {
  @Input() patterns: PatternDefinition[] = [];
  @Input() selected: PatternDefinition | null = null;
  @Output() patternSelected = new EventEmitter<PatternDefinition>();

  selectPattern(pattern: PatternDefinition) {
    this.patternSelected.emit(pattern);
  }

  getPatternIcon(type: string): string {
    const icons: Record<string, string> = {
      'sequence': 'timeline',
      'temporal_join': 'merge',
      'aggregation': 'bar_chart',
      'spike': 'trending_up'
    };
    return icons[type] || 'rule';
  }
}
