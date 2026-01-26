/**
 * Component test helpers for Angular testing.
 * Provides utilities for setting up TestBed and common test patterns.
 */
import { ComponentFixture, TestBed, TestModuleMetadata } from '@angular/core/testing';
import { Type } from '@angular/core';
import { NoopAnimationsModule } from '@angular/platform-browser/animations';
import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { provideRouter, Router } from '@angular/router';
import { RouterTestingHarness } from '@angular/router/testing';

import { provideMockServices } from './mock-services';

/**
 * Standard TestBed configuration for service tests.
 * Includes HttpClientTesting and mock services.
 */
export function configureServiceTestBed(additionalProviders: any[] = []): void {
  TestBed.configureTestingModule({
    providers: [
      provideHttpClient(withInterceptorsFromDi()),
      provideHttpClientTesting(),
      ...additionalProviders,
    ],
  });
}

/**
 * Standard TestBed configuration for component tests.
 * Includes NoopAnimations and mock services.
 */
export async function configureComponentTestBed<T>(
  component: Type<T>,
  config: Partial<TestModuleMetadata> = {}
): Promise<ComponentFixture<T>> {
  await TestBed.configureTestingModule({
    imports: [
      NoopAnimationsModule,
      component,
      ...(config.imports || []),
    ],
    providers: [
      ...provideMockServices(),
      provideRouter([]),
      ...(config.providers || []),
    ],
    declarations: config.declarations || [],
  }).compileComponents();

  return TestBed.createComponent(component);
}

/**
 * Configure TestBed with HTTP testing controller.
 * Returns the controller for setting up expectations.
 */
export function configureHttpTestBed(service: Type<any>): {
  service: any;
  httpMock: HttpTestingController;
} {
  configureServiceTestBed([service]);

  return {
    service: TestBed.inject(service),
    httpMock: TestBed.inject(HttpTestingController),
  };
}

/**
 * Create a component fixture with auto change detection.
 */
export function createComponentWithAutoDetect<T>(
  component: Type<T>
): ComponentFixture<T> {
  const fixture = TestBed.createComponent(component);
  fixture.autoDetectChanges(true);
  return fixture;
}

/**
 * Helper to query elements in component template.
 */
export class ComponentQuery<T> {
  constructor(private fixture: ComponentFixture<T>) {}

  /**
   * Query a single element by CSS selector.
   */
  query(selector: string): HTMLElement | null {
    return this.fixture.nativeElement.querySelector(selector);
  }

  /**
   * Query all elements by CSS selector.
   */
  queryAll(selector: string): HTMLElement[] {
    return Array.from(this.fixture.nativeElement.querySelectorAll(selector));
  }

  /**
   * Query by test ID attribute (data-testid).
   */
  byTestId(id: string): HTMLElement | null {
    return this.query(`[data-testid="${id}"]`);
  }

  /**
   * Query all by test ID attribute.
   */
  allByTestId(id: string): HTMLElement[] {
    return this.queryAll(`[data-testid="${id}"]`);
  }

  /**
   * Query button by text content.
   */
  buttonByText(text: string): HTMLButtonElement | null {
    const buttons = this.queryAll('button');
    return buttons.find(b => b.textContent?.trim() === text) as HTMLButtonElement || null;
  }

  /**
   * Query input by placeholder.
   */
  inputByPlaceholder(placeholder: string): HTMLInputElement | null {
    return this.query(`input[placeholder="${placeholder}"]`) as HTMLInputElement;
  }

  /**
   * Check if element exists.
   */
  exists(selector: string): boolean {
    return this.query(selector) !== null;
  }

  /**
   * Get text content of element.
   */
  text(selector: string): string {
    return this.query(selector)?.textContent?.trim() || '';
  }
}

/**
 * Create a ComponentQuery helper for a fixture.
 */
export function queryHelper<T>(fixture: ComponentFixture<T>): ComponentQuery<T> {
  return new ComponentQuery(fixture);
}

/**
 * Trigger input event on an input element.
 */
export function typeInInput(input: HTMLInputElement, value: string): void {
  input.value = value;
  input.dispatchEvent(new Event('input'));
  input.dispatchEvent(new Event('change'));
}

/**
 * Trigger click event on an element.
 */
export function click(element: HTMLElement): void {
  element.click();
  element.dispatchEvent(new Event('click'));
}

/**
 * Wait for async operations to complete.
 */
export async function waitForAsync(fixture: ComponentFixture<any>): Promise<void> {
  fixture.detectChanges();
  await fixture.whenStable();
  fixture.detectChanges();
}

/**
 * Create a spy object with optional method implementations.
 */
export function createSpyObj<T>(
  baseName: string,
  methods: (keyof T)[],
  properties?: Partial<T>
): jasmine.SpyObj<T> {
  const spy = jasmine.createSpyObj(baseName, methods);
  if (properties) {
    Object.assign(spy, properties);
  }
  return spy;
}

/**
 * Assert that an element has a specific CSS class.
 */
export function expectToHaveClass(element: HTMLElement, className: string): void {
  expect(element.classList.contains(className))
    .withContext(`Expected element to have class '${className}'`)
    .toBeTrue();
}

/**
 * Assert that an element does not have a specific CSS class.
 */
export function expectNotToHaveClass(element: HTMLElement, className: string): void {
  expect(element.classList.contains(className))
    .withContext(`Expected element NOT to have class '${className}'`)
    .toBeFalse();
}

/**
 * Assert that an element is visible (not hidden).
 */
export function expectToBeVisible(element: HTMLElement): void {
  const style = window.getComputedStyle(element);
  expect(style.display).not.toBe('none');
  expect(style.visibility).not.toBe('hidden');
  expect(element.hidden).toBeFalse();
}

/**
 * Assert that an element is disabled.
 */
export function expectToBeDisabled(element: HTMLElement): void {
  expect((element as HTMLButtonElement).disabled)
    .withContext('Expected element to be disabled')
    .toBeTrue();
}

/**
 * Assert that an element is enabled.
 */
export function expectToBeEnabled(element: HTMLElement): void {
  expect((element as HTMLButtonElement).disabled)
    .withContext('Expected element to be enabled')
    .toBeFalse();
}

/**
 * Mock ActivatedRoute with custom params and data.
 */
export function mockActivatedRoute(params: Record<string, string> = {}, data: Record<string, any> = {}) {
  return {
    snapshot: {
      params,
      paramMap: {
        get: (key: string) => params[key] || null,
        has: (key: string) => key in params,
      },
      data,
      queryParams: {},
    },
    params: {
      subscribe: (fn: (value: any) => void) => {
        fn(params);
        return { unsubscribe: () => {} };
      },
    },
    data: {
      subscribe: (fn: (value: any) => void) => {
        fn(data);
        return { unsubscribe: () => {} };
      },
    },
  };
}

/**
 * Flush pending timers in fakeAsync zone.
 */
export function flushTimers(): void {
  // This should be used within fakeAsync
  // tick() and flush() should be called from the test
}

/**
 * Create a mock Observable that emits values.
 */
export function mockObservable<T>(...values: T[]) {
  const { of } = require('rxjs');
  return of(...values);
}

/**
 * Create a mock Observable that errors.
 */
export function mockErrorObservable(error: any) {
  const { throwError } = require('rxjs');
  return throwError(() => error);
}
