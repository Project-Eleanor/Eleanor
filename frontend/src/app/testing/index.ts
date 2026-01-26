/**
 * Eleanor Frontend Testing Utilities
 *
 * This module exports all testing utilities for use in spec files.
 *
 * Usage:
 *   import { MockCaseService, mockCase, queryHelper } from '../../testing';
 */

// Mock services
export {
  createMockHttpClient,
  MockCaseService,
  MockGraphService,
  MockSearchService,
  MockWorkbookService,
  MockEntityService,
  MockRbacService,
  provideMockServices,
  provideMockService,
} from './mock-services';

// Test fixtures
export {
  // Cases
  mockCase,
  mockCaseList,
  mockTimelineEvent,
  createMockCase,
  // Graphs
  mockGraphNodes,
  mockGraphEdges,
  mockGraphData,
  mockSavedGraph,
  createMockGraphNode,
  // Search
  mockSearchResult,
  mockSearchResponse,
  mockSavedQuery,
  createMockSearchResult,
  // Workbooks
  mockTile,
  mockWorkbookDefinition,
  mockWorkbook,
  mockWorkbookList,
  createMockWorkbook,
  // Entities
  mockEntity,
  mockEntityEvent,
  createMockEntity,
} from './test-fixtures';

// Component helpers
export {
  configureServiceTestBed,
  configureComponentTestBed,
  configureHttpTestBed,
  createComponentWithAutoDetect,
  ComponentQuery,
  queryHelper,
  typeInInput,
  click,
  waitForAsync,
  createSpyObj,
  expectToHaveClass,
  expectNotToHaveClass,
  expectToBeVisible,
  expectToBeDisabled,
  expectToBeEnabled,
  mockActivatedRoute,
  mockObservable,
  mockErrorObservable,
} from './component-helpers';
