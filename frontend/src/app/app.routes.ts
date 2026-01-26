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
        path: 'soc',
        loadComponent: () => import('./features/soc-dashboard/soc-dashboard.component').then(m => m.SocDashboardComponent)
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
        path: 'investigation-graph',
        loadComponent: () => import('./features/investigation-graph/investigation-graph.component').then(m => m.InvestigationGraphComponent)
      },
      {
        path: 'artifact-timeline',
        loadComponent: () => import('./features/investigations/artifact-timeline.component').then(m => m.ArtifactTimelineComponent)
      },
      {
        path: 'workbooks',
        children: [
          {
            path: '',
            loadComponent: () => import('./features/workbooks/workbook-list.component').then(m => m.WorkbookListComponent)
          },
          {
            path: 'new',
            loadComponent: () => import('./features/workbooks/workbook-editor.component').then(m => m.WorkbookEditorComponent)
          },
          {
            path: ':id',
            loadComponent: () => import('./features/workbooks/workbook-viewer.component').then(m => m.WorkbookViewerComponent)
          },
          {
            path: ':id/edit',
            loadComponent: () => import('./features/workbooks/workbook-editor.component').then(m => m.WorkbookEditorComponent)
          }
        ]
      },
      {
        path: 'response',
        loadComponent: () => import('./features/response/response-actions.component').then(m => m.ResponseActionsComponent)
      },
      {
        path: 'threat-intel',
        loadComponent: () => import('./features/threat-intel/threat-intel.component').then(m => m.ThreatIntelComponent)
      },
      {
        path: 'analytics',
        loadComponent: () => import('./features/analytics/analytics.component').then(m => m.AnalyticsComponent)
      },
      {
        path: 'automation',
        loadComponent: () => import('./features/automation/automation.component').then(m => m.AutomationComponent)
      },
      {
        path: 'mitre',
        loadComponent: () => import('./features/mitre/mitre.component').then(m => m.MitreComponent)
      },
      {
        path: 'connectors',
        loadComponent: () => import('./features/connectors/connectors.component').then(m => m.ConnectorsComponent)
      },
      {
        path: 'reports',
        children: [
          {
            path: 'new',
            loadComponent: () => import('./features/reports/report-builder.component').then(m => m.ReportBuilderComponent)
          },
          {
            path: ':id',
            loadComponent: () => import('./features/reports/report-builder.component').then(m => m.ReportBuilderComponent)
          }
        ]
      },
      {
        path: 'settings',
        children: [
          {
            path: '',
            loadComponent: () => import('./features/settings/settings.component').then(m => m.SettingsComponent)
          },
          {
            path: 'notifications',
            loadComponent: () => import('./features/settings/notification-settings.component').then(m => m.NotificationSettingsComponent)
          }
        ]
      }
    ]
  },
  {
    path: '**',
    redirectTo: 'dashboard'
  }
];
