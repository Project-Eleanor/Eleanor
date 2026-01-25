import {
  Directive,
  Input,
  TemplateRef,
  ViewContainerRef,
  OnInit,
  OnDestroy,
  effect,
  inject
} from '@angular/core';
import { RbacService } from '../../core/api/rbac.service';

/**
 * Structural directive to conditionally show/hide elements based on user permissions.
 *
 * Usage:
 *   <button *appHasPermission="'cases:create'">Create Case</button>
 *   <div *appHasPermission="['cases:read', 'cases:update']">...</div>
 *   <button *appHasPermission="'admin:manage'; else noAccess">Admin Panel</button>
 */
@Directive({
  selector: '[appHasPermission]',
  standalone: true
})
export class HasPermissionDirective implements OnInit, OnDestroy {
  private readonly rbacService = inject(RbacService);
  private readonly templateRef = inject(TemplateRef<unknown>);
  private readonly viewContainer = inject(ViewContainerRef);

  private requiredPermissions: string[] = [];
  private requireAll = false;
  private elseTemplateRef: TemplateRef<unknown> | null = null;
  private hasView = false;

  @Input()
  set appHasPermission(permissions: string | string[]) {
    this.requiredPermissions = Array.isArray(permissions) ? permissions : [permissions];
    this.updateView();
  }

  @Input()
  set appHasPermissionAll(value: boolean) {
    this.requireAll = value;
    this.updateView();
  }

  @Input()
  set appHasPermissionElse(templateRef: TemplateRef<unknown> | null) {
    this.elseTemplateRef = templateRef;
    this.updateView();
  }

  constructor() {
    // React to permission changes
    effect(() => {
      // This reads the signal, establishing a dependency
      this.rbacService.permissions();
      this.updateView();
    });
  }

  ngOnInit(): void {
    this.updateView();
  }

  ngOnDestroy(): void {
    this.viewContainer.clear();
  }

  private updateView(): void {
    const hasPermission = this.checkPermission();

    if (hasPermission && !this.hasView) {
      this.viewContainer.clear();
      this.viewContainer.createEmbeddedView(this.templateRef);
      this.hasView = true;
    } else if (!hasPermission && this.hasView) {
      this.viewContainer.clear();
      if (this.elseTemplateRef) {
        this.viewContainer.createEmbeddedView(this.elseTemplateRef);
      }
      this.hasView = false;
    } else if (!hasPermission && !this.hasView && this.elseTemplateRef) {
      this.viewContainer.clear();
      this.viewContainer.createEmbeddedView(this.elseTemplateRef);
    }
  }

  private checkPermission(): boolean {
    if (this.requiredPermissions.length === 0) {
      return true;
    }

    if (this.requireAll) {
      return this.rbacService.hasAllPermissions(...this.requiredPermissions);
    }

    return this.rbacService.hasAnyPermission(...this.requiredPermissions);
  }
}

/**
 * Directive to show element only if user does NOT have the specified permission.
 *
 * Usage:
 *   <div *appLacksPermission="'admin:manage'">You are not an admin</div>
 */
@Directive({
  selector: '[appLacksPermission]',
  standalone: true
})
export class LacksPermissionDirective implements OnInit, OnDestroy {
  private readonly rbacService = inject(RbacService);
  private readonly templateRef = inject(TemplateRef<unknown>);
  private readonly viewContainer = inject(ViewContainerRef);

  private requiredPermission = '';
  private hasView = false;

  @Input()
  set appLacksPermission(permission: string) {
    this.requiredPermission = permission;
    this.updateView();
  }

  constructor() {
    effect(() => {
      this.rbacService.permissions();
      this.updateView();
    });
  }

  ngOnInit(): void {
    this.updateView();
  }

  ngOnDestroy(): void {
    this.viewContainer.clear();
  }

  private updateView(): void {
    const lacksPermission = !this.rbacService.hasPermission(this.requiredPermission);

    if (lacksPermission && !this.hasView) {
      this.viewContainer.clear();
      this.viewContainer.createEmbeddedView(this.templateRef);
      this.hasView = true;
    } else if (!lacksPermission && this.hasView) {
      this.viewContainer.clear();
      this.hasView = false;
    }
  }
}
