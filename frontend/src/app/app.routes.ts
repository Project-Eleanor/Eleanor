import { Routes } from '@angular/router';
import { authGuard, noAuthGuard } from './core/auth/auth.guard';

export const routes: Routes = [
  {
    path: 'login',
    loadComponent: () => import('./core/auth/login.component').then(m => m.LoginComponent),
    canActivate: [noAuthGuard]
  },
  {
    path: '',
    loadComponent: () => import('./core/layout/shell.component').then(m => m.ShellComponent),
    canActivate: [authGuard],
    children: [
      {
        path: '',
        redirectTo: 'dashboard',
        pathMatch: 'full'
      },
      {
        path: 'dashboard',
        loadComponent: () => import('./features/dashboard/dashboard.component').then(m => m.DashboardComponent)
      },
      {
        path: 'incidents',
        children: [
          {
            path: '',
            loadComponent: () => import('./features/incidents/incident-list.component').then(m => m.IncidentListComponent)
          },
          {
            path: ':id',
            loadComponent: () => import('./features/incidents/incident-detail.component').then(m => m.IncidentDetailComponent)
          }
        ]
      },
      {
        path: 'hunting',
        loadComponent: () => import('./features/hunting/hunting-console.component').then(m => m.HuntingConsoleComponent)
      },
      {
        path: 'entities',
        children: [
          {
            path: '',
            loadComponent: () => import('./features/entities/entity-search.component').then(m => m.EntitySearchComponent)
          },
          {
            path: ':type/:value',
            loadComponent: () => import('./features/entities/entity-profile.component').then(m => m.EntityProfileComponent)
          }
        ]
      },
      {
        path: 'evidence',
        loadComponent: () => import('./features/evidence/evidence-browser.component').then(m => m.EvidenceBrowserComponent)
      },
      {
        path: 'timeline',
        loadComponent: () => import('./features/timeline/timeline-view.component').then(m => m.TimelineViewComponent)
      },
      {
        path: 'response',
        loadComponent: () => import('./features/response/response-actions.component').then(m => m.ResponseActionsComponent)
      },
      {
        path: 'settings',
        loadComponent: () => import('./features/settings/settings.component').then(m => m.SettingsComponent)
      }
    ]
  },
  {
    path: '**',
    redirectTo: 'dashboard'
  }
];
