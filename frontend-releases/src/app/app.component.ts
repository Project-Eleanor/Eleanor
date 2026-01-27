import { Component, OnInit, inject } from '@angular/core';
import { HeroComponent } from './components/hero/hero.component';
import { DownloadsComponent } from './components/downloads/downloads.component';
import { RequirementsComponent } from './components/requirements/requirements.component';
import { FooterComponent } from './components/footer/footer.component';
import { AnimationService } from './services/animation.service';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [
    HeroComponent,
    DownloadsComponent,
    RequirementsComponent,
    FooterComponent
  ],
  template: `
    <main class="app-main">
      <app-hero />
      <app-downloads />
      <app-requirements />
      <app-footer />
    </main>
  `,
  styles: [`
    .app-main {
      min-height: 100vh;
      display: flex;
      flex-direction: column;
    }
  `]
})
export class AppComponent implements OnInit {
  private animationService = inject(AnimationService);

  ngOnInit(): void {
    this.animationService.initialize();
  }
}
