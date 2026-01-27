import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-features',
  standalone: true,
  imports: [CommonModule],
  template: `
    <section class="features" id="features">
      <div class="features-container">
        <!-- Section Header -->
        <div class="section-header">
          <span class="section-label">Why Eleanor</span>
          <h2 class="section-title">The DFIR Platform You've Been Waiting For</h2>
          <p class="section-description">
            Eleanor unifies the fragmented DFIR toolchain into a single, powerful platform.
            No more context-switching between a dozen tools during critical investigations.
          </p>
        </div>

        <!-- Who It's For -->
        <div class="audience-grid">
          <div class="audience-card">
            <div class="audience-icon">
              <span class="material-icons-round">shield</span>
            </div>
            <h3>SOC Analysts</h3>
            <p>Investigate alerts faster with unified entity profiles, automated enrichment, and one-click threat intel lookups.</p>
          </div>
          <div class="audience-card">
            <div class="audience-icon">
              <span class="material-icons-round">search</span>
            </div>
            <h3>Threat Hunters</h3>
            <p>Hunt across your entire environment with ES|QL queries, saved hunts, and workbooks that capture institutional knowledge.</p>
          </div>
          <div class="audience-card">
            <div class="audience-icon">
              <span class="material-icons-round">biotech</span>
            </div>
            <h3>Forensic Investigators</h3>
            <p>Process evidence with 34+ parsers, build timelines, and generate court-ready reports without leaving the platform.</p>
          </div>
          <div class="audience-card">
            <div class="audience-icon">
              <span class="material-icons-round">business</span>
            </div>
            <h3>IR Teams</h3>
            <p>Coordinate response efforts with case management, automated playbooks, and real-time collaboration features.</p>
          </div>
        </div>

        <!-- Core Capabilities -->
        <div class="capabilities">
          <h3 class="capabilities-title">Core Capabilities</h3>
          <div class="capabilities-grid">
            <div class="capability">
              <div class="capability-header">
                <span class="material-icons-round">terminal</span>
                <span class="capability-name">Threat Hunting Console</span>
              </div>
              <p>Monaco-powered ES|QL editor with autocomplete, syntax highlighting, and query history. Save and share hunts across your team.</p>
            </div>
            <div class="capability">
              <div class="capability-header">
                <span class="material-icons-round">folder_special</span>
                <span class="capability-name">Case Management</span>
              </div>
              <p>Full investigation lifecycle from intake to closure. Track assets, IOCs, notes, and evidence with IRIS integration.</p>
            </div>
            <div class="capability">
              <div class="capability-header">
                <span class="material-icons-round">timeline</span>
                <span class="capability-name">Timeline Analysis</span>
              </div>
              <p>Interactive D3-powered timelines that correlate events across sources. Zoom, filter, and annotate to reconstruct incidents.</p>
            </div>
            <div class="capability">
              <div class="capability-header">
                <span class="material-icons-round">hub</span>
                <span class="capability-name">Investigation Graphs</span>
              </div>
              <p>Cytoscape-powered entity relationship visualization. Trace lateral movement, map attack paths, and identify pivots.</p>
            </div>
            <div class="capability">
              <div class="capability-header">
                <span class="material-icons-round">dns</span>
                <span class="capability-name">Evidence Processing</span>
              </div>
              <p>34+ parsers for EVTX, Registry, MFT, Browser artifacts, Prefetch, SRUM, and more. Powered by Dissect and custom extractors.</p>
            </div>
            <div class="capability">
              <div class="capability-header">
                <span class="material-icons-round">smart_toy</span>
                <span class="capability-name">Automated Response</span>
              </div>
              <p>SOAR workflows via Shuffle with approval gates. Isolate hosts, block IPs, and reset credentials with auditable automation.</p>
            </div>
          </div>
        </div>

        <!-- What Makes It Unique -->
        <div class="unique-section">
          <h3 class="unique-title">What Makes Eleanor Different</h3>
          <div class="unique-grid">
            <div class="unique-item">
              <div class="unique-number">01</div>
              <div class="unique-content">
                <h4>Investigation-First Philosophy</h4>
                <p>Most SIEM/SOAR tools are alert-first—you react to what the system tells you. Eleanor is investigation-first. Start with a hypothesis, hunt proactively, and follow the evidence wherever it leads.</p>
              </div>
            </div>
            <div class="unique-item">
              <div class="unique-number">02</div>
              <div class="unique-content">
                <h4>Unified Interface, Best-of-Breed Tools</h4>
                <p>Eleanor doesn't reinvent the wheel. It integrates battle-tested tools like IRIS, Velociraptor, OpenCTI, and Shuffle under a single Sentinel-style dashboard. One UI to rule them all.</p>
              </div>
            </div>
            <div class="unique-item">
              <div class="unique-number">03</div>
              <div class="unique-content">
                <h4>Self-Hosted & Privacy-Preserving</h4>
                <p>Your investigation data never leaves your infrastructure. No cloud dependencies, no telemetry, no vendor lock-in. Full control over your sensitive forensic artifacts.</p>
              </div>
            </div>
            <div class="unique-item">
              <div class="unique-number">04</div>
              <div class="unique-content">
                <h4>Multi-Tenant by Design</h4>
                <p>Built for MSSPs and enterprise teams. Full tenant isolation with row-level security, scoped indices, and per-organization configurations. Serve multiple clients from one instance.</p>
              </div>
            </div>
          </div>
        </div>

        <!-- Integration Logos -->
        <div class="integrations">
          <span class="integrations-label">Integrates With</span>
          <div class="integration-list">
            <div class="integration-item">DFIR-IRIS</div>
            <div class="integration-item">Velociraptor</div>
            <div class="integration-item">OpenCTI</div>
            <div class="integration-item">Shuffle</div>
            <div class="integration-item">Timesketch</div>
            <div class="integration-item">Elasticsearch</div>
          </div>
        </div>
      </div>
    </section>
  `,
  styles: [`
    .features {
      padding: 6rem 2rem;
      background: var(--bg-primary);
      position: relative;
    }

    .features-container {
      max-width: 1200px;
      margin: 0 auto;
    }

    // Section Header
    .section-header {
      text-align: center;
      margin-bottom: 4rem;
    }

    .section-label {
      display: inline-block;
      padding: 0.5rem 1rem;
      background: var(--accent-glow);
      color: var(--accent);
      border-radius: 100px;
      font-size: 0.875rem;
      font-weight: 600;
      margin-bottom: 1rem;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }

    .section-title {
      font-family: 'Syne', sans-serif;
      font-size: clamp(2rem, 5vw, 3rem);
      font-weight: 700;
      color: var(--text-primary);
      margin-bottom: 1rem;
    }

    .section-description {
      font-size: 1.125rem;
      color: var(--text-secondary);
      max-width: 700px;
      margin: 0 auto;
      line-height: 1.7;
    }

    // Audience Grid
    .audience-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
      gap: 1.5rem;
      margin-bottom: 5rem;
    }

    .audience-card {
      background: var(--bg-card);
      border: 1px solid var(--border-subtle);
      border-radius: 12px;
      padding: 2rem;
      transition: all 0.3s ease;

      &:hover {
        border-color: var(--accent);
        transform: translateY(-4px);
        box-shadow: 0 8px 30px rgba(0, 0, 0, 0.3);
      }

      h3 {
        font-family: 'Syne', sans-serif;
        font-size: 1.25rem;
        font-weight: 600;
        color: var(--text-primary);
        margin-bottom: 0.75rem;
      }

      p {
        color: var(--text-secondary);
        font-size: 0.9375rem;
        line-height: 1.6;
      }
    }

    .audience-icon {
      width: 48px;
      height: 48px;
      background: var(--accent-glow);
      border-radius: 12px;
      display: flex;
      align-items: center;
      justify-content: center;
      margin-bottom: 1rem;

      .material-icons-round {
        font-size: 24px;
        color: var(--accent);
      }
    }

    // Capabilities
    .capabilities {
      margin-bottom: 5rem;
    }

    .capabilities-title {
      font-family: 'Syne', sans-serif;
      font-size: 1.5rem;
      font-weight: 600;
      color: var(--text-primary);
      margin-bottom: 2rem;
      text-align: center;
    }

    .capabilities-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(340px, 1fr));
      gap: 1.5rem;
    }

    .capability {
      background: var(--bg-secondary);
      border: 1px solid var(--border-subtle);
      border-radius: 8px;
      padding: 1.5rem;

      p {
        color: var(--text-secondary);
        font-size: 0.9375rem;
        line-height: 1.6;
        margin: 0;
      }
    }

    .capability-header {
      display: flex;
      align-items: center;
      gap: 0.75rem;
      margin-bottom: 0.75rem;

      .material-icons-round {
        font-size: 20px;
        color: var(--accent);
      }
    }

    .capability-name {
      font-family: 'Syne', sans-serif;
      font-weight: 600;
      color: var(--text-primary);
    }

    // Unique Section
    .unique-section {
      margin-bottom: 5rem;
      padding: 3rem;
      background: linear-gradient(135deg, var(--bg-secondary) 0%, var(--bg-card) 100%);
      border: 1px solid var(--border-subtle);
      border-radius: 16px;
    }

    .unique-title {
      font-family: 'Syne', sans-serif;
      font-size: 1.5rem;
      font-weight: 600;
      color: var(--text-primary);
      margin-bottom: 2rem;
      text-align: center;
    }

    .unique-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap: 2rem;
    }

    .unique-item {
      display: flex;
      gap: 1rem;
    }

    .unique-number {
      font-family: 'Syne', sans-serif;
      font-size: 2rem;
      font-weight: 700;
      color: var(--accent);
      opacity: 0.5;
      line-height: 1;
    }

    .unique-content {
      h4 {
        font-family: 'Syne', sans-serif;
        font-size: 1.125rem;
        font-weight: 600;
        color: var(--text-primary);
        margin-bottom: 0.5rem;
      }

      p {
        color: var(--text-secondary);
        font-size: 0.9375rem;
        line-height: 1.6;
      }
    }

    // Integrations
    .integrations {
      text-align: center;
    }

    .integrations-label {
      display: block;
      font-size: 0.875rem;
      color: var(--text-muted);
      margin-bottom: 1.5rem;
      text-transform: uppercase;
      letter-spacing: 0.1em;
    }

    .integration-list {
      display: flex;
      flex-wrap: wrap;
      justify-content: center;
      gap: 1rem;
    }

    .integration-item {
      padding: 0.75rem 1.5rem;
      background: var(--bg-secondary);
      border: 1px solid var(--border-subtle);
      border-radius: 8px;
      font-size: 0.875rem;
      font-weight: 500;
      color: var(--text-secondary);
      transition: all 0.2s ease;

      &:hover {
        border-color: var(--accent);
        color: var(--accent);
      }
    }
  `]
})
export class FeaturesComponent {}
