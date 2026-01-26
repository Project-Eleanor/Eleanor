import { TestBed } from '@angular/core/testing';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideHttpClient } from '@angular/common/http';

import { SearchService } from './search.service';
import { mockSearchResponse, mockSavedQuery } from '../../testing';
import { environment } from '../../../environments/environment';
import { SearchQuery, SavedQueryCreate } from '../../shared/models';

describe('SearchService', () => {
  let service: SearchService;
  let httpMock: HttpTestingController;
  const baseUrl = `${environment.apiUrl}/search`;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        SearchService,
        provideHttpClient(),
        provideHttpClientTesting(),
      ],
    });

    service = TestBed.inject(SearchService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
  });

  describe('query', () => {
    it('should execute a search query', () => {
      const searchQuery: SearchQuery = {
        query: 'process.name:powershell.exe',
        index: 'eleanor-events-*',
        from: 0,
        size: 100,
      };

      service.query(searchQuery).subscribe((result) => {
        expect(result.total).toBe(100);
        expect(result.hits.length).toBe(2);
        expect(result.took).toBe(15);
      });

      const req = httpMock.expectOne(`${baseUrl}/query`);
      expect(req.request.method).toBe('POST');
      expect(req.request.body).toEqual(searchQuery);
      req.flush(mockSearchResponse);
    });

    it('should handle empty results', () => {
      const searchQuery: SearchQuery = { query: 'nonexistent:value' };

      service.query(searchQuery).subscribe((result) => {
        expect(result.total).toBe(0);
        expect(result.hits.length).toBe(0);
      });

      const req = httpMock.expectOne(`${baseUrl}/query`);
      req.flush({ total: 0, hits: [], took: 5 });
    });

    it('should include filters in the query', () => {
      const searchQuery: SearchQuery = {
        query: '*',
        filters: {
          'event.category': ['process', 'network'],
          'host.name': 'WORKSTATION-01',
        },
      };

      service.query(searchQuery).subscribe();

      const req = httpMock.expectOne(`${baseUrl}/query`);
      expect(req.request.body.filters).toEqual({
        'event.category': ['process', 'network'],
        'host.name': 'WORKSTATION-01',
      });
      req.flush(mockSearchResponse);
    });
  });

  describe('esql', () => {
    it('should execute an ES|QL query', () => {
      const esqlQuery = 'FROM eleanor-events-* | WHERE process.name == "powershell.exe" | LIMIT 100';

      service.esql(esqlQuery).subscribe((result) => {
        expect(result.hits).toBeDefined();
      });

      const req = httpMock.expectOne(`${baseUrl}/esql`);
      expect(req.request.method).toBe('POST');
      expect(req.request.body.query).toBe(esqlQuery);
      req.flush(mockSearchResponse);
    });

    it('should pass pagination params', () => {
      const esqlQuery = 'FROM eleanor-events-*';

      service.esql(esqlQuery, { from: 100, size: 50 }).subscribe();

      const req = httpMock.expectOne(`${baseUrl}/esql`);
      expect(req.request.body.from).toBe(100);
      expect(req.request.body.size).toBe(50);
      req.flush(mockSearchResponse);
    });
  });

  describe('kql', () => {
    it('should execute a KQL query', () => {
      const kqlQuery = 'process.name:powershell.exe AND event.type:start';

      service.kql(kqlQuery).subscribe((result) => {
        expect(result.hits).toBeDefined();
      });

      const req = httpMock.expectOne(`${baseUrl}/kql`);
      expect(req.request.method).toBe('POST');
      expect(req.request.body.query).toBe(kqlQuery);
      req.flush(mockSearchResponse);
    });

    it('should specify indices for KQL', () => {
      const kqlQuery = 'host.name:*';

      service.kql(kqlQuery, { indices: ['eleanor-events-2025.01', 'eleanor-events-2025.02'] }).subscribe();

      const req = httpMock.expectOne(`${baseUrl}/kql`);
      expect(req.request.body.indices).toEqual(['eleanor-events-2025.01', 'eleanor-events-2025.02']);
      req.flush(mockSearchResponse);
    });
  });

  describe('getSavedQueries', () => {
    it('should list saved queries', () => {
      const savedQueries = [mockSavedQuery];

      service.getSavedQueries().subscribe((result) => {
        expect(result.length).toBe(1);
        expect(result[0].name).toBe('PowerShell Execution');
      });

      const req = httpMock.expectOne(`${baseUrl}/saved`);
      expect(req.request.method).toBe('GET');
      req.flush(savedQueries);
    });
  });

  describe('getSavedQuery', () => {
    it('should get a saved query by ID', () => {
      service.getSavedQuery('query-001').subscribe((result) => {
        expect(result.id).toBe('query-001');
        expect(result.query_type).toBe('kql');
      });

      const req = httpMock.expectOne(`${baseUrl}/saved/query-001`);
      expect(req.request.method).toBe('GET');
      req.flush(mockSavedQuery);
    });
  });

  describe('createSavedQuery', () => {
    it('should create a new saved query', () => {
      const newQuery: SavedQueryCreate = {
        name: 'New Query',
        query: 'event.category:malware',
        query_type: 'kql',
        is_public: true,
        tags: ['detection'],
      };

      service.createSavedQuery(newQuery).subscribe((result) => {
        expect(result.name).toBe('New Query');
        expect(result.id).toBeDefined();
      });

      const req = httpMock.expectOne(`${baseUrl}/saved`);
      expect(req.request.method).toBe('POST');
      expect(req.request.body).toEqual(newQuery);
      req.flush({ ...mockSavedQuery, ...newQuery, id: 'query-new' });
    });
  });

  describe('updateSavedQuery', () => {
    it('should update a saved query', () => {
      const update = { name: 'Updated Query Name' };

      service.updateSavedQuery('query-001', update).subscribe((result) => {
        expect(result.name).toBe('Updated Query Name');
      });

      const req = httpMock.expectOne(`${baseUrl}/saved/query-001`);
      expect(req.request.method).toBe('PATCH');
      expect(req.request.body).toEqual(update);
      req.flush({ ...mockSavedQuery, name: 'Updated Query Name' });
    });
  });

  describe('deleteSavedQuery', () => {
    it('should delete a saved query', () => {
      service.deleteSavedQuery('query-001').subscribe();

      const req = httpMock.expectOne(`${baseUrl}/saved/query-001`);
      expect(req.request.method).toBe('DELETE');
      req.flush(null);
    });
  });

  describe('getIndices', () => {
    it('should list available indices', () => {
      const indices = [
        { index: 'eleanor-events-2025.01', docs_count: '10000', store_size: '100mb', health: 'green' },
        { index: 'eleanor-events-2025.02', docs_count: '5000', store_size: '50mb', health: 'green' },
      ];

      service.getIndices().subscribe((result) => {
        expect(result.length).toBe(2);
        expect(result[0].index).toBe('eleanor-events-2025.01');
      });

      const req = httpMock.expectOne(`${baseUrl}/indices`);
      expect(req.request.method).toBe('GET');
      req.flush(indices);
    });
  });

  describe('getSchema', () => {
    it('should get field mappings for an index', () => {
      const schema = {
        index: 'eleanor-events-2025.01',
        mappings: {
          properties: {
            '@timestamp': { type: 'date' },
            'event.category': { type: 'keyword' },
            message: { type: 'text' },
          },
        },
      };

      service.getSchema('eleanor-events-2025.01').subscribe((result) => {
        expect(result.index).toBe('eleanor-events-2025.01');
        expect(result.mappings).toBeDefined();
      });

      const req = httpMock.expectOne(`${baseUrl}/schema/eleanor-events-2025.01`);
      expect(req.request.method).toBe('GET');
      req.flush(schema);
    });

    it('should handle special characters in index name', () => {
      service.getSchema('eleanor-events-*').subscribe();

      const req = httpMock.expectOne(`${baseUrl}/schema/eleanor-events-*`);
      req.flush({ index: 'eleanor-events-*', mappings: {} });
    });
  });
});
