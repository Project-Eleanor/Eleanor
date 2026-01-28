"""Database connection management for PostgreSQL and Elasticsearch."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from elasticsearch import AsyncElasticsearch
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

settings = get_settings()

# PostgreSQL
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_size=5,
    max_overflow=10,
)

async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """SQLAlchemy declarative base."""

    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting database sessions."""
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# Elasticsearch
_es_client: AsyncElasticsearch | None = None


async def get_elasticsearch() -> AsyncElasticsearch:
    """Get Elasticsearch client."""
    global _es_client
    if _es_client is None:
        _es_client = AsyncElasticsearch(
            hosts=[settings.elasticsearch_url],
            verify_certs=False,
        )
    return _es_client


async def close_elasticsearch() -> None:
    """Close Elasticsearch client."""
    global _es_client
    if _es_client is not None:
        await _es_client.close()
        _es_client = None


# Redis
_redis_client: Redis | None = None


async def get_redis() -> Redis:
    """Get Redis client."""
    global _redis_client
    if _redis_client is None:
        _redis_client = Redis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis_client


async def close_redis() -> None:
    """Close Redis client."""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.close()
        _redis_client = None


@asynccontextmanager
async def lifespan_context() -> AsyncGenerator[None, Any]:
    """Context manager for application lifespan."""
    # Startup
    yield
    # Shutdown
    await close_elasticsearch()
    await close_redis()


async def init_elasticsearch_indices() -> None:
    """Initialize Elasticsearch index templates."""
    es = await get_elasticsearch()

    # Events index template
    events_template = {
        "index_patterns": [f"{settings.elasticsearch_index_prefix}-events-*"],
        "template": {
            "settings": {
                "number_of_shards": 1,
                "number_of_replicas": 0,
            },
            "mappings": {
                "properties": {
                    "@timestamp": {"type": "date"},
                    "case_id": {"type": "keyword"},
                    "event_type": {"type": "keyword"},
                    "source_type": {"type": "keyword"},
                    "severity": {"type": "keyword"},
                    "host": {
                        "properties": {
                            "name": {"type": "keyword"},
                            "ip": {"type": "ip"},
                        }
                    },
                    "user": {
                        "properties": {
                            "name": {"type": "keyword"},
                            "domain": {"type": "keyword"},
                        }
                    },
                    "process": {
                        "properties": {
                            "name": {"type": "keyword"},
                            "pid": {"type": "integer"},
                            "command_line": {"type": "text"},
                            "executable": {"type": "keyword"},
                            "parent": {
                                "properties": {
                                    "name": {"type": "keyword"},
                                    "pid": {"type": "integer"},
                                }
                            },
                        }
                    },
                    "file": {
                        "properties": {
                            "path": {"type": "keyword"},
                            "name": {"type": "keyword"},
                            "extension": {"type": "keyword"},
                            "size": {"type": "long"},
                            "hash": {
                                "properties": {
                                    "sha256": {"type": "keyword"},
                                    "sha1": {"type": "keyword"},
                                    "md5": {"type": "keyword"},
                                }
                            },
                        }
                    },
                    "network": {
                        "properties": {
                            "source_ip": {"type": "ip"},
                            "destination_ip": {"type": "ip"},
                            "source_port": {"type": "integer"},
                            "destination_port": {"type": "integer"},
                            "protocol": {"type": "keyword"},
                            "bytes_sent": {"type": "long"},
                            "bytes_received": {"type": "long"},
                        }
                    },
                    "registry": {
                        "properties": {
                            "key": {"type": "keyword"},
                            "value": {"type": "keyword"},
                            "data": {"type": "text"},
                        }
                    },
                    "message": {"type": "text"},
                    "raw": {"type": "text", "index": False},
                    "tags": {"type": "keyword"},
                    "mitre": {
                        "properties": {
                            "tactic": {"type": "keyword"},
                            "technique": {"type": "keyword"},
                        }
                    },
                }
            },
        },
    }

    await es.indices.put_index_template(
        name=f"{settings.elasticsearch_index_prefix}-events",
        body=events_template,
    )

    # Timeline index template
    timeline_template = {
        "index_patterns": [f"{settings.elasticsearch_index_prefix}-timeline-*"],
        "template": {
            "settings": {
                "number_of_shards": 1,
                "number_of_replicas": 0,
            },
            "mappings": {
                "properties": {
                    "@timestamp": {"type": "date"},
                    "case_id": {"type": "keyword"},
                    "event_id": {"type": "keyword"},
                    "title": {"type": "text"},
                    "description": {"type": "text"},
                    "category": {"type": "keyword"},
                    "source": {"type": "keyword"},
                    "entities": {
                        "properties": {
                            "hosts": {"type": "keyword"},
                            "users": {"type": "keyword"},
                            "ips": {"type": "ip"},
                            "files": {"type": "keyword"},
                        }
                    },
                    "evidence_id": {"type": "keyword"},
                    "created_by": {"type": "keyword"},
                    "tags": {"type": "keyword"},
                }
            },
        },
    }

    await es.indices.put_index_template(
        name=f"{settings.elasticsearch_index_prefix}-timeline",
        body=timeline_template,
    )
