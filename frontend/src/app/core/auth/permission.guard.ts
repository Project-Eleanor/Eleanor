import { inject } from '@angular/core';
import { CanActivateFn, Router, ActivatedRouteSnapshot } from '@angular/router';
import { map, catchError, of, switchMap } from 'rxjs';
import { RbacService } from '../api/rbac.service';
import { AuthService } from './auth.service';

/**
 * Guard factory to protect routes based on required permissions.
 *
 * Usage in routes:
 *   {
 *     path: 'admin',
 *     component: AdminComponent,
 *     canActivate: [permissionGuard('admin:manage')]
 *   }
 *
 *   {
 *     path: 'cases/create',
 *     component: CreateCaseComponent,
 *     canActivate: [permissionGuard('cases:create')]
 *   }
 *
 *   {
 *     path: 'workflows',
 *     component: WorkflowsComponent,
 *     canActivate: [permissionGuard(['workflows:read', 'workflows:execute'], 'any')]
 *   }
 */
export function permissionGuard(
  requiredPermissions: string | string[],
  mode: 'all' | 'any' = 'all'
): CanActivateFn {
  return (route: ActivatedRouteSnapshot) => {
    const rbacService = inject(RbacService);
    const authService = inject(AuthService);
    const router = inject(Router);

    // Check if user is authenticated first
    if (!authService.isAuthenticated()) {
      return router.createUrlTree(['/login'], {
        queryParams: { returnUrl: route.url.join('/') }
      });
    }

    const permissions = Array.isArray(requiredPermissions)
      ? requiredPermissions
      : [requiredPermissions];

    // If permissions are already loaded, check immediately
    if (rbacService.userPermissions()) {
      const hasAccess = mode === 'all'
        ? rbacService.hasAllPermissions(...permissions)
        : rbacService.hasAnyPermission(...permissions);

      if (hasAccess) {
        return true;
      }

      // Redirect to unauthorized page or dashboard
      return router.createUrlTree(['/dashboard'], {
        queryParams: { error: 'unauthorized' }
      });
    }

    // Load permissions first, then check
    return rbacService.getMyPermissions().pipe(
      map(() => {
        const hasAccess = mode === 'all'
          ? rbacService.hasAllPermissions(...permissions)
          : rbacService.hasAnyPermission(...permissions);

        if (hasAccess) {
          return true;
        }

        return router.createUrlTree(['/dashboard'], {
          queryParams: { error: 'unauthorized' }
        });
      }),
      catchError(() => {
        return of(router.createUrlTree(['/login']));
      })
    );
  };
}

/**
 * Guard to ensure user has admin privileges.
 */
export const adminGuard: CanActivateFn = (route) => {
  return permissionGuard('admin:manage')(route);
};

/**
 * Route data interface for permission-based routing.
 */
export interface PermissionRouteData {
  permissions?: string | string[];
  permissionMode?: 'all' | 'any';
}

/**
 * Generic permission guard that reads permissions from route data.
 *
 * Usage:
 *   {
 *     path: 'workflows',
 *     component: WorkflowsComponent,
 *     canActivate: [dataPermissionGuard],
 *     data: { permissions: ['workflows:read'], permissionMode: 'any' }
 *   }
 */
export const dataPermissionGuard: CanActivateFn = (route) => {
  const data = route.data as PermissionRouteData;

  if (!data.permissions) {
    return true; // No permission required
  }

  return permissionGuard(data.permissions, data.permissionMode || 'all')(route);
};
