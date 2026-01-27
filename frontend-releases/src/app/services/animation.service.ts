import { Injectable, PLATFORM_ID, inject } from '@angular/core';
import { isPlatformBrowser } from '@angular/common';
import { gsap } from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';

@Injectable({ providedIn: 'root' })
export class AnimationService {
  private platformId = inject(PLATFORM_ID);
  private initialized = false;

  get isBrowser(): boolean {
    return isPlatformBrowser(this.platformId);
  }

  /**
   * Initialize GSAP and register plugins (call once at app startup)
   */
  initialize(): void {
    if (!this.isBrowser || this.initialized) return;

    gsap.registerPlugin(ScrollTrigger);

    // Configure GSAP defaults
    gsap.defaults({
      ease: 'power3.out',
      duration: 0.8
    });

    // Configure ScrollTrigger defaults
    ScrollTrigger.defaults({
      toggleActions: 'play none none none',
      once: true
    });

    this.initialized = true;
  }

  /**
   * Reveal element on scroll with fade up effect
   */
  scrollReveal(
    element: string | Element | Element[],
    options: {
      y?: number;
      x?: number;
      opacity?: number;
      duration?: number;
      delay?: number;
      stagger?: number;
      start?: string;
      trigger?: string | Element;
    } = {}
  ): gsap.core.Tween | null {
    if (!this.isBrowser) return null;

    const {
      y = 60,
      x = 0,
      opacity = 0,
      duration = 0.8,
      delay = 0,
      stagger = 0,
      start = 'top 80%',
      trigger
    } = options;

    return gsap.from(element, {
      y,
      x,
      opacity,
      duration,
      delay,
      stagger,
      ease: 'power3.out',
      scrollTrigger: {
        trigger: trigger || element,
        start
      }
    });
  }

  /**
   * Staggered reveal for multiple elements
   */
  staggerReveal(
    elements: string | Element[],
    options: {
      y?: number;
      duration?: number;
      stagger?: number;
      start?: string;
      trigger?: string | Element;
    } = {}
  ): gsap.core.Tween | null {
    if (!this.isBrowser) return null;

    const {
      y = 80,
      duration = 0.6,
      stagger = 0.15,
      start = 'top 75%',
      trigger
    } = options;

    return gsap.from(elements, {
      y,
      opacity: 0,
      duration,
      stagger,
      ease: 'power2.out',
      scrollTrigger: {
        trigger: trigger || elements,
        start
      }
    });
  }

  /**
   * Magnetic button effect - call on mousemove
   */
  magneticMove(
    element: Element,
    event: MouseEvent,
    strength: number = 0.3
  ): void {
    if (!this.isBrowser) return;

    const rect = element.getBoundingClientRect();
    const x = event.clientX - rect.left - rect.width / 2;
    const y = event.clientY - rect.top - rect.height / 2;

    gsap.to(element, {
      x: x * strength,
      y: y * strength,
      duration: 0.3,
      ease: 'power2.out'
    });
  }

  /**
   * Reset magnetic effect - call on mouseleave
   */
  magneticReset(element: Element): void {
    if (!this.isBrowser) return;

    gsap.to(element, {
      x: 0,
      y: 0,
      duration: 0.5,
      ease: 'elastic.out(1, 0.5)'
    });
  }

  /**
   * 3D tilt effect for elements
   */
  tilt3D(
    element: Element,
    event: MouseEvent,
    container: Element,
    options: { maxRotation?: number; perspective?: number } = {}
  ): void {
    if (!this.isBrowser) return;

    const { maxRotation = 15, perspective = 1000 } = options;
    const rect = container.getBoundingClientRect();
    const x = (event.clientX - rect.left) / rect.width - 0.5;
    const y = (event.clientY - rect.top) / rect.height - 0.5;

    gsap.to(element, {
      rotateY: x * maxRotation,
      rotateX: -y * maxRotation,
      transformPerspective: perspective,
      duration: 0.5,
      ease: 'power2.out'
    });
  }

  /**
   * Reset 3D tilt
   */
  tiltReset(element: Element): void {
    if (!this.isBrowser) return;

    gsap.to(element, {
      rotateY: 0,
      rotateX: 0,
      duration: 0.5,
      ease: 'power2.out'
    });
  }

  /**
   * Parallax effect for background elements
   */
  parallax(
    element: string | Element,
    options: {
      speed?: number;
      start?: string;
      end?: string;
    } = {}
  ): gsap.core.Tween | null {
    if (!this.isBrowser) return null;

    const { speed = 0.5, start = 'top bottom', end = 'bottom top' } = options;

    return gsap.to(element, {
      y: () => window.innerHeight * speed * -1,
      ease: 'none',
      scrollTrigger: {
        trigger: element,
        start,
        end,
        scrub: true
      }
    });
  }

  /**
   * Split text animation - animates characters or words
   */
  splitTextReveal(
    element: Element,
    options: {
      type?: 'chars' | 'words';
      stagger?: number;
      duration?: number;
      y?: number;
      delay?: number;
    } = {}
  ): gsap.core.Timeline | null {
    if (!this.isBrowser) return null;

    const {
      type = 'chars',
      stagger = 0.03,
      duration = 0.5,
      y = 50,
      delay = 0
    } = options;

    const text = element.textContent || '';
    const items = type === 'chars' ? text.split('') : text.split(' ');

    // Clear and rebuild with spans
    element.innerHTML = items
      .map((item, i) => {
        const content = type === 'words' && i < items.length - 1 ? item + ' ' : item;
        return `<span class="split-item" style="display: inline-block; overflow: hidden;">
          <span class="split-inner" style="display: inline-block;">${content === ' ' ? '&nbsp;' : content}</span>
        </span>`;
      })
      .join('');

    const innerElements = element.querySelectorAll('.split-inner');

    const tl = gsap.timeline({ delay });
    tl.from(innerElements, {
      y,
      opacity: 0,
      duration,
      stagger,
      ease: 'power3.out'
    });

    return tl;
  }

  /**
   * Button scale + glow effect
   */
  buttonHover(element: Element, isEntering: boolean): void {
    if (!this.isBrowser) return;

    if (isEntering) {
      gsap.to(element, {
        scale: 1.02,
        boxShadow: '0 12px 32px rgba(74, 158, 255, 0.4)',
        duration: 0.3,
        ease: 'power2.out'
      });
    } else {
      gsap.to(element, {
        scale: 1,
        boxShadow: '0 0 0 rgba(74, 158, 255, 0)',
        duration: 0.3,
        ease: 'power2.out'
      });
    }
  }

  /**
   * Copy button success animation
   */
  copySuccess(element: Element): gsap.core.Timeline {
    const tl = gsap.timeline();

    tl.to(element, {
      scale: 0.9,
      duration: 0.1,
      ease: 'power2.in'
    })
    .to(element, {
      scale: 1.1,
      duration: 0.15,
      ease: 'back.out(3)'
    })
    .to(element, {
      scale: 1,
      duration: 0.2,
      ease: 'power2.out'
    });

    return tl;
  }

  /**
   * Card 3D tilt effect (subtle)
   */
  cardTilt(element: Element, event: MouseEvent): void {
    if (!this.isBrowser) return;

    const rect = element.getBoundingClientRect();
    const x = (event.clientX - rect.left) / rect.width - 0.5;
    const y = (event.clientY - rect.top) / rect.height - 0.5;

    gsap.to(element, {
      rotateY: x * 5,
      rotateX: -y * 5,
      transformPerspective: 800,
      duration: 0.4,
      ease: 'power2.out'
    });
  }

  /**
   * Kill all ScrollTriggers (cleanup)
   */
  killAll(): void {
    if (!this.isBrowser) return;
    ScrollTrigger.getAll().forEach(trigger => trigger.kill());
  }

  /**
   * Refresh ScrollTrigger (after dynamic content changes)
   */
  refresh(): void {
    if (!this.isBrowser) return;
    ScrollTrigger.refresh();
  }
}
