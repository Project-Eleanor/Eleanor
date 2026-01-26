import { Injectable, inject } from '@angular/core';
import {
  HttpInterceptor,
  HttpRequest,
  HttpHandler,
  HttpEvent,
  HttpInterceptorFn,
  HttpHandlerFn
} from '@angular/common/http';
import { Observable } from 'rxjs';
import { TenantService } from '../services/tenant.service';

// Functional interceptor for modern Angular
export const tenantInterceptor: HttpInterceptorFn = (
  req: HttpRequest<unknown>,
  next: HttpHandlerFn
): Observable<HttpEvent<unknown>> => {
  const tenantService = inject(TenantService);
  const tenantId = tenantService.tenantId();

  // Skip tenant header for certain endpoints
  const skipTenantPaths = [
    '/auth/login',
    '/auth/register',
    '/auth/refresh',
    '/admin/tenants' // Admin tenant management doesn't need tenant context
  ];

  const shouldSkip = skipTenantPaths.some(path => req.url.includes(path));

  if (tenantId && !shouldSkip) {
    const clonedReq = req.clone({
      setHeaders: {
        'X-Tenant-ID': tenantId
      }
    });
    return next(clonedReq);
  }

  return next(req);
};

// Class-based interceptor for compatibility
@Injectable()
export class TenantInterceptor implements HttpInterceptor {
  constructor(private tenantService: TenantService) {}

  intercept(
    req: HttpRequest<unknown>,
    next: HttpHandler
  ): Observable<HttpEvent<unknown>> {
    const tenantId = this.tenantService.tenantId();

    // Skip tenant header for certain endpoints
    const skipTenantPaths = [
      '/auth/login',
      '/auth/register',
      '/auth/refresh',
      '/admin/tenants'
    ];

    const shouldSkip = skipTenantPaths.some(path => req.url.includes(path));

    if (tenantId && !shouldSkip) {
      const clonedReq = req.clone({
        setHeaders: {
          'X-Tenant-ID': tenantId
        }
      });
      return next.handle(clonedReq);
    }

    return next.handle(req);
  }
}
