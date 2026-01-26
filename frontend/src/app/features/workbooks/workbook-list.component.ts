import { Component, OnInit, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router, RouterModule } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatCardModule } from '@angular/material/card';
import { MatMenuModule } from '@angular/material/menu';
import { MatDialog, MatDialogModule } from '@angular/material/dialog';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatInputModule } from '@angular/material/input';
import { MatFormFieldModule } from '@angular/material/form-field';

import { WorkbookService } from '../../core/api/workbook.service';
import { Workbook, WorkbookTemplate } from '../../shared/models/workbook.model';
import { RelativeTimePipe } from '../../shared/pipes/relative-time.pipe';

@Component({
  selector: 'app-workbook-list',
  standalone: true,
  imports: [
    CommonModule,
    RouterModule,
    FormsModule,
    MatButtonModule,
    MatIconModule,
    MatCardModule,
    MatMenuModule,
    MatDialogModule,
    MatSnackBarModule,
    MatProgressSpinnerModule,
    MatTooltipModule,
    MatInputModule,
    MatFormFieldModule,
    RelativeTimePipe,
  ],
  template: `
    <div class="workbooks-page">
      <div class="page-header">
        <div class="header-left">
          <h1>Workbooks</h1>
          <p class="subtitle">Create and manage investigation dashboards</p>
        </div>
        <div class="header-right">
          <button mat-raised-button color="primary" [matMenuTriggerFor]="createMenu">
            <mat-icon>add</mat-icon>
            New Workbook
          </button>
          <mat-menu #createMenu="matMenu">
            <button mat-menu-item (click)="createBlankWorkbook()">
              <mat-icon>note_add</mat-icon>
              Blank Workbook
            </button>
            <button mat-menu-item [matMenuTriggerFor]="templateMenu">
              <mat-icon>dashboard</mat-icon>
              From Template
            </button>
          </mat-menu>
          <mat-menu #templateMenu="matMenu">
            @for (template of templates(); track template.name) {
              <button mat-menu-item (click)="createFromTemplate(template)">
                {{ template.name }}
                <span class="template-info">({{ template.tile_count }} tiles)</span>
              </button>
            }
          </mat-menu>
        </div>
      </div>

      @if (loading()) {
        <div class="loading-container">
          <mat-spinner diameter="48"></mat-spinner>
        </div>
      } @else {
        <div class="workbooks-grid">
          @for (workbook of workbooks(); track workbook.id) {
            <mat-card class="workbook-card" (click)="viewWorkbook(workbook)">
              <mat-card-header>
                <mat-icon mat-card-avatar>dashboard</mat-icon>
                <mat-card-title>{{ workbook.name }}</mat-card-title>
                <mat-card-subtitle>
                  @if (workbook.is_public) {
                    <mat-icon class="visibility-icon">public</mat-icon>
                  } @else {
                    <mat-icon class="visibility-icon">lock</mat-icon>
                  }
                  Updated {{ workbook.updated_at | relativeTime }}
                </mat-card-subtitle>
                <button mat-icon-button [matMenuTriggerFor]="cardMenu" (click)="$event.stopPropagation()">
                  <mat-icon>more_vert</mat-icon>
                </button>
                <mat-menu #cardMenu="matMenu">
                  <button mat-menu-item (click)="editWorkbook(workbook)">
                    <mat-icon>edit</mat-icon>
                    Edit
                  </button>
                  <button mat-menu-item (click)="cloneWorkbook(workbook)">
                    <mat-icon>content_copy</mat-icon>
                    Clone
                  </button>
                  <button mat-menu-item (click)="deleteWorkbook(workbook)" class="delete-action">
                    <mat-icon>delete</mat-icon>
                    Delete
                  </button>
                </mat-menu>
              </mat-card-header>
              <mat-card-content>
                <p class="description">{{ workbook.description || 'No description' }}</p>
                <div class="tile-info">
                  <mat-icon>widgets</mat-icon>
                  <span>{{ workbook.definition?.tiles?.length || 0 }} tiles</span>
                </div>
              </mat-card-content>
            </mat-card>
          }

          @if (workbooks().length === 0) {
            <div class="empty-state">
              <mat-icon>dashboard_customize</mat-icon>
              <h3>No workbooks yet</h3>
              <p>Create your first workbook to build custom investigation dashboards</p>
              <button mat-raised-button color="primary" (click)="createBlankWorkbook()">
                <mat-icon>add</mat-icon>
                Create Workbook
              </button>
            </div>
          }
        </div>
      }
    </div>
  `,
  styles: [`
    :host {
      display: block;
      height: 100%;
      overflow-y: auto;
    }

    .workbooks-page {
      padding: 24px;
    }

    .page-header {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      margin-bottom: 24px;
    }

    .header-left h1 {
      margin: 0;
      font-size: 24px;
    }

    .subtitle {
      margin: 4px 0 0;
      color: #888;
    }

    .loading-container {
      display: flex;
      justify-content: center;
      padding: 48px;
    }

    .workbooks-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
      gap: 16px;
    }

    .workbook-card {
      cursor: pointer;
      transition: transform 0.2s, box-shadow 0.2s;
    }

    .workbook-card:hover {
      transform: translateY(-2px);
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
    }

    mat-card-header {
      position: relative;
    }

    mat-card-header button {
      position: absolute;
      top: 0;
      right: 0;
    }

    .visibility-icon {
      font-size: 14px;
      width: 14px;
      height: 14px;
      vertical-align: middle;
      margin-right: 4px;
    }

    .description {
      color: #aaa;
      font-size: 14px;
      margin: 8px 0;
      overflow: hidden;
      text-overflow: ellipsis;
      display: -webkit-box;
      -webkit-line-clamp: 2;
      -webkit-box-orient: vertical;
    }

    .tile-info {
      display: flex;
      align-items: center;
      gap: 4px;
      color: #888;
      font-size: 12px;
    }

    .tile-info mat-icon {
      font-size: 16px;
      width: 16px;
      height: 16px;
    }

    .template-info {
      color: #888;
      font-size: 12px;
      margin-left: 8px;
    }

    .delete-action {
      color: #f44336;
    }

    .empty-state {
      grid-column: 1 / -1;
      text-align: center;
      padding: 48px;
      color: #888;
    }

    .empty-state mat-icon {
      font-size: 64px;
      width: 64px;
      height: 64px;
      margin-bottom: 16px;
    }

    .empty-state h3 {
      margin: 0 0 8px;
      color: #fff;
    }

    .empty-state p {
      margin: 0 0 24px;
    }
  `],
})
export class WorkbookListComponent implements OnInit {
  private router = inject(Router);
  private workbookService = inject(WorkbookService);
  private dialog = inject(MatDialog);
  private snackBar = inject(MatSnackBar);

  workbooks = signal<Workbook[]>([]);
  templates = signal<WorkbookTemplate[]>([]);
  loading = signal(false);

  ngOnInit(): void {
    this.loadWorkbooks();
    this.loadTemplates();
  }

  async loadWorkbooks(): Promise<void> {
    this.loading.set(true);
    try {
      const result = await this.workbookService.listWorkbooks().toPromise();
      this.workbooks.set(result?.items || []);
    } catch (error) {
      console.error('Failed to load workbooks:', error);
      this.snackBar.open('Failed to load workbooks', 'Close', { duration: 3000 });
    } finally {
      this.loading.set(false);
    }
  }

  async loadTemplates(): Promise<void> {
    try {
      const templates = await this.workbookService.listTemplates().toPromise();
      this.templates.set(templates || []);
    } catch (error) {
      console.error('Failed to load templates:', error);
    }
  }

  viewWorkbook(workbook: Workbook): void {
    this.router.navigate(['/workbooks', workbook.id]);
  }

  editWorkbook(workbook: Workbook): void {
    this.router.navigate(['/workbooks', workbook.id, 'edit']);
  }

  async createBlankWorkbook(): Promise<void> {
    const name = prompt('Enter workbook name:');
    if (!name) return;

    try {
      const workbook = await this.workbookService.createWorkbook({ name }).toPromise();
      if (workbook) {
        this.router.navigate(['/workbooks', workbook.id, 'edit']);
      }
    } catch (error) {
      console.error('Failed to create workbook:', error);
      this.snackBar.open('Failed to create workbook', 'Close', { duration: 3000 });
    }
  }

  async createFromTemplate(template: WorkbookTemplate): Promise<void> {
    const name = prompt('Enter workbook name:', `${template.name} Copy`);
    if (!name) return;

    try {
      const workbook = await this.workbookService.createFromTemplate(template.name, name).toPromise();
      if (workbook) {
        this.router.navigate(['/workbooks', workbook.id]);
      }
    } catch (error) {
      console.error('Failed to create from template:', error);
      this.snackBar.open('Failed to create workbook', 'Close', { duration: 3000 });
    }
  }

  async cloneWorkbook(workbook: Workbook): Promise<void> {
    const name = prompt('Enter name for clone:', `${workbook.name} Copy`);
    if (!name) return;

    try {
      const clone = await this.workbookService.cloneWorkbook(workbook.id, name).toPromise();
      if (clone) {
        this.workbooks.update((list) => [clone, ...list]);
        this.snackBar.open('Workbook cloned', 'Close', { duration: 3000 });
      }
    } catch (error) {
      console.error('Failed to clone workbook:', error);
      this.snackBar.open('Failed to clone workbook', 'Close', { duration: 3000 });
    }
  }

  async deleteWorkbook(workbook: Workbook): Promise<void> {
    if (!confirm(`Delete workbook "${workbook.name}"?`)) return;

    try {
      await this.workbookService.deleteWorkbook(workbook.id).toPromise();
      this.workbooks.update((list) => list.filter((w) => w.id !== workbook.id));
      this.snackBar.open('Workbook deleted', 'Close', { duration: 3000 });
    } catch (error) {
      console.error('Failed to delete workbook:', error);
      this.snackBar.open('Failed to delete workbook', 'Close', { duration: 3000 });
    }
  }
}
