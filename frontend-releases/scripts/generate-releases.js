#!/usr/bin/env node
/**
 * Generate releases.json from GitHub API response
 *
 * This script transforms the GitHub Releases API response into the format
 * expected by the Eleanor release portal frontend.
 *
 * Usage:
 *   1. Fetch releases: gh api /repos/Project-Eleanor/Eleanor/releases > github-releases.json
 *   2. Run script: node generate-releases.js
 *
 * Input: github-releases.json (GitHub API response)
 * Output: frontend-releases/src/assets/releases.json
 */

const fs = require('fs');
const path = require('path');

// File paths
const INPUT_FILE = path.join(process.cwd(), 'github-releases.json');
const OUTPUT_FILE = path.join(process.cwd(), 'frontend-releases', 'src', 'assets', 'releases.json');

/**
 * Transform GitHub release to portal format
 */
function transformRelease(release, isLatest) {
  const assets = extractOvaAssets(release.assets || []);
  const sha256Map = extractSha256Checksums(release);

  return {
    version: release.tag_name,
    date: formatDate(release.published_at),
    size: calculateSize(assets),
    sha256: sha256Map.primary || 'See SHA256SUMS in release assets',
    sha256Map: sha256Map.all,
    changelog: parseChangelog(release.body),
    isLatest: isLatest,
    prerelease: release.prerelease || false,
    assets: assets.map(asset => ({
      name: asset.name,
      downloadUrl: asset.browser_download_url,
      size: asset.size,
      platform: detectPlatform(asset.name),
      sha256: sha256Map.all[asset.name] || null
    }))
  };
}

/**
 * Extract OVA assets from GitHub release assets
 */
function extractOvaAssets(assets) {
  return assets.filter(asset =>
    asset.name.endsWith('.ova') &&
    asset.state === 'uploaded'
  );
}

/**
 * Detect platform from asset filename
 */
function detectPlatform(filename) {
  const lower = filename.toLowerCase();
  if (lower.includes('vmware')) return 'vmware';
  if (lower.includes('virtualbox') || lower.includes('vbox')) return 'virtualbox';
  return 'unknown';
}

/**
 * Extract SHA256 checksums from release
 * Looks in release body and SHA256SUMS asset
 */
function extractSha256Checksums(release) {
  const checksums = { all: {}, primary: null };
  const body = release.body || '';

  // Parse checksums from release body
  // Patterns:
  //   sha256: abc123...
  //   abc123...  filename.ova
  //   SHA256 (filename.ova) = abc123...
  const lines = body.split('\n');
  for (const line of lines) {
    // Pattern: hash  filename
    const match1 = line.match(/^([a-f0-9]{64})\s+(\S+\.ova)/i);
    if (match1) {
      checksums.all[match1[2]] = match1[1].toLowerCase();
      if (!checksums.primary) checksums.primary = match1[1].toLowerCase();
      continue;
    }

    // Pattern: SHA256 (filename) = hash
    const match2 = line.match(/SHA256\s*\(([^)]+\.ova)\)\s*=\s*([a-f0-9]{64})/i);
    if (match2) {
      checksums.all[match2[1]] = match2[2].toLowerCase();
      if (!checksums.primary) checksums.primary = match2[2].toLowerCase();
      continue;
    }

    // Pattern: simple sha256: hash
    const match3 = line.match(/sha256[:\s]+([a-f0-9]{64})/i);
    if (match3 && !checksums.primary) {
      checksums.primary = match3[1].toLowerCase();
    }
  }

  return checksums;
}

/**
 * Format ISO date to human-readable format
 */
function formatDate(isoDate) {
  if (!isoDate) return 'Date unknown';
  const date = new Date(isoDate);
  return date.toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'long',
    day: 'numeric'
  });
}

/**
 * Calculate human-readable size from assets
 */
function calculateSize(assets) {
  if (!assets.length) return 'Size not available';

  const maxSize = Math.max(...assets.map(a => a.size || 0));
  return formatBytes(maxSize);
}

/**
 * Format bytes to human-readable string
 */
function formatBytes(bytes) {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

/**
 * Parse changelog from markdown release body
 */
function parseChangelog(body) {
  if (!body) return ['See release notes for details'];

  const changelog = [];
  const lines = body.split('\n');

  for (const line of lines) {
    // Match markdown list items: - item, * item, or numbered lists
    const match = line.match(/^[\s]*[-*•]\s+(.+)$/) ||
                  line.match(/^[\s]*\d+\.\s+(.+)$/);

    if (match) {
      const item = match[1].trim();
      // Skip items that are just links, too short, or reference files
      if (item.length > 5 &&
          !item.startsWith('[') &&
          !item.startsWith('http') &&
          !item.match(/\.(ova|txt|asc)$/i)) {
        changelog.push(cleanMarkdown(item));
      }
    }
  }

  // Limit to first 6 items
  if (changelog.length > 6) {
    return changelog.slice(0, 6);
  }

  // Fallback: try to extract first meaningful paragraph
  if (changelog.length === 0) {
    const paragraphs = body.split(/\n\n+/);
    for (const para of paragraphs) {
      const cleaned = cleanMarkdown(para.trim());
      if (cleaned.length > 20 && !cleaned.startsWith('#')) {
        return [cleaned.substring(0, 200) + (cleaned.length > 200 ? '...' : '')];
      }
    }
    return ['See release notes for details'];
  }

  return changelog;
}

/**
 * Remove markdown formatting from text
 */
function cleanMarkdown(text) {
  return text
    .replace(/\*\*([^*]+)\*\*/g, '$1')  // Bold
    .replace(/\*([^*]+)\*/g, '$1')       // Italic
    .replace(/`([^`]+)`/g, '$1')         // Code
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')  // Links
    .trim();
}

/**
 * Main function
 */
function main() {
  console.log('Generating releases.json from GitHub API response...');

  // Read GitHub releases
  if (!fs.existsSync(INPUT_FILE)) {
    console.error(`Error: Input file not found: ${INPUT_FILE}`);
    console.error('Run: gh api /repos/Project-Eleanor/Eleanor/releases > github-releases.json');
    process.exit(1);
  }

  const githubReleases = JSON.parse(fs.readFileSync(INPUT_FILE, 'utf8'));
  console.log(`Found ${githubReleases.length} releases from GitHub API`);

  // Filter and sort releases
  const validReleases = githubReleases
    .filter(r => !r.draft)
    .sort((a, b) => new Date(b.published_at) - new Date(a.published_at));

  console.log(`Processing ${validReleases.length} valid releases (excluding drafts)`);

  // Transform releases
  const releases = validReleases.map((release, index) => {
    const isLatest = index === 0 && !release.prerelease;
    return transformRelease(release, isLatest);
  });

  // Find latest stable version
  const latestStable = releases.find(r => r.isLatest);
  const latestVersion = latestStable ? latestStable.version : (releases[0]?.version || 'unknown');

  // Create output
  const output = {
    releases: releases,
    latest: latestVersion,
    generated: new Date().toISOString()
  };

  // Ensure output directory exists
  const outputDir = path.dirname(OUTPUT_FILE);
  if (!fs.existsSync(outputDir)) {
    fs.mkdirSync(outputDir, { recursive: true });
  }

  // Write output
  fs.writeFileSync(OUTPUT_FILE, JSON.stringify(output, null, 2));
  console.log(`Generated: ${OUTPUT_FILE}`);

  // Summary
  console.log('\nRelease summary:');
  releases.slice(0, 5).forEach(r => {
    const marker = r.isLatest ? ' [LATEST]' : (r.prerelease ? ' [PRE]' : '');
    console.log(`  ${r.version}${marker} - ${r.date} - ${r.assets.length} assets`);
  });
  if (releases.length > 5) {
    console.log(`  ... and ${releases.length - 5} more releases`);
  }
}

main();
