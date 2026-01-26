import { TestBed } from '@angular/core/testing';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideHttpClient } from '@angular/common/http';

import { WorkbookService } from './workbook.service';
import { mockWorkbook, mockWorkbookList, mockTile } from '../../testing';
import { environment } from '../../../environments/environment';
import { WorkbookCreate, WorkbookUpdate, TileExecuteRequest } from '../../shared/models/workbook.model';

describe('WorkbookService', () => {
  let service: WorkbookService;
  let httpMock: HttpTestingController;
  const baseUrl = `${environment.apiUrl}/workbooks`;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        WorkbookService,
        provideHttpClient(),
        provideHttpClientTesting(),
      ],
    });

    service = TestBed.inject(WorkbookService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
  });

  describe('listWorkbooks', () => {
    it('should list workbooks with pagination', () => {
      service.listWorkbooks({ page: 1, page_size: 20 }).subscribe((result) => {
        expect(result.items.length).toBe(2);
        expect(result.total).toBe(2);
      });

      const req = httpMock.expectOne((r) =>
        r.url === baseUrl &&
        r.params.get('page') === '1' &&
        r.params.get('page_size') === '20'
      );
      expect(req.request.method).toBe('GET');
      req.flush(mockWorkbookList);
    });

    it('should filter by is_public', () => {
      service.listWorkbooks({ is_public: true }).subscribe((result) => {
        expect(result.items).toBeDefined();
      });

      const req = httpMock.expectOne((r) =>
        r.url === baseUrl && r.params.get('is_public') === 'true'
      );
      req.flush({ ...mockWorkbookList, items: [mockWorkbookList.items[1]] });
    });

    it('should handle empty list', () => {
      service.listWorkbooks().subscribe((result) => {
        expect(result.items.length).toBe(0);
        expect(result.total).toBe(0);
      });

      const req = httpMock.expectOne(baseUrl);
      req.flush({ items: [], total: 0, page: 1, page_size: 20, pages: 0 });
    });
  });

  describe('getWorkbook', () => {
    it('should get a workbook by ID', () => {
      service.getWorkbook('wb-001').subscribe((result) => {
        expect(result.id).toBe('wb-001');
        expect(result.name).toBe('Investigation Dashboard');
        expect(result.definition.tiles.length).toBeGreaterThan(0);
      });

      const req = httpMock.expectOne(`${baseUrl}/wb-001`);
      expect(req.request.method).toBe('GET');
      req.flush(mockWorkbook);
    });
  });

  describe('createWorkbook', () => {
    it('should create a new workbook', () => {
      const newWorkbook: WorkbookCreate = {
        name: 'New Workbook',
        description: 'Test workbook',
        definition: mockWorkbook.definition,
        is_public: false,
      };

      service.createWorkbook(newWorkbook).subscribe((result) => {
        expect(result.name).toBe('New Workbook');
        expect(result.id).toBeDefined();
      });

      const req = httpMock.expectOne(baseUrl);
      expect(req.request.method).toBe('POST');
      expect(req.request.body).toEqual(newWorkbook);
      req.flush({ ...mockWorkbook, name: 'New Workbook', id: 'wb-new' });
    });

    it('should create a minimal workbook', () => {
      const minimalWorkbook: WorkbookCreate = {
        name: 'Minimal',
      };

      service.createWorkbook(minimalWorkbook).subscribe((result) => {
        expect(result.name).toBe('Minimal');
      });

      const req = httpMock.expectOne(baseUrl);
      req.flush({
        ...mockWorkbook,
        name: 'Minimal',
        definition: { tiles: [], layout: { columns: 12, row_height: 80 }, variables: {} },
      });
    });
  });

  describe('updateWorkbook', () => {
    it('should update a workbook', () => {
      const update: WorkbookUpdate = {
        name: 'Updated Name',
        is_public: true,
      };

      service.updateWorkbook('wb-001', update).subscribe((result) => {
        expect(result.name).toBe('Updated Name');
        expect(result.is_public).toBeTrue();
      });

      const req = httpMock.expectOne(`${baseUrl}/wb-001`);
      expect(req.request.method).toBe('PATCH');
      expect(req.request.body).toEqual(update);
      req.flush({ ...mockWorkbook, name: 'Updated Name', is_public: true });
    });

    it('should update workbook definition', () => {
      const update: WorkbookUpdate = {
        definition: {
          ...mockWorkbook.definition,
          tiles: [...mockWorkbook.definition.tiles, mockTile],
        },
      };

      service.updateWorkbook('wb-001', update).subscribe((result) => {
        expect(result.definition.tiles.length).toBe(4);
      });

      const req = httpMock.expectOne(`${baseUrl}/wb-001`);
      req.flush({ ...mockWorkbook, definition: update.definition });
    });
  });

  describe('deleteWorkbook', () => {
    it('should delete a workbook', () => {
      service.deleteWorkbook('wb-001').subscribe((result) => {
        expect(result.status).toBe('deleted');
        expect(result.id).toBe('wb-001');
      });

      const req = httpMock.expectOne(`${baseUrl}/wb-001`);
      expect(req.request.method).toBe('DELETE');
      req.flush({ status: 'deleted', id: 'wb-001' });
    });
  });

  describe('cloneWorkbook', () => {
    it('should clone a workbook with new name', () => {
      service.cloneWorkbook('wb-001', 'Cloned Workbook').subscribe((result) => {
        expect(result.name).toBe('Cloned Workbook');
        expect(result.id).not.toBe('wb-001');
      });

      const req = httpMock.expectOne((r) =>
        r.url === `${baseUrl}/wb-001/clone` && r.params.get('name') === 'Cloned Workbook'
      );
      expect(req.request.method).toBe('POST');
      req.flush({ ...mockWorkbook, id: 'wb-clone', name: 'Cloned Workbook' });
    });
  });

  describe('listTemplates', () => {
    it('should list available templates', () => {
      const templates = [
        { name: 'incident-response', description: 'IR Workbook Template', tile_count: 6 },
        { name: 'threat-hunting', description: 'Threat Hunting Template', tile_count: 8 },
      ];

      service.listTemplates().subscribe((result) => {
        expect(result.length).toBe(2);
        expect(result[0].name).toBe('incident-response');
      });

      const req = httpMock.expectOne(`${baseUrl}/templates`);
      expect(req.request.method).toBe('GET');
      req.flush(templates);
    });
  });

  describe('createFromTemplate', () => {
    it('should create workbook from template', () => {
      service.createFromTemplate('incident-response', 'My IR Workbook').subscribe((result) => {
        expect(result.name).toBe('My IR Workbook');
      });

      const req = httpMock.expectOne((r) =>
        r.url === `${baseUrl}/templates/incident-response` &&
        r.params.get('name') === 'My IR Workbook'
      );
      expect(req.request.method).toBe('POST');
      req.flush({ ...mockWorkbook, name: 'My IR Workbook' });
    });
  });

  describe('executeTile', () => {
    it('should execute a tile query', () => {
      const request: TileExecuteRequest = {
        tile_type: 'table',
        config: {
          query: 'FROM eleanor-events-* | LIMIT 10',
          columns: ['@timestamp', 'message'],
        },
        case_id: 'case-001',
      };

      const response = {
        data: [
          { '@timestamp': '2025-01-15T10:00:00Z', message: 'Test event' },
        ],
        metadata: { took: 15, total: 1 },
      };

      service.executeTile(request).subscribe((result) => {
        expect(result.data.length).toBe(1);
        expect(result.metadata.took).toBe(15);
      });

      const req = httpMock.expectOne(`${baseUrl}/execute-tile`);
      expect(req.request.method).toBe('POST');
      expect(req.request.body).toEqual(request);
      req.flush(response);
    });

    it('should execute a metric tile', () => {
      const request: TileExecuteRequest = {
        tile_type: 'metric',
        config: {
          query: 'FROM eleanor-events-* | STATS COUNT(*)',
          aggregation: 'count',
        },
      };

      const response = {
        data: { value: 12500 },
        metadata: { took: 5 },
      };

      service.executeTile(request).subscribe((result) => {
        expect(result.data.value).toBe(12500);
      });

      const req = httpMock.expectOne(`${baseUrl}/execute-tile`);
      req.flush(response);
    });

    it('should pass variables to tile execution', () => {
      const request: TileExecuteRequest = {
        tile_type: 'table',
        config: { query: 'FROM $index | LIMIT 10' },
        variables: { index: 'eleanor-events-2025.01' },
      };

      service.executeTile(request).subscribe();

      const req = httpMock.expectOne(`${baseUrl}/execute-tile`);
      expect(req.request.body.variables).toEqual({ index: 'eleanor-events-2025.01' });
      req.flush({ data: [], metadata: {} });
    });
  });
});
