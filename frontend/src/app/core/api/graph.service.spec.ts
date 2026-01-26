import { TestBed } from '@angular/core/testing';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideHttpClient } from '@angular/common/http';

import { GraphService } from './graph.service';
import {
  mockGraphData,
  mockSavedGraph,
  mockGraphNodes,
  mockGraphEdges,
} from '../../testing';
import { environment } from '../../../environments/environment';

describe('GraphService', () => {
  let service: GraphService;
  let httpMock: HttpTestingController;
  const baseUrl = `${environment.apiUrl}/graphs`;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        GraphService,
        provideHttpClient(),
        provideHttpClientTesting(),
      ],
    });

    service = TestBed.inject(GraphService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
  });

  describe('buildGraph', () => {
    it('should build a graph for a case', () => {
      const request = {
        case_id: 'case-001',
        max_nodes: 100,
        entity_types: ['host', 'user', 'ip'] as any[],
      };

      service.buildGraph(request).subscribe((result) => {
        expect(result).toEqual(mockGraphData);
      });

      const req = httpMock.expectOne(`${baseUrl}/build`);
      expect(req.request.method).toBe('POST');
      expect(req.request.body).toEqual(request);
      req.flush(mockGraphData);
    });

    it('should handle empty graph response', () => {
      const request = { case_id: 'case-empty' };
      const emptyResponse = { nodes: [], edges: [], metadata: {} };

      service.buildGraph(request).subscribe((result) => {
        expect(result.nodes.length).toBe(0);
        expect(result.edges.length).toBe(0);
      });

      const req = httpMock.expectOne(`${baseUrl}/build`);
      req.flush(emptyResponse);
    });
  });

  describe('expandNode', () => {
    it('should expand node connections', () => {
      const request = {
        case_id: 'case-001',
        node_id: 'node-host-1',
        max_connections: 20,
      };

      service.expandNode(request).subscribe((result) => {
        expect(result.nodes.length).toBeGreaterThan(0);
      });

      const req = httpMock.expectOne(`${baseUrl}/expand`);
      expect(req.request.method).toBe('POST');
      expect(req.request.body).toEqual(request);
      req.flush(mockGraphData);
    });
  });

  describe('findPath', () => {
    it('should find path between two nodes', () => {
      const request = {
        case_id: 'case-001',
        source_node: 'node-user-1',
        target_node: 'node-file-1',
        max_hops: 5,
      };

      const pathResponse = {
        found: true,
        path_nodes: ['node-user-1', 'node-host-1', 'node-process-1', 'node-file-1'],
        path_edges: mockGraphEdges.slice(0, 3),
        hops: 3,
      };

      service.findPath(request).subscribe((result) => {
        expect(result.found).toBeTrue();
        expect(result.hops).toBe(3);
        expect(result.path_nodes.length).toBe(4);
      });

      const req = httpMock.expectOne(`${baseUrl}/path`);
      expect(req.request.method).toBe('POST');
      req.flush(pathResponse);
    });

    it('should handle no path found', () => {
      const request = {
        case_id: 'case-001',
        source_node: 'node-1',
        target_node: 'node-99',
      };

      const noPathResponse = {
        found: false,
        path_nodes: [],
        path_edges: [],
        hops: 0,
      };

      service.findPath(request).subscribe((result) => {
        expect(result.found).toBeFalse();
        expect(result.path_nodes.length).toBe(0);
      });

      const req = httpMock.expectOne(`${baseUrl}/path`);
      req.flush(noPathResponse);
    });
  });

  describe('getEntityRelationships', () => {
    it('should get relationships for an entity', () => {
      const relationships = {
        entity_id: 'entity-1',
        entity_type: 'host',
        entity_value: 'WORKSTATION-01',
        relationships: {
          logged_into: [{ entity_id: 'user-1', entity_type: 'user', entity_value: 'john.doe', event_count: 50 }],
        },
        related_entities: mockGraphNodes.slice(0, 2),
      };

      service.getEntityRelationships('case-001', 'host', 'WORKSTATION-01').subscribe((result) => {
        expect(result.entity_type).toBe('host');
        expect(result.relationships).toBeDefined();
      });

      const req = httpMock.expectOne((r) =>
        r.url === `${baseUrl}/entity-relationships` &&
        r.params.get('case_id') === 'case-001' &&
        r.params.get('entity_type') === 'host' &&
        r.params.get('entity_value') === 'WORKSTATION-01'
      );
      expect(req.request.method).toBe('GET');
      req.flush(relationships);
    });
  });

  describe('saveGraph', () => {
    it('should save a graph configuration', () => {
      const graphToSave = {
        name: 'Test Graph',
        description: 'Test description',
        case_id: 'case-001',
        definition: {
          nodes: mockGraphNodes,
          edges: mockGraphEdges,
          positions: { 'node-host-1': { x: 100, y: 100 } },
          zoom: 1.0,
          pan: { x: 0, y: 0 },
        },
        config: {
          layout: 'dagre',
          showLabels: true,
        },
      };

      service.saveGraph(graphToSave).subscribe((result) => {
        expect(result.id).toBeDefined();
        expect(result.name).toBe('Test Graph');
      });

      const req = httpMock.expectOne(`${baseUrl}/saved`);
      expect(req.request.method).toBe('POST');
      req.flush({ ...mockSavedGraph, name: 'Test Graph' });
    });
  });

  describe('listSavedGraphs', () => {
    it('should list saved graphs for a case', () => {
      const response = {
        items: [mockSavedGraph],
        total: 1,
      };

      service.listSavedGraphs('case-001').subscribe((result) => {
        expect(result.items.length).toBe(1);
        expect(result.total).toBe(1);
      });

      const req = httpMock.expectOne((r) =>
        r.url === `${baseUrl}/saved` && r.params.get('case_id') === 'case-001'
      );
      expect(req.request.method).toBe('GET');
      req.flush(response);
    });

    it('should list all saved graphs when no case specified', () => {
      const response = {
        items: [mockSavedGraph, { ...mockSavedGraph, id: 'graph-002' }],
        total: 2,
      };

      service.listSavedGraphs().subscribe((result) => {
        expect(result.items.length).toBe(2);
      });

      const req = httpMock.expectOne(`${baseUrl}/saved`);
      expect(req.request.params.has('case_id')).toBeFalse();
      req.flush(response);
    });
  });

  describe('getSavedGraph', () => {
    it('should get a saved graph by ID', () => {
      service.getSavedGraph('graph-001').subscribe((result) => {
        expect(result.id).toBe('graph-001');
        expect(result.definition).toBeDefined();
      });

      const req = httpMock.expectOne(`${baseUrl}/saved/graph-001`);
      expect(req.request.method).toBe('GET');
      req.flush(mockSavedGraph);
    });
  });

  describe('deleteSavedGraph', () => {
    it('should delete a saved graph', () => {
      service.deleteSavedGraph('graph-001').subscribe((result) => {
        expect(result.status).toBe('deleted');
        expect(result.id).toBe('graph-001');
      });

      const req = httpMock.expectOne(`${baseUrl}/saved/graph-001`);
      expect(req.request.method).toBe('DELETE');
      req.flush({ status: 'deleted', id: 'graph-001' });
    });
  });
});
