import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSlideToggleModule } from '@angular/material/slide-toggle';
import { MatDividerModule } from '@angular/material/divider';
import { AuthService } from '../../core/auth/auth.service';

@Component({
  selector: 'app-settings',
  standalone: true,
  imports: [
    CommonModule,
    MatCardModule,
    MatButtonModule,
    MatIconModule,
    MatFormFieldModule,
    MatInputModule,
    MatSlideToggleModule,
    MatDividerModule
  ],
  template: `
    <div class="settings">
      <h1>Settings</h1>

      <!-- Profile -->
      <mat-card class="settings-card">
        <mat-card-header>
          <mat-icon mat-card-avatar>person</mat-icon>
          <mat-card-title>Profile</mat-card-title>
          <mat-card-subtitle>Manage your account settings</mat-card-subtitle>
        </mat-card-header>
        <mat-card-content>
          <div class="profile-info">
            <div class="info-row">
              <span class="label">Username</span>
              <span class="value">{{ user()?.username }}</span>
            </div>
            <div class="info-row">
              <span class="label">Display Name</span>
              <span class="value">{{ user()?.display_name || 'Not set' }}</span>
            </div>
            <div class="info-row">
              <span class="label">Email</span>
              <span class="value">{{ user()?.email || 'Not set' }}</span>
            </div>
            <div class="info-row">
              <span class="label">Role</span>
              <span class="value">{{ user()?.is_admin ? 'Administrator' : 'Analyst' }}</span>
            </div>
            <div class="info-row">
              <span class="label">Last Login</span>
              <span class="value">{{ user()?.last_login | date:'medium' }}</span>
            </div>
          </div>
        </mat-card-content>
        <mat-card-actions>
          <button mat-stroked-button>Change Password</button>
        </mat-card-actions>
      </mat-card>

      <!-- Preferences -->
      <mat-card class="settings-card">
        <mat-card-header>
          <mat-icon mat-card-avatar>tune</mat-icon>
          <mat-card-title>Preferences</mat-card-title>
          <mat-card-subtitle>Customize your experience</mat-card-subtitle>
        </mat-card-header>
        <mat-card-content>
          <div class="preference-row">
            <div class="preference-info">
              <span class="preference-label">Desktop Notifications</span>
              <span class="preference-desc">Receive browser notifications for alerts</span>
            </div>
            <mat-slide-toggle></mat-slide-toggle>
          </div>
          <mat-divider></mat-divider>
          <div class="preference-row">
            <div class="preference-info">
              <span class="preference-label">Email Notifications</span>
              <span class="preference-desc">Receive email notifications for case updates</span>
            </div>
            <mat-slide-toggle></mat-slide-toggle>
          </div>
          <mat-divider></mat-divider>
          <div class="preference-row">
            <div class="preference-info">
              <span class="preference-label">Auto-refresh Dashboard</span>
              <span class="preference-desc">Automatically refresh dashboard data</span>
            </div>
            <mat-slide-toggle checked></mat-slide-toggle>
          </div>
        </mat-card-content>
      </mat-card>

      <!-- About -->
      <mat-card class="settings-card">
        <mat-card-header>
          <mat-icon mat-card-avatar>info</mat-icon>
          <mat-card-title>About Eleanor</mat-card-title>
          <mat-card-subtitle>System information</mat-card-subtitle>
        </mat-card-header>
        <mat-card-content>
          <div class="about-info">
            <div class="info-row">
              <span class="label">Version</span>
              <span class="value">1.0.0</span>
            </div>
            <div class="info-row">
              <span class="label">Build</span>
              <span class="value">{{ buildDate }}</span>
            </div>
            <div class="info-row">
              <span class="label">License</span>
              <span class="value">MIT</span>
            </div>
          </div>
          <p class="copyright">
            Eleanor - Digital Forensics & Incident Response Platform<br>
            &copy; 2024 Project Eleanor
          </p>
        </mat-card-content>
      </mat-card>
    </div>
  `,
  styles: [`
    .settings {
      max-width: 800px;
      margin: 0 auto;
    }

    h1 {
      font-size: 24px;
      margin-bottom: 24px;
    }

    .settings-card {
      margin-bottom: 24px;
      background: var(--bg-card);

      mat-card-avatar {
        font-size: 24px;
        width: 40px;
        height: 40px;
        display: flex;
        align-items: center;
        justify-content: center;
        color: var(--accent);
      }
    }

    .profile-info, .about-info {
      display: flex;
      flex-direction: column;
      gap: 4px;
    }

    .info-row {
      display: flex;
      justify-content: space-between;
      padding: 12px 0;
      border-bottom: 1px solid var(--border-color);

      &:last-child {
        border-bottom: none;
      }

      .label {
        color: var(--text-secondary);
      }

      .value {
        font-weight: 500;
      }
    }

    .preference-row {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 16px 0;
    }

    .preference-info {
      display: flex;
      flex-direction: column;
      gap: 4px;
    }

    .preference-label {
      font-weight: 500;
    }

    .preference-desc {
      font-size: 12px;
      color: var(--text-secondary);
    }

    .copyright {
      margin-top: 16px;
      padding-top: 16px;
      border-top: 1px solid var(--border-color);
      font-size: 12px;
      color: var(--text-muted);
      text-align: center;
    }
  `]
})
export class SettingsComponent {
  user = this.authService.user;
  buildDate = new Date().toISOString().split('T')[0];

  constructor(private authService: AuthService) {}
}
