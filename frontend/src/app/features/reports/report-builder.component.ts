import { Component, OnInit, signal, inject, ViewChild, ElementRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterModule } from '@angular/router';
import { CdkDragDrop, DragDropModule, moveItemInArray } from '@angular/cdk/drag-drop';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatMenuModule } from '@angular/material/menu';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatDialogModule, MatDialog } from '@angular/material/dialog';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { MatDividerModule } from '@angular/material/divider';
import { MatChipsModule } from '@angular/material/chips';
import { MatExpansionModule } from '@angular/material/expansion';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { MatStepperModule } from '@angular/material/stepper';
import { MatCardModule } from '@angular/material/card';
import { HttpClient } from '@angular/common/http';
import { environment } from '../../../environments/environment';

export type ReportTemplate = 'executive' | 'technical' | 'full' | 'ioc' | 'timeline';
export type SectionType = 'summary' | 'findings' | 'timeline' | 'iocs' | 'artifacts' | 'graph' | 'recommendations' | 'appendix' | 'custom';
export type ExportFormat = 'pdf' | 'docx' | 'html';

export interface ReportSection {
  id: string;
  type: SectionType;
  title: string;
  content: string;
  included: boolean;
  order: number;
  data?: Record<string, unknown>;
}

export interface ReportMetadata {
  title: string;
  subtitle?: string;
  author: string;
  organization?: string;
  classification?: string;
  date: string;
  caseId?: string;
  caseName?: string;
  version: string;
  logo?: string;
}

export interface ReportData {
  id?: string;
  template: ReportTemplate;
  metadata: ReportMetadata;
  sections: ReportSection[];
  createdAt?: string;
  updatedAt?: string;
}

interface TemplateOption {
  id: ReportTemplate;
  name: string;
  description: string;
  icon: string;
  sections: SectionType[];
}

@Component({
  selector: 'app-report-builder',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    RouterModule,
    DragDropModule,
    MatButtonModule,
    MatIconModule,
    MatMenuModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    MatDialogModule,
    MatProgressSpinnerModule,
    MatTooltipModule,
    MatSnackBarModule,
    MatDividerModule,
    MatChipsModule,
    MatExpansionModule,
    MatCheckboxModule,
    MatStepperModule,
    MatCardModule,
  ],
  template: `
    <div class="report-builder">
      <!-- Header -->
      <div class="builder-header">
        <div class="header-left">
          <button mat-icon-button (click)="goBack()">
            <mat-icon>arrow_back</mat-icon>
          </button>
          <h1>Forensic Report Builder</h1>
          @if (caseId()) {
            <span class="case-badge">Case: {{ caseName() || caseId() }}</span>
          }
        </div>
        <div class="header-right">
          <button mat-stroked-button (click)="saveReport()" [disabled]="isSaving()">
            @if (isSaving()) {
              <mat-spinner diameter="18"></mat-spinner>
            } @else {
              <mat-icon>save</mat-icon>
            }
            Save Draft
          </button>
          <button mat-flat-button color="primary" [matMenuTriggerFor]="exportMenu" [disabled]="isExporting()">
            @if (isExporting()) {
              <mat-spinner diameter="18"></mat-spinner>
            } @else {
              <mat-icon>download</mat-icon>
            }
            Export
          </button>
          <mat-menu #exportMenu="matMenu">
            <button mat-menu-item (click)="exportReport('pdf')">
              <mat-icon>picture_as_pdf</mat-icon>
              Export as PDF
            </button>
            <button mat-menu-item (click)="exportReport('docx')">
              <mat-icon>description</mat-icon>
              Export as DOCX
            </button>
            <button mat-menu-item (click)="exportReport('html')">
              <mat-icon>code</mat-icon>
              Export as HTML
            </button>
          </mat-menu>
        </div>
      </div>

      <div class="builder-content">
        <!-- Left Panel: Sections -->
        <div class="sections-panel">
          <div class="panel-header">
            <h3>Report Sections</h3>
            <button mat-icon-button [matMenuTriggerFor]="addSectionMenu" matTooltip="Add Section">
              <mat-icon>add</mat-icon>
            </button>
            <mat-menu #addSectionMenu="matMenu">
              <button mat-menu-item (click)="addSection('summary')">
                <mat-icon>summarize</mat-icon>
                Executive Summary
              </button>
              <button mat-menu-item (click)="addSection('findings')">
                <mat-icon>find_in_page</mat-icon>
                Findings
              </button>
              <button mat-menu-item (click)="addSection('timeline')">
                <mat-icon>timeline</mat-icon>
                Timeline
              </button>
              <button mat-menu-item (click)="addSection('iocs')">
                <mat-icon>warning</mat-icon>
                IOCs
              </button>
              <button mat-menu-item (click)="addSection('artifacts')">
                <mat-icon>folder</mat-icon>
                Artifacts
              </button>
              <button mat-menu-item (click)="addSection('graph')">
                <mat-icon>hub</mat-icon>
                Investigation Graph
              </button>
              <button mat-menu-item (click)="addSection('recommendations')">
                <mat-icon>lightbulb</mat-icon>
                Recommendations
              </button>
              <button mat-menu-item (click)="addSection('appendix')">
                <mat-icon>attachment</mat-icon>
                Appendix
              </button>
              <mat-divider></mat-divider>
              <button mat-menu-item (click)="addSection('custom')">
                <mat-icon>add_box</mat-icon>
                Custom Section
              </button>
            </mat-menu>
          </div>

          <div class="sections-list" cdkDropList (cdkDropListDropped)="onSectionDrop($event)">
            @for (section of sections(); track section.id) {
              <div class="section-item"
                   cdkDrag
                   [class.selected]="selectedSection()?.id === section.id"
                   [class.excluded]="!section.included"
                   (click)="selectSection(section)">
                <mat-icon cdkDragHandle class="drag-handle">drag_indicator</mat-icon>
                <mat-checkbox [(ngModel)]="section.included" (click)="$event.stopPropagation()"></mat-checkbox>
                <mat-icon class="section-icon">{{ getSectionIcon(section.type) }}</mat-icon>
                <span class="section-title">{{ section.title }}</span>
                <button mat-icon-button class="delete-btn" (click)="deleteSection(section, $event)">
                  <mat-icon>delete</mat-icon>
                </button>
              </div>
            }
          </div>

          @if (sections().length === 0) {
            <div class="empty-sections">
              <mat-icon>article</mat-icon>
              <p>No sections yet</p>
              <span>Select a template or add sections</span>
            </div>
          }

          <!-- Template Selection -->
          <div class="template-section">
            <h4>Quick Templates</h4>
            <div class="template-grid">
              @for (template of templates; track template.id) {
                <div class="template-card"
                     [class.selected]="selectedTemplate === template.id"
                     (click)="applyTemplate(template.id)">
                  <mat-icon>{{ template.icon }}</mat-icon>
                  <span class="template-name">{{ template.name }}</span>
                </div>
              }
            </div>
          </div>
        </div>

        <!-- Center: Editor -->
        <div class="editor-panel">
          @if (selectedSection()) {
            <div class="editor-header">
              <mat-form-field appearance="outline" class="title-field">
                <mat-label>Section Title</mat-label>
                <input matInput [(ngModel)]="selectedSection()!.title">
              </mat-form-field>
            </div>

            <div class="editor-content">
              @switch (selectedSection()!.type) {
                @case ('summary') {
                  <div class="section-editor">
                    <p class="editor-hint">Write an executive summary of the investigation findings.</p>
                    <textarea class="content-editor"
                              [(ngModel)]="selectedSection()!.content"
                              placeholder="Enter executive summary..."
                              rows="15"></textarea>
                    <button mat-stroked-button (click)="generateSummary()">
                      <mat-icon>auto_awesome</mat-icon>
                      Auto-Generate Summary
                    </button>
                  </div>
                }
                @case ('findings') {
                  <div class="section-editor">
                    <p class="editor-hint">Document key findings from the investigation.</p>
                    <div class="findings-list">
                      @for (finding of findings(); track $index) {
                        <div class="finding-item">
                          <mat-form-field appearance="outline" class="finding-title">
                            <mat-label>Finding Title</mat-label>
                            <input matInput [(ngModel)]="finding.title">
                          </mat-form-field>
                          <mat-form-field appearance="outline">
                            <mat-label>Severity</mat-label>
                            <mat-select [(ngModel)]="finding.severity">
                              <mat-option value="critical">Critical</mat-option>
                              <mat-option value="high">High</mat-option>
                              <mat-option value="medium">Medium</mat-option>
                              <mat-option value="low">Low</mat-option>
                              <mat-option value="info">Informational</mat-option>
                            </mat-select>
                          </mat-form-field>
                          <mat-form-field appearance="outline" class="full-width">
                            <mat-label>Description</mat-label>
                            <textarea matInput [(ngModel)]="finding.description" rows="3"></textarea>
                          </mat-form-field>
                          <button mat-icon-button (click)="removeFinding($index)" class="remove-btn">
                            <mat-icon>close</mat-icon>
                          </button>
                        </div>
                      }
                      <button mat-stroked-button (click)="addFinding()">
                        <mat-icon>add</mat-icon>
                        Add Finding
                      </button>
                    </div>
                  </div>
                }
                @case ('timeline') {
                  <div class="section-editor">
                    <p class="editor-hint">Include timeline events from the investigation.</p>
                    <div class="data-source-selector">
                      <button mat-stroked-button (click)="importFromTimeline()">
                        <mat-icon>download</mat-icon>
                        Import from Artifact Timeline
                      </button>
                      <button mat-stroked-button (click)="importBookmarks()">
                        <mat-icon>bookmark</mat-icon>
                        Import Bookmarked Events
                      </button>
                    </div>
                    <textarea class="content-editor"
                              [(ngModel)]="selectedSection()!.content"
                              placeholder="Timeline events will be displayed here..."
                              rows="12"></textarea>
                  </div>
                }
                @case ('iocs') {
                  <div class="section-editor">
                    <p class="editor-hint">List indicators of compromise discovered during the investigation.</p>
                    <div class="ioc-list">
                      @for (ioc of iocs(); track ioc.id) {
                        <div class="ioc-item">
                          <mat-form-field appearance="outline">
                            <mat-label>Type</mat-label>
                            <mat-select [(ngModel)]="ioc.type">
                              <mat-option value="ip">IP Address</mat-option>
                              <mat-option value="domain">Domain</mat-option>
                              <mat-option value="hash_md5">MD5 Hash</mat-option>
                              <mat-option value="hash_sha256">SHA256 Hash</mat-option>
                              <mat-option value="url">URL</mat-option>
                              <mat-option value="email">Email</mat-option>
                              <mat-option value="file_path">File Path</mat-option>
                            </mat-select>
                          </mat-form-field>
                          <mat-form-field appearance="outline" class="ioc-value">
                            <mat-label>Value</mat-label>
                            <input matInput [(ngModel)]="ioc.value">
                          </mat-form-field>
                          <mat-form-field appearance="outline">
                            <mat-label>Confidence</mat-label>
                            <mat-select [(ngModel)]="ioc.confidence">
                              <mat-option value="high">High</mat-option>
                              <mat-option value="medium">Medium</mat-option>
                              <mat-option value="low">Low</mat-option>
                            </mat-select>
                          </mat-form-field>
                          <button mat-icon-button (click)="removeIoc(ioc)" class="remove-btn">
                            <mat-icon>close</mat-icon>
                          </button>
                        </div>
                      }
                      <div class="ioc-actions">
                        <button mat-stroked-button (click)="addIoc()">
                          <mat-icon>add</mat-icon>
                          Add IOC
                        </button>
                        <button mat-stroked-button (click)="importIocs()">
                          <mat-icon>download</mat-icon>
                          Import from Case
                        </button>
                      </div>
                    </div>
                  </div>
                }
                @case ('graph') {
                  <div class="section-editor">
                    <p class="editor-hint">Include the investigation graph visualization.</p>
                    <div class="graph-preview">
                      <div class="graph-placeholder">
                        <mat-icon>hub</mat-icon>
                        <p>Investigation Graph</p>
                        <span>Graph will be rendered from saved investigation graph</span>
                      </div>
                    </div>
                    <button mat-stroked-button (click)="selectGraph()">
                      <mat-icon>image</mat-icon>
                      Select Graph to Include
                    </button>
                  </div>
                }
                @case ('recommendations') {
                  <div class="section-editor">
                    <p class="editor-hint">Provide recommendations based on the investigation findings.</p>
                    <div class="recommendations-list">
                      @for (rec of recommendations(); track $index) {
                        <div class="recommendation-item">
                          <mat-form-field appearance="outline">
                            <mat-label>Priority</mat-label>
                            <mat-select [(ngModel)]="rec.priority">
                              <mat-option value="immediate">Immediate</mat-option>
                              <mat-option value="short-term">Short-term</mat-option>
                              <mat-option value="long-term">Long-term</mat-option>
                            </mat-select>
                          </mat-form-field>
                          <mat-form-field appearance="outline" class="rec-text">
                            <mat-label>Recommendation</mat-label>
                            <textarea matInput [(ngModel)]="rec.text" rows="2"></textarea>
                          </mat-form-field>
                          <button mat-icon-button (click)="removeRecommendation($index)" class="remove-btn">
                            <mat-icon>close</mat-icon>
                          </button>
                        </div>
                      }
                      <button mat-stroked-button (click)="addRecommendation()">
                        <mat-icon>add</mat-icon>
                        Add Recommendation
                      </button>
                    </div>
                  </div>
                }
                @default {
                  <div class="section-editor">
                    <textarea class="content-editor"
                              [(ngModel)]="selectedSection()!.content"
                              placeholder="Enter section content..."
                              rows="20"></textarea>
                  </div>
                }
              }
            </div>
          } @else {
            <div class="no-selection">
              <mat-icon>edit_note</mat-icon>
              <p>Select a section to edit</p>
              <span>Or choose a template to get started</span>
            </div>
          }
        </div>

        <!-- Right Panel: Metadata & Preview -->
        <div class="metadata-panel">
          <mat-expansion-panel [expanded]="true">
            <mat-expansion-panel-header>
              <mat-panel-title>
                <mat-icon>info</mat-icon>
                Report Metadata
              </mat-panel-title>
            </mat-expansion-panel-header>

            <div class="metadata-form">
              <mat-form-field appearance="outline">
                <mat-label>Report Title</mat-label>
                <input matInput [(ngModel)]="metadata.title">
              </mat-form-field>

              <mat-form-field appearance="outline">
                <mat-label>Subtitle</mat-label>
                <input matInput [(ngModel)]="metadata.subtitle">
              </mat-form-field>

              <mat-form-field appearance="outline">
                <mat-label>Author</mat-label>
                <input matInput [(ngModel)]="metadata.author">
              </mat-form-field>

              <mat-form-field appearance="outline">
                <mat-label>Organization</mat-label>
                <input matInput [(ngModel)]="metadata.organization">
              </mat-form-field>

              <mat-form-field appearance="outline">
                <mat-label>Classification</mat-label>
                <mat-select [(ngModel)]="metadata.classification">
                  <mat-option value="">None</mat-option>
                  <mat-option value="CONFIDENTIAL">Confidential</mat-option>
                  <mat-option value="INTERNAL">Internal Only</mat-option>
                  <mat-option value="PUBLIC">Public</mat-option>
                  <mat-option value="TLP:RED">TLP:RED</mat-option>
                  <mat-option value="TLP:AMBER">TLP:AMBER</mat-option>
                  <mat-option value="TLP:GREEN">TLP:GREEN</mat-option>
                  <mat-option value="TLP:CLEAR">TLP:CLEAR</mat-option>
                </mat-select>
              </mat-form-field>

              <mat-form-field appearance="outline">
                <mat-label>Version</mat-label>
                <input matInput [(ngModel)]="metadata.version">
              </mat-form-field>
            </div>
          </mat-expansion-panel>

          <mat-expansion-panel>
            <mat-expansion-panel-header>
              <mat-panel-title>
                <mat-icon>visibility</mat-icon>
                Quick Preview
              </mat-panel-title>
            </mat-expansion-panel-header>

            <div class="preview-mini">
              <div class="preview-header">
                <h3>{{ metadata.title || 'Untitled Report' }}</h3>
                @if (metadata.subtitle) {
                  <p>{{ metadata.subtitle }}</p>
                }
                @if (metadata.classification) {
                  <span class="classification-badge">{{ metadata.classification }}</span>
                }
              </div>
              <div class="preview-toc">
                <h4>Table of Contents</h4>
                @for (section of sections(); track section.id) {
                  @if (section.included) {
                    <div class="toc-item">{{ section.title }}</div>
                  }
                }
              </div>
            </div>
          </mat-expansion-panel>

          <mat-expansion-panel>
            <mat-expansion-panel-header>
              <mat-panel-title>
                <mat-icon>history</mat-icon>
                Version History
              </mat-panel-title>
            </mat-expansion-panel-header>

            <div class="version-history">
              @for (version of versions(); track version.id) {
                <div class="version-item">
                  <span class="version-label">v{{ version.version }}</span>
                  <span class="version-date">{{ version.date | date:'short' }}</span>
                  <span class="version-author">{{ version.author }}</span>
                </div>
              }
              @if (versions().length === 0) {
                <p class="no-versions">No previous versions</p>
              }
            </div>
          </mat-expansion-panel>
        </div>
      </div>
    </div>
  `,
  styles: [`
    :host {
      display: block;
      height: 100%;
    }

    .report-builder {
      display: flex;
      flex-direction: column;
      height: 100%;
      background: #121212;
    }

    .builder-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 12px 16px;
      background: #1e1e1e;
      border-bottom: 1px solid #333;
    }

    .header-left, .header-right {
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .builder-header h1 {
      margin: 0;
      font-size: 18px;
      font-weight: 500;
    }

    .case-badge {
      padding: 4px 8px;
      background: #333;
      border-radius: 4px;
      font-size: 12px;
      color: #888;
    }

    .builder-content {
      flex: 1;
      display: flex;
      overflow: hidden;
    }

    .sections-panel {
      width: 280px;
      background: #1e1e1e;
      border-right: 1px solid #333;
      display: flex;
      flex-direction: column;
    }

    .panel-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 12px 16px;
      border-bottom: 1px solid #333;

      h3 {
        margin: 0;
        font-size: 14px;
      }
    }

    .sections-list {
      flex: 1;
      overflow-y: auto;
      padding: 8px;
    }

    .section-item {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 10px 12px;
      background: #252525;
      border-radius: 4px;
      margin-bottom: 4px;
      cursor: pointer;

      &:hover {
        background: #333;
      }

      &.selected {
        background: rgba(var(--accent-rgb), 0.2);
        border: 1px solid var(--accent);
      }

      &.excluded {
        opacity: 0.5;
      }

      .drag-handle {
        cursor: move;
        color: #666;
      }

      .section-icon {
        color: var(--accent);
      }

      .section-title {
        flex: 1;
        font-size: 13px;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }

      .delete-btn {
        width: 28px;
        height: 28px;
        opacity: 0;
      }

      &:hover .delete-btn {
        opacity: 1;
      }
    }

    .empty-sections {
      display: flex;
      flex-direction: column;
      align-items: center;
      padding: 32px 16px;
      color: #666;
      text-align: center;

      mat-icon {
        font-size: 32px;
        width: 32px;
        height: 32px;
        margin-bottom: 8px;
      }

      p {
        margin: 0 0 4px;
      }

      span {
        font-size: 12px;
      }
    }

    .template-section {
      padding: 16px;
      border-top: 1px solid #333;

      h4 {
        margin: 0 0 12px;
        font-size: 12px;
        color: #888;
        text-transform: uppercase;
      }
    }

    .template-grid {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 8px;
    }

    .template-card {
      display: flex;
      flex-direction: column;
      align-items: center;
      padding: 12px;
      background: #252525;
      border-radius: 4px;
      cursor: pointer;
      transition: all 0.15s ease;

      &:hover {
        background: #333;
      }

      &.selected {
        background: rgba(var(--accent-rgb), 0.2);
        border: 1px solid var(--accent);
      }

      mat-icon {
        font-size: 24px;
        width: 24px;
        height: 24px;
        margin-bottom: 4px;
      }

      .template-name {
        font-size: 11px;
        text-align: center;
      }
    }

    .editor-panel {
      flex: 1;
      display: flex;
      flex-direction: column;
      overflow: hidden;
      background: #0a0a0a;
    }

    .editor-header {
      padding: 16px;
      background: #1e1e1e;
      border-bottom: 1px solid #333;
    }

    .title-field {
      width: 100%;
    }

    .editor-content {
      flex: 1;
      padding: 16px;
      overflow-y: auto;
    }

    .section-editor {
      height: 100%;
      display: flex;
      flex-direction: column;
    }

    .editor-hint {
      margin: 0 0 16px;
      font-size: 13px;
      color: #888;
    }

    .content-editor {
      flex: 1;
      width: 100%;
      padding: 16px;
      background: #1e1e1e;
      border: 1px solid #333;
      border-radius: 8px;
      color: #fff;
      font-family: inherit;
      font-size: 14px;
      line-height: 1.6;
      resize: none;
      margin-bottom: 16px;

      &:focus {
        outline: none;
        border-color: var(--accent);
      }
    }

    .data-source-selector {
      display: flex;
      gap: 8px;
      margin-bottom: 16px;
    }

    .findings-list, .ioc-list, .recommendations-list {
      display: flex;
      flex-direction: column;
      gap: 16px;
    }

    .finding-item, .ioc-item, .recommendation-item {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      padding: 16px;
      background: #1e1e1e;
      border-radius: 8px;
      position: relative;

      mat-form-field {
        margin-bottom: 0;
      }

      .finding-title {
        flex: 1;
        min-width: 200px;
      }

      .full-width {
        width: 100%;
      }

      .ioc-value {
        flex: 1;
      }

      .rec-text {
        flex: 1;
      }

      .remove-btn {
        position: absolute;
        top: 8px;
        right: 8px;
      }
    }

    .ioc-actions {
      display: flex;
      gap: 8px;
    }

    .graph-preview {
      margin-bottom: 16px;
    }

    .graph-placeholder {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      padding: 48px;
      background: #1e1e1e;
      border: 2px dashed #333;
      border-radius: 8px;
      color: #666;

      mat-icon {
        font-size: 48px;
        width: 48px;
        height: 48px;
        margin-bottom: 8px;
      }

      p {
        margin: 0 0 4px;
        font-size: 14px;
      }

      span {
        font-size: 12px;
      }
    }

    .no-selection {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      height: 100%;
      color: #666;

      mat-icon {
        font-size: 48px;
        width: 48px;
        height: 48px;
        margin-bottom: 16px;
      }

      p {
        margin: 0 0 8px;
        font-size: 16px;
      }

      span {
        font-size: 13px;
      }
    }

    .metadata-panel {
      width: 320px;
      background: #1e1e1e;
      border-left: 1px solid #333;
      overflow-y: auto;
    }

    mat-expansion-panel {
      background: transparent !important;
      box-shadow: none !important;
    }

    mat-panel-title {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 14px;
    }

    .metadata-form {
      padding: 8px 0;

      mat-form-field {
        width: 100%;
        margin-bottom: 8px;
      }
    }

    .preview-mini {
      padding: 16px;
      background: white;
      color: black;
      border-radius: 4px;
      font-size: 11px;

      .preview-header {
        text-align: center;
        margin-bottom: 16px;
        padding-bottom: 16px;
        border-bottom: 1px solid #ddd;

        h3 {
          margin: 0 0 4px;
          font-size: 14px;
        }

        p {
          margin: 0;
          color: #666;
        }

        .classification-badge {
          display: inline-block;
          margin-top: 8px;
          padding: 2px 8px;
          background: #f44336;
          color: white;
          font-size: 10px;
          border-radius: 2px;
        }
      }

      .preview-toc {
        h4 {
          margin: 0 0 8px;
          font-size: 11px;
          text-transform: uppercase;
        }

        .toc-item {
          padding: 2px 0;
          color: #333;
        }
      }
    }

    .version-history {
      padding: 8px 0;
    }

    .version-item {
      display: flex;
      gap: 8px;
      padding: 8px 0;
      border-bottom: 1px solid #333;
      font-size: 12px;

      .version-label {
        font-weight: 500;
      }

      .version-date, .version-author {
        color: #888;
      }
    }

    .no-versions {
      color: #666;
      font-size: 12px;
      font-style: italic;
    }
  `]
})
export class ReportBuilderComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private http = inject(HttpClient);
  private snackBar = inject(MatSnackBar);

  caseId = signal<string | null>(null);
  caseName = signal<string | null>(null);
  sections = signal<ReportSection[]>([]);
  selectedSection = signal<ReportSection | null>(null);
  selectedTemplate: ReportTemplate | null = null;
  isSaving = signal(false);
  isExporting = signal(false);
  versions = signal<{ id: string; version: string; date: string; author: string }[]>([]);

  // Section-specific data
  findings = signal<{ title: string; severity: string; description: string }[]>([]);
  iocs = signal<{ id: string; type: string; value: string; confidence: string }[]>([]);
  recommendations = signal<{ priority: string; text: string }[]>([]);

  metadata: ReportMetadata = {
    title: 'Forensic Investigation Report',
    subtitle: '',
    author: '',
    organization: '',
    classification: '',
    date: new Date().toISOString().split('T')[0],
    version: '1.0'
  };

  templates: TemplateOption[] = [
    {
      id: 'executive',
      name: 'Executive',
      description: 'High-level summary for executives',
      icon: 'business',
      sections: ['summary', 'findings', 'recommendations']
    },
    {
      id: 'technical',
      name: 'Technical',
      description: 'Detailed technical analysis',
      icon: 'code',
      sections: ['summary', 'timeline', 'artifacts', 'iocs', 'recommendations']
    },
    {
      id: 'full',
      name: 'Full Report',
      description: 'Complete investigation report',
      icon: 'description',
      sections: ['summary', 'findings', 'timeline', 'artifacts', 'graph', 'iocs', 'recommendations', 'appendix']
    },
    {
      id: 'ioc',
      name: 'IOC Report',
      description: 'Focus on indicators of compromise',
      icon: 'warning',
      sections: ['summary', 'iocs', 'recommendations']
    },
    {
      id: 'timeline',
      name: 'Timeline',
      description: 'Chronological event analysis',
      icon: 'timeline',
      sections: ['summary', 'timeline', 'findings']
    }
  ];

  ngOnInit(): void {
    this.route.queryParams.subscribe(params => {
      if (params['case_id']) {
        this.caseId.set(params['case_id']);
        this.metadata.caseId = params['case_id'];
        this.loadCaseInfo(params['case_id']);
      }
    });
  }

  async loadCaseInfo(caseId: string): Promise<void> {
    try {
      const caseData = await this.http.get<{ name: string }>(
        `${environment.apiUrl}/cases/${caseId}`
      ).toPromise();
      if (caseData) {
        this.caseName.set(caseData.name);
        this.metadata.caseName = caseData.name;
        this.metadata.title = `Forensic Investigation Report: ${caseData.name}`;
      }
    } catch (error) {
      console.error('Failed to load case info:', error);
    }
  }

  applyTemplate(templateId: ReportTemplate): void {
    const template = this.templates.find(t => t.id === templateId);
    if (!template) return;

    this.selectedTemplate = templateId;
    const newSections = template.sections.map((type, index) => ({
      id: `section-${Date.now()}-${index}`,
      type,
      title: this.getDefaultTitle(type),
      content: '',
      included: true,
      order: index
    }));

    this.sections.set(newSections);
    if (newSections.length > 0) {
      this.selectSection(newSections[0]);
    }
  }

  getDefaultTitle(type: SectionType): string {
    const titles: Record<SectionType, string> = {
      summary: 'Executive Summary',
      findings: 'Key Findings',
      timeline: 'Incident Timeline',
      iocs: 'Indicators of Compromise',
      artifacts: 'Evidence Artifacts',
      graph: 'Investigation Graph',
      recommendations: 'Recommendations',
      appendix: 'Appendix',
      custom: 'Custom Section'
    };
    return titles[type] || 'Untitled Section';
  }

  getSectionIcon(type: SectionType): string {
    const icons: Record<SectionType, string> = {
      summary: 'summarize',
      findings: 'find_in_page',
      timeline: 'timeline',
      iocs: 'warning',
      artifacts: 'folder',
      graph: 'hub',
      recommendations: 'lightbulb',
      appendix: 'attachment',
      custom: 'article'
    };
    return icons[type] || 'article';
  }

  addSection(type: SectionType): void {
    const newSection: ReportSection = {
      id: `section-${Date.now()}`,
      type,
      title: this.getDefaultTitle(type),
      content: '',
      included: true,
      order: this.sections().length
    };

    this.sections.update(list => [...list, newSection]);
    this.selectSection(newSection);
  }

  selectSection(section: ReportSection): void {
    this.selectedSection.set(section);
  }

  deleteSection(section: ReportSection, event: Event): void {
    event.stopPropagation();
    if (confirm(`Delete section "${section.title}"?`)) {
      this.sections.update(list => list.filter(s => s.id !== section.id));
      if (this.selectedSection()?.id === section.id) {
        this.selectedSection.set(null);
      }
    }
  }

  onSectionDrop(event: CdkDragDrop<ReportSection[]>): void {
    const sections = [...this.sections()];
    moveItemInArray(sections, event.previousIndex, event.currentIndex);
    sections.forEach((s, i) => s.order = i);
    this.sections.set(sections);
  }

  // Findings management
  addFinding(): void {
    this.findings.update(list => [...list, { title: '', severity: 'medium', description: '' }]);
  }

  removeFinding(index: number): void {
    this.findings.update(list => list.filter((_, i) => i !== index));
  }

  // IOC management
  addIoc(): void {
    this.iocs.update(list => [...list, {
      id: `ioc-${Date.now()}`,
      type: 'ip',
      value: '',
      confidence: 'medium'
    }]);
  }

  removeIoc(ioc: { id: string }): void {
    this.iocs.update(list => list.filter(i => i.id !== ioc.id));
  }

  importIocs(): void {
    this.snackBar.open('Importing IOCs from case...', 'Close', { duration: 2000 });
    // Would fetch from backend
  }

  // Recommendation management
  addRecommendation(): void {
    this.recommendations.update(list => [...list, { priority: 'short-term', text: '' }]);
  }

  removeRecommendation(index: number): void {
    this.recommendations.update(list => list.filter((_, i) => i !== index));
  }

  // Auto-generation
  generateSummary(): void {
    this.snackBar.open('Generating summary...', 'Close', { duration: 2000 });
    // Would call AI service
  }

  importFromTimeline(): void {
    this.snackBar.open('Importing timeline events...', 'Close', { duration: 2000 });
  }

  importBookmarks(): void {
    this.snackBar.open('Importing bookmarked events...', 'Close', { duration: 2000 });
  }

  selectGraph(): void {
    this.snackBar.open('Select graph from saved graphs...', 'Close', { duration: 2000 });
  }

  // Save and export
  async saveReport(): Promise<void> {
    this.isSaving.set(true);

    try {
      const reportData: ReportData = {
        template: this.selectedTemplate || 'full',
        metadata: this.metadata,
        sections: this.sections()
      };

      await this.http.post(
        `${environment.apiUrl}/reports`,
        reportData
      ).toPromise();

      this.snackBar.open('Report saved', 'Close', { duration: 2000 });
    } catch (error) {
      console.error('Failed to save report:', error);
      this.snackBar.open('Failed to save report', 'Close', { duration: 3000 });
    } finally {
      this.isSaving.set(false);
    }
  }

  async exportReport(format: ExportFormat): Promise<void> {
    this.isExporting.set(true);

    try {
      const reportData: ReportData = {
        template: this.selectedTemplate || 'full',
        metadata: this.metadata,
        sections: this.sections().filter(s => s.included)
      };

      const response = await this.http.post(
        `${environment.apiUrl}/reports/export`,
        { ...reportData, format },
        { responseType: 'blob' }
      ).toPromise();

      if (response) {
        const url = URL.createObjectURL(response);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${this.metadata.title.replace(/\s+/g, '-').toLowerCase()}.${format}`;
        a.click();
        URL.revokeObjectURL(url);
      }

      this.snackBar.open(`Report exported as ${format.toUpperCase()}`, 'Close', { duration: 2000 });
    } catch (error) {
      console.error('Failed to export report:', error);
      this.snackBar.open('Failed to export report', 'Close', { duration: 3000 });
    } finally {
      this.isExporting.set(false);
    }
  }

  goBack(): void {
    window.history.back();
  }
}
