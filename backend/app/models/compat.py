"""Database compatibility types for PostgreSQL and SQLite.

This module provides type wrappers that work with both PostgreSQL (production)
and SQLite (testing). When running with PostgreSQL, the native types are used.
When running with SQLite, compatible fallback types are used.
"""


from sqlalchemy import JSON, String, TypeDecorator
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine import Dialect


class ArrayType(TypeDecorator):
    """Array type that works with both PostgreSQL and SQLite.

    Uses PostgreSQL ARRAY in production, JSON in SQLite for testing.
    """

    impl = JSON
    cache_ok = True

    def __init__(self, item_type=String):
        super().__init__()
        self.item_type = item_type

    def load_dialect_impl(self, dialect: Dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(postgresql.ARRAY(self.item_type))
        else:
            return dialect.type_descriptor(JSON())

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if dialect.name == "postgresql":
            return value
        # For SQLite, store as JSON
        return list(value) if value else []

    def process_result_value(self, value, dialect):
        if value is None:
            return []
        return list(value) if value else []


class JSONBType(TypeDecorator):
    """JSONB type that works with both PostgreSQL and SQLite.

    Uses PostgreSQL JSONB in production, JSON in SQLite for testing.
    """

    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect: Dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(postgresql.JSONB())
        else:
            return dialect.type_descriptor(JSON())

    def process_bind_param(self, value, dialect):
        if value is None:
            return {}
        return dict(value) if value else {}

    def process_result_value(self, value, dialect):
        if value is None:
            return {}
        return dict(value) if value else {}


class INETType(TypeDecorator):
    """INET type that works with both PostgreSQL and SQLite.

    Uses PostgreSQL INET in production, String in SQLite for testing.
    """

    impl = String(45)  # Max length for IPv6
    cache_ok = True

    def load_dialect_impl(self, dialect: Dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(postgresql.INET())
        else:
            return dialect.type_descriptor(String(45))

    def process_bind_param(self, value, dialect):
        return str(value) if value else None

    def process_result_value(self, value, dialect):
        return str(value) if value else None


class UUIDType(TypeDecorator):
    """UUID type that works with both PostgreSQL and SQLite.

    Uses PostgreSQL UUID in production, String in SQLite for testing.
    """

    impl = String(36)
    cache_ok = True

    def load_dialect_impl(self, dialect: Dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(postgresql.UUID(as_uuid=True))
        else:
            return dialect.type_descriptor(String(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if dialect.name == "postgresql":
            return value
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, str):
            from uuid import UUID
            return UUID(value)
        return value
