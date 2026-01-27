import { Component, OnInit, OnDestroy, AfterViewInit, ElementRef, ViewChild, inject, signal, PLATFORM_ID } from '@angular/core';
import { isPlatformBrowser } from '@angular/common';
import { gsap } from 'gsap';
import { AnimationService } from '../../services/animation.service';

@Component({
  selector: 'app-hero',
  standalone: true,
  template: `
    <section class="hero" #heroSection>
      <!-- Animated background -->
      <div class="hero-bg">
        <div class="gradient-orb orb-1" #orb1></div>
        <div class="gradient-orb orb-2" #orb2></div>
        <div class="grid-overlay" #gridOverlay></div>
      </div>

      <div class="hero-content">
        <!-- Logo with 3D tilt -->
        <div
          class="logo-container"
          #logoContainer
          (mousemove)="onLogoMouseMove($event)"
          (mouseleave)="onLogoMouseLeave()"
        >
          <img
            src="assets/logo.png"
            alt="Eleanor Logo"
            class="logo"
            #logoImg
          />
          <div class="logo-glow"></div>
        </div>

        <!-- Title with split text animation -->
        <div class="title-group">
          <h1 class="title" #titleEl>Eleanor</h1>
          <p class="tagline" #taglineEl>Hunt. Collect. Analyze. Respond.</p>
          <p class="subtitle">The open-source DFIR platform that unifies your investigation workflow</p>
        </div>

        <!-- Version badge -->
        <div class="badge-container" #badgeEl>
          <span class="version-badge">
            <span class="material-icons-round">verified</span>
            Latest: v2.1.0
          </span>
        </div>

        <!-- CTA Buttons with magnetic effect -->
        <div class="cta-group" #ctaGroup>
          <a
            href="#downloads"
            class="btn btn-primary cta-btn magnetic-btn"
            #primaryBtn
            (mouseenter)="onButtonEnter($event)"
            (mousemove)="onButtonMove($event)"
            (mouseleave)="onButtonLeave($event)"
          >
            <span class="material-icons-round">download</span>
            Download OVA
          </a>
          <a
            href="#requirements"
            class="btn btn-secondary magnetic-btn"
            #secondaryBtn
            (mouseenter)="onButtonEnter($event)"
            (mousemove)="onButtonMove($event)"
            (mouseleave)="onButtonLeave($event)"
          >
            <span class="material-icons-round">memory</span>
            System Requirements
          </a>
        </div>

        <!-- Quick stats -->
        <div class="stats" #statsEl>
          <div class="stat">
            <span class="stat-value">VMware</span>
            <span class="stat-label">& VirtualBox</span>
          </div>
          <div class="stat-divider"></div>
          <div class="stat">
            <span class="stat-value">Pre-configured</span>
            <span class="stat-label">Ready to deploy</span>
          </div>
          <div class="stat-divider"></div>
          <div class="stat">
            <span class="stat-value">Open Source</span>
            <span class="stat-label">MIT License</span>
          </div>
        </div>
      </div>

      <!-- Scroll indicator -->
      <div class="scroll-indicator" #scrollIndicator>
        <span class="material-icons-round">expand_more</span>
      </div>
    </section>
  `,
  styles: [`
    .hero {
      position: relative;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      overflow: hidden;
      padding: 2rem;
    }

    // Background effects
    .hero-bg {
      position: absolute;
      inset: 0;
      pointer-events: none;
    }

    .gradient-orb {
      position: absolute;
      border-radius: 50%;
      filter: blur(100px);
      opacity: 0.4;
      will-change: transform;
    }

    .orb-1 {
      width: 600px;
      height: 600px;
      background: radial-gradient(circle, var(--accent) 0%, transparent 70%);
      top: -200px;
      right: -100px;
    }

    .orb-2 {
      width: 400px;
      height: 400px;
      background: radial-gradient(circle, var(--silver) 0%, transparent 70%);
      bottom: -100px;
      left: -50px;
    }

    .grid-overlay {
      position: absolute;
      inset: 0;
      background-image:
        linear-gradient(rgba(74, 158, 255, 0.03) 1px, transparent 1px),
        linear-gradient(90deg, rgba(74, 158, 255, 0.03) 1px, transparent 1px);
      background-size: 60px 60px;
      mask-image: radial-gradient(ellipse at center, black 0%, transparent 75%);
      will-change: transform;
    }

    // Content
    .hero-content {
      position: relative;
      z-index: 1;
      display: flex;
      flex-direction: column;
      align-items: center;
      text-align: center;
      max-width: 800px;
    }

    // Logo with 3D transform
    .logo-container {
      position: relative;
      margin-bottom: 2rem;
      perspective: 1000px;
      transform-style: preserve-3d;
    }

    .logo {
      width: 180px;
      height: auto;
      filter: drop-shadow(0 0 30px rgba(74, 158, 255, 0.3));
      will-change: transform;
      transform-style: preserve-3d;
    }

    .logo-glow {
      position: absolute;
      inset: -20px;
      background: radial-gradient(circle, var(--accent-glow) 0%, transparent 70%);
      z-index: -1;
      animation: pulse-glow 4s ease-in-out infinite;
    }

    // Title
    .title-group {
      margin-bottom: 1.5rem;
    }

    .title {
      font-family: 'Syne', sans-serif;
      font-size: clamp(3rem, 8vw, 5rem);
      font-weight: 800;
      letter-spacing: -0.04em;
      background: linear-gradient(135deg, var(--text-primary) 0%, var(--silver) 50%, var(--accent) 100%);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      background-clip: text;
      margin-bottom: 0.5rem;

      :host ::ng-deep .split-item {
        display: inline-block;
        overflow: hidden;
      }

      :host ::ng-deep .split-inner {
        display: inline-block;
      }
    }

    .tagline {
      font-family: 'Syne', sans-serif;
      font-size: clamp(1.25rem, 3vw, 1.75rem);
      color: var(--accent);
      font-weight: 600;
      letter-spacing: 0.15em;
      text-transform: uppercase;

      :host ::ng-deep .split-item {
        display: inline-block;
        overflow: hidden;
      }

      :host ::ng-deep .split-inner {
        display: inline-block;
      }
    }

    .subtitle {
      font-size: clamp(1rem, 2vw, 1.125rem);
      color: var(--text-secondary);
      font-weight: 400;
      margin-top: 0.75rem;
    }

    // Badge
    .badge-container {
      margin-bottom: 2.5rem;
    }

    .version-badge {
      display: inline-flex;
      align-items: center;
      gap: 0.5rem;
      padding: 0.5rem 1rem;
      background: var(--accent-glow);
      color: var(--accent);
      border: 1px solid rgba(74, 158, 255, 0.2);
      border-radius: 100px;
      font-size: 0.875rem;
      font-weight: 600;

      .material-icons-round {
        font-size: 1rem;
      }
    }

    // CTA with magnetic effect
    .cta-group {
      display: flex;
      gap: 1rem;
      margin-bottom: 4rem;

      @media (max-width: 480px) {
        flex-direction: column;
        width: 100%;
      }
    }

    .cta-btn {
      padding: 1rem 2rem;
      font-size: 1rem;

      .material-icons-round {
        font-size: 1.25rem;
      }
    }

    .magnetic-btn {
      will-change: transform;
      transform-style: preserve-3d;
    }

    // Stats
    .stats {
      display: flex;
      align-items: center;
      gap: 2rem;

      @media (max-width: 640px) {
        flex-direction: column;
        gap: 1.5rem;
      }
    }

    .stat {
      text-align: center;
    }

    .stat-value {
      display: block;
      font-family: 'Syne', sans-serif;
      font-size: 1rem;
      font-weight: 600;
      color: var(--text-primary);
    }

    .stat-label {
      font-size: 0.8125rem;
      color: var(--text-muted);
    }

    .stat-divider {
      width: 1px;
      height: 40px;
      background: var(--border-subtle);

      @media (max-width: 640px) {
        width: 60px;
        height: 1px;
      }
    }

    // Scroll indicator
    .scroll-indicator {
      position: absolute;
      bottom: 2rem;
      opacity: 0;

      .material-icons-round {
        font-size: 2rem;
        color: var(--text-muted);
      }
    }

    @keyframes pulse-glow {
      0%, 100% { opacity: 0.5; }
      50% { opacity: 0.8; }
    }
  `]
})
export class HeroComponent implements OnInit, AfterViewInit, OnDestroy {
  @ViewChild('heroSection') heroSection!: ElementRef<HTMLElement>;
  @ViewChild('logoContainer') logoContainer!: ElementRef<HTMLElement>;
  @ViewChild('logoImg') logoImg!: ElementRef<HTMLImageElement>;
  @ViewChild('titleEl') titleEl!: ElementRef<HTMLElement>;
  @ViewChild('taglineEl') taglineEl!: ElementRef<HTMLElement>;
  @ViewChild('badgeEl') badgeEl!: ElementRef<HTMLElement>;
  @ViewChild('ctaGroup') ctaGroup!: ElementRef<HTMLElement>;
  @ViewChild('statsEl') statsEl!: ElementRef<HTMLElement>;
  @ViewChild('scrollIndicator') scrollIndicator!: ElementRef<HTMLElement>;
  @ViewChild('orb1') orb1!: ElementRef<HTMLElement>;
  @ViewChild('orb2') orb2!: ElementRef<HTMLElement>;
  @ViewChild('gridOverlay') gridOverlay!: ElementRef<HTMLElement>;

  private animationService = inject(AnimationService);
  private platformId = inject(PLATFORM_ID);
  private masterTimeline: gsap.core.Timeline | null = null;
  private isMobile = false;

  ngOnInit(): void {
    if (isPlatformBrowser(this.platformId)) {
      this.isMobile = window.matchMedia('(max-width: 768px)').matches || 'ontouchstart' in window;
    }
  }

  ngAfterViewInit(): void {
    if (!isPlatformBrowser(this.platformId)) return;

    // Small delay to ensure DOM is ready
    setTimeout(() => this.initAnimations(), 100);
  }

  ngOnDestroy(): void {
    if (this.masterTimeline) {
      this.masterTimeline.kill();
    }
  }

  private initAnimations(): void {
    this.masterTimeline = gsap.timeline();

    // Set initial states
    gsap.set([
      this.logoContainer.nativeElement,
      this.titleEl.nativeElement,
      this.taglineEl.nativeElement,
      this.badgeEl.nativeElement,
      this.ctaGroup.nativeElement,
      this.statsEl.nativeElement
    ], {
      opacity: 0,
      y: 40
    });

    gsap.set(this.scrollIndicator.nativeElement, {
      opacity: 0,
      y: -20
    });

    // Logo entrance with scale
    this.masterTimeline.to(this.logoContainer.nativeElement, {
      opacity: 1,
      y: 0,
      scale: 1,
      duration: 1,
      ease: 'power3.out'
    }, 0.2);

    // Split text animation for title
    this.masterTimeline.add(() => {
      this.animationService.splitTextReveal(this.titleEl.nativeElement, {
        type: 'chars',
        stagger: 0.04,
        duration: 0.6,
        y: 60
      });
    }, 0.5);

    // Tagline word-by-word
    this.masterTimeline.add(() => {
      this.animationService.splitTextReveal(this.taglineEl.nativeElement, {
        type: 'words',
        stagger: 0.08,
        duration: 0.5,
        y: 30
      });
    }, 0.8);

    // Badge fade in
    this.masterTimeline.to(this.badgeEl.nativeElement, {
      opacity: 1,
      y: 0,
      duration: 0.6,
      ease: 'power2.out'
    }, 1.2);

    // CTA buttons
    this.masterTimeline.to(this.ctaGroup.nativeElement, {
      opacity: 1,
      y: 0,
      duration: 0.6,
      ease: 'power2.out'
    }, 1.4);

    // Stats reveal
    const statItems = this.statsEl.nativeElement.querySelectorAll('.stat, .stat-divider');
    this.masterTimeline.to(this.statsEl.nativeElement, {
      opacity: 1,
      y: 0,
      duration: 0.6,
      ease: 'power2.out'
    }, 1.6);

    this.masterTimeline.from(statItems, {
      opacity: 0,
      y: 20,
      duration: 0.4,
      stagger: 0.1,
      ease: 'power2.out'
    }, 1.7);

    // Scroll indicator
    this.masterTimeline.to(this.scrollIndicator.nativeElement, {
      opacity: 0.5,
      y: 0,
      duration: 0.6,
      ease: 'power2.out'
    }, 2.0);

    // Add bounce animation to scroll indicator
    this.masterTimeline.add(() => {
      gsap.to(this.scrollIndicator.nativeElement, {
        y: 10,
        duration: 1,
        repeat: -1,
        yoyo: true,
        ease: 'power1.inOut'
      });
    }, 2.2);

    // Setup parallax for background elements
    this.setupParallax();
  }

  private setupParallax(): void {
    // Parallax for orbs on scroll
    this.animationService.parallax(this.orb1.nativeElement, { speed: 0.3 });
    this.animationService.parallax(this.orb2.nativeElement, { speed: 0.2 });
    this.animationService.parallax(this.gridOverlay.nativeElement, { speed: 0.15 });
  }

  // 3D Logo tilt on mouse move
  onLogoMouseMove(event: MouseEvent): void {
    if (this.isMobile) return;

    this.animationService.tilt3D(
      this.logoImg.nativeElement,
      event,
      this.logoContainer.nativeElement,
      { maxRotation: 20 }
    );
  }

  onLogoMouseLeave(): void {
    if (this.isMobile) return;
    this.animationService.tiltReset(this.logoImg.nativeElement);
  }

  // Magnetic button effects
  onButtonEnter(event: MouseEvent): void {
    if (this.isMobile) return;
    const target = event.currentTarget as HTMLElement;
    this.animationService.buttonHover(target, true);
  }

  onButtonMove(event: MouseEvent): void {
    if (this.isMobile) return;
    const target = event.currentTarget as HTMLElement;
    this.animationService.magneticMove(target, event, 0.2);
  }

  onButtonLeave(event: MouseEvent): void {
    if (this.isMobile) return;
    const target = event.currentTarget as HTMLElement;
    this.animationService.magneticReset(target);
    this.animationService.buttonHover(target, false);
  }
}
