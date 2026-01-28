import { Component, AfterViewInit, OnDestroy, ElementRef, ViewChild, inject, PLATFORM_ID } from '@angular/core';
import { CommonModule, isPlatformBrowser } from '@angular/common';
import { gsap } from 'gsap';
import { AnimationService } from '../../services/animation.service';

@Component({
  selector: 'app-requirements',
  standalone: true,
  imports: [CommonModule],
  template: `
    <section id="requirements" class="requirements section">
      <div class="container">
        <!-- Section header -->
        <div class="section-header" #sectionHeader>
          <span class="section-label">System Requirements</span>
          <h2 class="section-title">Hardware & Software</h2>
          <p class="section-subtitle">
            Ensure your system meets these requirements for optimal performance
          </p>
        </div>

        <!-- Requirements grid -->
        <div class="requirements-grid" #requirementsGrid>
          <!-- Minimum specs -->
          <div
            class="spec-card"
            #specCardMin
            (mouseenter)="onCardEnter($event)"
            (mousemove)="onCardMove($event)"
            (mouseleave)="onCardLeave($event)"
          >
            <div class="spec-header">
              <span class="material-icons-round spec-icon">memory</span>
              <div>
                <h3 class="spec-title">Minimum</h3>
                <span class="spec-subtitle">Basic functionality</span>
              </div>
            </div>
            <ul class="spec-list">
              <li>
                <span class="spec-label">CPU</span>
                <span class="spec-value">4 cores</span>
              </li>
              <li>
                <span class="spec-label">RAM</span>
                <span class="spec-value">16 GB</span>
              </li>
              <li>
                <span class="spec-label">Storage</span>
                <span class="spec-value">100 GB SSD</span>
              </li>
              <li>
                <span class="spec-label">Network</span>
                <span class="spec-value">1 Gbps</span>
              </li>
            </ul>
          </div>

          <!-- Recommended specs -->
          <div
            class="spec-card recommended"
            #specCardRec
            (mouseenter)="onCardEnter($event)"
            (mousemove)="onCardMove($event)"
            (mouseleave)="onCardLeave($event)"
          >
            <div class="recommended-badge">Recommended</div>
            <div class="spec-header">
              <span class="material-icons-round spec-icon">rocket_launch</span>
              <div>
                <h3 class="spec-title">Recommended</h3>
                <span class="spec-subtitle">Optimal performance</span>
              </div>
            </div>
            <ul class="spec-list">
              <li>
                <span class="spec-label">CPU</span>
                <span class="spec-value">8+ cores</span>
              </li>
              <li>
                <span class="spec-label">RAM</span>
                <span class="spec-value">32 GB+</span>
              </li>
              <li>
                <span class="spec-label">Storage</span>
                <span class="spec-value">500 GB NVMe</span>
              </li>
              <li>
                <span class="spec-label">Network</span>
                <span class="spec-value">10 Gbps</span>
              </li>
            </ul>
          </div>
        </div>

        <!-- Compatibility cards -->
        <div class="compatibility-section" #compatSection>
          <h3 class="compatibility-title">Hypervisor Compatibility</h3>
          <div class="compatibility-grid" #compatGrid>
            <div
              class="compat-card"
              (mouseenter)="onCompatEnter($event)"
              (mouseleave)="onCompatLeave($event)"
            >
              <div class="compat-icon vmware"></div>
              <div class="compat-info">
                <h4>VMware</h4>
                <p>Workstation Pro 17+, ESXi 7.0+, Fusion 13+</p>
              </div>
              <span class="compat-status supported">
                <span class="material-icons-round">check_circle</span>
                Fully Supported
              </span>
            </div>

            <div
              class="compat-card"
              (mouseenter)="onCompatEnter($event)"
              (mouseleave)="onCompatLeave($event)"
            >
              <div class="compat-icon virtualbox"></div>
              <div class="compat-info">
                <h4>VirtualBox</h4>
                <p>Version 7.0+ with Extension Pack</p>
              </div>
              <span class="compat-status supported">
                <span class="material-icons-round">check_circle</span>
                Fully Supported
              </span>
            </div>

            <div
              class="compat-card"
              (mouseenter)="onCompatEnter($event)"
              (mouseleave)="onCompatLeave($event)"
            >
              <div class="compat-icon proxmox"></div>
              <div class="compat-info">
                <h4>Proxmox VE</h4>
                <p>Version 8.0+ (convert OVA to qcow2)</p>
              </div>
              <span class="compat-status community">
                <span class="material-icons-round">groups</span>
                Community Tested
              </span>
            </div>
          </div>
        </div>

        <!-- Documentation links -->
        <div class="docs-section" #docsSection>
          <h3 class="docs-title">Documentation</h3>
          <div class="docs-grid" #docsGrid>
            <a
              href="#"
              class="doc-card"
              (mouseenter)="onDocEnter($event)"
              (mouseleave)="onDocLeave($event)"
            >
              <span class="material-icons-round doc-icon">menu_book</span>
              <div>
                <h4>Installation Guide</h4>
                <p>Step-by-step setup instructions</p>
              </div>
              <span class="material-icons-round arrow">arrow_forward</span>
            </a>

            <a
              href="#"
              class="doc-card"
              (mouseenter)="onDocEnter($event)"
              (mouseleave)="onDocLeave($event)"
            >
              <span class="material-icons-round doc-icon">play_circle</span>
              <div>
                <h4>Quick Start</h4>
                <p>Get running in minutes</p>
              </div>
              <span class="material-icons-round arrow">arrow_forward</span>
            </a>

            <a
              href="#"
              class="doc-card"
              (mouseenter)="onDocEnter($event)"
              (mouseleave)="onDocLeave($event)"
            >
              <span class="material-icons-round doc-icon">description</span>
              <div>
                <h4>Release Notes</h4>
                <p>Full changelog & updates</p>
              </div>
              <span class="material-icons-round arrow">arrow_forward</span>
            </a>

            <a
              href="#"
              class="doc-card"
              (mouseenter)="onDocEnter($event)"
              (mouseleave)="onDocLeave($event)"
            >
              <span class="material-icons-round doc-icon">help</span>
              <div>
                <h4>Troubleshooting</h4>
                <p>Common issues & solutions</p>
              </div>
              <span class="material-icons-round arrow">arrow_forward</span>
            </a>
          </div>
        </div>
      </div>
    </section>
  `,
  styles: [`
    .requirements {
      background: var(--bg-primary);
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

    // Requirements grid
    .requirements-grid {
      display: grid;
      gap: 2rem;
      margin-bottom: 4rem;

      @media (min-width: 768px) {
        grid-template-columns: repeat(2, 1fr);
      }
    }

    // Spec card - Glassmorphism
    .spec-card {
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
          0 20px 60px rgba(0, 0, 0, 0.35),
          inset 0 0 0 1px rgba(255, 255, 255, 0.08),
          0 0 30px rgba(74, 158, 255, 0.1);
      }

      &.recommended {
        border-color: rgba(74, 158, 255, 0.3);
        background: rgba(15, 20, 30, 0.55);
        box-shadow:
          0 8px 32px rgba(0, 0, 0, 0.25),
          inset 0 0 0 1px rgba(74, 158, 255, 0.1),
          0 0 30px rgba(74, 158, 255, 0.08);
      }
    }

    .recommended-badge {
      position: absolute;
      top: -1px;
      right: 2rem;
      padding: 0.5rem 1rem;
      background: var(--accent);
      color: var(--bg-primary);
      font-size: 0.75rem;
      font-weight: 700;
      border-radius: 0 0 8px 8px;
    }

    .spec-header {
      display: flex;
      align-items: center;
      gap: 1rem;
      margin-bottom: 1.5rem;
    }

    .spec-icon {
      font-size: 2.5rem;
      color: var(--accent);
    }

    .spec-title {
      font-family: 'Syne', sans-serif;
      font-size: 1.25rem;
      font-weight: 700;
      margin-bottom: 0.125rem;
    }

    .spec-subtitle {
      font-size: 0.875rem;
      color: var(--text-muted);
    }

    .spec-list {
      list-style: none;
      display: flex;
      flex-direction: column;
      gap: 0.875rem;

      li {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 0.75rem 1rem;
        background: var(--bg-primary);
        border-radius: 8px;
      }
    }

    .spec-label {
      color: var(--text-secondary);
      font-size: 0.9375rem;
    }

    .spec-value {
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.9375rem;
      font-weight: 500;
      color: var(--text-primary);
    }

    // Compatibility section
    .compatibility-section {
      margin-bottom: 4rem;
    }

    .compatibility-title {
      font-family: 'Syne', sans-serif;
      font-size: 1.5rem;
      font-weight: 700;
      margin-bottom: 1.5rem;
      text-align: center;
    }

    .compatibility-grid {
      display: grid;
      gap: 1.5rem;

      @media (min-width: 768px) {
        grid-template-columns: repeat(3, 1fr);
      }
    }

    .compat-card {
      display: flex;
      flex-direction: column;
      align-items: center;
      text-align: center;
      padding: 2rem 1.5rem;
      background: rgba(15, 20, 30, 0.5);
      backdrop-filter: blur(20px) saturate(180%);
      -webkit-backdrop-filter: blur(20px) saturate(180%);
      border: 1px solid rgba(255, 255, 255, 0.08);
      border-radius: 16px;
      box-shadow:
        0 8px 32px rgba(0, 0, 0, 0.25),
        inset 0 0 0 1px rgba(255, 255, 255, 0.05);
      transition: border-color 0.3s ease, transform 0.3s ease, box-shadow 0.3s ease, background 0.3s ease;
      will-change: transform;

      &:hover {
        background: rgba(20, 26, 40, 0.65);
        border-color: rgba(255, 255, 255, 0.12);
        box-shadow:
          0 12px 40px rgba(0, 0, 0, 0.35),
          inset 0 0 0 1px rgba(255, 255, 255, 0.08),
          0 0 20px rgba(74, 158, 255, 0.1);
      }
    }

    .compat-icon {
      width: 64px;
      height: 64px;
      margin-bottom: 1rem;
      background-size: contain;
      background-repeat: no-repeat;
      background-position: center;
      opacity: 0.9;

      &.vmware {
        background-color: var(--text-secondary);
        mask-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath d='M3.))6 7.2c-.3.4-.6 1.1-.6 1.8 0 1.4.7 2.3 1.6 3.1l4.5 3.9c.8.7 1.3 1.2 1.3 2.1 0 .8-.5 1.4-1.4 1.4-.8 0-1.3-.5-1.7-1.1l-1.5 1c.6 1 1.7 1.8 3.2 1.8 1.9 0 3.2-1.2 3.2-3 0-1.4-.7-2.2-1.6-3l-4.5-3.9c-.7-.6-1.3-1.2-1.3-2.1 0-.7.4-1.3 1.2-1.3.7 0 1.1.4 1.4 1l1.5-1c-.5-.9-1.5-1.7-2.9-1.7-1.6.1-2.9 1.1-2.9 2.8zm8.4-1.1v11.8h1.8V6.1h-1.8zm4.4 0l3.6 11.8h1.9l3.6-11.8h-1.9l-2.6 9.1-2.6-9.1h-2z'/%3E%3C/svg%3E");
        -webkit-mask-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath d='M3.6 7.2c-.3.4-.6 1.1-.6 1.8 0 1.4.7 2.3 1.6 3.1l4.5 3.9c.8.7 1.3 1.2 1.3 2.1 0 .8-.5 1.4-1.4 1.4-.8 0-1.3-.5-1.7-1.1l-1.5 1c.6 1 1.7 1.8 3.2 1.8 1.9 0 3.2-1.2 3.2-3 0-1.4-.7-2.2-1.6-3l-4.5-3.9c-.7-.6-1.3-1.2-1.3-2.1 0-.7.4-1.3 1.2-1.3.7 0 1.1.4 1.4 1l1.5-1c-.5-.9-1.5-1.7-2.9-1.7-1.6.1-2.9 1.1-2.9 2.8zm8.4-1.1v11.8h1.8V6.1h-1.8zm4.4 0l3.6 11.8h1.9l3.6-11.8h-1.9l-2.6 9.1-2.6-9.1h-2z'/%3E%3C/svg%3E");
      }

      &.virtualbox {
        background-color: var(--text-secondary);
        mask-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath d='M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z'/%3E%3C/svg%3E");
        -webkit-mask-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath d='M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z'/%3E%3C/svg%3E");
      }

      &.proxmox {
        background-color: var(--text-secondary);
        mask-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath d='M21 16.5c0 .38-.21.71-.53.88l-7.9 4.44c-.16.12-.36.18-.57.18-.21 0-.41-.06-.57-.18l-7.9-4.44A.991.991 0 0 1 3 16.5v-9c0-.38.21-.71.53-.88l7.9-4.44c.16-.12.36-.18.57-.18.21 0 .41.06.57.18l7.9 4.44c.32.17.53.5.53.88v9zM12 4.15L6.04 7.5 12 10.85l5.96-3.35L12 4.15zM5 15.91l6 3.38v-6.71L5 9.21v6.7zm14 0v-6.7l-6 3.37v6.71l6-3.38z'/%3E%3C/svg%3E");
        -webkit-mask-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath d='M21 16.5c0 .38-.21.71-.53.88l-7.9 4.44c-.16.12-.36.18-.57.18-.21 0-.41-.06-.57-.18l-7.9-4.44A.991.991 0 0 1 3 16.5v-9c0-.38.21-.71.53-.88l7.9-4.44c.16-.12.36-.18.57-.18.21 0 .41.06.57.18l7.9 4.44c.32.17.53.5.53.88v9zM12 4.15L6.04 7.5 12 10.85l5.96-3.35L12 4.15zM5 15.91l6 3.38v-6.71L5 9.21v6.7zm14 0v-6.7l-6 3.37v6.71l6-3.38z'/%3E%3C/svg%3E");
      }
    }

    .compat-info {
      margin-bottom: 1rem;

      h4 {
        font-family: 'Syne', sans-serif;
        font-size: 1.125rem;
        font-weight: 600;
        margin-bottom: 0.25rem;
      }

      p {
        font-size: 0.8125rem;
        color: var(--text-muted);
      }
    }

    .compat-status {
      display: inline-flex;
      align-items: center;
      gap: 0.375rem;
      padding: 0.375rem 0.75rem;
      border-radius: 100px;
      font-size: 0.75rem;
      font-weight: 600;

      .material-icons-round {
        font-size: 0.875rem;
      }

      &.supported {
        background: rgba(63, 185, 80, 0.1);
        color: var(--success);
      }

      &.community {
        background: rgba(210, 153, 34, 0.1);
        color: var(--warning);
      }
    }

    // Documentation section
    .docs-section {
      margin-top: 4rem;
    }

    .docs-title {
      font-family: 'Syne', sans-serif;
      font-size: 1.5rem;
      font-weight: 700;
      margin-bottom: 1.5rem;
      text-align: center;
    }

    .docs-grid {
      display: grid;
      gap: 1rem;

      @media (min-width: 768px) {
        grid-template-columns: repeat(2, 1fr);
      }

      @media (min-width: 1024px) {
        grid-template-columns: repeat(4, 1fr);
      }
    }

    .doc-card {
      display: flex;
      align-items: center;
      gap: 1rem;
      padding: 1.25rem 1.5rem;
      background: rgba(15, 20, 30, 0.5);
      backdrop-filter: blur(16px) saturate(180%);
      -webkit-backdrop-filter: blur(16px) saturate(180%);
      border: 1px solid rgba(255, 255, 255, 0.08);
      border-radius: 12px;
      text-decoration: none;
      color: inherit;
      box-shadow:
        0 4px 20px rgba(0, 0, 0, 0.2),
        inset 0 0 0 1px rgba(255, 255, 255, 0.03);
      transition: border-color 0.3s ease, background 0.3s ease, box-shadow 0.3s ease;
      will-change: transform;

      &:hover {
        background: rgba(20, 26, 40, 0.65);
        border-color: rgba(255, 255, 255, 0.12);
        box-shadow:
          0 8px 30px rgba(0, 0, 0, 0.3),
          inset 0 0 0 1px rgba(255, 255, 255, 0.05),
          0 0 20px rgba(74, 158, 255, 0.08);
      }

      @media (max-width: 767px) {
        padding: 1rem 1.25rem;
      }
    }

    .doc-icon {
      font-size: 1.75rem;
      color: var(--accent);
      flex-shrink: 0;
    }

    .doc-card div {
      flex: 1;
      min-width: 0;

      h4 {
        font-family: 'Syne', sans-serif;
        font-size: 0.9375rem;
        font-weight: 600;
        margin-bottom: 0.125rem;
      }

      p {
        font-size: 0.8125rem;
        color: var(--text-muted);
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }
    }

    .arrow {
      color: var(--text-muted);
      font-size: 1.25rem;
      transition: transform 0.3s ease, color 0.3s ease;
      flex-shrink: 0;
    }
  `]
})
export class RequirementsComponent implements AfterViewInit, OnDestroy {
  @ViewChild('sectionHeader') sectionHeader!: ElementRef<HTMLElement>;
  @ViewChild('requirementsGrid') requirementsGrid!: ElementRef<HTMLElement>;
  @ViewChild('specCardMin') specCardMin!: ElementRef<HTMLElement>;
  @ViewChild('specCardRec') specCardRec!: ElementRef<HTMLElement>;
  @ViewChild('compatSection') compatSection!: ElementRef<HTMLElement>;
  @ViewChild('compatGrid') compatGrid!: ElementRef<HTMLElement>;
  @ViewChild('docsSection') docsSection!: ElementRef<HTMLElement>;
  @ViewChild('docsGrid') docsGrid!: ElementRef<HTMLElement>;

  private animationService = inject(AnimationService);
  private platformId = inject(PLATFORM_ID);
  private isMobile = false;

  ngAfterViewInit(): void {
    if (!isPlatformBrowser(this.platformId)) return;

    this.isMobile = window.matchMedia('(max-width: 768px)').matches || 'ontouchstart' in window;

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

    // Spec cards - stagger from alternating sides
    gsap.from(this.specCardMin.nativeElement, {
      scrollTrigger: {
        trigger: this.requirementsGrid.nativeElement,
        start: 'top 75%'
      },
      x: -80,
      opacity: 0,
      duration: 0.8,
      ease: 'power3.out'
    });

    gsap.from(this.specCardRec.nativeElement, {
      scrollTrigger: {
        trigger: this.requirementsGrid.nativeElement,
        start: 'top 75%'
      },
      x: 80,
      opacity: 0,
      duration: 0.8,
      delay: 0.15,
      ease: 'power3.out'
    });

    // Compatibility section title
    gsap.from(this.compatSection.nativeElement.querySelector('.compatibility-title'), {
      scrollTrigger: {
        trigger: this.compatSection.nativeElement,
        start: 'top 80%'
      },
      y: 40,
      opacity: 0,
      duration: 0.6,
      ease: 'power2.out'
    });

    // Compatibility cards - cascade reveal
    const compatCards = this.compatGrid.nativeElement.querySelectorAll('.compat-card');
    gsap.from(compatCards, {
      scrollTrigger: {
        trigger: this.compatGrid.nativeElement,
        start: 'top 75%'
      },
      y: 60,
      opacity: 0,
      duration: 0.6,
      stagger: 0.12,
      ease: 'power2.out'
    });

    // Documentation section title
    gsap.from(this.docsSection.nativeElement.querySelector('.docs-title'), {
      scrollTrigger: {
        trigger: this.docsSection.nativeElement,
        start: 'top 80%'
      },
      y: 40,
      opacity: 0,
      duration: 0.6,
      ease: 'power2.out'
    });

    // Doc cards - slide in from left
    const docCards = this.docsGrid.nativeElement.querySelectorAll('.doc-card');
    gsap.from(docCards, {
      scrollTrigger: {
        trigger: this.docsGrid.nativeElement,
        start: 'top 75%'
      },
      x: -40,
      opacity: 0,
      duration: 0.5,
      stagger: 0.1,
      ease: 'power2.out'
    });
  }

  // Spec card 3D tilt
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

  // Compatibility card hover
  onCompatEnter(event: MouseEvent): void {
    if (this.isMobile) return;
    const target = event.currentTarget as HTMLElement;
    gsap.to(target, {
      y: -6,
      scale: 1.02,
      duration: 0.3,
      ease: 'power2.out'
    });
  }

  onCompatLeave(event: MouseEvent): void {
    if (this.isMobile) return;
    const target = event.currentTarget as HTMLElement;
    gsap.to(target, {
      y: 0,
      scale: 1,
      duration: 0.3,
      ease: 'power2.out'
    });
  }

  // Doc card hover with arrow animation
  onDocEnter(event: MouseEvent): void {
    if (this.isMobile) return;
    const target = event.currentTarget as HTMLElement;
    const arrow = target.querySelector('.arrow');

    gsap.to(target, {
      x: 4,
      duration: 0.3,
      ease: 'power2.out'
    });

    if (arrow) {
      gsap.to(arrow, {
        x: 4,
        color: 'var(--accent)',
        duration: 0.3,
        ease: 'power2.out'
      });
    }
  }

  onDocLeave(event: MouseEvent): void {
    if (this.isMobile) return;
    const target = event.currentTarget as HTMLElement;
    const arrow = target.querySelector('.arrow');

    gsap.to(target, {
      x: 0,
      duration: 0.3,
      ease: 'power2.out'
    });

    if (arrow) {
      gsap.to(arrow, {
        x: 0,
        color: 'var(--text-muted)',
        duration: 0.3,
        ease: 'power2.out'
      });
    }
  }
}
