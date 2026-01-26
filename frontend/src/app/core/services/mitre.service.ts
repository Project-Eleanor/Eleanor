import { Injectable, signal, computed } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable, tap, catchError, of } from 'rxjs';
import { environment } from '../../../environments/environment';

// =============================================================================
// Types
// =============================================================================

export interface MitreTactic {
  id: string;
  name: string;
  description: string;
  external_id: string;
}

export interface MitreTechniqueBasic {
  id: string;
  name: string;
  subtechniques: Array<{ id: string; name: string }>;
}

export interface MitreMatrixColumn {
  tactic: MitreTactic;
  techniques: MitreTechniqueBasic[];
}

export interface MitreMatrix {
  tactics: MitreTactic[];
  matrix: MitreMatrixColumn[];
  technique_count: number;
  subtechnique_count: number;
  last_updated: string;
}

export interface MitreTechniqueDetail {
  id: string;
  name: string;
  description: string;
  tactics: string[];
  platforms: string[];
  data_sources: string[];
  detection: string;
  is_subtechnique: boolean;
  parent_id: string | null;
  subtechniques: string[];
  url: string;
}

export interface CoverageRule {
  id: string;
  name: string;
  severity: string;
}

export interface TechniqueCoverage {
  technique_id: string;
  technique_name: string;
  rule_count: number;
  rules: CoverageRule[];
}

export interface CoverageStatistics {
  total_techniques: number;
  covered_techniques: number;
  coverage_percent: number;
  total_rules: number;
}

export interface TacticCoverage {
  tactic_id: string;
  tactic_name: string;
  total_techniques: number;
  covered_techniques: number;
  coverage_percent: number;
}

export interface CoverageResponse {
  coverage_map: TechniqueCoverage[];
  statistics: CoverageStatistics;
  by_tactic: TacticCoverage[];
}

export interface CoverageGap {
  technique_id: string;
  technique_name: string;
  tactics: string[];
  platforms: string[];
  data_sources: string[];
  detection_guidance: string | null;
  url: string;
}

export interface HeatmapItem {
  technique_id: string;
  technique_name: string;
  count: number;
  intensity: number;
  tactics: string[];
}

export interface HeatmapResponse {
  heatmap: HeatmapItem[];
  time_range: string;
  total_alerts: number;
  unique_techniques: number;
}

export interface NavigatorLayer {
  name: string;
  versions: {
    attack: string;
    navigator: string;
    layer: string;
  };
  domain: string;
  description: string;
  techniques: Array<{
    techniqueID: string;
    score: number;
    color: string;
    enabled: boolean;
    comment?: string;
  }>;
  [key: string]: unknown;
}

export interface ImportedTechnique {
  technique_id: string;
  technique_name: string;
  score: number;
  color: string | null;
  comment: string | null;
  enabled: boolean;
}

export interface LayerImportResponse {
  layer_name: string;
  description: string;
  technique_count: number;
  techniques: ImportedTechnique[];
}

export interface TechniqueSearchResult {
  id: string;
  name: string;
  tactics: string[];
  is_subtechnique: boolean;
}

export type TimeRange = '24h' | '7d' | '30d';

@Injectable({
  providedIn: 'root'
})
export class MitreService {
  private readonly apiUrl = `${environment.apiUrl}/mitre`;

  // Cached data
  private _matrix = signal<MitreMatrix | null>(null);
  private _coverage = signal<CoverageResponse | null>(null);
  private _heatmap = signal<HeatmapResponse | null>(null);
  private _isLoading = signal(false);
  private _error = signal<string | null>(null);

  // Public readable signals
  readonly matrix = this._matrix.asReadonly();
  readonly coverage = this._coverage.asReadonly();
  readonly heatmap = this._heatmap.asReadonly();
  readonly isLoading = this._isLoading.asReadonly();
  readonly error = this._error.asReadonly();

  // Computed values
  readonly tactics = computed(() => this._matrix()?.tactics ?? []);
  readonly matrixColumns = computed(() => this._matrix()?.matrix ?? []);
  readonly techniqueCount = computed(() => this._matrix()?.technique_count ?? 0);
  readonly coverageStats = computed(() => this._coverage()?.statistics ?? null);
  readonly coverageByTactic = computed(() => this._coverage()?.by_tactic ?? []);
  readonly coverageMap = computed(() => {
    const coverage = this._coverage()?.coverage_map ?? [];
    return new Map(coverage.map(c => [c.technique_id, c]));
  });
  readonly heatmapMap = computed(() => {
    const heatmap = this._heatmap()?.heatmap ?? [];
    return new Map(heatmap.map(h => [h.technique_id, h]));
  });

  constructor(private http: HttpClient) {}

  // ==========================================================================
  // Matrix Data
  // ==========================================================================

  loadMatrix(): void {
    if (this._matrix()) return; // Already loaded

    this._isLoading.set(true);
    this._error.set(null);

    this.http.get<MitreMatrix>(`${this.apiUrl}/matrix`)
      .pipe(
        catchError(err => {
          this._error.set('Failed to load MITRE ATT&CK matrix');
          return of(null);
        })
      )
      .subscribe(matrix => {
        if (matrix) {
          this._matrix.set(matrix);
        }
        this._isLoading.set(false);
      });
  }

  getMatrix(): Observable<MitreMatrix> {
    return this.http.get<MitreMatrix>(`${this.apiUrl}/matrix`);
  }

  getTechnique(techniqueId: string): Observable<MitreTechniqueDetail> {
    return this.http.get<MitreTechniqueDetail>(`${this.apiUrl}/techniques/${techniqueId}`);
  }

  searchTechniques(query: string, limit = 20): Observable<TechniqueSearchResult[]> {
    const params = new HttpParams()
      .set('q', query)
      .set('limit', limit.toString());

    return this.http.get<TechniqueSearchResult[]>(`${this.apiUrl}/techniques/search`, { params });
  }

  // ==========================================================================
  // Coverage Analysis
  // ==========================================================================

  loadCoverage(): void {
    this._isLoading.set(true);

    this.http.get<CoverageResponse>(`${this.apiUrl}/coverage`)
      .pipe(catchError(() => of(null)))
      .subscribe(coverage => {
        if (coverage) {
          this._coverage.set(coverage);
        }
        this._isLoading.set(false);
      });
  }

  getCoverage(): Observable<CoverageResponse> {
    return this.http.get<CoverageResponse>(`${this.apiUrl}/coverage`);
  }

  getCoverageGaps(priority = 'high'): Observable<CoverageGap[]> {
    const params = new HttpParams().set('priority', priority);
    return this.http.get<CoverageGap[]>(`${this.apiUrl}/coverage/gaps`, { params });
  }

  // ==========================================================================
  // Heatmap
  // ==========================================================================

  loadHeatmap(timeRange: TimeRange = '7d'): void {
    this._isLoading.set(true);

    const params = new HttpParams().set('time_range', timeRange);

    this.http.get<HeatmapResponse>(`${this.apiUrl}/heatmap`, { params })
      .pipe(catchError(() => of(null)))
      .subscribe(heatmap => {
        if (heatmap) {
          this._heatmap.set(heatmap);
        }
        this._isLoading.set(false);
      });
  }

  getHeatmap(timeRange: TimeRange = '7d'): Observable<HeatmapResponse> {
    const params = new HttpParams().set('time_range', timeRange);
    return this.http.get<HeatmapResponse>(`${this.apiUrl}/heatmap`, { params });
  }

  // ==========================================================================
  // Navigator Layer Operations
  // ==========================================================================

  exportLayer(layerName = 'Eleanor Detection Coverage', includeRules = true): Observable<NavigatorLayer> {
    const params = new HttpParams()
      .set('layer_name', layerName)
      .set('include_rules', includeRules.toString());

    return this.http.get<NavigatorLayer>(`${this.apiUrl}/layers/export`, { params });
  }

  importLayer(layer: NavigatorLayer): Observable<LayerImportResponse> {
    return this.http.post<LayerImportResponse>(`${this.apiUrl}/layers/import`, { layer });
  }

  downloadLayer(layerName = 'Eleanor Detection Coverage'): void {
    this.exportLayer(layerName).subscribe(layer => {
      const blob = new Blob([JSON.stringify(layer, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${layerName.replace(/\s+/g, '_')}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    });
  }

  // ==========================================================================
  // Utility Methods
  // ==========================================================================

  getTechniqueColor(techniqueId: string): string {
    const coverage = this.coverageMap().get(techniqueId);
    const heatmap = this.heatmapMap().get(techniqueId);

    if (heatmap && heatmap.count > 0) {
      // Active incidents - red scale
      const intensity = heatmap.intensity;
      if (intensity > 0.7) return '#f85149';
      if (intensity > 0.4) return '#ff7b6b';
      return '#ffa198';
    }

    if (coverage) {
      // Has coverage - green scale
      if (coverage.rule_count >= 3) return '#3fb950';
      if (coverage.rule_count >= 1) return '#d29922';
      return '#8b949e';
    }

    // No coverage
    return '#21262d';
  }

  refreshAll(): void {
    this._matrix.set(null);
    this._coverage.set(null);
    this._heatmap.set(null);
    this.loadMatrix();
    this.loadCoverage();
    this.loadHeatmap();
  }
}
