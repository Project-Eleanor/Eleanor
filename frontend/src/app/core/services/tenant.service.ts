import { Injectable, signal, computed } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable, tap } from 'rxjs';
import { environment } from '../../../environments/environment';
import {
  Tenant,
  TenantCreate,
  TenantUpdate,
  TenantMembership,
  TenantMembershipCreate,
  TenantMembershipUpdate,
  TenantAPIKey,
  TenantAPIKeyCreate,
  TenantAPIKeyCreated,
  TenantAdapterConfig,
  TenantAdapterConfigCreate,
  TenantAdapterConfigUpdate,
  TenantStatus,
  TenantPlan,
  TenantContext
} from '../../shared/models/tenant.model';

const TENANT_STORAGE_KEY = 'eleanor_current_tenant';

@Injectable({
  providedIn: 'root'
})
export class TenantService {
  private apiUrl = `${environment.apiUrl}/admin/tenants`;

  // Reactive state for current tenant
  private _currentTenant = signal<TenantContext | null>(null);

  // Public readable signals
  readonly currentTenant = this._currentTenant.asReadonly();
  readonly tenantId = computed(() => this._currentTenant()?.tenant_id ?? null);
  readonly tenantSlug = computed(() => this._currentTenant()?.tenant_slug ?? null);
  readonly tenantName = computed(() => this._currentTenant()?.tenant_name ?? null);
  readonly features = computed(() => this._currentTenant()?.features ?? []);
  readonly hasTenant = computed(() => this._currentTenant() !== null);

  constructor(private http: HttpClient) {
    // Restore tenant from storage on init
    this.restoreFromStorage();
  }

  // ==========================================================================
  // Tenant Context Management
  // ==========================================================================

  setCurrentTenant(tenant: Tenant): void {
    const context: TenantContext = {
      tenant_id: tenant.id,
      tenant_slug: tenant.slug,
      tenant_name: tenant.name,
      features: tenant.settings.features ?? []
    };
    this._currentTenant.set(context);
    this.saveToStorage(context);
  }

  clearCurrentTenant(): void {
    this._currentTenant.set(null);
    localStorage.removeItem(TENANT_STORAGE_KEY);
  }

  hasFeature(feature: string): boolean {
    return this.features().includes(feature);
  }

  private restoreFromStorage(): void {
    const stored = localStorage.getItem(TENANT_STORAGE_KEY);
    if (stored) {
      try {
        const context = JSON.parse(stored) as TenantContext;
        this._currentTenant.set(context);
      } catch {
        localStorage.removeItem(TENANT_STORAGE_KEY);
      }
    }
  }

  private saveToStorage(context: TenantContext): void {
    localStorage.setItem(TENANT_STORAGE_KEY, JSON.stringify(context));
  }

  // ==========================================================================
  // Tenant CRUD
  // ==========================================================================

  list(params?: {
    status?: TenantStatus;
    plan?: TenantPlan;
    search?: string;
    skip?: number;
    limit?: number;
  }): Observable<Tenant[]> {
    let httpParams = new HttpParams();

    if (params) {
      if (params.status) httpParams = httpParams.set('status', params.status);
      if (params.plan) httpParams = httpParams.set('plan', params.plan);
      if (params.search) httpParams = httpParams.set('search', params.search);
      if (params.skip !== undefined) httpParams = httpParams.set('skip', params.skip.toString());
      if (params.limit !== undefined) httpParams = httpParams.set('limit', params.limit.toString());
    }

    return this.http.get<Tenant[]>(this.apiUrl, { params: httpParams });
  }

  get(tenantId: string): Observable<Tenant> {
    return this.http.get<Tenant>(`${this.apiUrl}/${tenantId}`);
  }

  create(data: TenantCreate): Observable<Tenant> {
    return this.http.post<Tenant>(this.apiUrl, data);
  }

  update(tenantId: string, data: TenantUpdate): Observable<Tenant> {
    return this.http.patch<Tenant>(`${this.apiUrl}/${tenantId}`, data);
  }

  delete(tenantId: string): Observable<void> {
    return this.http.delete<void>(`${this.apiUrl}/${tenantId}`);
  }

  // ==========================================================================
  // Membership Management
  // ==========================================================================

  listMembers(tenantId: string): Observable<TenantMembership[]> {
    return this.http.get<TenantMembership[]>(`${this.apiUrl}/${tenantId}/members`);
  }

  addMember(tenantId: string, data: TenantMembershipCreate): Observable<TenantMembership> {
    return this.http.post<TenantMembership>(`${this.apiUrl}/${tenantId}/members`, data);
  }

  updateMember(
    tenantId: string,
    userId: string,
    data: TenantMembershipUpdate
  ): Observable<TenantMembership> {
    return this.http.patch<TenantMembership>(
      `${this.apiUrl}/${tenantId}/members/${userId}`,
      data
    );
  }

  removeMember(tenantId: string, userId: string): Observable<void> {
    return this.http.delete<void>(`${this.apiUrl}/${tenantId}/members/${userId}`);
  }

  // ==========================================================================
  // API Key Management
  // ==========================================================================

  listAPIKeys(tenantId: string): Observable<TenantAPIKey[]> {
    return this.http.get<TenantAPIKey[]>(`${this.apiUrl}/${tenantId}/api-keys`);
  }

  createAPIKey(tenantId: string, data: TenantAPIKeyCreate): Observable<TenantAPIKeyCreated> {
    return this.http.post<TenantAPIKeyCreated>(`${this.apiUrl}/${tenantId}/api-keys`, data);
  }

  revokeAPIKey(tenantId: string, keyId: string): Observable<void> {
    return this.http.delete<void>(`${this.apiUrl}/${tenantId}/api-keys/${keyId}`);
  }

  // ==========================================================================
  // Adapter Configuration
  // ==========================================================================

  listAdapterConfigs(tenantId: string): Observable<TenantAdapterConfig[]> {
    return this.http.get<TenantAdapterConfig[]>(`${this.apiUrl}/${tenantId}/adapters`);
  }

  createAdapterConfig(
    tenantId: string,
    data: TenantAdapterConfigCreate
  ): Observable<TenantAdapterConfig> {
    return this.http.post<TenantAdapterConfig>(`${this.apiUrl}/${tenantId}/adapters`, data);
  }

  updateAdapterConfig(
    tenantId: string,
    adapterType: string,
    data: TenantAdapterConfigUpdate
  ): Observable<TenantAdapterConfig> {
    return this.http.patch<TenantAdapterConfig>(
      `${this.apiUrl}/${tenantId}/adapters/${adapterType}`,
      data
    );
  }

  deleteAdapterConfig(tenantId: string, adapterType: string): Observable<void> {
    return this.http.delete<void>(`${this.apiUrl}/${tenantId}/adapters/${adapterType}`);
  }
}
