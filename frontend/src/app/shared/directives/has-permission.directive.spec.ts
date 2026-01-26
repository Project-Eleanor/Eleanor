import { Component, signal } from '@angular/core';
import { TestBed, ComponentFixture } from '@angular/core/testing';

import { HasPermissionDirective, LacksPermissionDirective } from './has-permission.directive';
import { RbacService } from '../../core/api/rbac.service';

// Mock RbacService with signals
class MockRbacService {
  private _permissions = signal<string[]>(['cases:read', 'cases:create']);

  permissions = this._permissions.asReadonly();

  setPermissions(perms: string[]): void {
    this._permissions.set(perms);
  }

  hasPermission(perm: string): boolean {
    return this._permissions().includes(perm);
  }

  hasAnyPermission(...perms: string[]): boolean {
    return perms.some(p => this._permissions().includes(p));
  }

  hasAllPermissions(...perms: string[]): boolean {
    return perms.every(p => this._permissions().includes(p));
  }
}

// Test component for HasPermissionDirective
@Component({
  standalone: true,
  imports: [HasPermissionDirective],
  template: `
    <div *appHasPermission="'cases:read'" data-testid="read-element">Read Access</div>
    <div *appHasPermission="'cases:delete'" data-testid="delete-element">Delete Access</div>
  `
})
class TestHostComponent {}

// Test component for multiple permissions
@Component({
  standalone: true,
  imports: [HasPermissionDirective],
  template: `
    <div *appHasPermission="['cases:read', 'cases:update']" data-testid="any-element">Any Permission</div>
    <div *appHasPermission="['admin:manage', 'super:admin']" data-testid="admin-element">Admin Access</div>
  `
})
class TestMultiplePermissionsComponent {}

// Test component for appHasPermissionAll
@Component({
  standalone: true,
  imports: [HasPermissionDirective],
  template: `
    <div *appHasPermission="['cases:read', 'cases:create']; all true" data-testid="all-element">All Permissions</div>
    <div *appHasPermission="['cases:read', 'admin:manage']; all true" data-testid="partial-element">Partial Permissions</div>
  `
})
class TestAllPermissionsComponent {}

// Test component for else template
@Component({
  standalone: true,
  imports: [HasPermissionDirective],
  template: `
    <div *appHasPermission="'admin:manage'; else noAccess" data-testid="admin-content">Admin Content</div>
    <ng-template #noAccess><div data-testid="no-access">No Access</div></ng-template>
  `
})
class TestElseTemplateComponent {}

// Test component for LacksPermissionDirective
@Component({
  standalone: true,
  imports: [LacksPermissionDirective],
  template: `
    <div *appLacksPermission="'admin:manage'" data-testid="lacks-admin">Not an admin</div>
    <div *appLacksPermission="'cases:read'" data-testid="lacks-read">Can't read</div>
  `
})
class TestLacksPermissionComponent {}

describe('HasPermissionDirective', () => {
  let fixture: ComponentFixture<TestHostComponent>;
  let rbacService: MockRbacService;

  beforeEach(async () => {
    rbacService = new MockRbacService();

    await TestBed.configureTestingModule({
      imports: [TestHostComponent],
      providers: [
        { provide: RbacService, useValue: rbacService },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(TestHostComponent);
    fixture.detectChanges();
  });

  it('should show element when user has permission', () => {
    const element = fixture.nativeElement.querySelector('[data-testid="read-element"]');
    expect(element).toBeTruthy();
    expect(element.textContent).toContain('Read Access');
  });

  it('should hide element when user lacks permission', () => {
    const element = fixture.nativeElement.querySelector('[data-testid="delete-element"]');
    expect(element).toBeNull();
  });

  it('should update view when permissions change', () => {
    // Initially no delete permission
    expect(fixture.nativeElement.querySelector('[data-testid="delete-element"]')).toBeNull();

    // Grant delete permission
    rbacService.setPermissions(['cases:read', 'cases:create', 'cases:delete']);
    fixture.detectChanges();

    expect(fixture.nativeElement.querySelector('[data-testid="delete-element"]')).toBeTruthy();
  });
});

describe('HasPermissionDirective with multiple permissions', () => {
  let fixture: ComponentFixture<TestMultiplePermissionsComponent>;
  let rbacService: MockRbacService;

  beforeEach(async () => {
    rbacService = new MockRbacService();

    await TestBed.configureTestingModule({
      imports: [TestMultiplePermissionsComponent],
      providers: [
        { provide: RbacService, useValue: rbacService },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(TestMultiplePermissionsComponent);
    fixture.detectChanges();
  });

  it('should show element when user has any of the permissions', () => {
    // User has cases:read
    const element = fixture.nativeElement.querySelector('[data-testid="any-element"]');
    expect(element).toBeTruthy();
  });

  it('should hide element when user has none of the permissions', () => {
    const element = fixture.nativeElement.querySelector('[data-testid="admin-element"]');
    expect(element).toBeNull();
  });
});

describe('HasPermissionDirective with all requirement', () => {
  let fixture: ComponentFixture<TestAllPermissionsComponent>;
  let rbacService: MockRbacService;

  beforeEach(async () => {
    rbacService = new MockRbacService();

    await TestBed.configureTestingModule({
      imports: [TestAllPermissionsComponent],
      providers: [
        { provide: RbacService, useValue: rbacService },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(TestAllPermissionsComponent);
    fixture.detectChanges();
  });

  it('should show element when user has all permissions', () => {
    // User has cases:read and cases:create
    const element = fixture.nativeElement.querySelector('[data-testid="all-element"]');
    expect(element).toBeTruthy();
  });

  it('should hide element when user only has some permissions', () => {
    // User has cases:read but not admin:manage
    const element = fixture.nativeElement.querySelector('[data-testid="partial-element"]');
    expect(element).toBeNull();
  });
});

describe('HasPermissionDirective with else template', () => {
  let fixture: ComponentFixture<TestElseTemplateComponent>;
  let rbacService: MockRbacService;

  beforeEach(async () => {
    rbacService = new MockRbacService();

    await TestBed.configureTestingModule({
      imports: [TestElseTemplateComponent],
      providers: [
        { provide: RbacService, useValue: rbacService },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(TestElseTemplateComponent);
    fixture.detectChanges();
  });

  it('should show else template when permission is missing', () => {
    // User doesn't have admin:manage
    expect(fixture.nativeElement.querySelector('[data-testid="admin-content"]')).toBeNull();
    expect(fixture.nativeElement.querySelector('[data-testid="no-access"]')).toBeTruthy();
  });

  it('should switch from else to main when permission granted', () => {
    // Grant admin permission
    rbacService.setPermissions(['admin:manage']);
    fixture.detectChanges();

    expect(fixture.nativeElement.querySelector('[data-testid="admin-content"]')).toBeTruthy();
    expect(fixture.nativeElement.querySelector('[data-testid="no-access"]')).toBeNull();
  });
});

describe('LacksPermissionDirective', () => {
  let fixture: ComponentFixture<TestLacksPermissionComponent>;
  let rbacService: MockRbacService;

  beforeEach(async () => {
    rbacService = new MockRbacService();

    await TestBed.configureTestingModule({
      imports: [TestLacksPermissionComponent],
      providers: [
        { provide: RbacService, useValue: rbacService },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(TestLacksPermissionComponent);
    fixture.detectChanges();
  });

  it('should show element when user lacks the permission', () => {
    // User doesn't have admin:manage
    const element = fixture.nativeElement.querySelector('[data-testid="lacks-admin"]');
    expect(element).toBeTruthy();
    expect(element.textContent).toContain('Not an admin');
  });

  it('should hide element when user has the permission', () => {
    // User has cases:read
    const element = fixture.nativeElement.querySelector('[data-testid="lacks-read"]');
    expect(element).toBeNull();
  });

  it('should update when permissions change', () => {
    // Grant admin permission
    rbacService.setPermissions(['admin:manage', 'cases:read']);
    fixture.detectChanges();

    expect(fixture.nativeElement.querySelector('[data-testid="lacks-admin"]')).toBeNull();
  });
});
