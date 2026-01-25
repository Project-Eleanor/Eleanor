/**
 * RBAC (Role-Based Access Control) models.
 */

export interface Permission {
  id: string;
  name: string;
  description: string | null;
  scope: PermissionScope;
  action: PermissionAction;
  resource: string | null;
}

export type PermissionScope =
  | 'cases'
  | 'evidence'
  | 'search'
  | 'entities'
  | 'enrichment'
  | 'collection'
  | 'workflows'
  | 'integrations'
  | 'analytics'
  | 'connectors'
  | 'users'
  | 'admin';

export type PermissionAction =
  | 'create'
  | 'read'
  | 'update'
  | 'delete'
  | 'execute'
  | 'approve'
  | 'manage';

export interface Role {
  id: string;
  name: string;
  description: string | null;
  is_system: boolean;
  priority: number;
  permissions: Permission[];
}

export interface RoleCreate {
  name: string;
  description?: string;
  permissions?: string[];
}

export interface RoleUpdate {
  name?: string;
  description?: string;
  permissions?: string[];
}

export interface UserPermissions {
  user_id: string;
  username: string;
  is_admin: boolean;
  roles: string[];
  permissions: string[];
}

export interface UserRoleAssignment {
  role_ids: string[];
}

/**
 * Check if a permission string matches a required permission.
 * Supports wildcards: "cases:*" matches "cases:read"
 */
export function hasPermission(userPermissions: string[], required: string): boolean {
  // Admin wildcard
  if (userPermissions.includes('*')) {
    return true;
  }

  // Exact match
  if (userPermissions.includes(required)) {
    return true;
  }

  // Scope wildcard (e.g., "cases:*" matches "cases:read")
  const [scope] = required.split(':');
  if (userPermissions.includes(`${scope}:*`)) {
    return true;
  }

  return false;
}
