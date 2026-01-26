import { Component, Inject, signal, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatDialogModule, MatDialogRef, MAT_DIALOG_DATA } from '@angular/material/dialog';
import { MatStepperModule } from '@angular/material/stepper';
import { MatSlideToggleModule } from '@angular/material/slide-toggle';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { MatDividerModule } from '@angular/material/divider';
import { MatChipsModule } from '@angular/material/chips';
import {
  ConnectorsService,
  DataConnector,
  ConnectorType,
  ConnectorCreate
} from '../../core/api/connectors.service';

interface DialogData {
  mode: 'create' | 'edit';
  connector?: DataConnector;
}

interface ConnectorTypeInfo {
  type: ConnectorType;
  label: string;
  icon: string;
  description: string;
  configFields: ConfigField[];
}

interface ConfigField {
  key: string;
  label: string;
  type: 'text' | 'number' | 'password' | 'textarea' | 'select';
  required?: boolean;
  placeholder?: string;
  options?: { value: string; label: string }[];
}

@Component({
  selector: 'app-connector-dialog',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatButtonModule,
    MatIconModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    MatDialogModule,
    MatStepperModule,
    MatSlideToggleModule,
    MatProgressSpinnerModule,
    MatSnackBarModule,
    MatDividerModule,
    MatChipsModule,
  ],
  template: `
    <div class="connector-dialog">
      <div class="dialog-header">
        <h2>{{ data.mode === 'create' ? 'Add New Connector' : 'Edit Connector' }}</h2>
        <button mat-icon-button (click)="close()">
          <mat-icon>close</mat-icon>
        </button>
      </div>

      <div class="dialog-body">
        @if (data.mode === 'create' && !selectedType()) {
          <!-- Type Selection -->
          <div class="type-selection">
            <p class="section-label">Select connector type</p>
            <div class="type-grid">
              @for (typeInfo of connectorTypes; track typeInfo.type) {
                <div class="type-card" (click)="selectType(typeInfo)">
                  <div class="type-icon" [class]="typeInfo.type">
                    <mat-icon>{{ typeInfo.icon }}</mat-icon>
                  </div>
                  <div class="type-info">
                    <h4>{{ typeInfo.label }}</h4>
                    <p>{{ typeInfo.description }}</p>
                  </div>
                </div>
              }
            </div>
          </div>
        } @else {
          <!-- Configuration Form -->
          <div class="config-form">
            @if (selectedType()) {
              <div class="selected-type">
                <div class="type-icon" [class]="selectedType()!.type">
                  <mat-icon>{{ selectedType()!.icon }}</mat-icon>
                </div>
                <div class="type-info">
                  <h4>{{ selectedType()!.label }}</h4>
                  <p>{{ selectedType()!.description }}</p>
                </div>
                @if (data.mode === 'create') {
                  <button mat-icon-button (click)="clearType()">
                    <mat-icon>close</mat-icon>
                  </button>
                }
              </div>
            }

            <mat-divider></mat-divider>

            <!-- Basic Settings -->
            <div class="form-section">
              <h3>Basic Settings</h3>

              <mat-form-field appearance="outline" class="full-width">
                <mat-label>Connector Name</mat-label>
                <input matInput [(ngModel)]="formData.name" required placeholder="e.g., Production Syslog">
              </mat-form-field>

              <mat-form-field appearance="outline" class="full-width">
                <mat-label>Description</mat-label>
                <textarea matInput [(ngModel)]="formData.description" rows="2" placeholder="Optional description"></textarea>
              </mat-form-field>

              <div class="form-row">
                <mat-form-field appearance="outline">
                  <mat-label>Target Index</mat-label>
                  <input matInput [(ngModel)]="formData.target_index" placeholder="e.g., logs-syslog">
                </mat-form-field>

                <mat-form-field appearance="outline">
                  <mat-label>Data Type</mat-label>
                  <mat-select [(ngModel)]="formData.data_type">
                    <mat-option value="syslog">Syslog</mat-option>
                    <mat-option value="windows_event">Windows Event</mat-option>
                    <mat-option value="network">Network</mat-option>
                    <mat-option value="cloud">Cloud Logs</mat-option>
                    <mat-option value="application">Application</mat-option>
                    <mat-option value="security">Security</mat-option>
                    <mat-option value="custom">Custom</mat-option>
                  </mat-select>
                </mat-form-field>
              </div>
            </div>

            <!-- Connection Settings -->
            <div class="form-section">
              <h3>Connection Settings</h3>

              @for (field of selectedType()?.configFields || []; track field.key) {
                <mat-form-field appearance="outline" class="full-width">
                  <mat-label>{{ field.label }}</mat-label>
                  @switch (field.type) {
                    @case ('textarea') {
                      <textarea matInput
                        [(ngModel)]="configValues[field.key]"
                        [required]="field.required || false"
                        [placeholder]="field.placeholder || ''"
                        rows="3"></textarea>
                    }
                    @case ('password') {
                      <input matInput type="password"
                        [(ngModel)]="configValues[field.key]"
                        [required]="field.required || false"
                        [placeholder]="field.placeholder || ''">
                    }
                    @case ('number') {
                      <input matInput type="number"
                        [(ngModel)]="configValues[field.key]"
                        [required]="field.required || false"
                        [placeholder]="field.placeholder || ''">
                    }
                    @case ('select') {
                      <mat-select [(ngModel)]="configValues[field.key]" [required]="field.required || false">
                        @for (opt of field.options || []; track opt.value) {
                          <mat-option [value]="opt.value">{{ opt.label }}</mat-option>
                        }
                      </mat-select>
                    }
                    @default {
                      <input matInput
                        [(ngModel)]="configValues[field.key]"
                        [required]="field.required || false"
                        [placeholder]="field.placeholder || ''">
                    }
                  }
                </mat-form-field>
              }

              @if (selectedType()?.type === 'api_polling') {
                <mat-form-field appearance="outline" class="full-width">
                  <mat-label>Polling Interval (seconds)</mat-label>
                  <input matInput type="number" [(ngModel)]="formData.polling_interval" placeholder="60">
                </mat-form-field>
              }
            </div>

            <!-- Tags -->
            <div class="form-section">
              <h3>Tags</h3>
              <div class="tags-input">
                <mat-form-field appearance="outline" class="tag-field">
                  <mat-label>Tag Key</mat-label>
                  <input matInput [(ngModel)]="newTagKey" placeholder="e.g., environment">
                </mat-form-field>
                <mat-form-field appearance="outline" class="tag-field">
                  <mat-label>Tag Value</mat-label>
                  <input matInput [(ngModel)]="newTagValue" placeholder="e.g., production">
                </mat-form-field>
                <button mat-icon-button color="primary" (click)="addTag()" [disabled]="!newTagKey || !newTagValue">
                  <mat-icon>add</mat-icon>
                </button>
              </div>
              <div class="tags-list">
                @for (tag of tagsList(); track tag.key) {
                  <div class="tag-chip">
                    <span>{{ tag.key }}: {{ tag.value }}</span>
                    <mat-icon (click)="removeTag(tag.key)">close</mat-icon>
                  </div>
                }
              </div>
            </div>
          </div>
        }
      </div>

      <div class="dialog-footer">
        <button mat-button (click)="close()">Cancel</button>
        @if (selectedType()) {
          <button mat-flat-button color="primary" [disabled]="saving() || !isValid()" (click)="save()">
            @if (saving()) {
              <mat-spinner diameter="20"></mat-spinner>
            } @else {
              {{ data.mode === 'create' ? 'Create Connector' : 'Save Changes' }}
            }
          </button>
        }
      </div>
    </div>
  `,
  styles: [`
    .connector-dialog {
      display: flex;
      flex-direction: column;
      max-height: 90vh;
    }

    .dialog-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 16px 24px;
      border-bottom: 1px solid #333;
    }

    .dialog-header h2 {
      margin: 0;
      font-size: 20px;
      font-weight: 500;
    }

    .dialog-body {
      flex: 1;
      overflow-y: auto;
      padding: 24px;
    }

    .section-label {
      margin: 0 0 16px;
      color: #888;
      font-size: 14px;
    }

    /* Type Selection */
    .type-grid {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 12px;
    }

    .type-card {
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 16px;
      background: #252525;
      border: 1px solid #333;
      border-radius: 8px;
      cursor: pointer;
      transition: border-color 0.2s, background 0.2s;
    }

    .type-card:hover {
      border-color: #4CAF50;
      background: #2a2a2a;
    }

    .type-icon {
      width: 40px;
      height: 40px;
      border-radius: 8px;
      display: flex;
      align-items: center;
      justify-content: center;
      background: #333;
      flex-shrink: 0;
    }

    .type-icon.syslog { background: rgba(0, 188, 212, 0.15); color: #00BCD4; }
    .type-icon.windows_event { background: rgba(33, 150, 243, 0.15); color: #2196F3; }
    .type-icon.cloud_trail { background: rgba(255, 152, 0, 0.15); color: #FF9800; }
    .type-icon.azure_ad { background: rgba(0, 120, 212, 0.15); color: #0078D4; }
    .type-icon.office_365 { background: rgba(235, 59, 90, 0.15); color: #EB3B5A; }
    .type-icon.aws_s3 { background: rgba(255, 153, 0, 0.15); color: #FF9900; }
    .type-icon.beats { background: rgba(0, 191, 178, 0.15); color: #00BFB2; }
    .type-icon.kafka { background: rgba(100, 100, 100, 0.15); color: #ccc; }
    .type-icon.webhook { background: rgba(156, 39, 176, 0.15); color: #9C27B0; }
    .type-icon.api_polling { background: rgba(76, 175, 80, 0.15); color: #4CAF50; }
    .type-icon.file_upload { background: rgba(121, 85, 72, 0.15); color: #795548; }
    .type-icon.custom { background: rgba(158, 158, 158, 0.15); color: #9E9E9E; }

    .type-info h4 {
      margin: 0 0 4px;
      font-size: 14px;
      font-weight: 500;
    }

    .type-info p {
      margin: 0;
      font-size: 12px;
      color: #888;
    }

    /* Config Form */
    .config-form {
      display: flex;
      flex-direction: column;
      gap: 20px;
    }

    .selected-type {
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 12px;
      background: #252525;
      border-radius: 8px;
    }

    .selected-type .type-info {
      flex: 1;
    }

    .form-section h3 {
      margin: 0 0 16px;
      font-size: 14px;
      font-weight: 500;
      color: #aaa;
    }

    .full-width {
      width: 100%;
    }

    .form-row {
      display: flex;
      gap: 16px;
    }

    .form-row mat-form-field {
      flex: 1;
    }

    /* Tags */
    .tags-input {
      display: flex;
      gap: 12px;
      align-items: flex-start;
    }

    .tag-field {
      flex: 1;
    }

    .tags-list {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 12px;
    }

    .tag-chip {
      display: flex;
      align-items: center;
      gap: 6px;
      padding: 4px 8px 4px 12px;
      background: #333;
      border-radius: 16px;
      font-size: 12px;
    }

    .tag-chip mat-icon {
      font-size: 16px;
      width: 16px;
      height: 16px;
      cursor: pointer;
      opacity: 0.7;
    }

    .tag-chip mat-icon:hover {
      opacity: 1;
    }

    .dialog-footer {
      display: flex;
      justify-content: flex-end;
      gap: 12px;
      padding: 16px 24px;
      border-top: 1px solid #333;
    }

    .dialog-footer button mat-spinner {
      display: inline-block;
    }
  `]
})
export class ConnectorDialogComponent implements OnInit {
  selectedType = signal<ConnectorTypeInfo | null>(null);
  saving = signal(false);
  tagsList = signal<{ key: string; value: string }[]>([]);

  formData: Partial<ConnectorCreate> = {
    name: '',
    description: '',
    target_index: '',
    data_type: '',
    polling_interval: 60
  };

  configValues: Record<string, unknown> = {};
  newTagKey = '';
  newTagValue = '';

  connectorTypes: ConnectorTypeInfo[] = [
    {
      type: 'syslog',
      label: 'Syslog',
      icon: 'terminal',
      description: 'Receive syslog messages via UDP/TCP',
      configFields: [
        { key: 'protocol', label: 'Protocol', type: 'select', required: true, options: [
          { value: 'udp', label: 'UDP' }, { value: 'tcp', label: 'TCP' }, { value: 'tls', label: 'TLS' }
        ]},
        { key: 'port', label: 'Port', type: 'number', required: true, placeholder: '514' },
        { key: 'bind_address', label: 'Bind Address', type: 'text', placeholder: '0.0.0.0' }
      ]
    },
    {
      type: 'windows_event',
      label: 'Windows Events',
      icon: 'desktop_windows',
      description: 'Collect Windows Event logs via WEF',
      configFields: [
        { key: 'subscription_name', label: 'Subscription Name', type: 'text', required: true },
        { key: 'channels', label: 'Event Channels', type: 'textarea', placeholder: 'Security, Application, System' }
      ]
    },
    {
      type: 'cloud_trail',
      label: 'AWS CloudTrail',
      icon: 'cloud',
      description: 'Ingest AWS CloudTrail logs',
      configFields: [
        { key: 'aws_access_key', label: 'AWS Access Key', type: 'text', required: true },
        { key: 'aws_secret_key', label: 'AWS Secret Key', type: 'password', required: true },
        { key: 'region', label: 'AWS Region', type: 'text', required: true, placeholder: 'us-east-1' },
        { key: 'trail_name', label: 'Trail Name', type: 'text' }
      ]
    },
    {
      type: 'azure_ad',
      label: 'Azure AD',
      icon: 'account_circle',
      description: 'Collect Azure AD audit and sign-in logs',
      configFields: [
        { key: 'tenant_id', label: 'Tenant ID', type: 'text', required: true },
        { key: 'client_id', label: 'Client ID', type: 'text', required: true },
        { key: 'client_secret', label: 'Client Secret', type: 'password', required: true }
      ]
    },
    {
      type: 'office_365',
      label: 'Office 365',
      icon: 'mail',
      description: 'Ingest Office 365 audit logs',
      configFields: [
        { key: 'tenant_id', label: 'Tenant ID', type: 'text', required: true },
        { key: 'client_id', label: 'Client ID', type: 'text', required: true },
        { key: 'client_secret', label: 'Client Secret', type: 'password', required: true },
        { key: 'content_types', label: 'Content Types', type: 'textarea', placeholder: 'Audit.AzureActiveDirectory, Audit.Exchange' }
      ]
    },
    {
      type: 'aws_s3',
      label: 'AWS S3',
      icon: 'cloud_upload',
      description: 'Pull logs from S3 buckets',
      configFields: [
        { key: 'aws_access_key', label: 'AWS Access Key', type: 'text', required: true },
        { key: 'aws_secret_key', label: 'AWS Secret Key', type: 'password', required: true },
        { key: 'bucket', label: 'Bucket Name', type: 'text', required: true },
        { key: 'prefix', label: 'Prefix', type: 'text', placeholder: 'logs/' },
        { key: 'region', label: 'Region', type: 'text', placeholder: 'us-east-1' }
      ]
    },
    {
      type: 'beats',
      label: 'Elastic Beats',
      icon: 'sensors',
      description: 'Receive data from Filebeat, Winlogbeat, etc.',
      configFields: [
        { key: 'port', label: 'Port', type: 'number', required: true, placeholder: '5044' },
        { key: 'ssl_enabled', label: 'SSL Enabled', type: 'select', options: [
          { value: 'true', label: 'Yes' }, { value: 'false', label: 'No' }
        ]}
      ]
    },
    {
      type: 'kafka',
      label: 'Apache Kafka',
      icon: 'stream',
      description: 'Consume from Kafka topics',
      configFields: [
        { key: 'bootstrap_servers', label: 'Bootstrap Servers', type: 'text', required: true, placeholder: 'localhost:9092' },
        { key: 'topics', label: 'Topics', type: 'textarea', required: true, placeholder: 'logs, events' },
        { key: 'group_id', label: 'Consumer Group ID', type: 'text', required: true }
      ]
    },
    {
      type: 'webhook',
      label: 'Webhook',
      icon: 'webhook',
      description: 'Receive data via HTTP webhooks',
      configFields: [
        { key: 'path', label: 'Endpoint Path', type: 'text', required: true, placeholder: '/webhook/alerts' },
        { key: 'auth_token', label: 'Auth Token', type: 'password' },
        { key: 'content_type', label: 'Content Type', type: 'select', options: [
          { value: 'json', label: 'JSON' }, { value: 'text', label: 'Plain Text' }
        ]}
      ]
    },
    {
      type: 'api_polling',
      label: 'API Polling',
      icon: 'sync',
      description: 'Poll external APIs periodically',
      configFields: [
        { key: 'url', label: 'API URL', type: 'text', required: true, placeholder: 'https://api.example.com/logs' },
        { key: 'method', label: 'HTTP Method', type: 'select', options: [
          { value: 'GET', label: 'GET' }, { value: 'POST', label: 'POST' }
        ]},
        { key: 'headers', label: 'Headers (JSON)', type: 'textarea', placeholder: '{"Authorization": "Bearer token"}' },
        { key: 'auth_type', label: 'Auth Type', type: 'select', options: [
          { value: 'none', label: 'None' }, { value: 'basic', label: 'Basic' }, { value: 'bearer', label: 'Bearer Token' }, { value: 'api_key', label: 'API Key' }
        ]}
      ]
    },
    {
      type: 'file_upload',
      label: 'File Upload',
      icon: 'upload_file',
      description: 'Manual file upload endpoint',
      configFields: [
        { key: 'allowed_extensions', label: 'Allowed Extensions', type: 'text', placeholder: '.log, .csv, .json' },
        { key: 'max_file_size_mb', label: 'Max File Size (MB)', type: 'number', placeholder: '100' }
      ]
    },
    {
      type: 'custom',
      label: 'Custom',
      icon: 'extension',
      description: 'Custom connector with manual configuration',
      configFields: [
        { key: 'custom_config', label: 'Custom Configuration (JSON)', type: 'textarea', placeholder: '{}' }
      ]
    }
  ];

  constructor(
    public dialogRef: MatDialogRef<ConnectorDialogComponent>,
    @Inject(MAT_DIALOG_DATA) public data: DialogData,
    private connectorsService: ConnectorsService,
    private snackBar: MatSnackBar
  ) {}

  ngOnInit(): void {
    if (this.data.mode === 'edit' && this.data.connector) {
      const connector = this.data.connector;
      const typeInfo = this.connectorTypes.find(t => t.type === connector.connector_type);
      this.selectedType.set(typeInfo || null);

      this.formData = {
        name: connector.name,
        description: connector.description || '',
        target_index: connector.target_index || '',
        data_type: connector.data_type || '',
        polling_interval: connector.polling_interval || 60
      };

      this.configValues = { ...connector.config };
      this.tagsList.set(Object.entries(connector.tags || {}).map(([key, value]) => ({ key, value })));
    }
  }

  selectType(typeInfo: ConnectorTypeInfo): void {
    this.selectedType.set(typeInfo);
    this.formData.connector_type = typeInfo.type;
  }

  clearType(): void {
    this.selectedType.set(null);
    this.configValues = {};
  }

  addTag(): void {
    if (this.newTagKey && this.newTagValue) {
      this.tagsList.update(tags => [...tags, { key: this.newTagKey, value: this.newTagValue }]);
      this.newTagKey = '';
      this.newTagValue = '';
    }
  }

  removeTag(key: string): void {
    this.tagsList.update(tags => tags.filter(t => t.key !== key));
  }

  isValid(): boolean {
    return !!this.formData.name && !!this.selectedType();
  }

  close(): void {
    this.dialogRef.close();
  }

  save(): void {
    if (!this.isValid()) return;

    this.saving.set(true);

    const tags: Record<string, string> = {};
    for (const tag of this.tagsList()) {
      tags[tag.key] = tag.value;
    }

    const connectorData: ConnectorCreate = {
      name: this.formData.name!,
      description: this.formData.description,
      connector_type: this.selectedType()!.type,
      config: this.configValues,
      target_index: this.formData.target_index,
      data_type: this.formData.data_type,
      polling_interval: this.formData.polling_interval,
      tags
    };

    const request = this.data.mode === 'create'
      ? this.connectorsService.create(connectorData)
      : this.connectorsService.update(this.data.connector!.id, connectorData);

    request.subscribe({
      next: (result) => {
        this.saving.set(false);
        this.snackBar.open(
          this.data.mode === 'create' ? 'Connector created' : 'Connector updated',
          'OK',
          { duration: 3000 }
        );
        this.dialogRef.close(result);
      },
      error: (err) => {
        this.saving.set(false);
        this.snackBar.open(
          'Failed to save connector: ' + (err.error?.detail || 'Unknown error'),
          'Dismiss',
          { duration: 5000 }
        );
      }
    });
  }
}
