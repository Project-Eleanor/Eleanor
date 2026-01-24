import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterModule, Router } from '@angular/router';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatChipsModule } from '@angular/material/chips';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatTableModule } from '@angular/material/table';
import { MatTooltipModule } from '@angular/material/tooltip';
import { EntityService } from '../../core/api/entity.service';
import { Entity, EntityType } from '../../shared/models';

@Component({
  selector: 'app-entity-search',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    RouterModule,
    MatCardModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    MatButtonModule,
    MatIconModule,
    MatChipsModule,
    MatProgressSpinnerModule,
    MatTableModule,
    MatTooltipModule
  ],
  template: `
    <div class="entity-search">
      <h1>Entities</h1>

      <!-- Search Bar -->
      <mat-card class="search-card">
        <div class="search-row">
          <mat-form-field appearance="outline" class="search-input">
            <mat-label>Search entities</mat-label>
            <mat-icon matPrefix>search</mat-icon>
            <input matInput [(ngModel)]="searchQuery"
                   placeholder="Hostname, IP, username, domain..."
                   (keyup.enter)="search()">
          </mat-form-field>

          <mat-form-field appearance="outline">
            <mat-label>Type</mat-label>
            <mat-select [(ngModel)]="entityType">
              <mat-option [value]="null">All Types</mat-option>
              <mat-option value="host">Hosts</mat-option>
              <mat-option value="user">Users</mat-option>
              <mat-option value="ip">IP Addresses</mat-option>
              <mat-option value="domain">Domains</mat-option>
              <mat-option value="file">Files</mat-option>
              <mat-option value="url">URLs</mat-option>
            </mat-select>
          </mat-form-field>

          <button mat-flat-button color="accent" (click)="search()">
            <mat-icon>search</mat-icon>
            Search
          </button>
        </div>

        <!-- Quick Links -->
        <div class="quick-links">
          <span class="label">Quick access:</span>
          @for (link of quickLinks; track link.type) {
            <button mat-stroked-button (click)="setType(link.type)">
              <mat-icon>{{ link.icon }}</mat-icon>
              {{ link.label }}
            </button>
          }
        </div>
      </mat-card>

      <!-- Results -->
      @if (isLoading()) {
        <div class="loading">
          <mat-spinner diameter="40"></mat-spinner>
        </div>
      } @else if (entities().length > 0) {
        <div class="results-grid">
          @for (entity of entities(); track entity.id) {
            <mat-card class="entity-card" (click)="viewEntity(entity)">
              <div class="entity-header">
                <mat-icon class="entity-icon" [class]="'type-' + entity.entity_type">
                  {{ getEntityIcon(entity.entity_type) }}
                </mat-icon>
                <div class="entity-info">
                  <span class="entity-type">{{ entity.entity_type | uppercase }}</span>
                  <h3>{{ entity.value }}</h3>
                </div>
                @if (entity.risk_score !== null) {
                  <div class="risk-score" [class]="getRiskClass(entity.risk_score)">
                    {{ entity.risk_score }}
                  </div>
                }
              </div>

              <div class="entity-meta">
                @if (entity.first_seen) {
                  <span>First seen: {{ entity.first_seen | date:'short' }}</span>
                }
                @if (entity.last_seen) {
                  <span>Last seen: {{ entity.last_seen | date:'short' }}</span>
                }
              </div>

              @if (entity.tags.length > 0) {
                <div class="entity-tags">
                  @for (tag of entity.tags.slice(0, 3); track tag) {
                    <mat-chip class="mini-chip">{{ tag }}</mat-chip>
                  }
                  @if (entity.tags.length > 3) {
                    <span class="more">+{{ entity.tags.length - 3 }}</span>
                  }
                </div>
              }

              @if (entity.related_cases.length > 0) {
                <div class="related-cases">
                  <mat-icon>folder</mat-icon>
                  {{ entity.related_cases.length }} related case(s)
                </div>
              }
            </mat-card>
          }
        </div>
      } @else if (hasSearched()) {
        <div class="empty-state">
          <mat-icon>search_off</mat-icon>
          <p>No entities found</p>
        </div>
      } @else {
        <div class="empty-state">
          <mat-icon>hub</mat-icon>
          <h3>Entity Browser</h3>
          <p>Search for hosts, users, IPs, and other entities across your environment</p>
        </div>
      }
    </div>
  `,
  styles: [`
    .entity-search {
      max-width: 1200px;
      margin: 0 auto;
    }

    h1 {
      font-size: 24px;
      margin-bottom: 24px;
    }

    .search-card {
      padding: 24px;
      margin-bottom: 24px;
      background: var(--bg-card);
    }

    .search-row {
      display: flex;
      gap: 16px;
      align-items: flex-start;
    }

    .search-input {
      flex: 1;
    }

    .quick-links {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-top: 16px;
      flex-wrap: wrap;

      .label {
        font-size: 12px;
        color: var(--text-secondary);
      }

      button {
        font-size: 12px;
      }
    }

    .loading {
      display: flex;
      justify-content: center;
      padding: 48px;
    }

    .results-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
      gap: 16px;
    }

    .entity-card {
      padding: 16px;
      cursor: pointer;
      background: var(--bg-card);
      border: 1px solid var(--border-color);
      transition: border-color 0.15s ease;

      &:hover {
        border-color: var(--accent);
      }
    }

    .entity-header {
      display: flex;
      align-items: flex-start;
      gap: 12px;
      margin-bottom: 12px;
    }

    .entity-icon {
      font-size: 32px;
      width: 32px;
      height: 32px;

      &.type-host { color: var(--info); }
      &.type-user { color: var(--success); }
      &.type-ip { color: var(--warning); }
      &.type-domain { color: var(--accent); }
      &.type-file { color: var(--text-secondary); }
    }

    .entity-info {
      flex: 1;
      min-width: 0;

      .entity-type {
        font-size: 10px;
        color: var(--text-secondary);
      }

      h3 {
        margin: 4px 0 0;
        font-size: 16px;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
    }

    .risk-score {
      width: 36px;
      height: 36px;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: 600;
      font-size: 14px;

      &.risk-high { background: var(--danger); color: white; }
      &.risk-medium { background: var(--warning); color: black; }
      &.risk-low { background: var(--success); color: black; }
    }

    .entity-meta {
      display: flex;
      gap: 16px;
      font-size: 12px;
      color: var(--text-secondary);
      margin-bottom: 12px;
    }

    .entity-tags {
      display: flex;
      gap: 4px;
      flex-wrap: wrap;
      margin-bottom: 12px;

      .more {
        font-size: 11px;
        color: var(--text-secondary);
      }
    }

    .mini-chip {
      font-size: 10px;
      min-height: 20px !important;
      padding: 2px 8px !important;
    }

    .related-cases {
      display: flex;
      align-items: center;
      gap: 4px;
      font-size: 12px;
      color: var(--text-secondary);

      mat-icon {
        font-size: 14px;
        width: 14px;
        height: 14px;
      }
    }

    .empty-state {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      padding: 64px;
      color: var(--text-muted);
      text-align: center;

      mat-icon {
        font-size: 64px;
        width: 64px;
        height: 64px;
        margin-bottom: 16px;
      }

      h3 {
        margin: 0 0 8px;
        color: var(--text-primary);
      }

      p {
        margin: 0;
        max-width: 400px;
      }
    }
  `]
})
export class EntitySearchComponent implements OnInit {
  searchQuery = '';
  entityType: EntityType | null = null;
  entities = signal<Entity[]>([]);
  isLoading = signal(false);
  hasSearched = signal(false);

  quickLinks = [
    { type: 'host' as EntityType, label: 'Hosts', icon: 'computer' },
    { type: 'user' as EntityType, label: 'Users', icon: 'person' },
    { type: 'ip' as EntityType, label: 'IPs', icon: 'language' },
    { type: 'domain' as EntityType, label: 'Domains', icon: 'dns' }
  ];

  constructor(
    private entityService: EntityService,
    private router: Router
  ) {}

  ngOnInit(): void {}

  search(): void {
    this.isLoading.set(true);
    this.hasSearched.set(true);

    this.entityService.search({
      query: this.searchQuery || undefined,
      entity_type: this.entityType || undefined,
      page_size: 50
    }).subscribe({
      next: (response) => {
        this.entities.set(response.items);
        this.isLoading.set(false);
      },
      error: () => {
        this.isLoading.set(false);
      }
    });
  }

  setType(type: EntityType): void {
    this.entityType = type;
    this.search();
  }

  viewEntity(entity: Entity): void {
    this.router.navigate(['/entities', entity.entity_type, entity.value]);
  }

  getEntityIcon(type: EntityType): string {
    const icons: Record<EntityType, string> = {
      host: 'computer',
      user: 'person',
      ip: 'language',
      domain: 'dns',
      file: 'insert_drive_file',
      process: 'memory',
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
}
