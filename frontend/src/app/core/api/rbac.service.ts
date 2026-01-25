import { Injectable, inject, signal, computed } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, tap } from 'rxjs';
import { AppConfigService } from '../config/app-config.service';
import {
  Permission,
  Role,
  RoleCreate,
  RoleUpdate,
  UserPermissions,
  UserRoleAssignment,
  hasPermission
} from '../../shared/models';

@Injectable({
  providedIn: 'root'
})
export class RbacService {
  private readonly config = inject(AppConfigService);
  private readonly http = inject(HttpClient);

  private get apiUrl(): string {
    return `${this.config.apiUrl}/rbac`;
  }

  // Current user's permissions - cached
  private readonly userPermissionsSignal = signal<UserPermissions | null>(null);

  readonly userPermissions = this.userPermissionsSignal.asReadonly();
  readonly isAdmin = computed(() => this.userPermissionsSignal()?.is_admin ?? false);
  readonly roles = computed(() => this.userPermissionsSignal()?.roles ?? []);
  readonly permissions = computed(() => this.userPermissionsSignal()?.permissions ?? []);

  // ==========================================================================
  // Permission Operations
  // ==========================================================================

  /**
   * List all permissions.
   */
  getPermissions(scope?: string): Observable<Permission[]> {
    if (scope) {
      return this.http.get<Permission[]>(`${this.apiUrl}/permissions`, { params: { scope } });
    }
    return this.http.get<Permission[]>(`${this.apiUrl}/permissions`);
  }

  // ==========================================================================
  // Role Operations
  // ==========================================================================

  /**
   * List all roles.
   */
  getRoles(): Observable<Role[]> {
    return this.http.get<Role[]>(`${this.apiUrl}/roles`);
  }

  /**
   * Get a role by ID.
   */
  getRole(roleId: string): Observable<Role> {
    return this.http.get<Role>(`${this.apiUrl}/roles/${roleId}`);
  }

  /**
   * Create a new role.
   */
  createRole(role: RoleCreate): Observable<Role> {
    return this.http.post<Role>(`${this.apiUrl}/roles`, role);
  }

  /**
   * Update a role.
   */
  updateRole(roleId: string, updates: RoleUpdate): Observable<Role> {
    return this.http.patch<Role>(`${this.apiUrl}/roles/${roleId}`, updates);
  }

  /**
   * Delete a role.
   */
  deleteRole(roleId: string): Observable<void> {
    return this.http.delete<void>(`${this.apiUrl}/roles/${roleId}`);
  }

  // ==========================================================================
  // User Permission Operations
  // ==========================================================================

  /**
   * Get current user's permissions.
   * Caches the result for quick access via signals.
   */
  getMyPermissions(): Observable<UserPermissions> {
    return this.http.get<UserPermissions>(`${this.apiUrl}/users/me/permissions`).pipe(
      tap(perms => this.userPermissionsSignal.set(perms))
    );
  }

  /**
   * Get a specific user's permissions.
   */
  getUserPermissions(userId: string): Observable<UserPermissions> {
    return this.http.get<UserPermissions>(`${this.apiUrl}/users/${userId}/permissions`);
  }

  /**
   * Assign roles to a user.
   */
  assignUserRoles(userId: string, roleIds: string[]): Observable<UserPermissions> {
    const assignment: UserRoleAssignment = { role_ids: roleIds };
    return this.http.put<UserPermissions>(`${this.apiUrl}/users/${userId}/roles`, assignment);
  }

  // ==========================================================================
  // Permission Checks
  // ==========================================================================

  /**
   * Check if current user has a specific permission.
   */
  hasPermission(permission: string): boolean {
    const perms = this.userPermissionsSignal();
    if (!perms) return false;
    if (perms.is_admin) return true;
    return hasPermission(perms.permissions, permission);
  }

  /**
   * Check if current user has any of the specified permissions.
   */
  hasAnyPermission(...permissions: string[]): boolean {
    return permissions.some(p => this.hasPermission(p));
  }

  /**
   * Check if current user has all of the specified permissions.
   */
  hasAllPermissions(...permissions: string[]): boolean {
    return permissions.every(p => this.hasPermission(p));
  }

  /**
   * Check if current user has a specific role.
   */
  hasRole(role: string): boolean {
    const perms = this.userPermissionsSignal();
    if (!perms) return false;
    return perms.roles.includes(role);
  }

  /**
   * Clear cached permissions (call on logout).
   */
  clearPermissions(): void {
    this.userPermissionsSignal.set(null);
  }
}
