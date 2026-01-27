import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, of, catchError, map, shareReplay } from 'rxjs';

export interface Release {
  version: string;
  date: string;
  size: string;
  sha256: string;
  changelog: string[];
  isLatest?: boolean;
  assets: ReleaseAsset[];
}

export interface ReleaseAsset {
  name: string;
  downloadUrl: string;
  size: number;
  platform: 'vmware' | 'virtualbox' | 'unknown';
}

interface GitHubRelease {
  tag_name: string;
  published_at: string;
  body: string;
  assets: GitHubAsset[];
  prerelease: boolean;
  draft: boolean;
}

interface GitHubAsset {
  name: string;
  browser_download_url: string;
  size: number;
}

interface ReleasesJson {
  releases: Release[];
  latest: string;
}

@Injectable({
  providedIn: 'root'
})
export class ReleaseService {
  private http = inject(HttpClient);
  private readonly GITHUB_API_URL = 'https://api.github.com/repos/Project-Eleanor/Eleanor/releases';
  private readonly FALLBACK_URL = '/assets/releases.json';

  private releases$: Observable<Release[]> | null = null;

  /**
   * Get all releases, fetching from GitHub API with fallback to static JSON
   */
  getReleases(): Observable<Release[]> {
    if (!this.releases$) {
      this.releases$ = this.fetchFromGitHub().pipe(
        catchError(error => {
          console.warn('GitHub API fetch failed, falling back to static releases.json:', error.message);
          return this.fetchFromFallback();
        }),
        shareReplay(1)
      );
    }
    return this.releases$;
  }

  /**
   * Fetch releases from GitHub API
   */
  private fetchFromGitHub(): Observable<Release[]> {
    return this.http.get<GitHubRelease[]>(this.GITHUB_API_URL).pipe(
      map(githubReleases => this.transformGitHubReleases(githubReleases))
    );
  }

  /**
   * Fetch releases from static fallback JSON
   */
  private fetchFromFallback(): Observable<Release[]> {
    return this.http.get<ReleasesJson>(this.FALLBACK_URL).pipe(
      map(data => data.releases),
      catchError(error => {
        console.error('Failed to load fallback releases.json:', error);
        return of([]);
      })
    );
  }

  /**
   * Transform GitHub API response to our Release format
   */
  private transformGitHubReleases(githubReleases: GitHubRelease[]): Release[] {
    // Filter out drafts and sort by date (newest first)
    const validReleases = githubReleases
      .filter(r => !r.draft)
      .sort((a, b) => new Date(b.published_at).getTime() - new Date(a.published_at).getTime());

    return validReleases.map((release, index) => {
      const assets = this.extractAssets(release.assets);
      const sha256 = this.extractSha256(release);

      return {
        version: release.tag_name,
        date: this.formatDate(release.published_at),
        size: this.calculateTotalSize(assets),
        sha256: sha256,
        changelog: this.parseChangelog(release.body),
        isLatest: index === 0 && !release.prerelease,
        assets: assets
      };
    });
  }

  /**
   * Extract OVA assets from GitHub release assets
   */
  private extractAssets(githubAssets: GitHubAsset[]): ReleaseAsset[] {
    return githubAssets
      .filter(asset => asset.name.endsWith('.ova'))
      .map(asset => ({
        name: asset.name,
        downloadUrl: asset.browser_download_url,
        size: asset.size,
        platform: this.detectPlatform(asset.name)
      }));
  }

  /**
   * Detect platform from asset filename
   */
  private detectPlatform(filename: string): 'vmware' | 'virtualbox' | 'unknown' {
    const lowerName = filename.toLowerCase();
    if (lowerName.includes('vmware')) return 'vmware';
    if (lowerName.includes('virtualbox') || lowerName.includes('vbox')) return 'virtualbox';
    return 'unknown';
  }

  /**
   * Extract SHA256 checksum from release
   * Looks for SHA256SUMS asset or parses from release body
   */
  private extractSha256(release: GitHubRelease): string {
    // First, try to find SHA256 in release body
    const sha256Match = release.body?.match(/sha256[:\s]+([a-f0-9]{64})/i);
    if (sha256Match) {
      return sha256Match[1];
    }

    // Check if there's a SHA256SUMS file in assets (we'd need to fetch it separately)
    const sha256Asset = release.assets.find(a =>
      a.name.includes('SHA256') || a.name.includes('sha256')
    );
    if (sha256Asset) {
      // Return placeholder - the actual checksum would need async fetch
      // For now, indicate checksum is available
      return 'See SHA256SUMS file in release assets';
    }

    return 'Checksum not available';
  }

  /**
   * Format ISO date to human-readable format
   */
  private formatDate(isoDate: string): string {
    const date = new Date(isoDate);
    return date.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric'
    });
  }

  /**
   * Calculate total size of OVA assets in human-readable format
   */
  private calculateTotalSize(assets: ReleaseAsset[]): string {
    if (assets.length === 0) return 'Size not available';

    // Use the largest asset size (VMware and VirtualBox OVAs are similar size)
    const maxSize = Math.max(...assets.map(a => a.size));
    return this.formatBytes(maxSize);
  }

  /**
   * Format bytes to human-readable size
   */
  private formatBytes(bytes: number): string {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  }

  /**
   * Parse changelog from GitHub release body (markdown)
   */
  private parseChangelog(body: string | null): string[] {
    if (!body) return ['See release notes for details'];

    const changelog: string[] = [];

    // Look for bullet points or numbered lists
    const lines = body.split('\n');
    for (const line of lines) {
      // Match markdown list items: - item, * item, 1. item
      const match = line.match(/^[\s]*[-*•]\s+(.+)$/) ||
                    line.match(/^[\s]*\d+\.\s+(.+)$/);
      if (match) {
        const item = match[1].trim();
        // Skip items that are just links or very short
        if (item.length > 5 && !item.startsWith('[') && !item.startsWith('http')) {
          changelog.push(item);
        }
      }
    }

    // Limit to first 6 items for display
    if (changelog.length > 6) {
      return changelog.slice(0, 6);
    }

    // If no list items found, try to extract first meaningful paragraph
    if (changelog.length === 0) {
      const firstParagraph = body.split('\n\n')[0];
      if (firstParagraph && firstParagraph.length > 10) {
        return [firstParagraph.substring(0, 150) + (firstParagraph.length > 150 ? '...' : '')];
      }
      return ['See release notes for details'];
    }

    return changelog;
  }

  /**
   * Clear the cache to force a fresh fetch
   */
  clearCache(): void {
    this.releases$ = null;
  }
}
