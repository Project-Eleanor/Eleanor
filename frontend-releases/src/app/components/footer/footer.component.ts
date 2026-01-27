import { Component } from '@angular/core';

@Component({
  selector: 'app-footer',
  standalone: true,
  template: `
    <footer class="footer">
      <div class="container">
        <div class="footer-content">
          <!-- Brand -->
          <div class="footer-brand">
            <img src="assets/logo.png" alt="Eleanor" class="footer-logo" />
            <span class="footer-title">Eleanor</span>
          </div>

          <!-- Links -->
          <nav class="footer-nav">
            <div class="footer-section">
              <h4>Product</h4>
              <a href="#">Main Application</a>
              <a href="#downloads">Downloads</a>
              <a href="#requirements">Requirements</a>
            </div>

            <div class="footer-section">
              <h4>Resources</h4>
              <a href="#">Documentation</a>
              <a href="#">Installation Guide</a>
              <a href="#">Release Notes</a>
            </div>

            <div class="footer-section">
              <h4>Community</h4>
              <a href="https://github.com/project-eleanor" target="_blank" rel="noopener">
                GitHub
              </a>
              <a href="#">Discussions</a>
              <a href="#">Report Issue</a>
            </div>
          </nav>
        </div>

        <!-- Bottom bar -->
        <div class="footer-bottom">
          <p class="copyright">
            &copy; {{ currentYear }} Eleanor Project. Released under MIT License.
          </p>
          <div class="footer-links">
            <a href="#">Privacy</a>
            <a href="#">Terms</a>
            <a href="#">Security</a>
          </div>
        </div>
      </div>
    </footer>
  `,
  styles: [`
    .footer {
      background: var(--bg-secondary);
      border-top: 1px solid var(--border-subtle);
      padding: 4rem 0 2rem;
      margin-top: auto;
    }

    .footer-content {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 3rem;
      margin-bottom: 3rem;

      @media (max-width: 768px) {
        flex-direction: column;
        gap: 2rem;
      }
    }

    // Brand
    .footer-brand {
      display: flex;
      align-items: center;
      gap: 0.75rem;
    }

    .footer-logo {
      width: 40px;
      height: auto;
      filter: drop-shadow(0 0 10px rgba(74, 158, 255, 0.3));
    }

    .footer-title {
      font-family: 'Syne', sans-serif;
      font-size: 1.25rem;
      font-weight: 700;
      background: linear-gradient(135deg, var(--text-primary), var(--accent));
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      background-clip: text;
    }

    // Navigation
    .footer-nav {
      display: flex;
      gap: 4rem;

      @media (max-width: 640px) {
        flex-direction: column;
        gap: 2rem;
      }
    }

    .footer-section {
      display: flex;
      flex-direction: column;
      gap: 0.75rem;

      h4 {
        font-family: 'Syne', sans-serif;
        font-size: 0.875rem;
        font-weight: 600;
        color: var(--text-primary);
        margin-bottom: 0.25rem;
      }

      a {
        color: var(--text-secondary);
        text-decoration: none;
        font-size: 0.875rem;
        transition: color 0.2s ease;

        &:hover {
          color: var(--accent);
        }
      }
    }

    // Bottom bar
    .footer-bottom {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding-top: 2rem;
      border-top: 1px solid var(--border-subtle);

      @media (max-width: 640px) {
        flex-direction: column;
        gap: 1rem;
        text-align: center;
      }
    }

    .copyright {
      font-size: 0.8125rem;
      color: var(--text-muted);
    }

    .footer-links {
      display: flex;
      gap: 1.5rem;

      a {
        color: var(--text-muted);
        text-decoration: none;
        font-size: 0.8125rem;
        transition: color 0.2s ease;

        &:hover {
          color: var(--text-secondary);
        }
      }
    }
  `]
})
export class FooterComponent {
  currentYear = new Date().getFullYear();
}
