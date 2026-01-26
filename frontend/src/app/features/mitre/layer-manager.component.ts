import { Component, signal, output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatCardModule } from '@angular/material/card';
import { MatIconModule } from '@angular/material/icon';
import { MatButtonModule } from '@angular/material/button';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { MitreService, NavigatorLayer, LayerImportResponse } from '../../core/services/mitre.service';

@Component({
  selector: 'app-layer-manager',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatCardModule,
    MatIconModule,
    MatButtonModule,
    MatFormFieldModule,
    MatInputModule,
    MatCheckboxModule,
    MatProgressSpinnerModule,
    MatSnackBarModule
  ],
  template: `
    <div class="layer-manager">
      <!-- Export Section -->
      <mat-card class="action-card">
        <div class="card-header">
          <mat-icon>file_download</mat-icon>
          <div>
            <h3>Export Navigator Layer</h3>
            <p>Export your detection coverage as a MITRE ATT&CK Navigator layer</p>
          </div>
        </div>
        <div class="card-content">
          <mat-form-field appearance="outline" class="full-width">
            <mat-label>Layer Name</mat-label>
            <input matInput [(ngModel)]="exportLayerName" placeholder="Eleanor Detection Coverage">
          </mat-form-field>
          <mat-checkbox [(ngModel)]="includeRuleNames">Include rule names in comments</mat-checkbox>
        </div>
        <div class="card-actions">
          <button mat-raised-button color="primary" (click)="exportLayer()" [disabled]="isExporting()">
            @if (isExporting()) {
              <mat-spinner diameter="20"></mat-spinner>
            } @else {
              <mat-icon>download</mat-icon>
            }
            Download Layer
          </button>
          <a mat-button href="https://mitre-attack.github.io/attack-navigator/" target="_blank">
            <mat-icon>open_in_new</mat-icon>
            Open Navigator
          </a>
        </div>
      </mat-card>

      <!-- Import Section -->
      <mat-card class="action-card">
        <div class="card-header">
          <mat-icon>file_upload</mat-icon>
          <div>
            <h3>Import Navigator Layer</h3>
            <p>Import a Navigator layer to view technique mappings</p>
          </div>
        </div>
        <div class="card-content">
          <div class="file-drop-zone"
               [class.active]="isDragging()"
               (dragover)="onDragOver($event)"
               (dragleave)="onDragLeave($event)"
               (drop)="onDrop($event)"
               (click)="fileInput.click()">
            <input #fileInput type="file" accept=".json" (change)="onFileSelected($event)" hidden>
            <mat-icon>cloud_upload</mat-icon>
            <p>Drop a Navigator layer file here or click to browse</p>
            <span class="hint">Supports .json files from ATT&CK Navigator</span>
          </div>

          @if (importedLayer()) {
            <div class="import-result">
              <div class="result-header">
                <mat-icon class="success">check_circle</mat-icon>
                <span>Layer imported successfully</span>
              </div>
              <div class="result-details">
                <div class="detail-row">
                  <span class="label">Name:</span>
                  <span class="value">{{ importedLayer()!.layer_name }}</span>
                </div>
                <div class="detail-row">
                  <span class="label">Techniques:</span>
                  <span class="value">{{ importedLayer()!.technique_count }}</span>
                </div>
                @if (importedLayer()!.description) {
                  <div class="detail-row">
                    <span class="label">Description:</span>
                    <span class="value">{{ importedLayer()!.description }}</span>
                  </div>
                }
              </div>
            </div>
          }
        </div>
        <div class="card-actions">
          @if (importedLayer()) {
            <button mat-raised-button color="primary" (click)="applyImportedLayer()">
              <mat-icon>check</mat-icon>
              Apply to Matrix
            </button>
            <button mat-button (click)="clearImport()">Clear</button>
          }
        </div>
      </mat-card>

      <!-- Quick Tips -->
      <mat-card class="tips-card">
        <h3>
          <mat-icon>lightbulb</mat-icon>
          Tips for Navigator Integration
        </h3>
        <ul>
          <li>
            <strong>Export</strong>: Download your coverage layer and open it in the
            <a href="https://mitre-attack.github.io/attack-navigator/" target="_blank">ATT&CK Navigator</a>
            to visualize your detection coverage.
          </li>
          <li>
            <strong>Import</strong>: Import layers from threat intelligence reports, red team assessments,
            or other security tools to map adversary techniques.
          </li>
          <li>
            <strong>Compare</strong>: Overlay imported layers with your coverage to identify gaps
            against specific threat actors or campaigns.
          </li>
          <li>
            <strong>Share</strong>: Export layers to share your detection strategy with teammates
            or compare with industry benchmarks.
          </li>
        </ul>
      </mat-card>
    </div>
  `,
  styles: [`
    .layer-manager {
      display: flex;
      flex-direction: column;
      gap: 24px;
      padding: 16px 0;
    }

    .action-card {
      background: var(--bg-card);
      border: 1px solid var(--border-color);
    }

    .card-header {
      display: flex;
      gap: 16px;
      padding: 20px;
      border-bottom: 1px solid var(--border-color);

      > mat-icon {
        font-size: 32px;
        width: 32px;
        height: 32px;
        color: var(--accent);
      }

      h3 {
        margin: 0;
        font-size: 16px;
        font-weight: 600;
        color: var(--text-primary);
      }

      p {
        margin: 4px 0 0 0;
        font-size: 13px;
        color: var(--text-secondary);
      }
    }

    .card-content {
      padding: 20px;
    }

    .full-width {
      width: 100%;
    }

    mat-checkbox {
      margin-top: 8px;
    }

    .card-actions {
      display: flex;
      gap: 12px;
      padding: 16px 20px;
      border-top: 1px solid var(--border-color);

      button mat-spinner {
        display: inline-block;
        margin-right: 8px;
      }
    }

    /* File Drop Zone */
    .file-drop-zone {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      padding: 40px;
      border: 2px dashed var(--border-color);
      border-radius: 8px;
      cursor: pointer;
      transition: all 0.2s ease;

      &:hover, &.active {
        border-color: var(--accent);
        background: rgba(74, 158, 255, 0.05);
      }

      mat-icon {
        font-size: 48px;
        width: 48px;
        height: 48px;
        color: var(--text-muted);
        margin-bottom: 16px;
      }

      p {
        margin: 0;
        font-size: 14px;
        color: var(--text-primary);
      }

      .hint {
        font-size: 12px;
        color: var(--text-muted);
        margin-top: 4px;
      }
    }

    /* Import Result */
    .import-result {
      margin-top: 20px;
      padding: 16px;
      background: rgba(63, 185, 80, 0.1);
      border: 1px solid var(--success);
      border-radius: 8px;
    }

    .result-header {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 12px;

      mat-icon.success {
        color: var(--success);
      }

      span {
        font-weight: 500;
        color: var(--success);
      }
    }

    .result-details {
      display: flex;
      flex-direction: column;
      gap: 4px;
    }

    .detail-row {
      display: flex;
      gap: 8px;
      font-size: 13px;

      .label {
        color: var(--text-muted);
        min-width: 100px;
      }

      .value {
        color: var(--text-primary);
      }
    }

    /* Tips Card */
    .tips-card {
      padding: 20px;
      background: var(--bg-card);
      border: 1px solid var(--border-color);

      h3 {
        display: flex;
        align-items: center;
        gap: 8px;
        margin: 0 0 16px 0;
        font-size: 14px;
        font-weight: 600;
        color: var(--text-primary);

        mat-icon {
          color: var(--warning);
        }
      }

      ul {
        margin: 0;
        padding-left: 20px;
      }

      li {
        margin-bottom: 8px;
        font-size: 13px;
        color: var(--text-secondary);
        line-height: 1.5;

        strong {
          color: var(--text-primary);
        }

        a {
          color: var(--accent);
        }
      }
    }
  `]
})
export class LayerManagerComponent {
  private mitreService: MitreService;
  private snackBar: MatSnackBar;

  exportLayerName = 'Eleanor Detection Coverage';
  includeRuleNames = true;

  isExporting = signal(false);
  isDragging = signal(false);
  importedLayer = signal<LayerImportResponse | null>(null);

  layerApplied = output<LayerImportResponse>();

  constructor(mitreService: MitreService, snackBar: MatSnackBar) {
    this.mitreService = mitreService;
    this.snackBar = snackBar;
  }

  exportLayer(): void {
    this.isExporting.set(true);
    this.mitreService.exportLayer(this.exportLayerName, this.includeRuleNames).subscribe({
      next: (layer) => {
        this.downloadJson(layer, this.exportLayerName);
        this.isExporting.set(false);
        this.snackBar.open('Layer exported successfully', 'Close', { duration: 3000 });
      },
      error: () => {
        this.isExporting.set(false);
        this.snackBar.open('Failed to export layer', 'Close', { duration: 3000 });
      }
    });
  }

  private downloadJson(data: any, name: string): void {
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${name.replace(/\s+/g, '_')}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  onDragOver(event: DragEvent): void {
    event.preventDefault();
    event.stopPropagation();
    this.isDragging.set(true);
  }

  onDragLeave(event: DragEvent): void {
    event.preventDefault();
    event.stopPropagation();
    this.isDragging.set(false);
  }

  onDrop(event: DragEvent): void {
    event.preventDefault();
    event.stopPropagation();
    this.isDragging.set(false);

    const files = event.dataTransfer?.files;
    if (files && files.length > 0) {
      this.processFile(files[0]);
    }
  }

  onFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    if (input.files && input.files.length > 0) {
      this.processFile(input.files[0]);
    }
  }

  private processFile(file: File): void {
    if (!file.name.endsWith('.json')) {
      this.snackBar.open('Please select a JSON file', 'Close', { duration: 3000 });
      return;
    }

    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const content = e.target?.result as string;
        const layer = JSON.parse(content) as NavigatorLayer;

        // Validate it's a Navigator layer
        if (!layer.techniques || !Array.isArray(layer.techniques)) {
          throw new Error('Invalid Navigator layer format');
        }

        this.mitreService.importLayer(layer).subscribe({
          next: (response) => {
            this.importedLayer.set(response);
            this.snackBar.open('Layer imported successfully', 'Close', { duration: 3000 });
          },
          error: () => {
            this.snackBar.open('Failed to process layer', 'Close', { duration: 3000 });
          }
        });
      } catch (error) {
        this.snackBar.open('Invalid layer file format', 'Close', { duration: 3000 });
      }
    };
    reader.readAsText(file);
  }

  applyImportedLayer(): void {
    const layer = this.importedLayer();
    if (layer) {
      this.layerApplied.emit(layer);
      this.snackBar.open('Layer applied to matrix', 'Close', { duration: 3000 });
    }
  }

  clearImport(): void {
    this.importedLayer.set(null);
  }
}
