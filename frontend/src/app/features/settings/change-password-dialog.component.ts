import { Component, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatButtonModule } from '@angular/material/button';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatIconModule } from '@angular/material/icon';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { environment } from '../../../environments/environment';

@Component({
  selector: 'app-change-password-dialog',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatDialogModule,
    MatButtonModule,
    MatFormFieldModule,
    MatInputModule,
    MatIconModule,
    MatSnackBarModule,
    MatProgressSpinnerModule
  ],
  template: `
    <h2 mat-dialog-title>
      <mat-icon>lock</mat-icon>
      Change Password
    </h2>

    <mat-dialog-content>
      <form (ngSubmit)="submit()">
        <mat-form-field appearance="outline" class="full-width">
          <mat-label>Current Password</mat-label>
          <input matInput
                 [type]="showCurrentPassword() ? 'text' : 'password'"
                 [(ngModel)]="currentPassword"
                 name="currentPassword"
                 required>
          <button mat-icon-button matSuffix type="button"
                  (click)="showCurrentPassword.set(!showCurrentPassword())">
            <mat-icon>{{ showCurrentPassword() ? 'visibility_off' : 'visibility' }}</mat-icon>
          </button>
        </mat-form-field>

        <mat-form-field appearance="outline" class="full-width">
          <mat-label>New Password</mat-label>
          <input matInput
                 [type]="showNewPassword() ? 'text' : 'password'"
                 [(ngModel)]="newPassword"
                 name="newPassword"
                 required
                 minlength="8">
          <button mat-icon-button matSuffix type="button"
                  (click)="showNewPassword.set(!showNewPassword())">
            <mat-icon>{{ showNewPassword() ? 'visibility_off' : 'visibility' }}</mat-icon>
          </button>
          <mat-hint>Minimum 8 characters</mat-hint>
        </mat-form-field>

        <mat-form-field appearance="outline" class="full-width">
          <mat-label>Confirm New Password</mat-label>
          <input matInput
                 [type]="showConfirmPassword() ? 'text' : 'password'"
                 [(ngModel)]="confirmPassword"
                 name="confirmPassword"
                 required>
          <button mat-icon-button matSuffix type="button"
                  (click)="showConfirmPassword.set(!showConfirmPassword())">
            <mat-icon>{{ showConfirmPassword() ? 'visibility_off' : 'visibility' }}</mat-icon>
          </button>
          @if (confirmPassword && newPassword !== confirmPassword) {
            <mat-error>Passwords do not match</mat-error>
          }
        </mat-form-field>

        @if (error()) {
          <div class="error-message">
            <mat-icon>error</mat-icon>
            {{ error() }}
          </div>
        }
      </form>
    </mat-dialog-content>

    <mat-dialog-actions align="end">
      <button mat-stroked-button (click)="cancel()" [disabled]="isSubmitting()">Cancel</button>
      <button mat-flat-button color="accent"
              [disabled]="!isValid() || isSubmitting()"
              (click)="submit()">
        @if (isSubmitting()) {
          <mat-spinner diameter="18"></mat-spinner>
        } @else {
          <mat-icon>check</mat-icon>
        }
        Change Password
      </button>
    </mat-dialog-actions>
  `,
  styles: [`
    mat-dialog-title {
      display: flex;
      align-items: center;
      gap: 12px;

      mat-icon {
        font-size: 24px;
        width: 24px;
        height: 24px;
        color: var(--accent);
      }
    }

    .full-width {
      width: 100%;
      margin-bottom: 8px;
    }

    mat-dialog-content {
      min-width: 350px;
    }

    .error-message {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 12px 16px;
      background: rgba(var(--danger-rgb), 0.15);
      border: 1px solid var(--danger);
      border-radius: 8px;
      color: var(--danger);
      font-size: 13px;
      margin-top: 8px;

      mat-icon {
        flex-shrink: 0;
        font-size: 18px;
        width: 18px;
        height: 18px;
      }
    }

    mat-dialog-actions button mat-spinner {
      display: inline-block;
      margin-right: 8px;
    }
  `]
})
export class ChangePasswordDialogComponent {
  currentPassword = '';
  newPassword = '';
  confirmPassword = '';

  showCurrentPassword = signal(false);
  showNewPassword = signal(false);
  showConfirmPassword = signal(false);

  isSubmitting = signal(false);
  error = signal<string | null>(null);

  constructor(
    private dialogRef: MatDialogRef<ChangePasswordDialogComponent>,
    private http: HttpClient,
    private snackBar: MatSnackBar
  ) {}

  isValid(): boolean {
    return !!(
      this.currentPassword &&
      this.newPassword &&
      this.newPassword.length >= 8 &&
      this.newPassword === this.confirmPassword
    );
  }

  cancel(): void {
    this.dialogRef.close(false);
  }

  submit(): void {
    if (!this.isValid() || this.isSubmitting()) return;

    this.isSubmitting.set(true);
    this.error.set(null);

    this.http.put(`${environment.apiUrl}/users/me/password`, {
      current_password: this.currentPassword,
      new_password: this.newPassword
    }).subscribe({
      next: () => {
        this.isSubmitting.set(false);
        this.snackBar.open('Password changed successfully', 'Dismiss', { duration: 3000 });
        this.dialogRef.close(true);
      },
      error: (err) => {
        this.isSubmitting.set(false);
        const message = err.error?.detail || err.message || 'Failed to change password';
        this.error.set(message);
      }
    });
  }
}
