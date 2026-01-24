import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, Router, RouterModule } from '@angular/router';
import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatTabsModule } from '@angular/material/tabs';
import { MatChipsModule } from '@angular/material/chips';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatTableModule } from '@angular/material/table';
import { MatTooltipModule } from '@angular/material/tooltip';
import { EntityService } from '../../core/api/entity.service';
import { EnrichmentService } from '../../core/api/enrichment.service';
import { EntityType, HostProfile, UserProfile, IPProfile, Entity } from '../../shared/models';

@Component({
  selector: 'app-entity-profile',
  standalone: true,
  imports: [
    CommonModule,
    RouterModule,
    MatCardModule,
    MatButtonModule,
    MatIconModule,
    MatTabsModule,
    MatChipsModule,
    MatProgressSpinnerModule,
    MatTableModule,
    MatTooltipModule
  ],
  template: `
    @if (isLoading()) {
      <div class="loading">
        <mat-spinner></mat-spinner>
      </div>
    } @else if (entity()) {
      <div class="entity-profile">
        <!-- Header -->
        <div class="profile-header">
          <button mat-icon-button (click)="goBack()">
            <mat-icon>arrow_back</mat-icon>
          </button>

          <mat-icon class="entity-icon" [class]="'type-' + entityType">
            {{ getEntityIcon() }}
          </mat-icon>

          <div class="entity-info">
            <span class="entity-type">{{ entityType | uppercase }}</span>
            <h1>{{ entityValue }}</h1>
          </div>

          <div class="header-actions">
            <button mat-stroked-button (click)="enrich()" [disabled]="isEnriching()">
              @if (isEnriching()) {
                <mat-spinner diameter="18"></mat-spinner>
              } @else {
                <mat-icon>security</mat-icon>
              }
              Enrich
            </button>
            <button mat-flat-button color="accent" routerLink="/hunting"
                    [queryParams]="{q: entityValue}">
              <mat-icon>search</mat-icon>
              Hunt
            </button>
          </div>
        </div>

        <!-- Content -->
        <div class="profile-content">
          <!-- Main Panel -->
          <main class="main-panel">
            <mat-tab-group>
              <mat-tab label="Overview">
                <div class="tab-content">
                  @if (entityType === 'host' && hostProfile()) {
                    <ng-container *ngTemplateOutlet="hostOverview"></ng-container>
                  } @else if (entityType === 'user' && userProfile()) {
                    <ng-container *ngTemplateOutlet="userOverview"></ng-container>
                  } @else if (entityType === 'ip' && ipProfile()) {
                    <ng-container *ngTemplateOutlet="ipOverview"></ng-container>
                  } @else {
                    <ng-container *ngTemplateOutlet="genericOverview"></ng-container>
                  }
                </div>
              </mat-tab>

              <mat-tab label="Related Cases ({{ relatedCases().length }})">
                <div class="tab-content">
                  @if (relatedCases().length === 0) {
                    <div class="empty">No related cases</div>
                  } @else {
                    <div class="cases-list">
                      @for (c of relatedCases(); track c.case_id) {
                        <mat-card class="case-item" [routerLink]="['/incidents', c.case_id]">
                          <span class="case-number">{{ c.case_number }}</span>
                          <span class="case-title">{{ c.title }}</span>
                        </mat-card>
                      }
                    </div>
                  }
                </div>
              </mat-tab>

              <mat-tab label="Timeline">
                <div class="tab-content">
                  <div class="empty">Timeline view coming soon</div>
                </div>
              </mat-tab>
            </mat-tab-group>
          </main>

          <!-- Enrichment Sidebar -->
          <aside class="enrichment-panel">
            <mat-card>
              <mat-card-header>
                <mat-card-title>Threat Intelligence</mat-card-title>
              </mat-card-header>
              <mat-card-content>
                @if (enrichment()) {
                  <div class="enrichment-data">
                    <div class="risk-indicator" [class]="getRiskClass(enrichment()!.summary.risk_score)">
                      <span class="score">{{ enrichment()!.summary.risk_score ?? 'N/A' }}</span>
                      <span class="label">Risk Score</span>
                    </div>

                    @if (enrichment()!.summary.category) {
                      <div class="enrichment-row">
                        <span class="key">Category</span>
                        <span class="value">{{ enrichment()!.summary.category }}</span>
                      </div>
                    }

                    <div class="enrichment-row">
                      <span class="key">Malicious</span>
                      <span class="value" [class.danger]="enrichment()!.summary.is_malicious">
                        {{ enrichment()!.summary.is_malicious ? 'Yes' : 'No' }}
                      </span>
                    </div>

                    @if (enrichment()!.summary.tags.length > 0) {
                      <div class="enrichment-tags">
                        @for (tag of enrichment()!.summary.tags; track tag) {
                          <mat-chip class="mini-chip">{{ tag }}</mat-chip>
                        }
                      </div>
                    }

                    <div class="sources-list">
                      <h4>Sources</h4>
                      @for (source of enrichment()!.sources; track source.name) {
                        <div class="source-item">
                          <span class="source-name">{{ source.name }}</span>
                          <span class="source-date">{{ source.enriched_at | date:'short' }}</span>
                        </div>
                      }
                    </div>
                  </div>
                } @else {
                  <div class="no-enrichment">
                    <mat-icon>security</mat-icon>
                    <p>No enrichment data available</p>
                    <button mat-stroked-button (click)="enrich()">
                      Enrich Now
                    </button>
                  </div>
                }
              </mat-card-content>
            </mat-card>
          </aside>
        </div>
      </div>
    }

    <!-- Templates -->
    <ng-template #hostOverview>
      <mat-card>
        <mat-card-header>
          <mat-card-title>Host Information</mat-card-title>
        </mat-card-header>
        <mat-card-content>
          <div class="info-grid">
            <div class="info-item">
              <span class="label">Hostname</span>
              <span class="value">{{ hostProfile()!.hostname }}</span>
            </div>
            <div class="info-item">
              <span class="label">OS</span>
              <span class="value">{{ hostProfile()!.os_name }} {{ hostProfile()!.os_version }}</span>
            </div>
            <div class="info-item">
              <span class="label">Domain</span>
              <span class="value">{{ hostProfile()!.domain || 'N/A' }}</span>
            </div>
            <div class="info-item">
              <span class="label">IP Addresses</span>
              <span class="value">{{ hostProfile()!.ip_addresses.join(', ') || 'N/A' }}</span>
            </div>
            <div class="info-item">
              <span class="label">Last Seen</span>
              <span class="value">{{ hostProfile()!.last_seen | date:'medium' }}</span>
            </div>
            <div class="info-item">
              <span class="label">Agent Version</span>
              <span class="value">{{ hostProfile()!.agent_version || 'N/A' }}</span>
            </div>
          </div>
        </mat-card-content>
      </mat-card>
    </ng-template>

    <ng-template #userOverview>
      <mat-card>
        <mat-card-header>
          <mat-card-title>User Information</mat-card-title>
        </mat-card-header>
        <mat-card-content>
          <div class="info-grid">
            <div class="info-item">
              <span class="label">Username</span>
              <span class="value">{{ userProfile()!.username }}</span>
            </div>
            <div class="info-item">
              <span class="label">Display Name</span>
              <span class="value">{{ userProfile()!.display_name || 'N/A' }}</span>
            </div>
            <div class="info-item">
              <span class="label">Email</span>
              <span class="value">{{ userProfile()!.email || 'N/A' }}</span>
            </div>
            <div class="info-item">
              <span class="label">Domain</span>
              <span class="value">{{ userProfile()!.domain || 'N/A' }}</span>
            </div>
            <div class="info-item">
              <span class="label">Last Logon</span>
              <span class="value">{{ userProfile()!.last_logon | date:'medium' }}</span>
            </div>
            <div class="info-item">
              <span class="label">Groups</span>
              <span class="value">{{ userProfile()!.groups.length }} groups</span>
            </div>
          </div>
        </mat-card-content>
      </mat-card>
    </ng-template>

    <ng-template #ipOverview>
      <mat-card>
        <mat-card-header>
          <mat-card-title>IP Information</mat-card-title>
        </mat-card-header>
        <mat-card-content>
          <div class="info-grid">
            <div class="info-item">
              <span class="label">IP Address</span>
              <span class="value">{{ ipProfile()!.ip_address }}</span>
            </div>
            <div class="info-item">
              <span class="label">Type</span>
              <span class="value">{{ ipProfile()!.is_private ? 'Private' : 'Public' }}</span>
            </div>
            @if (ipProfile()!.geolocation) {
              <div class="info-item">
                <span class="label">Location</span>
                <span class="value">
                  {{ ipProfile()!.geolocation!.city }}, {{ ipProfile()!.geolocation!.country }}
                </span>
              </div>
            }
            @if (ipProfile()!.asn) {
              <div class="info-item">
                <span class="label">ASN</span>
                <span class="value">{{ ipProfile()!.asn!.name }} ({{ ipProfile()!.asn!.asn }})</span>
              </div>
            }
          </div>
        </mat-card-content>
      </mat-card>
    </ng-template>

    <ng-template #genericOverview>
      <mat-card>
        <mat-card-header>
          <mat-card-title>Entity Information</mat-card-title>
        </mat-card-header>
        <mat-card-content>
          <div class="info-grid">
            <div class="info-item">
              <span class="label">Type</span>
              <span class="value">{{ entityType | titlecase }}</span>
            </div>
            <div class="info-item">
              <span class="label">Value</span>
              <span class="value">{{ entityValue }}</span>
            </div>
            @if (entity()!.first_seen) {
              <div class="info-item">
                <span class="label">First Seen</span>
                <span class="value">{{ entity()!.first_seen | date:'medium' }}</span>
              </div>
            }
            @if (entity()!.last_seen) {
              <div class="info-item">
                <span class="label">Last Seen</span>
                <span class="value">{{ entity()!.last_seen | date:'medium' }}</span>
              </div>
            }
          </div>
        </mat-card-content>
      </mat-card>
    </ng-template>
  `,
  styles: [`
    .loading {
      display: flex;
      justify-content: center;
      padding: 48px;
    }

    .entity-profile {
      max-width: 1400px;
      margin: 0 auto;
    }

    .profile-header {
      display: flex;
      align-items: center;
      gap: 16px;
      margin-bottom: 24px;
      padding-bottom: 24px;
      border-bottom: 1px solid var(--border-color);
    }

    .entity-icon {
      font-size: 48px;
      width: 48px;
      height: 48px;

      &.type-host { color: var(--info); }
      &.type-user { color: var(--success); }
      &.type-ip { color: var(--warning); }
      &.type-domain { color: var(--accent); }
    }

    .entity-info {
      flex: 1;

      .entity-type {
        font-size: 12px;
        color: var(--text-secondary);
      }

      h1 {
        margin: 4px 0 0;
        font-size: 24px;
      }
    }

    .header-actions {
      display: flex;
      gap: 8px;
    }

    .profile-content {
      display: flex;
      gap: 24px;
    }

    .main-panel {
      flex: 1;
      min-width: 0;
    }

    .tab-content {
      padding: 16px 0;
    }

    .enrichment-panel {
      width: 320px;
      flex-shrink: 0;

      mat-card {
        background: var(--bg-card);
        position: sticky;
        top: 24px;
      }
    }

    .info-grid {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 16px;
    }

    .info-item {
      display: flex;
      flex-direction: column;
      gap: 4px;

      .label {
        font-size: 12px;
        color: var(--text-secondary);
      }

      .value {
        font-weight: 500;
      }
    }

    .risk-indicator {
      display: flex;
      flex-direction: column;
      align-items: center;
      padding: 20px;
      margin-bottom: 16px;
      border-radius: 8px;

      .score {
        font-size: 32px;
        font-weight: 700;
      }

      .label {
        font-size: 12px;
        opacity: 0.8;
      }

      &.risk-high { background: var(--danger); color: white; }
      &.risk-medium { background: var(--warning); color: black; }
      &.risk-low { background: var(--success); color: black; }
      &.risk-unknown { background: var(--text-muted); color: white; }
    }

    .enrichment-row {
      display: flex;
      justify-content: space-between;
      padding: 8px 0;
      border-bottom: 1px solid var(--border-color);

      .key {
        color: var(--text-secondary);
        font-size: 13px;
      }

      .value {
        font-weight: 500;

        &.danger {
          color: var(--danger);
        }
      }
    }

    .enrichment-tags {
      display: flex;
      flex-wrap: wrap;
      gap: 4px;
      margin-top: 12px;
    }

    .mini-chip {
      font-size: 10px;
      min-height: 20px !important;
    }

    .sources-list {
      margin-top: 16px;

      h4 {
        font-size: 12px;
        color: var(--text-secondary);
        margin-bottom: 8px;
      }
    }

    .source-item {
      display: flex;
      justify-content: space-between;
      padding: 8px 0;
      font-size: 13px;

      .source-date {
        color: var(--text-secondary);
      }
    }

    .no-enrichment {
      display: flex;
      flex-direction: column;
      align-items: center;
      padding: 24px;
      text-align: center;
      color: var(--text-muted);

      mat-icon {
        font-size: 32px;
        width: 32px;
        height: 32px;
        margin-bottom: 8px;
      }

      p {
        margin: 0 0 12px;
      }
    }

    .cases-list {
      display: flex;
      flex-direction: column;
      gap: 8px;
    }

    .case-item {
      display: flex;
      gap: 12px;
      padding: 12px;
      cursor: pointer;
      background: var(--bg-card);

      &:hover {
        border-color: var(--accent);
      }

      .case-number {
        font-family: monospace;
        font-size: 12px;
        color: var(--text-secondary);
      }

      .case-title {
        font-weight: 500;
      }
    }

    .empty {
      padding: 32px;
      text-align: center;
      color: var(--text-muted);
    }
  `]
})
export class EntityProfileComponent implements OnInit {
  entityType!: EntityType;
  entityValue!: string;

  entity = signal<Entity | null>(null);
  hostProfile = signal<HostProfile | null>(null);
  userProfile = signal<UserProfile | null>(null);
  ipProfile = signal<IPProfile | null>(null);
  enrichment = signal<any>(null);
  relatedCases = signal<{ case_id: string; case_number: string; title: string }[]>([]);

  isLoading = signal(true);
  isEnriching = signal(false);

  constructor(
    private route: ActivatedRoute,
    private router: Router,
    private entityService: EntityService,
    private enrichmentService: EnrichmentService
  ) {}

  ngOnInit(): void {
    this.entityType = this.route.snapshot.paramMap.get('type') as EntityType;
    this.entityValue = decodeURIComponent(this.route.snapshot.paramMap.get('value')!);
    this.loadEntity();
  }

  private loadEntity(): void {
    this.entityService.get(this.entityType, this.entityValue).subscribe({
      next: (entity) => {
        this.entity.set(entity);
        this.isLoading.set(false);
        this.loadProfile();
        this.loadRelatedCases();
      },
      error: () => {
        this.isLoading.set(false);
      }
    });
  }

  private loadProfile(): void {
    switch (this.entityType) {
      case 'host':
        this.entityService.getHostProfile(this.entityValue).subscribe({
          next: (profile) => this.hostProfile.set(profile)
        });
        break;
      case 'user':
        this.entityService.getUserProfile(this.entityValue).subscribe({
          next: (profile) => this.userProfile.set(profile)
        });
        break;
      case 'ip':
        this.entityService.getIPProfile(this.entityValue).subscribe({
          next: (profile) => this.ipProfile.set(profile)
        });
        break;
    }
  }

  private loadRelatedCases(): void {
    this.entityService.getRelatedCases(this.entityType, this.entityValue).subscribe({
      next: (cases) => this.relatedCases.set(cases)
    });
  }

  enrich(): void {
    this.isEnriching.set(true);
    this.enrichmentService.enrich(this.entityValue, this.entityType).subscribe({
      next: (result) => {
        this.enrichment.set(result);
        this.isEnriching.set(false);
      },
      error: () => this.isEnriching.set(false)
    });
  }

  goBack(): void {
    this.router.navigate(['/entities']);
  }

  getEntityIcon(): string {
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
    return icons[this.entityType] || 'help';
  }

  getRiskClass(score: number | null): string {
    if (score === null) return 'risk-unknown';
    if (score >= 70) return 'risk-high';
    if (score >= 40) return 'risk-medium';
    return 'risk-low';
  }
}
