import { TestBed } from '@angular/core/testing';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideHttpClient } from '@angular/common/http';

import { CaseService } from './case.service';
import { mockCase, mockCaseList, mockTimelineEvent } from '../../testing';
import { environment } from '../../../environments/environment';
import { CaseCreate, CaseUpdate, TimelineEventCreate } from '../../shared/models';

describe('CaseService', () => {
  let service: CaseService;
  let httpMock: HttpTestingController;
  const baseUrl = `${environment.apiUrl}/cases`;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        CaseService,
        provideHttpClient(),
        provideHttpClientTesting(),
      ],
    });

    service = TestBed.inject(CaseService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
  });

  describe('list', () => {
    it('should list cases with pagination', () => {
      service.list({ page: 1, page_size: 20 }).subscribe((result) => {
        expect(result.items.length).toBe(3);
        expect(result.total).toBe(3);
        expect(result.page).toBe(1);
      });

      const req = httpMock.expectOne((r) =>
        r.url === baseUrl &&
        r.params.get('page') === '1' &&
        r.params.get('page_size') === '20'
      );
      expect(req.request.method).toBe('GET');
      req.flush(mockCaseList);
    });

    it('should filter by status', () => {
      service.list({ status: 'open' }).subscribe((result) => {
        expect(result.items).toBeDefined();
      });

      const req = httpMock.expectOne((r) =>
        r.url === baseUrl && r.params.get('status') === 'open'
      );
      req.flush({ ...mockCaseList, items: [mockCaseList.items[1]] });
    });

    it('should filter by severity', () => {
      service.list({ severity: 'high' }).subscribe();

      const req = httpMock.expectOne((r) =>
        r.url === baseUrl && r.params.get('severity') === 'high'
      );
      req.flush(mockCaseList);
    });

    it('should filter by assignee', () => {
      service.list({ assignee_id: 'user-001' }).subscribe();

      const req = httpMock.expectOne((r) =>
        r.url === baseUrl && r.params.get('assignee_id') === 'user-001'
      );
      req.flush(mockCaseList);
    });

    it('should search cases', () => {
      service.list({ search: 'malware' }).subscribe();

      const req = httpMock.expectOne((r) =>
        r.url === baseUrl && r.params.get('search') === 'malware'
      );
      req.flush(mockCaseList);
    });

    it('should list all cases without params', () => {
      service.list().subscribe((result) => {
        expect(result.items).toBeDefined();
      });

      const req = httpMock.expectOne(baseUrl);
      expect(req.request.params.keys().length).toBe(0);
      req.flush(mockCaseList);
    });
  });

  describe('get', () => {
    it('should get a case by ID', () => {
      service.get('case-001').subscribe((result) => {
        expect(result.id).toBe('case-001');
        expect(result.title).toBe('Test Investigation Case');
        expect(result.severity).toBe('high');
      });

      const req = httpMock.expectOne(`${baseUrl}/case-001`);
      expect(req.request.method).toBe('GET');
      req.flush(mockCase);
    });
  });

  describe('create', () => {
    it('should create a new case', () => {
      const newCase: CaseCreate = {
        title: 'New Investigation',
        description: 'Test case description',
        severity: 'medium',
        priority: 'P3',
        tags: ['test'],
      };

      service.create(newCase).subscribe((result) => {
        expect(result.title).toBe('New Investigation');
        expect(result.severity).toBe('medium');
      });

      const req = httpMock.expectOne(baseUrl);
      expect(req.request.method).toBe('POST');
      expect(req.request.body).toEqual(newCase);
      req.flush({ ...mockCase, ...newCase, id: 'case-new' });
    });

    it('should create a minimal case', () => {
      const minimalCase: CaseCreate = {
        title: 'Minimal Case',
      };

      service.create(minimalCase).subscribe((result) => {
        expect(result.title).toBe('Minimal Case');
      });

      const req = httpMock.expectOne(baseUrl);
      req.flush({
        ...mockCase,
        title: 'Minimal Case',
        description: null,
        severity: 'medium',
        priority: 'P3',
      });
    });
  });

  describe('update', () => {
    it('should update a case', () => {
      const update: CaseUpdate = {
        title: 'Updated Title',
        status: 'closed',
      };

      service.update('case-001', update).subscribe((result) => {
        expect(result.title).toBe('Updated Title');
        expect(result.status).toBe('closed');
      });

      const req = httpMock.expectOne(`${baseUrl}/case-001`);
      expect(req.request.method).toBe('PATCH');
      expect(req.request.body).toEqual(update);
      req.flush({ ...mockCase, ...update });
    });

    it('should update MITRE mappings', () => {
      const update: CaseUpdate = {
        mitre_tactics: ['TA0001', 'TA0002'],
        mitre_techniques: ['T1059', 'T1071'],
      };

      service.update('case-001', update).subscribe((result) => {
        expect(result.mitre_tactics).toContain('TA0001');
        expect(result.mitre_techniques).toContain('T1059');
      });

      const req = httpMock.expectOne(`${baseUrl}/case-001`);
      req.flush({ ...mockCase, ...update });
    });
  });

  describe('delete', () => {
    it('should delete a case', () => {
      service.delete('case-001').subscribe();

      const req = httpMock.expectOne(`${baseUrl}/case-001`);
      expect(req.request.method).toBe('DELETE');
      req.flush(null);
    });
  });

  describe('getTimeline', () => {
    it('should get timeline events for a case', () => {
      const timeline = [mockTimelineEvent];

      service.getTimeline('case-001').subscribe((result) => {
        expect(result.length).toBe(1);
        expect(result[0].title).toBe('Initial Detection');
      });

      const req = httpMock.expectOne(`${baseUrl}/case-001/timeline`);
      expect(req.request.method).toBe('GET');
      req.flush(timeline);
    });

    it('should handle empty timeline', () => {
      service.getTimeline('case-new').subscribe((result) => {
        expect(result.length).toBe(0);
      });

      const req = httpMock.expectOne(`${baseUrl}/case-new/timeline`);
      req.flush([]);
    });
  });

  describe('addTimelineEvent', () => {
    it('should add a timeline event', () => {
      const newEvent: TimelineEventCreate = {
        timestamp: '2025-01-20T14:00:00Z',
        title: 'Malware Contained',
        description: 'Successfully isolated infected host',
        category: 'containment',
        source: 'analyst',
        tags: ['manual'],
      };

      service.addTimelineEvent('case-001', newEvent).subscribe((result) => {
        expect(result.title).toBe('Malware Contained');
        expect(result.id).toBeDefined();
      });

      const req = httpMock.expectOne(`${baseUrl}/case-001/timeline`);
      expect(req.request.method).toBe('POST');
      expect(req.request.body).toEqual(newEvent);
      req.flush({
        ...mockTimelineEvent,
        ...newEvent,
        id: 'event-new',
      });
    });
  });
});
