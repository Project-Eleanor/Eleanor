import { HttpInterceptorFn, HttpErrorResponse } from '@angular/common/http';
import { inject } from '@angular/core';
import { MatSnackBar } from '@angular/material/snack-bar';
import { catchError, throwError } from 'rxjs';

export interface ErrorDetail {
  field: string | null;
  message: string;
  code: string | null;
}

export interface ApiError {
  error: string;
  message: string;
  code: string;
  status_code: number;
  request_id: string;
  details?: ErrorDetail[];
  path?: string;
}

function parseError(error: HttpErrorResponse): ApiError {
  // Check if response matches our standardized format
  if (error.error && typeof error.error === 'object' && 'code' in error.error) {
    return error.error as ApiError;
  }

  // Create standardized error from non-standard response
  const errorTypes: Record<number, string> = {
    0: 'NetworkError',
    400: 'BadRequest',
    401: 'AuthenticationError',
    403: 'AuthorizationError',
    404: 'NotFound',
    409: 'Conflict',
    422: 'ValidationError',
    429: 'RateLimitExceeded',
    500: 'InternalServerError',
    502: 'BadGateway',
    503: 'ServiceUnavailable'
  };

  return {
    error: errorTypes[error.status] || 'UnknownError',
    message: getErrorMessage(error),
    code: `HTTP_${error.status}`,
    status_code: error.status,
    request_id: error.headers?.get('X-Request-ID') || 'unknown',
    path: error.url || undefined
  };
}

function getErrorMessage(error: HttpErrorResponse): string {
  if (error.status === 0) {
    return 'Unable to connect to server. Please check your network connection.';
  }

  if (error.error?.message) {
    return error.error.message;
  }

  if (error.error?.detail) {
    return error.error.detail;
  }

  if (typeof error.error === 'string') {
    return error.error;
  }

  const defaultMessages: Record<number, string> = {
    400: 'Invalid request',
    401: 'Please log in to continue',
    403: 'You do not have permission to perform this action',
    404: 'The requested resource was not found',
    409: 'A conflict occurred with the current state',
    422: 'The request data is invalid',
    429: 'Too many requests. Please try again later.',
    500: 'An unexpected error occurred',
    502: 'Unable to reach the server',
    503: 'Service temporarily unavailable'
  };

  return defaultMessages[error.status] || 'An error occurred';
}

export const errorInterceptor: HttpInterceptorFn = (req, next) => {
  const snackBar = inject(MatSnackBar);

  return next(req).pipe(
    catchError((error: HttpErrorResponse) => {
      const apiError = parseError(error);

      // Don't show snackbar for auth errors (handled by auth interceptor)
      if (error.status !== 401) {
        // Handle validation errors with details
        if (error.status === 422 && apiError.details?.length) {
          const messages = apiError.details
            .slice(0, 3)
            .map(d => d.message)
            .join('; ');
          showError(snackBar, `Validation error: ${messages}`);
        }
        // Handle network errors
        else if (error.status === 0) {
          showError(snackBar, 'Network error. Please check your connection.');
        }
        // Handle server errors
        else if (error.status >= 500) {
          showError(snackBar, 'Server error. Please try again later.');
        }
        // Handle other errors (403, 404, etc.)
        else if (error.status !== 404) {
          // Don't show 404 errors as snackbars
          showError(snackBar, apiError.message);
        }
      }

      return throwError(() => apiError);
    })
  );
};

function showError(snackBar: MatSnackBar, message: string): void {
  snackBar.open(message, 'Dismiss', {
    duration: 5000,
    horizontalPosition: 'right',
    verticalPosition: 'top',
    panelClass: ['snackbar-error']
  });
}
