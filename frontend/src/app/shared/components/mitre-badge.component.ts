import { Component, input, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { MatTooltipModule } from '@angular/material/tooltip';

@Component({
  selector: 'app-mitre-badge',
  standalone: true,
  imports: [CommonModule, RouterModule, MatTooltipModule],
  template: `
    @if (clickable()) {
      <a class="mitre-badge"
         [class.compact]="compact()"
         [routerLink]="['/mitre']"
         [queryParams]="{technique: techniqueId()}"
         [matTooltip]="tooltip()">
        <span class="technique-id">{{ techniqueId() }}</span>
        @if (showName() && techniqueName()) {
          <span class="technique-name">{{ techniqueName() }}</span>
        }
      </a>
    } @else {
      <span class="mitre-badge"
            [class.compact]="compact()"
            [matTooltip]="tooltip()">
        <span class="technique-id">{{ techniqueId() }}</span>
        @if (showName() && techniqueName()) {
          <span class="technique-name">{{ techniqueName() }}</span>
        }
      </span>
    }
  `,
  styles: [`
    .mitre-badge {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 4px 10px;
      border-radius: 4px;
      font-size: 12px;
      background: rgba(74, 158, 255, 0.1);
      color: var(--accent);
      text-decoration: none;
      transition: all 0.2s ease;
      cursor: default;

      &:hover {
        background: rgba(74, 158, 255, 0.2);
      }

      &.compact {
        padding: 2px 6px;
        font-size: 10px;
        gap: 4px;
      }
    }

    a.mitre-badge {
      cursor: pointer;

      &:hover {
        background: rgba(74, 158, 255, 0.25);
        color: var(--accent-light);
      }
    }

    .technique-id {
      font-family: var(--font-mono);
      font-weight: 500;
    }

    .technique-name {
      color: var(--text-secondary);
      max-width: 150px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
  `]
})
export class MitreBadgeComponent {
  techniqueId = input.required<string>();
  techniqueName = input<string>();
  showName = input(false);
  compact = input(false);
  clickable = input(true);

  tooltip = computed(() => {
    const name = this.techniqueName();
    if (name) {
      return `${this.techniqueId()}: ${name}`;
    }
    return `View ${this.techniqueId()} in MITRE ATT&CK`;
  });
}
