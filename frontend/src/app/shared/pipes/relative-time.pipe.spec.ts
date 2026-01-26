import { RelativeTimePipe } from './relative-time.pipe';

describe('RelativeTimePipe', () => {
  let pipe: RelativeTimePipe;

  beforeEach(() => {
    pipe = new RelativeTimePipe();
    // Set a fixed "now" time for consistent testing
    jasmine.clock().install();
    jasmine.clock().mockDate(new Date('2025-01-20T12:00:00Z'));
  });

  afterEach(() => {
    jasmine.clock().uninstall();
  });

  describe('null and undefined handling', () => {
    it('should return empty string for null value', () => {
      expect(pipe.transform(null)).toBe('');
    });

    it('should return empty string for undefined value', () => {
      expect(pipe.transform(undefined)).toBe('');
    });

    it('should return empty string for empty string', () => {
      expect(pipe.transform('')).toBe('');
    });
  });

  describe('ISO string input', () => {
    it('should handle ISO string timestamps', () => {
      const result = pipe.transform('2025-01-20T11:00:00Z');
      expect(result).toContain('hour');
      expect(result).toContain('ago');
    });

    it('should handle ISO string with timezone', () => {
      const result = pipe.transform('2025-01-20T11:00:00+00:00');
      expect(result).toBeDefined();
    });

    it('should handle ISO string without time', () => {
      const result = pipe.transform('2025-01-19');
      expect(result).toContain('day');
    });
  });

  describe('Date object input', () => {
    it('should handle Date object', () => {
      const date = new Date('2025-01-20T11:30:00Z');
      const result = pipe.transform(date);
      expect(result).toBeDefined();
      expect(result).toContain('ago');
    });
  });

  describe('relative time calculations', () => {
    it('should show "less than a minute ago" for recent times', () => {
      const result = pipe.transform('2025-01-20T11:59:30Z');
      expect(result).toContain('less than a minute');
    });

    it('should show minutes ago', () => {
      const result = pipe.transform('2025-01-20T11:50:00Z');
      expect(result).toContain('10 minutes ago');
    });

    it('should show hour ago (singular)', () => {
      const result = pipe.transform('2025-01-20T11:00:00Z');
      expect(result.includes('1 hour ago') || result.includes('about 1 hour ago')).toBe(true);
    });

    it('should show hours ago (plural)', () => {
      const result = pipe.transform('2025-01-20T09:00:00Z');
      expect(result).toContain('hours ago');
    });

    it('should show day ago', () => {
      const result = pipe.transform('2025-01-19T12:00:00Z');
      expect(result).toContain('day');
    });

    it('should show days ago', () => {
      const result = pipe.transform('2025-01-17T12:00:00Z');
      expect(result).toContain('days');
    });

    it('should show month ago', () => {
      const result = pipe.transform('2024-12-20T12:00:00Z');
      expect(result).toContain('month');
    });

    it('should show year ago', () => {
      const result = pipe.transform('2024-01-20T12:00:00Z');
      expect(result).toContain('year');
    });
  });

  describe('future dates', () => {
    it('should handle future dates', () => {
      const result = pipe.transform('2025-01-21T12:00:00Z');
      expect(result).toContain('in');
    });
  });

  describe('common DFIR scenarios', () => {
    it('should format recent event timestamp', () => {
      const result = pipe.transform('2025-01-20T11:55:00Z');
      expect(result).toBeDefined();
      expect(result.length).toBeGreaterThan(0);
    });

    it('should format incident start time', () => {
      // Incident started 3 days ago
      const result = pipe.transform('2025-01-17T08:30:00Z');
      expect(result).toContain('days ago');
    });

    it('should format case creation date', () => {
      // Case created 2 weeks ago
      const result = pipe.transform('2025-01-06T10:00:00Z');
      expect(result.includes('days ago') || result.includes('weeks ago')).toBe(true);
    });

    it('should format evidence collection time', () => {
      // Evidence collected 6 hours ago
      const result = pipe.transform('2025-01-20T06:00:00Z');
      expect(result).toContain('hours ago');
    });
  });

  describe('edge cases', () => {
    it('should handle exact current time', () => {
      const result = pipe.transform('2025-01-20T12:00:00Z');
      expect(result).toContain('less than a minute');
    });

    it('should handle dates at year boundary', () => {
      const result = pipe.transform('2024-12-31T23:59:59Z');
      expect(result).toBeDefined();
    });

    it('should handle very old dates', () => {
      const result = pipe.transform('2020-01-01T00:00:00Z');
      expect(result).toContain('years ago');
    });
  });
});
