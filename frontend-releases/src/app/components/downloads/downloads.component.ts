import { Component, signal, AfterViewInit, OnDestroy, OnInit, ElementRef, ViewChild, QueryList, ViewChildren, inject, PLATFORM_ID } from '@angular/core';
import { CommonModule, isPlatformBrowser } from '@angular/common';
import { gsap } from 'gsap';
import { AnimationService } from '../../services/animation.service';
import { ReleaseService, Release } from '../../services/release.service';

@Component({
  selector: 'app-downloads',
  standalone: true,
  imports: [CommonModule],
  template: `
    <section id="downloads" class="downloads section">
      <div class="container">
        <!-- Section header -->
        <div class="section-header" #sectionHeader>
          <span class="section-label">Downloads</span>
          <h2 class="section-title">Get Eleanor OVA</h2>
          <p class="section-subtitle">
            Pre-configured virtual machine images ready for VMware and VirtualBox
          </p>
        </div>

        <!-- Loading state -->
        @if (loading()) {
          <div class="loading-state">
            <div class="loading-spinner"></div>
            <p>Loading releases...</p>
          </div>
        }

        <!-- Error state -->
        @if (error()) {
          <div class="error-state">
            <span class="material-icons-round">error_outline</span>
            <p>{{ error() }}</p>
            <button class="btn btn-secondary" (click)="loadReleases()">Try Again</button>
          </div>
        }

        <!-- Coming Soon state (no releases yet) -->
        @if (!loading() && !error() && releases().length === 0) {
          <div class="coming-soon-state" #comingSoon>
            <div class="coming-soon-card">
              <div class="coming-soon-icon">
                <span class="material-icons-round">construction</span>
              </div>
              <h3 class="coming-soon-title">Coming Soon</h3>
              <p class="coming-soon-description">
                Eleanor is currently in active development. We're working hard to bring you
                a production-ready DFIR platform with pre-configured OVA images.
              </p>
              <div class="coming-soon-features">
                <div class="feature-item">
                  <span class="material-icons-round">check_circle</span>
                  <span>VMware & VirtualBox compatible</span>
                </div>
                <div class="feature-item">
                  <span class="material-icons-round">check_circle</span>
                  <span>Pre-configured with all integrations</span>
                </div>
                <div class="feature-item">
                  <span class="material-icons-round">check_circle</span>
                  <span>Ready-to-use forensics environment</span>
                </div>
              </div>
              <div class="coming-soon-actions">
                <a
                  href="https://github.com/Project-Eleanor/Eleanor"
                  class="btn btn-primary"
                  target="_blank"
                  rel="noopener"
                  (mouseenter)="onButtonEnter($event)"
                  (mousemove)="onButtonMove($event)"
                  (mouseleave)="onButtonLeave($event)"
                >
                  <span class="material-icons-round">code</span>
                  View Source on GitHub
                </a>
                <a
                  href="https://github.com/Project-Eleanor/Eleanor/stargazers"
                  class="btn btn-secondary"
                  target="_blank"
                  rel="noopener"
                  (mouseenter)="onButtonEnter($event)"
                  (mousemove)="onButtonMove($event)"
                  (mouseleave)="onButtonLeave($event)"
                >
                  <span class="material-icons-round">star</span>
                  Star to Get Notified
                </a>
              </div>
            </div>
          </div>
        }

        <!-- Release cards (shown when releases exist) -->
        <div class="releases-grid" #releasesGrid [class.hidden]="loading() || error() || releases().length === 0">
          @for (release of releases(); track release.version) {
            <div
              class="release-card"
              [class.latest]="release.isLatest"
              #releaseCard
              (mouseenter)="onCardEnter($event)"
              (mousemove)="onCardMove($event)"
              (mouseleave)="onCardLeave($event)"
            >
              @if (release.isLatest) {
                <div class="latest-badge">
                  <span class="material-icons-round">star</span>
                  Latest Release
                </div>
              }

              <div class="release-header">
                <div class="version-info">
                  <h3 class="version">{{ release.version }}</h3>
                  <span class="date">{{ release.date }}</span>
                </div>
                <span class="file-size">{{ release.size }}</span>
              </div>

              <!-- Changelog -->
              <div class="changelog">
                <h4 class="changelog-title">What's New</h4>
                <ul class="changelog-list">
                  @for (item of release.changelog; track item) {
                    <li>{{ item }}</li>
                  }
                </ul>
              </div>

              <!-- Checksum -->
              <div class="checksum">
                <div class="checksum-header">
                  <span class="checksum-label">SHA256 Checksum</span>
                  <button
                    class="copy-btn"
                    #copyBtn
                    (click)="copyChecksum(release.sha256, $event)"
                    [class.copied]="copiedHash() === release.sha256"
                  >
                    <span class="material-icons-round">
                      {{ copiedHash() === release.sha256 ? 'check' : 'content_copy' }}
                    </span>
                    {{ copiedHash() === release.sha256 ? 'Copied!' : 'Copy' }}
                  </button>
                </div>
                <code class="checksum-value">{{ release.sha256 }}</code>
              </div>

              <!-- Download buttons -->
              <div class="download-buttons">
                @if (release.assets && release.assets.length > 0) {
                  @for (asset of release.assets; track asset.name) {
                    <a
                      [href]="asset.downloadUrl"
                      class="download-btn btn"
                      [class.btn-primary]="asset.platform === 'vmware'"
                      [class.btn-secondary]="asset.platform !== 'vmware'"
                      (mouseenter)="onButtonEnter($event)"
                      (mousemove)="onButtonMove($event)"
                      (mouseleave)="onButtonLeave($event)"
                    >
                      <span class="material-icons-round">download</span>
                      {{ getPlatformLabel(asset.platform) }}
                    </a>
                  }
                } @else {
                  <a
                    [href]="getGitHubReleaseUrl(release.version)"
                    class="download-btn btn btn-primary"
                    target="_blank"
                    rel="noopener"
                    (mouseenter)="onButtonEnter($event)"
                    (mousemove)="onButtonMove($event)"
                    (mouseleave)="onButtonLeave($event)"
                  >
                    <span class="material-icons-round">open_in_new</span>
                    View on GitHub
                  </a>
                }
              </div>
            </div>
          }
        </div>

        <!-- Verification helper (only shown when releases exist) -->
        <div class="verify-section" #verifySection [class.hidden]="releases().length === 0">
          <div class="verify-card">
            <span class="material-icons-round verify-icon">verified_user</span>
            <div class="verify-content">
              <h4>Verify Your Download</h4>
              <p>Always verify the SHA256 checksum after downloading to ensure file integrity.</p>
              <div class="verify-commands">
                <div class="command-block">
                  <span class="command-label">Linux/macOS:</span>
                  <code>sha256sum eleanor-*.ova</code>
                </div>
                <div class="command-block">
                  <span class="command-label">Windows (PowerShell):</span>
                  <code>Get-FileHash eleanor-*.ova -Algorithm SHA256</code>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  `,
  styles: [`
    .downloads {
      background: var(--bg-secondary);
      position: relative;
    }

    .section-header {
      text-align: center;
      margin-bottom: 4rem;
    }

    .section-label {
      display: inline-block;
      padding: 0.375rem 0.875rem;
      background: var(--accent-glow);
      color: var(--accent);
      border-radius: 100px;
      font-size: 0.75rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      margin-bottom: 1rem;
    }

    .section-title {
      font-family: 'Syne', sans-serif;
      font-size: clamp(2rem, 5vw, 3rem);
      font-weight: 700;
      margin-bottom: 0.75rem;
    }

    .section-subtitle {
      color: var(--text-secondary);
      font-size: 1.125rem;
      max-width: 500px;
      margin: 0 auto;
    }

    // Releases grid
    .releases-grid {
      display: grid;
      gap: 2rem;
      margin-bottom: 3rem;

      @media (min-width: 768px) {
        grid-template-columns: repeat(2, 1fr);
      }
    }

    // Release card - Glassmorphism
    .release-card {
      background: rgba(15, 20, 30, 0.5);
      backdrop-filter: blur(20px) saturate(180%);
      -webkit-backdrop-filter: blur(20px) saturate(180%);
      border: 1px solid rgba(255, 255, 255, 0.08);
      border-radius: 20px;
      padding: 2rem;
      position: relative;
      box-shadow:
        0 8px 32px rgba(0, 0, 0, 0.25),
        inset 0 0 0 1px rgba(255, 255, 255, 0.05);
      transition: border-color 0.3s ease, box-shadow 0.3s ease, background 0.3s ease;
      will-change: transform;
      transform-style: preserve-3d;

      &:hover {
        background: rgba(20, 26, 40, 0.65);
        border-color: rgba(255, 255, 255, 0.12);
        box-shadow:
          0 20px 60px rgba(0, 0, 0, 0.4),
          inset 0 0 0 1px rgba(255, 255, 255, 0.08),
          0 0 40px rgba(74, 158, 255, 0.1);
      }

      &.latest {
        border-color: rgba(74, 158, 255, 0.3);
        background: rgba(15, 20, 30, 0.55);
        box-shadow:
          0 8px 32px rgba(0, 0, 0, 0.25),
          inset 0 0 0 1px rgba(74, 158, 255, 0.1),
          0 0 30px rgba(74, 158, 255, 0.08);
      }
    }

    .latest-badge {
      position: absolute;
      top: -1px;
      right: 2rem;
      display: flex;
      align-items: center;
      gap: 0.375rem;
      padding: 0.5rem 1rem;
      background: var(--accent);
      color: var(--bg-primary);
      font-size: 0.75rem;
      font-weight: 700;
      border-radius: 0 0 8px 8px;

      .material-icons-round {
        font-size: 0.875rem;
      }
    }

    .release-header {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      margin-bottom: 1.5rem;
    }

    .version {
      font-family: 'Syne', sans-serif;
      font-size: 1.5rem;
      font-weight: 700;
      margin-bottom: 0.25rem;
    }

    .date {
      color: var(--text-muted);
      font-size: 0.875rem;
    }

    .file-size {
      padding: 0.375rem 0.75rem;
      background: var(--bg-tertiary);
      border-radius: 6px;
      font-size: 0.875rem;
      font-weight: 500;
      color: var(--text-secondary);
    }

    // Changelog
    .changelog {
      margin-bottom: 1.5rem;
      padding-bottom: 1.5rem;
      border-bottom: 1px solid var(--border-subtle);
    }

    .changelog-title {
      font-size: 0.75rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: var(--text-muted);
      margin-bottom: 0.75rem;
    }

    .changelog-list {
      list-style: none;
      display: flex;
      flex-direction: column;
      gap: 0.5rem;

      li {
        position: relative;
        padding-left: 1rem;
        color: var(--text-secondary);
        font-size: 0.9375rem;

        &::before {
          content: '';
          position: absolute;
          left: 0;
          top: 0.6em;
          width: 4px;
          height: 4px;
          background: var(--accent);
          border-radius: 50%;
        }
      }
    }

    // Checksum
    .checksum {
      margin-bottom: 1.5rem;
    }

    .checksum-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 0.5rem;
    }

    .checksum-label {
      font-size: 0.75rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: var(--text-muted);
    }

    .copy-btn {
      display: inline-flex;
      align-items: center;
      gap: 0.25rem;
      padding: 0.25rem 0.625rem;
      background: transparent;
      border: 1px solid var(--border-subtle);
      border-radius: 6px;
      color: var(--text-secondary);
      font-size: 0.75rem;
      font-weight: 500;
      cursor: pointer;
      transition: all 0.2s ease;
      will-change: transform;

      .material-icons-round {
        font-size: 0.875rem;
      }

      &:hover {
        background: var(--bg-tertiary);
        border-color: var(--border-hover);
        color: var(--text-primary);
      }

      &.copied {
        background: rgba(63, 185, 80, 0.1);
        border-color: var(--success);
        color: var(--success);
      }
    }

    .checksum-value {
      display: block;
      padding: 0.75rem 1rem;
      background: var(--bg-primary);
      border: 1px solid var(--border-subtle);
      border-radius: 8px;
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.6875rem;
      color: var(--text-secondary);
      word-break: break-all;
      line-height: 1.5;
    }

    // Download buttons
    .download-buttons {
      display: flex;
      flex-direction: column;
      gap: 0.75rem;
    }

    .download-btn {
      width: 100%;
      padding: 0.875rem 1rem;
      font-size: 0.9375rem;
      justify-content: center;
      will-change: transform;

      .material-icons-round {
        font-size: 1.125rem;
      }
    }

    .btn-secondary {
      background: var(--bg-tertiary);
      border: 1px solid var(--border-subtle);
      color: var(--text-primary);

      &:hover {
        background: var(--bg-secondary);
        border-color: var(--border-hover);
      }
    }

    // Loading state
    .loading-state {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      padding: 4rem 2rem;
      gap: 1.5rem;

      p {
        color: var(--text-secondary);
        font-size: 1rem;
      }
    }

    .loading-spinner {
      width: 48px;
      height: 48px;
      border: 3px solid var(--border-subtle);
      border-top-color: var(--accent);
      border-radius: 50%;
      animation: spin 1s linear infinite;
    }

    @keyframes spin {
      to { transform: rotate(360deg); }
    }

    // Error state
    .error-state {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      padding: 4rem 2rem;
      gap: 1rem;
      text-align: center;

      .material-icons-round {
        font-size: 3rem;
        color: var(--error, #f85149);
      }

      p {
        color: var(--text-secondary);
        font-size: 1rem;
        max-width: 400px;
      }
    }

    .hidden {
      display: none;
    }

    // Coming soon state
    .coming-soon-state {
      display: flex;
      justify-content: center;
      margin-bottom: 3rem;
    }

    .coming-soon-card {
      max-width: 600px;
      width: 100%;
      background: rgba(15, 20, 30, 0.5);
      backdrop-filter: blur(24px) saturate(180%);
      -webkit-backdrop-filter: blur(24px) saturate(180%);
      border: 1px solid rgba(255, 255, 255, 0.08);
      border-radius: 24px;
      padding: 3rem 2.5rem;
      text-align: center;
      box-shadow:
        0 8px 32px rgba(0, 0, 0, 0.25),
        inset 0 0 0 1px rgba(255, 255, 255, 0.05);
    }

    .coming-soon-icon {
      width: 80px;
      height: 80px;
      margin: 0 auto 1.5rem;
      display: flex;
      align-items: center;
      justify-content: center;
      background: linear-gradient(135deg, var(--accent-glow) 0%, rgba(74, 158, 255, 0.15) 100%);
      border-radius: 20px;

      .material-icons-round {
        font-size: 2.5rem;
        color: var(--accent);
      }
    }

    .coming-soon-title {
      font-family: 'Syne', sans-serif;
      font-size: 1.75rem;
      font-weight: 700;
      margin-bottom: 0.75rem;
    }

    .coming-soon-description {
      color: var(--text-secondary);
      font-size: 1rem;
      line-height: 1.6;
      margin-bottom: 2rem;
      max-width: 450px;
      margin-left: auto;
      margin-right: auto;
    }

    .coming-soon-features {
      display: flex;
      flex-direction: column;
      gap: 0.75rem;
      margin-bottom: 2rem;
      padding: 1.5rem;
      background: var(--bg-primary);
      border-radius: 12px;
      border: 1px solid var(--border-subtle);
    }

    .feature-item {
      display: flex;
      align-items: center;
      gap: 0.75rem;
      color: var(--text-secondary);
      font-size: 0.9375rem;

      .material-icons-round {
        font-size: 1.25rem;
        color: var(--success);
      }
    }

    .coming-soon-actions {
      display: flex;
      flex-direction: column;
      gap: 0.75rem;

      @media (min-width: 480px) {
        flex-direction: row;
        justify-content: center;
      }
    }

    .coming-soon-actions .btn {
      padding: 0.875rem 1.5rem;
      justify-content: center;
      will-change: transform;
    }

    // Verify section
    .verify-section {
      margin-top: 2rem;
    }

    .verify-card {
      display: flex;
      gap: 1.5rem;
      padding: 2rem;
      background: rgba(15, 20, 30, 0.5);
      backdrop-filter: blur(20px) saturate(180%);
      -webkit-backdrop-filter: blur(20px) saturate(180%);
      border: 1px solid rgba(255, 255, 255, 0.08);
      border-radius: 16px;
      box-shadow:
        0 8px 32px rgba(0, 0, 0, 0.25),
        inset 0 0 0 1px rgba(255, 255, 255, 0.05);

      @media (max-width: 640px) {
        flex-direction: column;
        text-align: center;
      }
    }

    .verify-icon {
      font-size: 2.5rem;
      color: var(--success);
      flex-shrink: 0;
    }

    .verify-content {
      h4 {
        font-family: 'Syne', sans-serif;
        font-size: 1.125rem;
        margin-bottom: 0.5rem;
      }

      p {
        color: var(--text-secondary);
        font-size: 0.9375rem;
        margin-bottom: 1rem;
      }
    }

    .verify-commands {
      display: flex;
      flex-direction: column;
      gap: 0.75rem;
    }

    .command-block {
      display: flex;
      align-items: center;
      gap: 0.75rem;
      flex-wrap: wrap;

      @media (max-width: 640px) {
        justify-content: center;
      }
    }

    .command-label {
      font-size: 0.8125rem;
      color: var(--text-muted);
      min-width: 140px;

      @media (max-width: 640px) {
        min-width: auto;
      }
    }

    .command-block code {
      padding: 0.5rem 0.875rem;
      background: var(--bg-primary);
      border: 1px solid var(--border-subtle);
      border-radius: 6px;
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.8125rem;
      color: var(--accent);
    }
  `]
})
export class DownloadsComponent implements OnInit, AfterViewInit, OnDestroy {
  @ViewChild('sectionHeader') sectionHeader!: ElementRef<HTMLElement>;
  @ViewChild('releasesGrid') releasesGrid!: ElementRef<HTMLElement>;
  @ViewChild('verifySection') verifySection!: ElementRef<HTMLElement>;
  @ViewChildren('releaseCard') releaseCards!: QueryList<ElementRef<HTMLElement>>;

  private animationService = inject(AnimationService);
  private releaseService = inject(ReleaseService);
  private platformId = inject(PLATFORM_ID);
  private isMobile = false;

  copiedHash = signal<string | null>(null);
  loading = signal<boolean>(true);
  error = signal<string | null>(null);
  releases = signal<Release[]>([]);

  ngOnInit(): void {
    this.loadReleases();
  }

  loadReleases(): void {
    this.loading.set(true);
    this.error.set(null);

    this.releaseService.getReleases().subscribe({
      next: (releases) => {
        this.releases.set(releases);
        this.loading.set(false);
      },
      error: (err) => {
        console.error('Failed to load releases:', err);
        this.error.set('Failed to load releases. Please try again later.');
        this.loading.set(false);
      }
    });
  }

  ngAfterViewInit(): void {
    if (!isPlatformBrowser(this.platformId)) return;

    this.isMobile = window.matchMedia('(max-width: 768px)').matches || 'ontouchstart' in window;

    // Small delay to ensure DOM is ready
    setTimeout(() => this.initScrollAnimations(), 100);
  }

  ngOnDestroy(): void {
    this.animationService.killAll();
  }

  private initScrollAnimations(): void {
    // Section header reveal
    const headerElements = this.sectionHeader.nativeElement.children;
    gsap.from(headerElements, {
      scrollTrigger: {
        trigger: this.sectionHeader.nativeElement,
        start: 'top 80%'
      },
      y: 60,
      opacity: 0,
      duration: 0.8,
      stagger: 0.15,
      ease: 'power3.out'
    });

    // Staggered card entrance
    const cards = this.releasesGrid.nativeElement.querySelectorAll('.release-card');
    gsap.from(cards, {
      scrollTrigger: {
        trigger: this.releasesGrid.nativeElement,
        start: 'top 75%'
      },
      y: 80,
      opacity: 0,
      duration: 0.7,
      stagger: 0.2,
      ease: 'power2.out'
    });

    // Verify section reveal
    gsap.from(this.verifySection.nativeElement, {
      scrollTrigger: {
        trigger: this.verifySection.nativeElement,
        start: 'top 85%'
      },
      y: 50,
      opacity: 0,
      duration: 0.7,
      ease: 'power2.out'
    });
  }

  // Card 3D tilt effect
  onCardEnter(event: MouseEvent): void {
    if (this.isMobile) return;
    const target = event.currentTarget as HTMLElement;
    gsap.to(target, {
      y: -8,
      duration: 0.3,
      ease: 'power2.out'
    });
  }

  onCardMove(event: MouseEvent): void {
    if (this.isMobile) return;
    const target = event.currentTarget as HTMLElement;
    this.animationService.cardTilt(target, event);
  }

  onCardLeave(event: MouseEvent): void {
    if (this.isMobile) return;
    const target = event.currentTarget as HTMLElement;
    gsap.to(target, {
      y: 0,
      rotateX: 0,
      rotateY: 0,
      duration: 0.5,
      ease: 'power2.out'
    });
  }

  // Button magnetic effect
  onButtonEnter(event: MouseEvent): void {
    if (this.isMobile) return;
    const target = event.currentTarget as HTMLElement;
    this.animationService.buttonHover(target, true);
  }

  onButtonMove(event: MouseEvent): void {
    if (this.isMobile) return;
    const target = event.currentTarget as HTMLElement;
    this.animationService.magneticMove(target, event, 0.15);
  }

  onButtonLeave(event: MouseEvent): void {
    if (this.isMobile) return;
    const target = event.currentTarget as HTMLElement;
    this.animationService.magneticReset(target);
    this.animationService.buttonHover(target, false);
  }

  async copyChecksum(hash: string, event: Event): Promise<void> {
    try {
      await navigator.clipboard.writeText(hash);

      // Animate the copy button
      const button = event.currentTarget as HTMLElement;
      this.animationService.copySuccess(button);

      this.copiedHash.set(hash);
      setTimeout(() => this.copiedHash.set(null), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  }

  getPlatformLabel(platform: string): string {
    switch (platform) {
      case 'vmware': return 'VMware OVA';
      case 'virtualbox': return 'VirtualBox OVA';
      default: return 'Download OVA';
    }
  }

  getGitHubReleaseUrl(version: string): string {
    return `https://github.com/Project-Eleanor/Eleanor/releases/tag/${version}`;
  }
}
