"""Request audit logging middleware for Eleanor.

Logs all API requests for security monitoring and compliance.
"""

import logging
import time
from typing import Callable
from uuid import uuid4

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("eleanor.audit")


def get_client_ip(request: Request) -> str:
    """Extract client IP from request."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def sanitize_path(path: str) -> str:
    """Sanitize path for logging (remove sensitive params)."""
    # Remove query string for logging
    return path.split("?")[0]


class RequestAuditMiddleware(BaseHTTPMiddleware):
    """Middleware for logging all API requests.

    Logs request details including:
    - Request ID (for correlation)
    - Method and path
    - Client IP
    - User agent
    - User ID (if authenticated)
    - Response status
    - Duration
    """

    # Paths to exclude from detailed logging
    EXCLUDE_PATHS = {
        "/health",
        "/api/health",
        "/api/v1/health",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/favicon.ico",
    }

    # Paths that should always be logged (security-sensitive)
    ALWAYS_LOG_PATHS = {
        "/api/v1/auth/login",
        "/api/v1/auth/logout",
        "/api/v1/auth/token",
        "/api/v1/admin/",
        "/api/v1/rbac/",
        "/api/v1/response/",
    }

    def __init__(self, app, log_all: bool = False):
        """Initialize audit middleware.

        Args:
            app: FastAPI application
            log_all: Log all requests (not just security-sensitive)
        """
        super().__init__(app)
        self.log_all = log_all

    async def dispatch(
        self,
        request: Request,
        call_next: Callable,
    ) -> Response:
        """Process request with audit logging."""
        # Generate request ID
        request_id = str(uuid4())[:8]
        request.state.request_id = request_id

        path = request.url.path
        sanitized_path = sanitize_path(path)

        # Check if we should log this request
        should_log = self.log_all or any(
            path.startswith(p) for p in self.ALWAYS_LOG_PATHS
        )

        if path in self.EXCLUDE_PATHS:
            should_log = False

        # Get client info
        client_ip = get_client_ip(request)
        user_agent = request.headers.get("User-Agent", "unknown")[:200]
        method = request.method

        # Start timing
        start_time = time.time()

        # Get user info if available
        user_id = None
        username = None
        if hasattr(request.state, "user") and request.state.user:
            user_id = str(request.state.user.id)
            username = request.state.user.username

        try:
            response = await call_next(request)
            status_code = response.status_code

            # Calculate duration
            duration_ms = (time.time() - start_time) * 1000

            if should_log:
                # Log successful request
                log_data = {
                    "request_id": request_id,
                    "method": method,
                    "path": sanitized_path,
                    "status": status_code,
                    "duration_ms": round(duration_ms, 2),
                    "client_ip": client_ip,
                    "user_id": user_id,
                    "username": username,
                }

                if status_code >= 400:
                    logger.warning("Request failed: %s", log_data)
                else:
                    logger.info("Request completed: %s", log_data)

            # Add request ID to response headers
            response.headers["X-Request-ID"] = request_id

            return response

        except Exception as e:
            # Calculate duration even for errors
            duration_ms = (time.time() - start_time) * 1000

            # Log error
            logger.error(
                "Request error: request_id=%s method=%s path=%s client_ip=%s user=%s error=%s duration_ms=%.2f",
                request_id,
                method,
                sanitized_path,
                client_ip,
                username or "anonymous",
                str(e),
                duration_ms,
            )
            raise


class SecurityEventLogger:
    """Helper for logging security-relevant events."""

    @staticmethod
    def log_login_success(
        username: str,
        user_id: str,
        client_ip: str,
        method: str = "password",
    ) -> None:
        """Log successful login."""
        logger.info(
            "LOGIN_SUCCESS: user=%s user_id=%s ip=%s method=%s",
            username,
            user_id,
            client_ip,
            method,
        )

    @staticmethod
    def log_login_failure(
        username: str,
        client_ip: str,
        reason: str = "invalid_credentials",
    ) -> None:
        """Log failed login attempt."""
        logger.warning(
            "LOGIN_FAILURE: user=%s ip=%s reason=%s",
            username,
            client_ip,
            reason,
        )

    @staticmethod
    def log_logout(
        username: str,
        user_id: str,
        client_ip: str,
    ) -> None:
        """Log user logout."""
        logger.info(
            "LOGOUT: user=%s user_id=%s ip=%s",
            username,
            user_id,
            client_ip,
        )

    @staticmethod
    def log_permission_denied(
        username: str,
        user_id: str,
        resource: str,
        action: str,
        client_ip: str,
    ) -> None:
        """Log permission denied event."""
        logger.warning(
            "PERMISSION_DENIED: user=%s user_id=%s resource=%s action=%s ip=%s",
            username,
            user_id,
            resource,
            action,
            client_ip,
        )

    @staticmethod
    def log_response_action(
        username: str,
        user_id: str,
        action_type: str,
        target: str,
        client_ip: str,
        case_id: str = None,
    ) -> None:
        """Log response action execution."""
        logger.info(
            "RESPONSE_ACTION: user=%s user_id=%s action=%s target=%s case=%s ip=%s",
            username,
            user_id,
            action_type,
            target,
            case_id or "none",
            client_ip,
        )

    @staticmethod
    def log_data_export(
        username: str,
        user_id: str,
        export_type: str,
        record_count: int,
        client_ip: str,
    ) -> None:
        """Log data export event."""
        logger.info(
            "DATA_EXPORT: user=%s user_id=%s type=%s records=%d ip=%s",
            username,
            user_id,
            export_type,
            record_count,
            client_ip,
        )

    @staticmethod
    def log_admin_action(
        username: str,
        user_id: str,
        action: str,
        target: str,
        client_ip: str,
        details: dict = None,
    ) -> None:
        """Log admin action."""
        logger.info(
            "ADMIN_ACTION: user=%s user_id=%s action=%s target=%s ip=%s details=%s",
            username,
            user_id,
            action,
            target,
            client_ip,
            details or {},
        )


# Singleton instance for easy import
security_logger = SecurityEventLogger()
