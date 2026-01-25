"""Eleanor DFIR Platform - Main Application Entry Point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.adapters import get_registry, init_adapters
from app.api.v1 import router as api_v1_router
from app.config import get_settings
from app.database import close_elasticsearch, close_redis, init_elasticsearch_indices
from app.exceptions import setup_exception_handlers

settings = get_settings()

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    logger.info("Starting Eleanor DFIR Platform v%s", settings.app_version)

    try:
        await init_elasticsearch_indices()
        logger.info("Elasticsearch indices initialized")
    except Exception as e:
        logger.warning("Failed to initialize Elasticsearch indices: %s", e)

    # Initialize tool adapters
    try:
        registry = await init_adapters(settings)
        enabled = registry.list_enabled()
        if enabled:
            logger.info("Initialized adapters: %s", ", ".join(enabled))
        else:
            logger.info("No adapters enabled")
    except Exception as e:
        logger.warning("Failed to initialize adapters: %s", e)

    yield

    # Shutdown
    logger.info("Shutting down Eleanor DFIR Platform")

    # Disconnect adapters
    try:
        registry = get_registry()
        await registry.disconnect_all()
    except Exception as e:
        logger.warning("Error disconnecting adapters: %s", e)

    await close_elasticsearch()
    await close_redis()


app = FastAPI(
    title=settings.app_name,
    description="Open-source DFIR platform with Sentinel-style UI and built-in case management",
    version=settings.app_version,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    openapi_url="/openapi.json" if settings.debug else "/api/openapi.json",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Setup exception handlers for standardized error responses
setup_exception_handlers(app)

# Include API routers
app.include_router(api_v1_router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "app": settings.app_name,
        "version": settings.app_version,
    }


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "tagline": "Hunt. Collect. Analyze. Respond.",
        "docs": "/docs" if settings.debug else "/api/openapi.json",
    }
