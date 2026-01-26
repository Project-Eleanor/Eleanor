/**
 * Mock services for Angular testing.
 * Provides stubbed HTTP services to isolate unit tests from the backend.
 */
import { of } from 'rxjs';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Provider } from '@angular/core';
import { signal, WritableSignal } from '@angular/core';

import { CaseService } from '../core/api/case.service';
import { GraphService } from '../core/api/graph.service';
import { SearchService } from '../core/api/search.service';
import { WorkbookService } from '../core/api/workbook.service';
import { EntityService } from '../core/api/entity.service';
import { RbacService } from '../core/api/rbac.service';

import {
  mockCase,
  mockCaseList,
  mockGraphData,
  mockSavedGraph,
  mockSearchResponse,
  mockWorkbook,
  mockWorkbookList,
  mockEntity,
} from './test-fixtures';

/**
 * Mock HttpClient for tests that need to verify HTTP calls.
 */
export function createMockHttpClient(): jasmine.SpyObj<HttpClient> {
  return jasmine.createSpyObj('HttpClient', ['get', 'post', 'patch', 'put', 'delete']);
}

/**
 * Mock CaseService with predefined responses.
 */
export class MockCaseService {
  list = jasmine.createSpy('list').and.returnValue(of(mockCaseList));
  get = jasmine.createSpy('get').and.returnValue(of(mockCase));
  create = jasmine.createSpy('create').and.returnValue(of(mockCase));
  update = jasmine.createSpy('update').and.returnValue(of(mockCase));
  delete = jasmine.createSpy('delete').and.returnValue(of(undefined));
  getTimeline = jasmine.createSpy('getTimeline').and.returnValue(of([]));
  addTimelineEvent = jasmine.createSpy('addTimelineEvent').and.returnValue(of({}));
}

/**
 * Mock GraphService with predefined responses.
 */
export class MockGraphService {
  buildGraph = jasmine.createSpy('buildGraph').and.returnValue(of(mockGraphData));
  expandNode = jasmine.createSpy('expandNode').and.returnValue(of(mockGraphData));
  findPath = jasmine.createSpy('findPath').and.returnValue(of({ found: false, path_nodes: [], path_edges: [], hops: 0 }));
  getEntityRelationships = jasmine.createSpy('getEntityRelationships').and.returnValue(of({ entity_id: '', entity_type: 'host', entity_value: '', relationships: {}, related_entities: [] }));
  saveGraph = jasmine.createSpy('saveGraph').and.returnValue(of(mockSavedGraph));
  listSavedGraphs = jasmine.createSpy('listSavedGraphs').and.returnValue(of({ items: [mockSavedGraph], total: 1 }));
  getSavedGraph = jasmine.createSpy('getSavedGraph').and.returnValue(of(mockSavedGraph));
  deleteSavedGraph = jasmine.createSpy('deleteSavedGraph').and.returnValue(of({ status: 'deleted', id: 'graph-1' }));
}

/**
 * Mock SearchService with predefined responses.
 */
export class MockSearchService {
  query = jasmine.createSpy('query').and.returnValue(of(mockSearchResponse));
  esql = jasmine.createSpy('esql').and.returnValue(of(mockSearchResponse));
  kql = jasmine.createSpy('kql').and.returnValue(of(mockSearchResponse));
  getSavedQueries = jasmine.createSpy('getSavedQueries').and.returnValue(of([]));
  getSavedQuery = jasmine.createSpy('getSavedQuery').and.returnValue(of({ id: '1', name: 'Test Query', description: null, query: 'test', query_type: 'kql', is_public: false, created_by: 'user1', created_at: '2025-01-01T00:00:00Z', updated_at: '2025-01-01T00:00:00Z', tags: [] }));
  createSavedQuery = jasmine.createSpy('createSavedQuery').and.returnValue(of({ id: '1', name: 'New Query', description: null, query: 'new', query_type: 'kql', is_public: false, created_by: 'user1', created_at: '2025-01-01T00:00:00Z', updated_at: '2025-01-01T00:00:00Z', tags: [] }));
  updateSavedQuery = jasmine.createSpy('updateSavedQuery').and.returnValue(of({ id: '1', name: 'Updated Query', description: null, query: 'updated', query_type: 'kql', is_public: false, created_by: 'user1', created_at: '2025-01-01T00:00:00Z', updated_at: '2025-01-01T00:00:00Z', tags: [] }));
  deleteSavedQuery = jasmine.createSpy('deleteSavedQuery').and.returnValue(of(undefined));
  getIndices = jasmine.createSpy('getIndices').and.returnValue(of([]));
  getSchema = jasmine.createSpy('getSchema').and.returnValue(of({ index: 'test', mappings: {} }));
}

/**
 * Mock WorkbookService with predefined responses.
 */
export class MockWorkbookService {
  listWorkbooks = jasmine.createSpy('listWorkbooks').and.returnValue(of(mockWorkbookList));
  getWorkbook = jasmine.createSpy('getWorkbook').and.returnValue(of(mockWorkbook));
  createWorkbook = jasmine.createSpy('createWorkbook').and.returnValue(of(mockWorkbook));
  updateWorkbook = jasmine.createSpy('updateWorkbook').and.returnValue(of(mockWorkbook));
  deleteWorkbook = jasmine.createSpy('deleteWorkbook').and.returnValue(of({ status: 'deleted', id: 'wb-1' }));
  cloneWorkbook = jasmine.createSpy('cloneWorkbook').and.returnValue(of(mockWorkbook));
  listTemplates = jasmine.createSpy('listTemplates').and.returnValue(of([]));
  createFromTemplate = jasmine.createSpy('createFromTemplate').and.returnValue(of(mockWorkbook));
  executeTile = jasmine.createSpy('executeTile').and.returnValue(of({ data: [], metadata: {} }));
}

/**
 * Mock EntityService with predefined responses.
 */
export class MockEntityService {
  search = jasmine.createSpy('search').and.returnValue(of({ items: [mockEntity], total: 1 }));
  get = jasmine.createSpy('get').and.returnValue(of(mockEntity));
  getHostProfile = jasmine.createSpy('getHostProfile').and.returnValue(of({ hostname: 'test-host', ip_addresses: [], mac_addresses: [], os_name: null, os_version: null, domain: null, last_seen: null, agent_id: null, agent_version: null, recent_events: [], installed_software: [], open_ports: [] }));
  getUserProfile = jasmine.createSpy('getUserProfile').and.returnValue(of({ username: 'testuser', display_name: null, email: null, domain: null, sid: null, groups: [], last_logon: null, logon_history: [], permissions: [] }));
  getIPProfile = jasmine.createSpy('getIPProfile').and.returnValue(of({ ip_address: '10.0.0.1', ip_version: 4, is_private: true, geolocation: null, asn: null, reputation: null, related_domains: [], related_connections: [] }));
  getEntityEvents = jasmine.createSpy('getEntityEvents').and.returnValue(of([]));
  enrich = jasmine.createSpy('enrich').and.returnValue(of(mockEntity));
  getRelatedCases = jasmine.createSpy('getRelatedCases').and.returnValue(of([]));
}

/**
 * Mock RbacService with permission controls for testing.
 */
export class MockRbacService {
  private _permissions: WritableSignal<string[]> = signal(['cases:read', 'cases:create', 'cases:update', 'cases:delete']);

  permissions = this._permissions.asReadonly();

  setPermissions(perms: string[]): void {
    this._permissions.set(perms);
  }

  hasPermission = jasmine.createSpy('hasPermission').and.callFake((perm: string) => {
    return this._permissions().includes(perm);
  });

  hasAnyPermission = jasmine.createSpy('hasAnyPermission').and.callFake((...perms: string[]) => {
    return perms.some(p => this._permissions().includes(p));
  });

  hasAllPermissions = jasmine.createSpy('hasAllPermissions').and.callFake((...perms: string[]) => {
    return perms.every(p => this._permissions().includes(p));
  });

  loadPermissions = jasmine.createSpy('loadPermissions').and.returnValue(of(undefined));
}

/**
 * Provider helper to inject mock services in TestBed.
 */
export function provideMockServices(): Provider[] {
  return [
    { provide: CaseService, useClass: MockCaseService },
    { provide: GraphService, useClass: MockGraphService },
    { provide: SearchService, useClass: MockSearchService },
    { provide: WorkbookService, useClass: MockWorkbookService },
    { provide: EntityService, useClass: MockEntityService },
    { provide: RbacService, useClass: MockRbacService },
  ];
}

/**
 * Provider for a single mock service.
 */
export function provideMockService<T>(serviceToken: any, mockClass: new () => T): Provider {
  return { provide: serviceToken, useClass: mockClass };
}
