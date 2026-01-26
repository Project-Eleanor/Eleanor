import { FileSizePipe } from './file-size.pipe';

describe('FileSizePipe', () => {
  let pipe: FileSizePipe;

  beforeEach(() => {
    pipe = new FileSizePipe();
  });

  describe('basic byte formatting', () => {
    it('should return "0 B" for null value', () => {
      expect(pipe.transform(null)).toBe('0 B');
    });

    it('should return "0 B" for undefined value', () => {
      expect(pipe.transform(undefined)).toBe('0 B');
    });

    it('should return "0 B" for zero bytes', () => {
      expect(pipe.transform(0)).toBe('0 B');
    });

    it('should format bytes under 1KB', () => {
      expect(pipe.transform(100)).toBe('100 B');
      expect(pipe.transform(500)).toBe('500 B');
      expect(pipe.transform(1023)).toBe('1023 B');
    });
  });

  describe('kilobytes formatting', () => {
    it('should format exactly 1KB', () => {
      expect(pipe.transform(1024)).toBe('1 KB');
    });

    it('should format KB with decimals', () => {
      expect(pipe.transform(1536)).toBe('1.5 KB');
    });

    it('should format large KB values', () => {
      expect(pipe.transform(512000)).toBe('500 KB');
    });
  });

  describe('megabytes formatting', () => {
    it('should format exactly 1MB', () => {
      expect(pipe.transform(1048576)).toBe('1 MB');
    });

    it('should format MB with decimals', () => {
      expect(pipe.transform(2621440)).toBe('2.5 MB');
    });

    it('should format large MB values', () => {
      expect(pipe.transform(524288000)).toBe('500 MB');
    });
  });

  describe('gigabytes formatting', () => {
    it('should format exactly 1GB', () => {
      expect(pipe.transform(1073741824)).toBe('1 GB');
    });

    it('should format GB with decimals', () => {
      expect(pipe.transform(2684354560)).toBe('2.5 GB');
    });
  });

  describe('terabytes formatting', () => {
    it('should format exactly 1TB', () => {
      expect(pipe.transform(1099511627776)).toBe('1 TB');
    });

    it('should format TB with decimals', () => {
      expect(pipe.transform(1649267441664)).toBe('1.5 TB');
    });
  });

  describe('custom decimal places', () => {
    it('should format with 0 decimals', () => {
      expect(pipe.transform(1536, 0)).toBe('2 KB');
    });

    it('should format with 2 decimals', () => {
      expect(pipe.transform(1536, 2)).toBe('1.5 KB');
    });

    it('should format with 3 decimals', () => {
      expect(pipe.transform(1500, 3)).toBe('1.465 KB');
    });
  });

  describe('edge cases', () => {
    it('should handle very small non-zero bytes', () => {
      expect(pipe.transform(1)).toBe('1 B');
    });

    it('should handle negative values as positive', () => {
      // Negative bytes don't make sense, but test behavior
      const result = pipe.transform(-1024);
      expect(result).toBeDefined();
    });

    it('should handle floating point bytes', () => {
      // Should truncate to integer behavior
      expect(pipe.transform(1024.5)).toBe('1 KB');
    });
  });

  describe('realistic file sizes', () => {
    it('should format a typical document (100KB)', () => {
      expect(pipe.transform(102400)).toBe('100 KB');
    });

    it('should format a typical image (2MB)', () => {
      expect(pipe.transform(2097152)).toBe('2 MB');
    });

    it('should format a typical video (500MB)', () => {
      expect(pipe.transform(524288000)).toBe('500 MB');
    });

    it('should format a typical disk image (4GB)', () => {
      expect(pipe.transform(4294967296)).toBe('4 GB');
    });
  });
});
