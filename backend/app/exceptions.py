"""Standardized exceptions and error handling for Eleanor API."""

from collections.abc import Awaitable, Callable
from uuid import uuid4

from fastapi import FastAPI, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# =============================================================================
# Error Response Model
# =============================================================================


class ErrorDetail(BaseModel):
    """Detailed error information."""

    field: str | None = None
    message: str
    code: str | None = None


class ErrorResponse(BaseModel):
    """Standardized error response format."""

    error: str  # Error type/category
    message: str  # Human-readable message
    code: str  # Machine-readable error code
    status_code: int  # HTTP status code
    request_id: str  # Unique request identifier
    details: list[ErrorDetail] | None = None  # Additional error details
    path: str | None = None  # Request path


# =============================================================================
# Custom Exceptions
# =============================================================================


class EleanorException(Exception):
    """Base exception for Eleanor API errors."""

    def __init__(
        self,
        message: str,
        code: str = "INTERNAL_ERROR",
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: list[ErrorDetail] | None = None,
    ):
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details
        super().__init__(message)


class NotFoundError(EleanorException):
    """Resource not found error."""

    def __init__(
        self,
        resource: str,
        identifier: str | None = None,
        details: list[ErrorDetail] | None = None,
    ):
        message = f"{resource} not found"
        if identifier:
            message = f"{resource} '{identifier}' not found"
        super().__init__(
            message=message,
            code="NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
            details=details,
        )


class ConflictError(EleanorException):
    """Resource conflict error."""

    def __init__(
        self,
        message: str = "Resource conflict",
        details: list[ErrorDetail] | None = None,
    ):
        super().__init__(
            message=message,
            code="CONFLICT",
            status_code=status.HTTP_409_CONFLICT,
            details=details,
        )


class ValidationError(EleanorException):
    """Validation error."""

    def __init__(
        self,
        message: str = "Validation failed",
        details: list[ErrorDetail] | None = None,
    ):
        super().__init__(
            message=message,
            code="VALIDATION_ERROR",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details=details,
        )


class AuthenticationError(EleanorException):
    """Authentication error."""

    def __init__(
        self,
        message: str = "Authentication required",
        details: list[ErrorDetail] | None = None,
    ):
        super().__init__(
            message=message,
            code="AUTHENTICATION_REQUIRED",
            status_code=status.HTTP_401_UNAUTHORIZED,
            details=details,
        )


class AuthorizationError(EleanorException):
    """Authorization error."""

    def __init__(
        self,
        message: str = "Permission denied",
        details: list[ErrorDetail] | None = None,
    ):
        super().__init__(
            message=message,
            code="PERMISSION_DENIED",
            status_code=status.HTTP_403_FORBIDDEN,
            details=details,
        )


class RateLimitError(EleanorException):
    """Rate limit exceeded error."""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: int | None = None,
        details: list[ErrorDetail] | None = None,
    ):
        self.retry_after = retry_after
        super().__init__(
            message=message,
            code="RATE_LIMIT_EXCEEDED",
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            details=details,
        )


class ServiceUnavailableError(EleanorException):
    """External service unavailable error."""

    def __init__(
        self,
        service: str,
        message: str | None = None,
        details: list[ErrorDetail] | None = None,
    ):
        msg = message or f"Service '{service}' is unavailable"
        super().__init__(
            message=msg,
            code="SERVICE_UNAVAILABLE",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            details=details,
        )


class BadRequestError(EleanorException):
    """Bad request error."""

    def __init__(
        self,
        message: str = "Bad request",
        details: list[ErrorDetail] | None = None,
    ):
        super().__init__(
            message=message,
            code="BAD_REQUEST",
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details,
        )


# =============================================================================
# Exception Handlers
# =============================================================================


def create_error_response(
    request: Request,
    error: str,
    message: str,
    code: str,
    status_code: int,
    details: list[ErrorDetail] | None = None,
) -> JSONResponse:
    """Create a standardized error response."""
    request_id = getattr(request.state, "request_id", str(uuid4()))

    response = ErrorResponse(
        error=error,
        message=message,
        code=code,
        status_code=status_code,
        request_id=request_id,
        details=details,
        path=str(request.url.path),
    )

    return JSONResponse(
        status_code=status_code,
        content=response.model_dump(exclude_none=True),
    )


async def eleanor_exception_handler(request: Request, exc: EleanorException) -> JSONResponse:
    """Handle Eleanor custom exceptions."""
    return create_error_response(
        request=request,
        error=exc.__class__.__name__,
        message=exc.message,
        code=exc.code,
        status_code=exc.status_code,
        details=exc.details,
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Handle Pydantic validation errors."""
    details = []
    for error in exc.errors():
        field = ".".join(str(loc) for loc in error["loc"])
        details.append(
            ErrorDetail(
                field=field,
                message=error["msg"],
                code=error["type"],
            )
        )

    return create_error_response(
        request=request,
        error="ValidationError",
        message="Request validation failed",
        code="VALIDATION_ERROR",
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        details=details,
    )


async def http_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle generic HTTP exceptions."""
    from fastapi import HTTPException

    if isinstance(exc, HTTPException):
        # Map common status codes to error types
        error_map = {
            400: ("BadRequest", "BAD_REQUEST"),
            401: ("AuthenticationError", "AUTHENTICATION_REQUIRED"),
            403: ("AuthorizationError", "PERMISSION_DENIED"),
            404: ("NotFound", "NOT_FOUND"),
            409: ("Conflict", "CONFLICT"),
            429: ("RateLimitExceeded", "RATE_LIMIT_EXCEEDED"),
            500: ("InternalServerError", "INTERNAL_ERROR"),
            502: ("BadGateway", "BAD_GATEWAY"),
            503: ("ServiceUnavailable", "SERVICE_UNAVAILABLE"),
        }

        error_type, code = error_map.get(exc.status_code, ("HTTPError", f"HTTP_{exc.status_code}"))

        return create_error_response(
            request=request,
            error=error_type,
            message=str(exc.detail),
            code=code,
            status_code=exc.status_code,
        )

    # Fallback for unknown exceptions
    return create_error_response(
        request=request,
        error="InternalServerError",
        message="An unexpected error occurred",
        code="INTERNAL_ERROR",
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle uncaught exceptions."""
    import logging
    import traceback

    logger = logging.getLogger(__name__)
    logger.error("Unhandled exception: %s\n%s", str(exc), traceback.format_exc())

    return create_error_response(
        request=request,
        error="InternalServerError",
        message="An unexpected error occurred",
        code="INTERNAL_ERROR",
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


# =============================================================================
# Middleware
# =============================================================================


async def request_id_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Add request ID to each request for tracing."""
    request_id = request.headers.get("X-Request-ID", str(uuid4()))
    request.state.request_id = request_id

    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


# =============================================================================
# Setup Function
# =============================================================================


def setup_exception_handlers(app: FastAPI) -> None:
    """Register all exception handlers with the FastAPI app."""
    from fastapi import HTTPException

    app.add_exception_handler(EleanorException, eleanor_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)

    # Add request ID middleware
    app.middleware("http")(request_id_middleware)
