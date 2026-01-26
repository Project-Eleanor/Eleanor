export type TenantStatus = 'active' | 'suspended' | 'pending';
export type TenantPlan = 'free' | 'professional' | 'enterprise';
export type TenantMembershipRole = 'owner' | 'admin' | 'member' | 'viewer';

export interface TenantSettings {
  max_users?: number;
  max_cases?: number;
  max_evidence_gb?: number;
  retention_days?: number;
  features?: string[];
  branding?: {
    logo_url?: string;
    primary_color?: string;
  };
}

export interface Tenant {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  status: TenantStatus;
  plan: TenantPlan;
  contact_email: string | null;
  contact_name: string | null;
  domain: string | null;
  settings: TenantSettings;
  created_at: string;
  updated_at: string;
  member_count: number;
}

export interface TenantCreate {
  name: string;
  slug: string;
  description?: string;
  contact_email?: string;
  contact_name?: string;
  plan?: TenantPlan;
  domain?: string;
  settings?: TenantSettings;
}

export interface TenantUpdate {
  name?: string;
  description?: string;
  contact_email?: string;
  contact_name?: string;
  status?: TenantStatus;
  plan?: TenantPlan;
  domain?: string;
  settings?: TenantSettings;
}

export interface TenantMembership {
  id: string;
  tenant_id: string;
  user_id: string;
  role: TenantMembershipRole;
  is_default: boolean;
  joined_at: string;
  user_email?: string;
  user_display_name?: string;
}

export interface TenantMembershipCreate {
  user_id: string;
  role?: TenantMembershipRole;
  is_default?: boolean;
}

export interface TenantMembershipUpdate {
  role?: TenantMembershipRole;
  is_default?: boolean;
}

export interface TenantAPIKey {
  id: string;
  name: string;
  key_prefix: string;
  scopes: string[];
  is_active: boolean;
  expires_at: string | null;
  last_used_at: string | null;
  created_at: string;
}

export interface TenantAPIKeyCreate {
  name: string;
  scopes?: string[];
  expires_at?: string;
}

export interface TenantAPIKeyCreated extends TenantAPIKey {
  key: string; // Full key, only shown once
}

export interface TenantAdapterConfig {
  id: string;
  adapter_type: string;
  config: Record<string, unknown>;
  is_enabled: boolean;
  health_status: string | null;
  last_health_check: string | null;
  created_at: string;
  updated_at: string;
}

export interface TenantAdapterConfigCreate {
  adapter_type: string;
  config?: Record<string, unknown>;
  is_enabled?: boolean;
}

export interface TenantAdapterConfigUpdate {
  config?: Record<string, unknown>;
  is_enabled?: boolean;
}

// Context for current tenant
export interface TenantContext {
  tenant_id: string;
  tenant_slug: string;
  tenant_name: string;
  features: string[];
}
