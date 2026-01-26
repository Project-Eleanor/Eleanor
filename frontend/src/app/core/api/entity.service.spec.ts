import { TestBed } from '@angular/core/testing';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideHttpClient } from '@angular/common/http';

import { EntityService } from './entity.service';
import { mockEntity, mockEntityEvent } from '../../testing';
import { environment } from '../../../environments/environment';
import { EntityType } from '../../shared/models';

describe('EntityService', () => {
  let service: EntityService;
  let httpMock: HttpTestingController;
  const baseUrl = `${environment.apiUrl}/entities`;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        EntityService,
        provideHttpClient(),
        provideHttpClientTesting(),
      ],
    });

    service = TestBed.inject(EntityService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
  });

  describe('search', () => {
    it('should search entities with query', () => {
      const response = { items: [mockEntity], total: 1 };

      service.search({ query: 'WORKSTATION' }).subscribe((result) => {
        expect(result.items.length).toBe(1);
        expect(result.total).toBe(1);
      });

      const req = httpMock.expectOne((r) =>
        r.url === baseUrl && r.params.get('query') === 'WORKSTATION'
      );
      expect(req.request.method).toBe('GET');
      req.flush(response);
    });

    it('should filter by entity type', () => {
      service.search({ entity_type: 'host' }).subscribe();

      const req = httpMock.expectOne((r) =>
        r.url === baseUrl && r.params.get('entity_type') === 'host'
      );
      req.flush({ items: [mockEntity], total: 1 });
    });

    it('should support pagination', () => {
      service.search({ page: 2, page_size: 50 }).subscribe();

      const req = httpMock.expectOne((r) =>
        r.url === baseUrl &&
        r.params.get('page') === '2' &&
        r.params.get('page_size') === '50'
      );
      req.flush({ items: [], total: 100 });
    });

    it('should combine search params', () => {
      service.search({
        query: 'admin',
        entity_type: 'user',
        page: 1,
        page_size: 20,
      }).subscribe();

      const req = httpMock.expectOne((r) =>
        r.url === baseUrl &&
        r.params.get('query') === 'admin' &&
        r.params.get('entity_type') === 'user'
      );
      req.flush({ items: [], total: 0 });
    });
  });

  describe('get', () => {
    it('should get an entity by type and value', () => {
      service.get('host', 'WORKSTATION-01').subscribe((result) => {
        expect(result.entity_type).toBe('host');
        expect(result.value).toBe('WORKSTATION-01');
      });

      const req = httpMock.expectOne(`${baseUrl}/host/WORKSTATION-01`);
      expect(req.request.method).toBe('GET');
      req.flush(mockEntity);
    });

    it('should encode special characters in entity value', () => {
      service.get('user', 'DOMAIN\\admin').subscribe();

      const req = httpMock.expectOne(`${baseUrl}/user/DOMAIN%5Cadmin`);
      req.flush({ ...mockEntity, entity_type: 'user', value: 'DOMAIN\\admin' });
    });

    it('should handle IP addresses', () => {
      service.get('ip', '192.168.1.100').subscribe((result) => {
        expect(result.entity_type).toBe('ip');
      });

      const req = httpMock.expectOne(`${baseUrl}/ip/192.168.1.100`);
      req.flush({ ...mockEntity, entity_type: 'ip', value: '192.168.1.100' });
    });
  });

  describe('getHostProfile', () => {
    it('should get a host profile', () => {
      const hostProfile = {
        hostname: 'WORKSTATION-01',
        ip_addresses: ['10.0.0.50'],
        mac_addresses: ['00:11:22:33:44:55'],
        os_name: 'Windows 10',
        os_version: '22H2',
        domain: 'CORP',
        last_seen: '2025-01-20T16:00:00Z',
        agent_id: 'agent-001',
        agent_version: '1.0.0',
        recent_events: [],
        installed_software: [],
        open_ports: [],
      };

      service.getHostProfile('WORKSTATION-01').subscribe((result) => {
        expect(result.hostname).toBe('WORKSTATION-01');
        expect(result.os_name).toBe('Windows 10');
      });

      const req = httpMock.expectOne(`${baseUrl}/hosts/WORKSTATION-01`);
      expect(req.request.method).toBe('GET');
      req.flush(hostProfile);
    });
  });

  describe('getUserProfile', () => {
    it('should get a user profile', () => {
      const userProfile = {
        username: 'john.doe',
        display_name: 'John Doe',
        email: 'john.doe@example.com',
        domain: 'CORP',
        sid: 'S-1-5-21-...',
        groups: ['Domain Users', 'IT Staff'],
        last_logon: '2025-01-20T08:00:00Z',
        logon_history: [],
        permissions: ['read', 'write'],
      };

      service.getUserProfile('john.doe').subscribe((result) => {
        expect(result.username).toBe('john.doe');
        expect(result.groups).toContain('Domain Users');
      });

      const req = httpMock.expectOne(`${baseUrl}/users/john.doe`);
      expect(req.request.method).toBe('GET');
      req.flush(userProfile);
    });
  });

  describe('getIPProfile', () => {
    it('should get an IP profile', () => {
      const ipProfile = {
        ip_address: '192.168.1.100',
        ip_version: 4 as const,
        is_private: true,
        geolocation: null,
        asn: null,
        reputation: null,
        related_domains: [],
        related_connections: [],
      };

      service.getIPProfile('192.168.1.100').subscribe((result) => {
        expect(result.ip_address).toBe('192.168.1.100');
        expect(result.is_private).toBeTrue();
      });

      const req = httpMock.expectOne(`${baseUrl}/ips/192.168.1.100`);
      expect(req.request.method).toBe('GET');
      req.flush(ipProfile);
    });

    it('should get a public IP with geolocation', () => {
      const publicIP = {
        ip_address: '8.8.8.8',
        ip_version: 4 as const,
        is_private: false,
        geolocation: {
          country: 'United States',
          country_code: 'US',
          city: 'Mountain View',
          region: 'California',
          latitude: 37.4056,
          longitude: -122.0775,
        },
        asn: { asn: 15169, name: 'Google LLC', description: 'GOOGLE' },
        reputation: { score: 100, category: 'safe', sources: ['VirusTotal'], details: {} },
        related_domains: ['dns.google'],
        related_connections: [],
      };

      service.getIPProfile('8.8.8.8').subscribe((result) => {
        expect(result.is_private).toBeFalse();
        expect(result.geolocation?.country).toBe('United States');
        expect(result.asn?.name).toBe('Google LLC');
      });

      const req = httpMock.expectOne(`${baseUrl}/ips/8.8.8.8`);
      req.flush(publicIP);
    });
  });

  describe('getEntityEvents', () => {
    it('should get events for an entity', () => {
      const events = [mockEntityEvent];

      service.getEntityEvents('host', 'WORKSTATION-01').subscribe((result) => {
        expect(result.length).toBe(1);
        expect(result[0].event_type).toBe('process_start');
      });

      const req = httpMock.expectOne(`${baseUrl}/host/WORKSTATION-01/events`);
      expect(req.request.method).toBe('GET');
      req.flush(events);
    });

    it('should support pagination for events', () => {
      service.getEntityEvents('user', 'admin', { from: 100, size: 50 }).subscribe();

      const req = httpMock.expectOne((r) =>
        r.url === `${baseUrl}/user/admin/events` &&
        r.params.get('from') === '100' &&
        r.params.get('size') === '50'
      );
      req.flush([]);
    });
  });

  describe('enrich', () => {
    it('should enrich an entity', () => {
      const enrichedEntity = {
        ...mockEntity,
        enrichment: {
          source: 'VirusTotal',
          enriched_at: '2025-01-20T12:00:00Z',
          data: { malicious: 0, suspicious: 0 },
          iocs: [],
          reputation: { score: 100, category: 'safe', sources: ['VT'], details: {} },
        },
      };

      service.enrich('ip', '8.8.8.8').subscribe((result) => {
        expect(result.enrichment).toBeDefined();
        expect(result.enrichment?.source).toBe('VirusTotal');
      });

      const req = httpMock.expectOne(`${baseUrl}/ip/8.8.8.8/enrich`);
      expect(req.request.method).toBe('POST');
      expect(req.request.body).toEqual({});
      req.flush(enrichedEntity);
    });
  });

  describe('getRelatedCases', () => {
    it('should get related cases for an entity', () => {
      const relatedCases = [
        { case_id: 'case-001', case_number: 'ELEANOR-2025-0001', title: 'Test Investigation' },
        { case_id: 'case-002', case_number: 'ELEANOR-2025-0002', title: 'Related Incident' },
      ];

      service.getRelatedCases('host', 'WORKSTATION-01').subscribe((result) => {
        expect(result.length).toBe(2);
        expect(result[0].case_number).toBe('ELEANOR-2025-0001');
      });

      const req = httpMock.expectOne(`${baseUrl}/host/WORKSTATION-01/cases`);
      expect(req.request.method).toBe('GET');
      req.flush(relatedCases);
    });

    it('should handle entity with no related cases', () => {
      service.getRelatedCases('ip', '10.0.0.1').subscribe((result) => {
        expect(result.length).toBe(0);
      });

      const req = httpMock.expectOne(`${baseUrl}/ip/10.0.0.1/cases`);
      req.flush([]);
    });
  });
});
