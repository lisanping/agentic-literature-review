"""Unified exception classes and global exception handlers — §8.3.7."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import structlog

logger = structlog.stdlib.get_logger()


class AppError(Exception):
    """Base application error with structured error response."""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        params: dict | None = None,
    ):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.params = params or {}
        super().__init__(message)

    def to_detail(self) -> dict:
        detail: dict = {"code": self.code, "message": self.message}
        if self.params:
            detail["params"] = self.params
        return detail


class NotFoundError(AppError):
    def __init__(self, resource: str, resource_id: str):
        super().__init__(
            code=f"{resource.upper()}_NOT_FOUND",
            message=f"{resource} with id '{resource_id}' not found",
            status_code=404,
            params={f"{resource}_id": resource_id},
        )


class ConflictError(AppError):
    def __init__(self, message: str, code: str = "CONFLICT"):
        super().__init__(code=code, message=message, status_code=409)


class ServiceUnavailableError(AppError):
    def __init__(self, service: str):
        super().__init__(
            code="SERVICE_UNAVAILABLE",
            message=f"Dependency unavailable: {service}",
            status_code=503,
            params={"service": service},
        )


def register_exception_handlers(app: FastAPI) -> None:
    """Register global exception handlers on the FastAPI app."""

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        logger.warning(
            "app_error",
            code=exc.code,
            message=exc.message,
            path=request.url.path,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.to_detail()},
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error(
            "unhandled_exception",
            path=request.url.path,
            method=request.method,
            error=str(exc),
        )
        return JSONResponse(
            status_code=500,
            content={
                "detail": {
                    "code": "INTERNAL_ERROR",
                    "message": "An unexpected error occurred",
                }
            },
        )
