import { Component, OnInit, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule, ReactiveFormsModule, FormBuilder, FormGroup, FormArray, Validators } from '@angular/forms';
import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatStepperModule } from '@angular/material/stepper';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatChipsModule } from '@angular/material/chips';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatDividerModule } from '@angular/material/divider';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { MatExpansionModule } from '@angular/material/expansion';
import { MatSlideToggleModule } from '@angular/material/slide-toggle';
import { MatTabsModule } from '@angular/material/tabs';
import { MatTableModule } from '@angular/material/table';
import { RuleBuilderService, PatternDefinition, RuleBuilderConfig, ValidationResult, PreviewResult } from './rule-builder.service';
import { EventDefinitionComponent } from './event-definition.component';
import { PatternSelectorComponent } from './pattern-selector.component';
import { RulePreviewComponent } from './rule-preview.component';

@Component({
  selector: 'app-rule-builder',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    ReactiveFormsModule,
    MatCardModule,
    MatButtonModule,
    MatIconModule,
    MatStepperModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    MatChipsModule,
    MatTooltipModule,
    MatDividerModule,
    MatProgressSpinnerModule,
    MatSnackBarModule,
    MatExpansionModule,
    MatSlideToggleModule,
    MatTabsModule,
    MatTableModule,
    EventDefinitionComponent,
    PatternSelectorComponent,
    RulePreviewComponent
  ],
  template: `
    <div class="rule-builder">
      <div class="header">
        <div class="title-section">
          <h1>Rule Builder</h1>
          <p class="subtitle">Create correlation rules visually</p>
        </div>
        <div class="header-actions">
          <button mat-stroked-button (click)="resetBuilder()">
            <mat-icon>refresh</mat-icon>
            Reset
          </button>
          <button mat-raised-button color="primary"
                  [disabled]="!canSave()"
                  (click)="saveRule()">
            <mat-icon>save</mat-icon>
            Save Rule
          </button>
        </div>
      </div>

      <div class="builder-content">
        <!-- Left Panel: Configuration -->
        <div class="config-panel">
          <mat-stepper orientation="vertical" [linear]="false" #stepper>
            <!-- Step 1: Pattern Selection -->
            <mat-step [completed]="selectedPattern() !== null">
              <ng-template matStepLabel>
                <span class="step-label">
                  Pattern Type
                  @if (selectedPattern()) {
                    <mat-chip class="step-value">{{ selectedPattern()?.name }}</mat-chip>
                  }
                </span>
              </ng-template>
              <app-pattern-selector
                [patterns]="patterns()"
                [selected]="selectedPattern()"
                (patternSelected)="onPatternSelected($event)">
              </app-pattern-selector>
              <div class="step-actions">
                <button mat-button matStepperNext [disabled]="!selectedPattern()">Next</button>
              </div>
            </mat-step>

            <!-- Step 2: Event Definitions -->
            <mat-step [completed]="eventDefinitions().length > 0">
              <ng-template matStepLabel>
                <span class="step-label">
                  Event Definitions
                  <mat-chip class="step-value">{{ eventDefinitions().length }} events</mat-chip>
                </span>
              </ng-template>
              <div class="events-section">
                @for (event of eventDefinitions(); track event.id; let i = $index) {
                  <app-event-definition
                    [event]="event"
                    [index]="i"
                    [fields]="availableFields()"
                    (eventChanged)="onEventChanged($event, i)"
                    (eventRemoved)="removeEvent(i)">
                  </app-event-definition>
                }
                <button mat-stroked-button (click)="addEvent()" class="add-event-btn">
                  <mat-icon>add</mat-icon>
                  Add Event Type
                </button>
              </div>
              <div class="step-actions">
                <button mat-button matStepperPrevious>Back</button>
                <button mat-button matStepperNext [disabled]="eventDefinitions().length === 0">Next</button>
              </div>
            </mat-step>

            <!-- Step 3: Correlation Settings -->
            <mat-step [completed]="correlationConfigured()">
              <ng-template matStepLabel>
                <span class="step-label">Correlation Settings</span>
              </ng-template>
              <div class="correlation-settings">
                <!-- Time Window -->
                <mat-form-field appearance="outline" class="full-width">
                  <mat-label>Time Window</mat-label>
                  <mat-select [(ngModel)]="timeWindow" (ngModelChange)="onConfigChanged()">
                    <mat-option value="1m">1 minute</mat-option>
                    <mat-option value="5m">5 minutes</mat-option>
                    <mat-option value="15m">15 minutes</mat-option>
                    <mat-option value="30m">30 minutes</mat-option>
                    <mat-option value="1h">1 hour</mat-option>
                    <mat-option value="6h">6 hours</mat-option>
                    <mat-option value="24h">24 hours</mat-option>
                  </mat-select>
                  <mat-hint>Maximum time between correlated events</mat-hint>
                </mat-form-field>

                <!-- Join Fields -->
                <div class="join-fields-section">
                  <h4>Join Fields</h4>
                  <p class="section-hint">Fields used to correlate events together (e.g., same user, same host)</p>
                  @for (field of joinFields; track $index; let i = $index) {
                    <div class="join-field-row">
                      <mat-form-field appearance="outline" class="flex-grow">
                        <mat-label>Field {{ i + 1 }}</mat-label>
                        <mat-select [(ngModel)]="joinFields[i]" (ngModelChange)="onConfigChanged()">
                          @for (f of availableFields(); track f.path) {
                            <mat-option [value]="f.path">{{ f.path }}</mat-option>
                          }
                        </mat-select>
                      </mat-form-field>
                      <button mat-icon-button (click)="removeJoinField(i)" matTooltip="Remove">
                        <mat-icon>close</mat-icon>
                      </button>
                    </div>
                  }
                  <button mat-stroked-button (click)="addJoinField()" class="add-btn">
                    <mat-icon>add</mat-icon>
                    Add Join Field
                  </button>
                </div>

                <!-- Pattern-specific settings -->
                @if (selectedPattern()?.type === 'sequence') {
                  <div class="sequence-settings">
                    <h4>Sequence Order</h4>
                    <p class="section-hint">Define the order events must occur</p>
                    <div class="sequence-order">
                      @for (eventId of sequenceOrder; track $index; let i = $index) {
                        <div class="sequence-item">
                          <span class="sequence-number">{{ i + 1 }}</span>
                          <mat-form-field appearance="outline" class="flex-grow">
                            <mat-select [(ngModel)]="sequenceOrder[i]" (ngModelChange)="onConfigChanged()">
                              @for (event of eventDefinitions(); track event.id) {
                                <mat-option [value]="event.id">{{ event.name || event.id }}</mat-option>
                              }
                            </mat-select>
                          </mat-form-field>
                          <button mat-icon-button (click)="removeFromSequence(i)">
                            <mat-icon>close</mat-icon>
                          </button>
                        </div>
                      }
                      <button mat-stroked-button (click)="addToSequence()" class="add-btn">
                        <mat-icon>add</mat-icon>
                        Add Step
                      </button>
                    </div>
                  </div>
                }

                <!-- Thresholds -->
                <div class="thresholds-section">
                  <h4>Thresholds</h4>
                  <p class="section-hint">Minimum event counts to trigger the rule</p>
                  @for (threshold of thresholds; track $index; let i = $index) {
                    <div class="threshold-row">
                      <mat-form-field appearance="outline">
                        <mat-label>Event</mat-label>
                        <mat-select [(ngModel)]="thresholds[i].eventId" (ngModelChange)="onConfigChanged()">
                          @for (event of eventDefinitions(); track event.id) {
                            <mat-option [value]="event.id">{{ event.name || event.id }}</mat-option>
                          }
                        </mat-select>
                      </mat-form-field>
                      <mat-form-field appearance="outline" class="operator-field">
                        <mat-label>Operator</mat-label>
                        <mat-select [(ngModel)]="thresholds[i].operator" (ngModelChange)="onConfigChanged()">
                          <mat-option value=">=">>=</mat-option>
                          <mat-option value=">">></mat-option>
                          <mat-option value="==">=</mat-option>
                          <mat-option value="<"><</mat-option>
                          <mat-option value="<="><=</mat-option>
                        </mat-select>
                      </mat-form-field>
                      <mat-form-field appearance="outline" class="count-field">
                        <mat-label>Count</mat-label>
                        <input matInput type="number" [(ngModel)]="thresholds[i].count" (ngModelChange)="onConfigChanged()">
                      </mat-form-field>
                      <button mat-icon-button (click)="removeThreshold(i)">
                        <mat-icon>close</mat-icon>
                      </button>
                    </div>
                  }
                  <button mat-stroked-button (click)="addThreshold()" class="add-btn">
                    <mat-icon>add</mat-icon>
                    Add Threshold
                  </button>
                </div>

                <!-- Realtime Toggle -->
                <div class="realtime-toggle">
                  <mat-slide-toggle [(ngModel)]="realtimeEnabled" (ngModelChange)="onConfigChanged()">
                    Enable Real-time Processing
                  </mat-slide-toggle>
                  <p class="toggle-hint">Process events as they arrive for immediate detection</p>
                </div>
              </div>
              <div class="step-actions">
                <button mat-button matStepperPrevious>Back</button>
                <button mat-button matStepperNext>Next</button>
              </div>
            </mat-step>

            <!-- Step 4: Preview & Test -->
            <mat-step>
              <ng-template matStepLabel>
                <span class="step-label">Preview & Test</span>
              </ng-template>
              <app-rule-preview
                [config]="buildConfig()"
                [validationResult]="validationResult()"
                [previewResult]="previewResult()"
                [isValidating]="isValidating()"
                [isPreviewing]="isPreviewing()"
                (validate)="validateRule()"
                (preview)="previewRule()">
              </app-rule-preview>
              <div class="step-actions">
                <button mat-button matStepperPrevious>Back</button>
              </div>
            </mat-step>
          </mat-stepper>
        </div>

        <!-- Right Panel: Live Config Preview -->
        <div class="preview-panel">
          <mat-card>
            <mat-card-header>
              <mat-card-title>Generated Configuration</mat-card-title>
            </mat-card-header>
            <mat-card-content>
              <pre class="config-preview">{{ buildConfig() | json }}</pre>
            </mat-card-content>
          </mat-card>

          @if (validationResult()) {
            <mat-card class="validation-card" [class.valid]="validationResult()!.valid" [class.invalid]="!validationResult()!.valid">
              <mat-card-header>
                <mat-icon mat-card-avatar [class.valid]="validationResult()!.valid">
                  {{ validationResult()!.valid ? 'check_circle' : 'error' }}
                </mat-icon>
                <mat-card-title>
                  {{ validationResult()!.valid ? 'Valid Configuration' : 'Validation Errors' }}
                </mat-card-title>
              </mat-card-header>
              @if (validationResult()!.errors.length > 0) {
                <mat-card-content>
                  <ul class="error-list">
                    @for (error of validationResult()!.errors; track error.field) {
                      <li class="error-item">
                        <strong>{{ error.field }}:</strong> {{ error.message }}
                      </li>
                    }
                  </ul>
                </mat-card-content>
              }
              @if (validationResult()!.warnings.length > 0) {
                <mat-card-content>
                  <ul class="warning-list">
                    @for (warning of validationResult()!.warnings; track warning.field) {
                      <li class="warning-item">
                        <mat-icon>warning</mat-icon>
                        {{ warning.message }}
                      </li>
                    }
                  </ul>
                </mat-card-content>
              }
            </mat-card>
          }
        </div>
      </div>
    </div>
  `,
  styles: [`
    .rule-builder {
      padding: 24px;
      max-width: 1600px;
      margin: 0 auto;
    }

    .header {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      margin-bottom: 24px;
    }

    .title-section h1 {
      margin: 0;
      font-size: 28px;
      font-weight: 500;
    }

    .subtitle {
      margin: 4px 0 0;
      color: var(--text-secondary);
    }

    .header-actions {
      display: flex;
      gap: 12px;
    }

    .builder-content {
      display: grid;
      grid-template-columns: 1fr 400px;
      gap: 24px;
    }

    .config-panel {
      background: var(--card-bg);
      border-radius: 12px;
      padding: 24px;
    }

    .step-label {
      display: flex;
      align-items: center;
      gap: 12px;
    }

    .step-value {
      font-size: 11px;
    }

    .step-actions {
      margin-top: 24px;
      display: flex;
      gap: 12px;
    }

    .events-section {
      display: flex;
      flex-direction: column;
      gap: 16px;
    }

    .add-event-btn, .add-btn {
      align-self: flex-start;
    }

    .correlation-settings {
      display: flex;
      flex-direction: column;
      gap: 24px;
    }

    .full-width {
      width: 100%;
    }

    .section-hint {
      font-size: 12px;
      color: var(--text-secondary);
      margin: 4px 0 12px;
    }

    .join-fields-section, .thresholds-section, .sequence-settings {
      padding: 16px;
      background: var(--hover-bg);
      border-radius: 8px;
    }

    .join-fields-section h4, .thresholds-section h4, .sequence-settings h4 {
      margin: 0;
    }

    .join-field-row, .threshold-row, .sequence-item {
      display: flex;
      align-items: center;
      gap: 12px;
      margin-bottom: 12px;
    }

    .flex-grow {
      flex: 1;
    }

    .operator-field {
      width: 100px;
    }

    .count-field {
      width: 100px;
    }

    .sequence-number {
      width: 24px;
      height: 24px;
      background: var(--primary-color);
      color: white;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 12px;
      font-weight: 600;
    }

    .realtime-toggle {
      padding: 16px;
      background: var(--hover-bg);
      border-radius: 8px;
    }

    .toggle-hint {
      font-size: 12px;
      color: var(--text-secondary);
      margin: 8px 0 0;
    }

    .preview-panel {
      display: flex;
      flex-direction: column;
      gap: 16px;
    }

    .config-preview {
      background: #1e1e1e;
      color: #d4d4d4;
      padding: 16px;
      border-radius: 8px;
      font-size: 12px;
      overflow-x: auto;
      max-height: 400px;
    }

    .validation-card {
      &.valid {
        border-left: 4px solid #4caf50;
      }
      &.invalid {
        border-left: 4px solid #f44336;
      }
    }

    .validation-card mat-icon.valid {
      color: #4caf50;
    }

    .validation-card mat-icon:not(.valid) {
      color: #f44336;
    }

    .error-list, .warning-list {
      list-style: none;
      padding: 0;
      margin: 0;
    }

    .error-item {
      padding: 8px;
      background: rgba(244, 67, 54, 0.1);
      border-radius: 4px;
      margin-bottom: 8px;
      color: #f44336;
    }

    .warning-item {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 8px;
      background: rgba(255, 152, 0, 0.1);
      border-radius: 4px;
      margin-bottom: 8px;
      color: #ff9800;
    }

    .warning-item mat-icon {
      font-size: 18px;
      width: 18px;
      height: 18px;
    }

    @media (max-width: 1200px) {
      .builder-content {
        grid-template-columns: 1fr;
      }
      .preview-panel {
        display: none;
      }
    }
  `]
})
export class RuleBuilderComponent implements OnInit {
  // Signals
  patterns = signal<PatternDefinition[]>([]);
  selectedPattern = signal<PatternDefinition | null>(null);
  eventDefinitions = signal<EventDefinition[]>([]);
  availableFields = signal<AvailableField[]>([]);
  validationResult = signal<ValidationResult | null>(null);
  previewResult = signal<PreviewResult | null>(null);
  isValidating = signal(false);
  isPreviewing = signal(false);

  // Form state
  timeWindow = '5m';
  joinFields: string[] = [];
  sequenceOrder: string[] = [];
  thresholds: { eventId: string; operator: string; count: number }[] = [];
  realtimeEnabled = false;

  correlationConfigured = computed(() => {
    return this.joinFields.length > 0 || this.thresholds.length > 0;
  });

  canSave = computed(() => {
    const validation = this.validationResult();
    return validation?.valid === true && this.selectedPattern() !== null;
  });

  constructor(
    private ruleBuilderService: RuleBuilderService,
    private snackBar: MatSnackBar
  ) {}

  ngOnInit() {
    this.loadPatterns();
    this.loadFields();
  }

  loadPatterns() {
    this.ruleBuilderService.getPatterns().subscribe({
      next: (response) => this.patterns.set(response.patterns),
      error: (err) => console.error('Failed to load patterns:', err)
    });
  }

  loadFields() {
    this.ruleBuilderService.getFields().subscribe({
      next: (response) => this.availableFields.set(response.fields),
      error: (err) => console.error('Failed to load fields:', err)
    });
  }

  onPatternSelected(pattern: PatternDefinition) {
    this.selectedPattern.set(pattern);
    this.onConfigChanged();
  }

  addEvent() {
    const events = this.eventDefinitions();
    const newId = `event_${events.length + 1}`;
    this.eventDefinitions.set([...events, {
      id: newId,
      name: `Event ${events.length + 1}`,
      conditions: []
    }]);
  }

  onEventChanged(event: EventDefinition, index: number) {
    const events = [...this.eventDefinitions()];
    events[index] = event;
    this.eventDefinitions.set(events);
    this.onConfigChanged();
  }

  removeEvent(index: number) {
    const events = this.eventDefinitions().filter((_, i) => i !== index);
    this.eventDefinitions.set(events);
    this.onConfigChanged();
  }

  addJoinField() {
    this.joinFields = [...this.joinFields, ''];
  }

  removeJoinField(index: number) {
    this.joinFields = this.joinFields.filter((_, i) => i !== index);
    this.onConfigChanged();
  }

  addToSequence() {
    const events = this.eventDefinitions();
    if (events.length > 0) {
      this.sequenceOrder = [...this.sequenceOrder, events[0].id];
      this.onConfigChanged();
    }
  }

  removeFromSequence(index: number) {
    this.sequenceOrder = this.sequenceOrder.filter((_, i) => i !== index);
    this.onConfigChanged();
  }

  addThreshold() {
    const events = this.eventDefinitions();
    if (events.length > 0) {
      this.thresholds = [...this.thresholds, {
        eventId: events[0].id,
        operator: '>=',
        count: 1
      }];
    }
  }

  removeThreshold(index: number) {
    this.thresholds = this.thresholds.filter((_, i) => i !== index);
    this.onConfigChanged();
  }

  onConfigChanged() {
    // Clear validation when config changes
    this.validationResult.set(null);
    this.previewResult.set(null);
  }

  buildConfig(): RuleBuilderConfig | null {
    const pattern = this.selectedPattern();
    if (!pattern) return null;

    const config: RuleBuilderConfig = {
      pattern_type: pattern.type,
      window: this.timeWindow,
      events: this.eventDefinitions(),
      join_on: this.joinFields.filter(f => f).map(f => ({ field: f })),
      thresholds: this.thresholds.map(t => ({
        event_id: t.eventId,
        operator: t.operator,
        count: t.count
      })),
      realtime: this.realtimeEnabled
    };

    if (pattern.type === 'sequence' && this.sequenceOrder.length > 0) {
      config.sequence = {
        order: this.sequenceOrder,
        strict_order: false
      };
    }

    return config;
  }

  validateRule() {
    const config = this.buildConfig();
    if (!config) return;

    this.isValidating.set(true);
    this.ruleBuilderService.validate(config).subscribe({
      next: (result) => {
        this.validationResult.set(result);
        this.isValidating.set(false);
      },
      error: (err) => {
        console.error('Validation failed:', err);
        this.isValidating.set(false);
        this.snackBar.open('Validation failed', 'Dismiss', { duration: 3000 });
      }
    });
  }

  previewRule() {
    const config = this.buildConfig();
    if (!config) return;

    this.isPreviewing.set(true);
    this.ruleBuilderService.preview({ config, time_range: '24h', limit: 100 }).subscribe({
      next: (result) => {
        this.previewResult.set(result);
        this.isPreviewing.set(false);
      },
      error: (err) => {
        console.error('Preview failed:', err);
        this.isPreviewing.set(false);
        this.snackBar.open('Preview failed', 'Dismiss', { duration: 3000 });
      }
    });
  }

  saveRule() {
    // TODO: Implement rule saving
    this.snackBar.open('Rule saving coming soon', 'Dismiss', { duration: 3000 });
  }

  resetBuilder() {
    this.selectedPattern.set(null);
    this.eventDefinitions.set([]);
    this.timeWindow = '5m';
    this.joinFields = [];
    this.sequenceOrder = [];
    this.thresholds = [];
    this.realtimeEnabled = false;
    this.validationResult.set(null);
    this.previewResult.set(null);
  }
}

// Interfaces
interface EventDefinition {
  id: string;
  name: string;
  description?: string;
  conditions: FieldCondition[];
  raw_query?: string;
}

interface FieldCondition {
  field: string;
  operator: string;
  value: any;
  negate?: boolean;
}

interface AvailableField {
  path: string;
  type: string;
  description?: string;
  sample_values?: any[];
}
