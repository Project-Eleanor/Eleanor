import { Component, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, FormGroup, Validators, ReactiveFormsModule } from '@angular/forms';
import { Router, ActivatedRoute } from '@angular/router';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { AuthService } from './auth.service';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [
    CommonModule,
    ReactiveFormsModule,
    MatCardModule,
    MatFormFieldModule,
    MatInputModule,
    MatButtonModule,
    MatIconModule,
    MatProgressSpinnerModule
  ],
  template: `
    <div class="login-container">
      <div class="background-pattern"></div>
      <div class="login-card">
        <div class="card-accent"></div>
        <div class="logo-section">
          <div class="logo">
            <img src="assets/logo.png" alt="Eleanor" class="logo-img">
          </div>
          <h1 class="logo-text">Eleanor</h1>
          <p class="tagline">Digital Forensics & Incident Response Platform</p>
        </div>

        <form [formGroup]="loginForm" (ngSubmit)="onSubmit()">
          <mat-form-field appearance="outline" class="full-width">
            <mat-label>Username</mat-label>
            <input matInput formControlName="username" autocomplete="username">
            <mat-icon matPrefix>person</mat-icon>
            @if (loginForm.get('username')?.hasError('required') && loginForm.get('username')?.touched) {
              <mat-error>Username is required</mat-error>
            }
          </mat-form-field>

          <mat-form-field appearance="outline" class="full-width">
            <mat-label>Password</mat-label>
            <input matInput
                   [type]="hidePassword() ? 'password' : 'text'"
                   formControlName="password"
                   autocomplete="current-password">
            <mat-icon matPrefix>lock</mat-icon>
            <button mat-icon-button matSuffix type="button" (click)="togglePasswordVisibility()">
              <mat-icon>{{ hidePassword() ? 'visibility_off' : 'visibility' }}</mat-icon>
            </button>
            @if (loginForm.get('password')?.hasError('required') && loginForm.get('password')?.touched) {
              <mat-error>Password is required</mat-error>
            }
          </mat-form-field>

          @if (errorMessage()) {
            <div class="error-message">
              <mat-icon>error</mat-icon>
              <span>{{ errorMessage() }}</span>
            </div>
          }

          <button mat-flat-button
                  color="accent"
                  type="submit"
                  class="login-button"
                  [disabled]="isLoading() || !loginForm.valid">
            @if (isLoading()) {
              <mat-spinner diameter="20"></mat-spinner>
            } @else {
              <span class="button-text">Sign In</span>
              <mat-icon class="button-icon">arrow_forward</mat-icon>
            }
          </button>
        </form>

        <div class="footer">
          <span class="version">v1.0.0</span>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .login-container {
      display: flex;
      align-items: center;
      justify-content: center;
      min-height: 100vh;
      background: radial-gradient(ellipse at 50% 0%, #1a2535 0%, var(--bg-primary) 60%);
      position: relative;
      overflow: hidden;
    }

    /* Subtle animated grid pattern */
    .background-pattern {
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      bottom: 0;
      background-image:
        linear-gradient(rgba(74, 158, 255, 0.03) 1px, transparent 1px),
        linear-gradient(90deg, rgba(74, 158, 255, 0.03) 1px, transparent 1px);
      background-size: 50px 50px;
      animation: gridMove 20s linear infinite;
    }

    @keyframes gridMove {
      0% { transform: translate(0, 0); }
      100% { transform: translate(50px, 50px); }
    }

    .login-card {
      width: 100%;
      max-width: 420px;
      padding: 48px 40px;
      background: rgba(20, 26, 36, 0.8);
      backdrop-filter: blur(20px);
      border: 1px solid var(--border-color);
      border-radius: 16px;
      box-shadow:
        0 8px 32px rgba(0, 0, 0, 0.4),
        0 0 80px rgba(74, 158, 255, 0.05);
      position: relative;
      z-index: 1;
      overflow: hidden;
    }

    /* Top accent line */
    .card-accent {
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      height: 3px;
      background: linear-gradient(90deg, transparent, var(--accent), transparent);
    }

    .logo-section {
      text-align: center;
      margin-bottom: 40px;
    }

    .logo {
      display: flex;
      align-items: center;
      justify-content: center;
      margin-bottom: 16px;
    }

    .logo-img {
      width: 72px;
      height: 72px;
      object-fit: contain;
      filter: drop-shadow(0 4px 20px rgba(74, 158, 255, 0.4));
      animation: float 4s ease-in-out infinite;
    }

    @keyframes float {
      0%, 100% { transform: translateY(0); }
      50% { transform: translateY(-8px); }
    }

    .logo-text {
      font-family: var(--font-display);
      font-size: 36px;
      font-weight: 700;
      margin: 0 0 8px 0;
      background: linear-gradient(135deg, var(--text-primary) 0%, var(--silver) 50%, var(--accent) 100%);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      background-clip: text;
      letter-spacing: -1px;
    }

    .tagline {
      color: var(--text-secondary);
      font-size: 14px;
      margin: 0;
      font-weight: 400;
    }

    .full-width {
      width: 100%;
      margin-bottom: 20px;
    }

    .login-button {
      width: 100%;
      height: 52px;
      font-size: 16px;
      font-weight: 600;
      margin-top: 8px;
      border-radius: 8px;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      position: relative;
      overflow: hidden;
      transition: all 0.3s ease;

      .button-text {
        transition: transform 0.2s ease;
      }

      .button-icon {
        opacity: 0;
        transform: translateX(-10px);
        transition: all 0.2s ease;
      }

      &:not(:disabled):hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 24px rgba(74, 158, 255, 0.3);

        .button-text {
          transform: translateX(-8px);
        }

        .button-icon {
          opacity: 1;
          transform: translateX(0);
        }
      }

      &::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: linear-gradient(
          90deg,
          transparent 0%,
          rgba(255, 255, 255, 0.15) 50%,
          transparent 100%
        );
        background-size: 200% 100%;
        opacity: 0;
        transition: opacity 0.3s ease;
      }

      &:not(:disabled):hover::before {
        opacity: 1;
        animation: shimmer 1.5s ease-in-out infinite;
      }
    }

    @keyframes shimmer {
      0% { background-position: -200% center; }
      100% { background-position: 200% center; }
    }

    .error-message {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 12px 16px;
      background: rgba(248, 81, 73, 0.1);
      border: 1px solid var(--danger);
      border-radius: 8px;
      color: var(--danger);
      margin-bottom: 20px;
      font-size: 14px;

      mat-icon {
        font-size: 20px;
        width: 20px;
        height: 20px;
      }
    }

    .footer {
      text-align: center;
      margin-top: 32px;
      padding-top: 20px;
      border-top: 1px solid var(--border-color);
    }

    .version {
      color: var(--text-muted);
      font-size: 12px;
      font-family: var(--font-mono);
    }

    ::ng-deep .mat-mdc-form-field-icon-prefix {
      color: var(--text-secondary);
      margin-right: 8px;
    }

    ::ng-deep .mat-mdc-text-field-wrapper {
      background: rgba(13, 18, 25, 0.6) !important;
    }
  `]
})
export class LoginComponent {
  loginForm: FormGroup;
  hidePassword = signal(true);
  isLoading = signal(false);
  errorMessage = signal<string | null>(null);

  constructor(
    private fb: FormBuilder,
    private authService: AuthService,
    private router: Router,
    private route: ActivatedRoute
  ) {
    this.loginForm = this.fb.group({
      username: ['', Validators.required],
      password: ['', Validators.required]
    });
  }

  togglePasswordVisibility(): void {
    this.hidePassword.update(v => !v);
  }

  onSubmit(): void {
    if (!this.loginForm.valid) return;

    this.isLoading.set(true);
    this.errorMessage.set(null);

    this.authService.login(this.loginForm.value).subscribe({
      next: () => {
        const returnUrl = this.route.snapshot.queryParams['returnUrl'] || '/';
        this.router.navigateByUrl(returnUrl);
      },
      error: (error) => {
        this.isLoading.set(false);
        if (error.status === 401) {
          this.errorMessage.set('Invalid username or password');
        } else {
          this.errorMessage.set('An error occurred. Please try again.');
        }
      }
    });
  }
}
