import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatCardModule } from '@angular/material/card';
import { MatIconModule } from '@angular/material/icon';
import { MatButtonModule } from '@angular/material/button';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatChipsModule } from '@angular/material/chips';
import { MatDialogModule, MatDialog } from '@angular/material/dialog';

interface Technique {
  id: string;
  name: string;
  description: string;
  tactics: string[];
  detection_count: number;
  case_count: number;
}

interface Tactic {
  id: string;
  name: string;
  shortName: string;
  description: string;
  techniques: Technique[];
}

@Component({
  selector: 'app-mitre',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatCardModule,
    MatIconModule,
    MatButtonModule,
    MatTooltipModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    MatProgressSpinnerModule,
    MatChipsModule,
    MatDialogModule
  ],
  template: `
    <div class="mitre">
      <!-- Header -->
      <div class="page-header">
        <div class="header-content">
          <h1>MITRE ATT&CK Framework</h1>
          <p class="subtitle">Visualize adversary tactics and techniques mapped to your detections and incidents</p>
        </div>
        <div class="header-actions">
          <mat-form-field appearance="outline" class="search-field">
            <mat-label>Search techniques</mat-label>
            <mat-icon matPrefix>search</mat-icon>
            <input matInput [(ngModel)]="searchQuery" (keyup)="filterTechniques()" placeholder="e.g., T1059 or PowerShell">
          </mat-form-field>
        </div>
      </div>

      <!-- Legend -->
      <div class="legend">
        <span class="legend-title">Coverage:</span>
        <div class="legend-item">
          <div class="legend-color high"></div>
          <span>High (3+ detections)</span>
        </div>
        <div class="legend-item">
          <div class="legend-color medium"></div>
          <span>Medium (1-2 detections)</span>
        </div>
        <div class="legend-item">
          <div class="legend-color low"></div>
          <span>No detections</span>
        </div>
        <div class="legend-item">
          <div class="legend-color active"></div>
          <span>Active incidents</span>
        </div>
      </div>

      <!-- Matrix Grid -->
      @if (isLoading()) {
        <div class="loading">
          <mat-spinner diameter="40"></mat-spinner>
        </div>
      } @else {
        <div class="matrix-container">
          <div class="matrix-scroll">
            <div class="matrix">
              @for (tactic of tactics(); track tactic.id) {
                <div class="tactic-column">
                  <div class="tactic-header" [matTooltip]="tactic.description">
                    <span class="tactic-name">{{ tactic.shortName }}</span>
                    <span class="technique-count">{{ getTacticTechniqueCount(tactic) }}</span>
                  </div>
                  <div class="techniques-list">
                    @for (technique of getFilteredTechniques(tactic); track technique.id) {
                      <div class="technique-cell"
                           [class.has-detections]="technique.detection_count > 0"
                           [class.high-coverage]="technique.detection_count >= 3"
                           [class.medium-coverage]="technique.detection_count > 0 && technique.detection_count < 3"
                           [class.has-incidents]="technique.case_count > 0"
                           [class.highlighted]="isHighlighted(technique)"
                           (click)="selectTechnique(technique)"
                           [matTooltip]="getTechniqueTooltip(technique)">
                        <span class="technique-id">{{ technique.id }}</span>
                        <span class="technique-name">{{ technique.name }}</span>
                        @if (technique.case_count > 0) {
                          <span class="incident-badge">{{ technique.case_count }}</span>
                        }
                      </div>
                    }
                  </div>
                </div>
              }
            </div>
          </div>
        </div>
      }

      <!-- Selected Technique Detail -->
      @if (selectedTechnique()) {
        <mat-card class="technique-detail">
          <mat-card-header>
            <mat-icon mat-card-avatar>security</mat-icon>
            <mat-card-title>{{ selectedTechnique()!.id }}: {{ selectedTechnique()!.name }}</mat-card-title>
            <mat-card-subtitle>
              Tactics: {{ selectedTechnique()!.tactics.join(', ') }}
            </mat-card-subtitle>
          </mat-card-header>
          <mat-card-content>
            <p class="technique-description">{{ selectedTechnique()!.description }}</p>

            <div class="technique-stats">
              <div class="stat-box">
                <span class="stat-value">{{ selectedTechnique()!.detection_count }}</span>
                <span class="stat-label">Detection Rules</span>
              </div>
              <div class="stat-box">
                <span class="stat-value">{{ selectedTechnique()!.case_count }}</span>
                <span class="stat-label">Related Incidents</span>
              </div>
            </div>
          </mat-card-content>
          <mat-card-actions align="end">
            <button mat-button (click)="viewDetections(selectedTechnique()!)">
              <mat-icon>rule</mat-icon>
              View Detections
            </button>
            <button mat-button (click)="viewIncidents(selectedTechnique()!)">
              <mat-icon>warning_amber</mat-icon>
              View Incidents
            </button>
            <button mat-button (click)="huntForTechnique(selectedTechnique()!)">
              <mat-icon>manage_search</mat-icon>
              Hunt
            </button>
            <a mat-button [href]="getMitreUrl(selectedTechnique()!)" target="_blank" color="primary">
              <mat-icon>open_in_new</mat-icon>
              MITRE ATT&CK
            </a>
          </mat-card-actions>
        </mat-card>
      }

      <!-- Coverage Stats -->
      <div class="coverage-stats">
        <mat-card class="coverage-card">
          <h3>Coverage Summary</h3>
          <div class="coverage-grid">
            <div class="coverage-item">
              <span class="coverage-value">{{ totalTechniques() }}</span>
              <span class="coverage-label">Total Techniques</span>
            </div>
            <div class="coverage-item">
              <span class="coverage-value">{{ coveredTechniques() }}</span>
              <span class="coverage-label">With Detections</span>
            </div>
            <div class="coverage-item">
              <span class="coverage-value">{{ coveragePercent() }}%</span>
              <span class="coverage-label">Coverage</span>
            </div>
            <div class="coverage-item">
              <span class="coverage-value">{{ techniquesWithIncidents() }}</span>
              <span class="coverage-label">With Active Incidents</span>
            </div>
          </div>
        </mat-card>
      </div>
    </div>
  `,
  styles: [`
    .mitre {
      max-width: 100%;
    }

    .page-header {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      margin-bottom: 16px;
      flex-wrap: wrap;
      gap: 16px;
    }

    .header-content h1 {
      font-size: 24px;
      font-weight: 600;
      margin: 0 0 4px 0;
    }

    .subtitle {
      color: var(--text-secondary);
      margin: 0;
    }

    .search-field {
      width: 300px;
    }

    /* Legend */
    .legend {
      display: flex;
      align-items: center;
      gap: 24px;
      margin-bottom: 16px;
      padding: 12px 16px;
      background: var(--bg-card);
      border: 1px solid var(--border-color);
      border-radius: 8px;
      flex-wrap: wrap;
    }

    .legend-title {
      font-weight: 500;
      color: var(--text-primary);
    }

    .legend-item {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 13px;
      color: var(--text-secondary);
    }

    .legend-color {
      width: 16px;
      height: 16px;
      border-radius: 4px;

      &.high { background: var(--success); }
      &.medium { background: var(--warning); }
      &.low { background: var(--bg-tertiary); }
      &.active { background: var(--danger); }
    }

    .loading {
      display: flex;
      justify-content: center;
      padding: 48px;
    }

    /* Matrix Container */
    .matrix-container {
      background: var(--bg-card);
      border: 1px solid var(--border-color);
      border-radius: 8px;
      padding: 16px;
      margin-bottom: 24px;
    }

    .matrix-scroll {
      overflow-x: auto;
    }

    .matrix {
      display: flex;
      gap: 2px;
      min-width: max-content;
    }

    .tactic-column {
      width: 180px;
      flex-shrink: 0;
    }

    .tactic-header {
      background: var(--bg-tertiary);
      padding: 12px 8px;
      text-align: center;
      border-radius: 4px 4px 0 0;
      margin-bottom: 2px;
      cursor: help;
    }

    .tactic-name {
      display: block;
      font-size: 12px;
      font-weight: 600;
      color: var(--text-primary);
      text-transform: uppercase;
    }

    .technique-count {
      display: block;
      font-size: 11px;
      color: var(--text-muted);
      margin-top: 2px;
    }

    .techniques-list {
      display: flex;
      flex-direction: column;
      gap: 2px;
    }

    .technique-cell {
      background: var(--bg-tertiary);
      padding: 8px;
      border-radius: 4px;
      cursor: pointer;
      transition: all 0.15s ease;
      position: relative;
      border-left: 3px solid transparent;

      &:hover {
        background: rgba(88, 166, 255, 0.2);
      }

      &.highlighted {
        background: rgba(88, 166, 255, 0.3);
        border-left-color: var(--accent);
      }

      &.high-coverage {
        background: rgba(63, 185, 80, 0.2);
        border-left-color: var(--success);
      }

      &.medium-coverage {
        background: rgba(210, 153, 34, 0.2);
        border-left-color: var(--warning);
      }

      &.has-incidents {
        &::after {
          content: '';
          position: absolute;
          top: 4px;
          right: 4px;
          width: 8px;
          height: 8px;
          border-radius: 50%;
          background: var(--danger);
        }
      }
    }

    .technique-id {
      display: block;
      font-size: 10px;
      font-family: monospace;
      color: var(--accent);
      margin-bottom: 2px;
    }

    .technique-name {
      display: block;
      font-size: 11px;
      color: var(--text-primary);
      line-height: 1.3;
    }

    .incident-badge {
      position: absolute;
      top: 4px;
      right: 16px;
      background: var(--danger);
      color: white;
      font-size: 10px;
      padding: 0 4px;
      border-radius: 4px;
      font-weight: 600;
    }

    /* Technique Detail */
    .technique-detail {
      background: var(--bg-card);
      border: 1px solid var(--border-color);
      margin-bottom: 24px;
    }

    .technique-description {
      color: var(--text-secondary);
      line-height: 1.6;
      margin-bottom: 16px;
    }

    .technique-stats {
      display: flex;
      gap: 24px;
    }

    .stat-box {
      display: flex;
      flex-direction: column;
      padding: 16px 24px;
      background: var(--bg-tertiary);
      border-radius: 8px;
    }

    .stat-value {
      font-size: 24px;
      font-weight: 700;
      color: var(--text-primary);
    }

    .stat-label {
      font-size: 12px;
      color: var(--text-secondary);
    }

    /* Coverage Stats */
    .coverage-stats {
      margin-bottom: 24px;
    }

    .coverage-card {
      background: var(--bg-card);
      border: 1px solid var(--border-color);
      padding: 20px;

      h3 {
        margin: 0 0 16px 0;
        font-size: 16px;
        font-weight: 600;
      }
    }

    .coverage-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
      gap: 16px;
    }

    .coverage-item {
      display: flex;
      flex-direction: column;
      align-items: center;
      padding: 16px;
      background: var(--bg-tertiary);
      border-radius: 8px;
    }

    .coverage-value {
      font-size: 28px;
      font-weight: 700;
      color: var(--accent);
    }

    .coverage-label {
      font-size: 12px;
      color: var(--text-secondary);
      text-align: center;
    }
  `]
})
export class MitreComponent implements OnInit {
  searchQuery = '';
  isLoading = signal(true);
  tactics = signal<Tactic[]>([]);
  selectedTechnique = signal<Technique | null>(null);

  totalTechniques = signal(0);
  coveredTechniques = signal(0);
  coveragePercent = signal(0);
  techniquesWithIncidents = signal(0);

  constructor(private dialog: MatDialog) {}

  ngOnInit(): void {
    this.loadMitreData();
  }

  loadMitreData(): void {
    // Mock MITRE ATT&CK data - in production this would come from API
    const mockTactics: Tactic[] = [
      {
        id: 'TA0001',
        name: 'Initial Access',
        shortName: 'Initial Access',
        description: 'The adversary is trying to get into your network.',
        techniques: [
          { id: 'T1566', name: 'Phishing', description: 'Adversaries may send phishing messages to gain access to victim systems.', tactics: ['Initial Access'], detection_count: 5, case_count: 2 },
          { id: 'T1566.001', name: 'Spearphishing Attachment', description: 'Adversaries may send spearphishing emails with a malicious attachment.', tactics: ['Initial Access'], detection_count: 3, case_count: 1 },
          { id: 'T1190', name: 'Exploit Public-Facing App', description: 'Adversaries may attempt to exploit a weakness in an Internet-facing host.', tactics: ['Initial Access'], detection_count: 2, case_count: 0 },
          { id: 'T1133', name: 'External Remote Services', description: 'Adversaries may leverage external-facing remote services to initially access a network.', tactics: ['Initial Access'], detection_count: 1, case_count: 0 }
        ]
      },
      {
        id: 'TA0002',
        name: 'Execution',
        shortName: 'Execution',
        description: 'The adversary is trying to run malicious code.',
        techniques: [
          { id: 'T1059', name: 'Command and Scripting Interpreter', description: 'Adversaries may abuse command and script interpreters to execute commands.', tactics: ['Execution'], detection_count: 8, case_count: 3 },
          { id: 'T1059.001', name: 'PowerShell', description: 'Adversaries may abuse PowerShell commands and scripts for execution.', tactics: ['Execution'], detection_count: 6, case_count: 2 },
          { id: 'T1059.003', name: 'Windows Command Shell', description: 'Adversaries may abuse the Windows command shell for execution.', tactics: ['Execution'], detection_count: 4, case_count: 1 },
          { id: 'T1047', name: 'Windows Management Instrumentation', description: 'Adversaries may abuse WMI to execute malicious commands.', tactics: ['Execution'], detection_count: 3, case_count: 0 },
          { id: 'T1053', name: 'Scheduled Task/Job', description: 'Adversaries may abuse task scheduling functionality.', tactics: ['Execution', 'Persistence', 'Privilege Escalation'], detection_count: 2, case_count: 0 }
        ]
      },
      {
        id: 'TA0003',
        name: 'Persistence',
        shortName: 'Persistence',
        description: 'The adversary is trying to maintain their foothold.',
        techniques: [
          { id: 'T1547', name: 'Boot or Logon Autostart Execution', description: 'Adversaries may configure system settings to automatically execute a program.', tactics: ['Persistence', 'Privilege Escalation'], detection_count: 4, case_count: 1 },
          { id: 'T1547.001', name: 'Registry Run Keys', description: 'Adversaries may achieve persistence by adding registry run keys.', tactics: ['Persistence', 'Privilege Escalation'], detection_count: 3, case_count: 1 },
          { id: 'T1543', name: 'Create or Modify System Process', description: 'Adversaries may create or modify system-level processes for persistence.', tactics: ['Persistence', 'Privilege Escalation'], detection_count: 2, case_count: 0 },
          { id: 'T1136', name: 'Create Account', description: 'Adversaries may create an account to maintain access.', tactics: ['Persistence'], detection_count: 1, case_count: 0 }
        ]
      },
      {
        id: 'TA0004',
        name: 'Privilege Escalation',
        shortName: 'Priv Escalation',
        description: 'The adversary is trying to gain higher-level permissions.',
        techniques: [
          { id: 'T1055', name: 'Process Injection', description: 'Adversaries may inject code into processes to evade process-based defenses.', tactics: ['Privilege Escalation', 'Defense Evasion'], detection_count: 3, case_count: 0 },
          { id: 'T1068', name: 'Exploitation for Privilege Escalation', description: 'Adversaries may exploit software vulnerabilities to elevate privileges.', tactics: ['Privilege Escalation'], detection_count: 1, case_count: 0 },
          { id: 'T1078', name: 'Valid Accounts', description: 'Adversaries may obtain and abuse credentials of existing accounts.', tactics: ['Defense Evasion', 'Persistence', 'Privilege Escalation', 'Initial Access'], detection_count: 2, case_count: 1 }
        ]
      },
      {
        id: 'TA0005',
        name: 'Defense Evasion',
        shortName: 'Defense Evasion',
        description: 'The adversary is trying to avoid being detected.',
        techniques: [
          { id: 'T1027', name: 'Obfuscated Files or Information', description: 'Adversaries may attempt to make payloads difficult to discover.', tactics: ['Defense Evasion'], detection_count: 4, case_count: 1 },
          { id: 'T1070', name: 'Indicator Removal', description: 'Adversaries may delete or modify artifacts to remove evidence.', tactics: ['Defense Evasion'], detection_count: 2, case_count: 0 },
          { id: 'T1562', name: 'Impair Defenses', description: 'Adversaries may modify security tools to avoid detection.', tactics: ['Defense Evasion'], detection_count: 3, case_count: 0 },
          { id: 'T1036', name: 'Masquerading', description: 'Adversaries may attempt to manipulate features of artifacts.', tactics: ['Defense Evasion'], detection_count: 2, case_count: 0 }
        ]
      },
      {
        id: 'TA0006',
        name: 'Credential Access',
        shortName: 'Credential Access',
        description: 'The adversary is trying to steal account names and passwords.',
        techniques: [
          { id: 'T1003', name: 'OS Credential Dumping', description: 'Adversaries may attempt to dump credentials to obtain account login information.', tactics: ['Credential Access'], detection_count: 5, case_count: 2 },
          { id: 'T1003.001', name: 'LSASS Memory', description: 'Adversaries may attempt to access credential material from LSASS memory.', tactics: ['Credential Access'], detection_count: 4, case_count: 1 },
          { id: 'T1110', name: 'Brute Force', description: 'Adversaries may use brute force techniques to gain access to accounts.', tactics: ['Credential Access'], detection_count: 3, case_count: 0 },
          { id: 'T1555', name: 'Credentials from Password Stores', description: 'Adversaries may search for common password storage locations.', tactics: ['Credential Access'], detection_count: 2, case_count: 0 }
        ]
      },
      {
        id: 'TA0007',
        name: 'Discovery',
        shortName: 'Discovery',
        description: 'The adversary is trying to figure out your environment.',
        techniques: [
          { id: 'T1087', name: 'Account Discovery', description: 'Adversaries may attempt to get a listing of accounts on a system.', tactics: ['Discovery'], detection_count: 2, case_count: 0 },
          { id: 'T1082', name: 'System Information Discovery', description: 'Adversaries may attempt to get detailed information about the OS.', tactics: ['Discovery'], detection_count: 1, case_count: 0 },
          { id: 'T1083', name: 'File and Directory Discovery', description: 'Adversaries may enumerate files and directories.', tactics: ['Discovery'], detection_count: 1, case_count: 0 }
        ]
      },
      {
        id: 'TA0008',
        name: 'Lateral Movement',
        shortName: 'Lateral Movement',
        description: 'The adversary is trying to move through your environment.',
        techniques: [
          { id: 'T1021', name: 'Remote Services', description: 'Adversaries may use valid accounts to log into remote services.', tactics: ['Lateral Movement'], detection_count: 3, case_count: 1 },
          { id: 'T1021.001', name: 'Remote Desktop Protocol', description: 'Adversaries may use RDP to log into computers remotely.', tactics: ['Lateral Movement'], detection_count: 2, case_count: 0 },
          { id: 'T1570', name: 'Lateral Tool Transfer', description: 'Adversaries may transfer tools between systems in a compromised environment.', tactics: ['Lateral Movement'], detection_count: 1, case_count: 0 }
        ]
      },
      {
        id: 'TA0009',
        name: 'Collection',
        shortName: 'Collection',
        description: 'The adversary is trying to gather data of interest.',
        techniques: [
          { id: 'T1560', name: 'Archive Collected Data', description: 'Adversaries may compress and/or encrypt collected data prior to exfil.', tactics: ['Collection'], detection_count: 2, case_count: 0 },
          { id: 'T1005', name: 'Data from Local System', description: 'Adversaries may search local system sources for data of interest.', tactics: ['Collection'], detection_count: 1, case_count: 0 }
        ]
      },
      {
        id: 'TA0011',
        name: 'Command and Control',
        shortName: 'Command & Control',
        description: 'The adversary is trying to communicate with compromised systems.',
        techniques: [
          { id: 'T1071', name: 'Application Layer Protocol', description: 'Adversaries may communicate using OSI application layer protocols.', tactics: ['Command and Control'], detection_count: 4, case_count: 1 },
          { id: 'T1071.001', name: 'Web Protocols', description: 'Adversaries may communicate using HTTP/HTTPS to blend in with network traffic.', tactics: ['Command and Control'], detection_count: 3, case_count: 1 },
          { id: 'T1105', name: 'Ingress Tool Transfer', description: 'Adversaries may transfer tools or other files from an external system.', tactics: ['Command and Control'], detection_count: 2, case_count: 0 }
        ]
      },
      {
        id: 'TA0010',
        name: 'Exfiltration',
        shortName: 'Exfiltration',
        description: 'The adversary is trying to steal data.',
        techniques: [
          { id: 'T1041', name: 'Exfiltration Over C2 Channel', description: 'Adversaries may steal data by exfiltrating it over an existing C2 channel.', tactics: ['Exfiltration'], detection_count: 2, case_count: 0 },
          { id: 'T1048', name: 'Exfiltration Over Alternative Protocol', description: 'Adversaries may steal data by exfiltrating via a different protocol.', tactics: ['Exfiltration'], detection_count: 1, case_count: 0 }
        ]
      },
      {
        id: 'TA0040',
        name: 'Impact',
        shortName: 'Impact',
        description: 'The adversary is trying to manipulate, interrupt, or destroy systems.',
        techniques: [
          { id: 'T1486', name: 'Data Encrypted for Impact', description: 'Adversaries may encrypt data to interrupt availability (ransomware).', tactics: ['Impact'], detection_count: 3, case_count: 0 },
          { id: 'T1489', name: 'Service Stop', description: 'Adversaries may stop or disable services on a system.', tactics: ['Impact'], detection_count: 1, case_count: 0 },
          { id: 'T1490', name: 'Inhibit System Recovery', description: 'Adversaries may delete or remove data to inhibit system recovery.', tactics: ['Impact'], detection_count: 2, case_count: 0 }
        ]
      }
    ];

    setTimeout(() => {
      this.tactics.set(mockTactics);
      this.calculateStats();
      this.isLoading.set(false);
    }, 500);
  }

  calculateStats(): void {
    const allTechniques = this.tactics().flatMap(t => t.techniques);
    const uniqueTechniques = [...new Map(allTechniques.map(t => [t.id, t])).values()];

    this.totalTechniques.set(uniqueTechniques.length);
    this.coveredTechniques.set(uniqueTechniques.filter(t => t.detection_count > 0).length);
    this.coveragePercent.set(Math.round((this.coveredTechniques() / this.totalTechniques()) * 100));
    this.techniquesWithIncidents.set(uniqueTechniques.filter(t => t.case_count > 0).length);
  }

  filterTechniques(): void {
    // Filtering is handled in getFilteredTechniques
  }

  getFilteredTechniques(tactic: Tactic): Technique[] {
    if (!this.searchQuery) return tactic.techniques;

    const query = this.searchQuery.toLowerCase();
    return tactic.techniques.filter(t =>
      t.id.toLowerCase().includes(query) ||
      t.name.toLowerCase().includes(query)
    );
  }

  getTacticTechniqueCount(tactic: Tactic): string {
    const filtered = this.getFilteredTechniques(tactic);
    return `${filtered.length} techniques`;
  }

  isHighlighted(technique: Technique): boolean {
    return this.selectedTechnique()?.id === technique.id;
  }

  getTechniqueTooltip(technique: Technique): string {
    return `${technique.id}: ${technique.name}\nDetections: ${technique.detection_count}\nIncidents: ${technique.case_count}`;
  }

  selectTechnique(technique: Technique): void {
    this.selectedTechnique.set(technique);
  }

  getMitreUrl(technique: Technique): string {
    const baseId = technique.id.split('.')[0];
    return `https://attack.mitre.org/techniques/${baseId}/`;
  }

  viewDetections(technique: Technique): void {
    window.location.href = `/analytics?technique=${technique.id}`;
  }

  viewIncidents(technique: Technique): void {
    window.location.href = `/incidents?mitre=${technique.id}`;
  }

  huntForTechnique(technique: Technique): void {
    window.location.href = `/hunting?technique=${technique.id}`;
  }
}
