"""Pytest fixtures and configuration for Eleanor tests.

This test suite supports two modes:
1. Unit tests: Use mocked database and services (default)
2. Integration tests: Use real PostgreSQL (requires --live flag)

The models use PostgreSQL-specific types (ARRAY, JSONB, INET) which don't work
with SQLite, so unit tests use mock sessions.
"""

import asyncio
import os
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

# Set testing mode before importing app modules (affects cached settings)
os.environ["TESTING"] = "true"

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.adapters.storage import init_storage_adapter
from app.config import Settings, get_settings
from app.database import get_db, get_elasticsearch, get_redis
from app.models.user import AuthProvider


# =============================================================================
# Configuration Fixtures
# =============================================================================

@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def test_settings() -> Settings:
    """Override settings for testing."""
    return Settings(
        app_name="Eleanor-Test",
        debug=True,
        testing=True,  # Skip tenant DB lookups in tests
        database_url="postgresql://test:test@localhost:5432/test",  # Not used in unit tests
        elasticsearch_url="http://localhost:9200",
        elasticsearch_index_prefix="eleanor-test",
        redis_url="redis://localhost:6379/1",
        secret_key="test-secret-key-for-testing-only",
        jwt_expire_minutes=60,
        cors_origins=["http://localhost:4200"],
        sam_enabled=True,
        sam_allow_registration=True,
        velociraptor_enabled=False,
        iris_enabled=False,
        opencti_enabled=False,
        shuffle_enabled=False,
        timesketch_enabled=False,
        evidence_path="/tmp/eleanor-test-evidence",
    )


# =============================================================================
# Mock User Class (for unit tests without database)
# =============================================================================

class MockUser:
    """Mock user object for testing."""

    def __init__(
        self,
        id=None,
        username="testuser",
        email="testuser@example.com",
        display_name="Test User",
        is_active=True,
        is_admin=False,
        roles=None,
        password_hash=None,
        role_objects=None,
    ):
        self.id = id or uuid4()
        self.username = username
        self.email = email
        self.display_name = display_name
        self.is_active = is_active
        self.is_admin = is_admin
        self.roles = roles or ["analyst"]
        self.role_objects = role_objects or []
        self.password_hash = password_hash or self._hash_password("testpassword123")
        self.created_at = datetime.now(timezone.utc)
        self.updated_at = datetime.now(timezone.utc)
        self.auth_provider = AuthProvider.SAM
        self.last_login = None
        self.external_id = None

    @staticmethod
    def _hash_password(password: str) -> str:
        import bcrypt
        # bcrypt 5.0+ enforces 72-byte limit strictly - truncate to be safe
        password_bytes = password.encode('utf-8')[:72]
        salt = bcrypt.gensalt(rounds=4)  # Use lower rounds for faster tests
        return bcrypt.hashpw(password_bytes, salt).decode('utf-8')

    def verify_password(self, password: str) -> bool:
        import bcrypt
        # bcrypt 5.0+ enforces 72-byte limit strictly - truncate to be safe
        password_bytes = password.encode('utf-8')[:72]
        return bcrypt.checkpw(password_bytes, self.password_hash.encode('utf-8'))

    def has_permission(self, permission: str) -> bool:
        """Check if user has a specific permission."""
        # Admins have all permissions
        if self.is_admin:
            return True
        # Check role-based permissions
        for role in getattr(self, "role_objects", []):
            for perm in getattr(role, "permissions", []):
                if perm.name == "*" or perm.name == permission:
                    return True
                if perm.name.endswith(":*"):
                    scope = perm.name[:-2]
                    if permission.startswith(f"{scope}:"):
                        return True
        return False

    def get_permissions(self) -> set[str]:
        """Get all permissions for this user."""
        if self.is_admin:
            return {"*"}
        permissions = set()
        for role in getattr(self, "role_objects", []):
            for perm in getattr(role, "permissions", []):
                permissions.add(perm.name)
        return permissions


class MockCase:
    """Mock case object for testing."""

    __tablename__ = "cases"

    def __init__(
        self,
        id=None,
        case_number="ELEANOR-2026-0001",
        title="Test Case",
        description="Test description",
        severity="high",
        priority="P2",
        status="new",
        created_by=None,
        assignee_id=None,
        tags=None,
        mitre_tactics=None,
        mitre_techniques=None,
        case_metadata=None,
    ):
        self.id = id or uuid4()
        self.case_number = case_number
        self.title = title
        self.description = description
        self.severity = severity
        self.priority = priority
        self.status = status
        self.created_by = created_by
        self.assignee_id = assignee_id
        self.tags = tags or []
        self.mitre_tactics = mitre_tactics or []
        self.mitre_techniques = mitre_techniques or []
        self.case_metadata = case_metadata or {}
        self.created_at = datetime.now(timezone.utc)
        self.updated_at = datetime.now(timezone.utc)
        self.closed_at = None
        self.evidence = []
        self.assignee = None
        self.created_by_user = None


class MockDetectionRule:
    """Mock detection rule object for testing."""

    __tablename__ = "detection_rules"

    def __init__(
        self,
        id=None,
        name="Test Rule",
        description="Test detection rule",
        rule_type="query",
        severity="medium",
        status="enabled",
        query="* | LIMIT 10",
        query_language="kql",
        indices=None,
        schedule_interval=None,
        lookback_period=None,
        threshold_count=None,
        threshold_field=None,
        mitre_tactics=None,
        mitre_techniques=None,
        tags=None,
        category=None,
        data_sources=None,
        auto_create_incident=False,
        playbook_id=None,
        correlation_config=None,
        custom_fields=None,
        references=None,
        created_by=None,
        tenant_id=None,
    ):
        self.id = id or uuid4()
        self.name = name
        self.description = description
        self.rule_type = rule_type
        self.severity = severity
        self.status = status
        self.query = query
        self.query_language = query_language
        self.indices = indices or []
        self.schedule_interval = schedule_interval
        self.lookback_period = lookback_period
        self.threshold_count = threshold_count
        self.threshold_field = threshold_field
        self.mitre_tactics = mitre_tactics or []
        self.mitre_techniques = mitre_techniques or []
        self.tags = tags or []
        self.category = category
        self.data_sources = data_sources or []
        self.auto_create_incident = auto_create_incident
        self.playbook_id = playbook_id
        self.correlation_config = correlation_config
        self.custom_fields = custom_fields or {}
        self.references = references or []
        self.created_by = created_by
        self.tenant_id = tenant_id
        self.created_at = datetime.now(timezone.utc)
        self.updated_at = datetime.now(timezone.utc)
        self.last_run_at = None
        self.hit_count = 0
        self.false_positive_count = 0
        self.executions = []
        self.creator = None
        self.tenant = None


class MockEvidence:
    """Mock evidence object for testing."""

    __tablename__ = "evidence"

    def __init__(
        self,
        id=None,
        case_id=None,
        filename="test_file.exe",
        original_filename=None,
        file_path="/evidence/test_file.exe",
        file_size=1024,
        sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        sha1="da39a3ee5e6b4b0d3255bfef95601890afd80709",
        md5="d41d8cd98f00b204e9800998ecf8427e",
        evidence_type="other",
        status="ready",
    ):
        from app.models.evidence import EvidenceType, EvidenceStatus

        self.id = id or uuid4()
        self.case_id = case_id or uuid4()
        self.filename = filename
        self.original_filename = original_filename or filename
        self.file_path = file_path
        self.file_size = file_size
        self.sha256 = sha256
        self.sha1 = sha1
        self.md5 = md5
        self.mime_type = "application/octet-stream"
        # Convert string to enum if needed
        if isinstance(evidence_type, str):
            self.evidence_type = EvidenceType(evidence_type)
        else:
            self.evidence_type = evidence_type
        if isinstance(status, str):
            self.status = EvidenceStatus(status)
        else:
            self.status = status
        self.source_host = "test-host"
        self.collected_at = datetime.now(timezone.utc)
        self.collected_by = "Test Collector"
        self.uploaded_by = None
        self.uploaded_at = datetime.now(timezone.utc)
        self.description = "Test evidence"
        self.evidence_metadata = {}
        # Relationships
        self.uploader = None
        self.case = None
        self.custody_events = []


# =============================================================================
# Mock Session Fixture
# =============================================================================

class MockScalars:
    """Mock scalars result for database queries."""

    def __init__(self, items=None):
        self._items = items or []
        self._index = 0

    def first(self):
        return self._items[0] if self._items else None

    def all(self):
        return self._items

    def __iter__(self):
        return iter(self._items)


class MockResult:
    """Mock result for database execute."""

    def __init__(self, items=None):
        self._items = items or []

    def scalars(self):
        return MockScalars(self._items)

    def scalar_one_or_none(self):
        return self._items[0] if self._items else None

    def scalar(self):
        return self._items[0] if self._items else 0

    def all(self):
        """Return all items as tuples (for GROUP BY queries)."""
        return self._items


class MockSessionFactory:
    """Factory for creating mock sessions with pre-configured data."""

    def __init__(self):
        self.users = {}
        self.cases = {}
        self.evidence = {}
        self.detection_rules = {}
        self.saved_queries = {}
        self.custody_events = {}
        self.added_items = []
        self.case_counter = 0

    def add_user(self, user):
        self.users[user.username] = user
        self.users[str(user.id)] = user

    def add_case(self, case):
        self.cases[str(case.id)] = case
        if hasattr(case, 'case_number') and case.case_number:
            self.cases[case.case_number] = case

    def add_evidence(self, evidence):
        self.evidence[str(evidence.id)] = evidence

    def add_rule(self, rule):
        self.detection_rules[str(rule.id)] = rule

    def add_saved_query(self, query):
        self.saved_queries[str(query.id)] = query

    def add_custody_event(self, event):
        self.custody_events[str(event.id)] = event

    def _extract_pagination(self, stmt):
        """Extract limit and offset from SQLAlchemy statement."""
        limit = None
        offset = None
        try:
            # Try to get limit and offset from the statement
            if hasattr(stmt, '_limit_clause') and stmt._limit_clause is not None:
                limit = stmt._limit_clause.value if hasattr(stmt._limit_clause, 'value') else int(stmt._limit_clause)
            if hasattr(stmt, '_offset_clause') and stmt._offset_clause is not None:
                offset = stmt._offset_clause.value if hasattr(stmt._offset_clause, 'value') else int(stmt._offset_clause)
        except Exception:
            pass
        return limit, offset

    def _extract_filters(self, stmt):
        """Extract filter parameters from SQLAlchemy statement."""
        filters = {}
        try:
            compiled = stmt.compile()
            params = compiled.params
            stmt_str = str(stmt).lower()

            # Map parameter names to filter fields
            for key, value in params.items():
                if value is not None:
                    # Check if this is a search pattern (contains % wildcards)
                    if isinstance(value, str) and value.startswith('%') and value.endswith('%'):
                        # Extract the search term from ILIKE pattern (%term%)
                        search_term = value.strip('%')
                        filters['search'] = search_term
                    elif isinstance(value, str) and value.endswith('%') and not value.startswith('%'):
                        # This is a prefix LIKE pattern (term%) - used for case numbers
                        import re
                        clean_key = re.sub(r'_\d+$', '', key)
                        filters[f'{clean_key}_prefix'] = value.rstrip('%')
                    else:
                        # Normalize key name (remove _1, _2 suffixes added by SQLAlchemy)
                        import re
                        clean_key = re.sub(r'_\d+$', '', key)
                        filters[clean_key] = value

        except Exception:
            pass
        return filters

    def _apply_filters(self, items, filters, table_type):
        """Apply filters to a list of items based on table type."""
        if not filters:
            return items

        filtered = []
        for item in items:
            match = True
            for field, value in filters.items():
                # Handle special text search fields (used with ILIKE in actual queries)
                if field == 'search':
                    # Search across text fields based on table type
                    search_term = str(value).lower()
                    found = False
                    if table_type == 'cases':
                        for attr in ['title', 'description', 'case_number']:
                            attr_val = getattr(item, attr, '')
                            if attr_val and search_term in str(attr_val).lower():
                                found = True
                                break
                        # Also check tags if present
                        tags = getattr(item, 'tags', []) or []
                        for tag in tags:
                            if search_term in str(tag).lower():
                                found = True
                                break
                    elif table_type == 'evidence':
                        for attr in ['filename', 'original_filename', 'description']:
                            attr_val = getattr(item, attr, '')
                            if attr_val and search_term in str(attr_val).lower():
                                found = True
                                break
                    elif table_type == 'saved_queries':
                        for attr in ['name', 'description', 'query']:
                            attr_val = getattr(item, attr, '')
                            if attr_val and search_term in str(attr_val).lower():
                                found = True
                                break
                    if not found:
                        match = False
                        break
                    continue

                # Handle prefix filters (e.g., case_number_prefix)
                if field.endswith('_prefix'):
                    actual_field = field[:-7]  # Remove '_prefix' suffix
                    item_value = getattr(item, actual_field, None)
                    if item_value is None or not str(item_value).startswith(str(value)):
                        match = False
                        break
                    continue

                item_value = getattr(item, field, None)
                if item_value is None:
                    continue
                # Handle enum comparisons
                if hasattr(item_value, 'value'):
                    item_value = item_value.value
                if hasattr(value, 'value'):
                    value = value.value
                # Compare values
                if str(item_value).lower() != str(value).lower():
                    match = False
                    break
            if match:
                filtered.append(item)
        return filtered

    def _apply_pagination(self, items, limit, offset):
        """Apply pagination to a list of items."""
        if offset:
            items = items[offset:]
        if limit:
            items = items[:limit]
        return items

    async def execute(self, stmt):
        """Mock execute that returns appropriate results based on query."""
        stmt_str = str(stmt).lower()
        limit, offset = self._extract_pagination(stmt)

        # GROUP BY queries - return tuples for aggregation
        is_group_by = "group by" in stmt_str
        if is_group_by and ("detection_rules" in stmt_str or "detectionrule" in stmt_str):
            # For GROUP BY status/severity queries, return mock enum/count tuples
            from collections import Counter
            if "status" in stmt_str:
                status_counts = Counter(r.status for r in self.detection_rules.values())
                # Create enum-like mock objects for the grouping
                class MockEnum:
                    def __init__(self, value):
                        self.value = value
                return MockResult([(MockEnum(status), count) for status, count in status_counts.items()])
            if "severity" in stmt_str:
                severity_counts = Counter(r.severity for r in self.detection_rules.values())
                class MockEnum:
                    def __init__(self, value):
                        self.value = value
                return MockResult([(MockEnum(sev), count) for sev, count in severity_counts.items()])
            return MockResult([])

        # Count queries - check for count(*) or count( patterns
        is_count_query = "count(*)" in stmt_str or "count(" in stmt_str
        if is_count_query:
            filters = self._extract_filters(stmt)
            if "cases" in stmt_str:
                items = list(set(self.cases.values()))
                items = self._apply_filters(items, filters, 'cases')
                return MockResult([len(items)])
            if "detection_rules" in stmt_str or "detectionrule" in stmt_str:
                return MockResult([len(self.detection_rules)])
            if "evidence" in stmt_str:
                items = list(self.evidence.values())
                items = self._apply_filters(items, filters, 'evidence')
                return MockResult([len(items)])
            if "saved_queries" in stmt_str or "savedquery" in stmt_str:
                return MockResult([len(self.saved_queries)])
            return MockResult([0])

        # SUM queries for detection rules
        if "sum(" in stmt_str and ("detection_rules" in stmt_str or "detectionrule" in stmt_str):
            total = sum(getattr(r, 'hit_count', 0) or 0 for r in self.detection_rules.values())
            return MockResult([total])

        # User queries
        if "users" in stmt_str:
            # Try to extract bind parameters from the statement
            try:
                # SQLAlchemy statements may have compile() method
                compiled = stmt.compile()
                params = compiled.params
                # Check for username or id in params
                for key, value in params.items():
                    if value and str(value).lower() in [u.username.lower() for u in set(self.users.values())]:
                        for user in set(self.users.values()):
                            if user.username.lower() == str(value).lower():
                                return MockResult([user])
                    if value and str(value).lower() in [str(u.id).lower() for u in set(self.users.values())]:
                        for user in set(self.users.values()):
                            if str(user.id).lower() == str(value).lower():
                                return MockResult([user])
            except Exception:
                pass
            # Fall back to checking query string
            for username, user in self.users.items():
                if username.lower() in stmt_str or str(user.id).lower() in stmt_str:
                    return MockResult([user])
            return MockResult([])

        # Case queries
        if "cases" in stmt_str:
            # Check for specific case ID lookup first
            filters = self._extract_filters(stmt)
            for key, case in self.cases.items():
                if key.lower() in stmt_str:
                    return MockResult([case])
            items = list(set(self.cases.values()))
            # Apply filters (status, severity, etc.)
            items = self._apply_filters(items, filters, 'cases')
            items = self._apply_pagination(items, limit, offset)
            return MockResult(items)

        # Custody events queries (must be before evidence check since contains "evidence")
        if "custody_events" in stmt_str or "custodyevent" in stmt_str:
            # Filter by evidence_id if present in parameters
            try:
                compiled = stmt.compile()
                params = compiled.params
                for key, value in params.items():
                    if value:
                        # Return custody events for this evidence_id
                        matching_events = [
                            e for e in self.custody_events.values()
                            if str(getattr(e, 'evidence_id', '')) == str(value)
                        ]
                        return MockResult(matching_events)
            except Exception:
                pass
            return MockResult(list(self.custody_events.values()))

        # Evidence queries
        if "evidence" in stmt_str:
            # Check for specific evidence ID lookup first
            filters = self._extract_filters(stmt)
            for key, ev in self.evidence.items():
                if key.lower() in stmt_str:
                    return MockResult([ev])
            items = list(self.evidence.values())
            # Apply filters (evidence_type, status, case_id, etc.)
            items = self._apply_filters(items, filters, 'evidence')
            items = self._apply_pagination(items, limit, offset)
            return MockResult(items)

        # Detection rules queries
        if "detection_rules" in stmt_str or "detectionrule" in stmt_str:
            for key, rule in self.detection_rules.items():
                if key.lower() in stmt_str:
                    return MockResult([rule])
            items = list(self.detection_rules.values())
            items = self._apply_pagination(items, limit, offset)
            return MockResult(items)

        # Saved queries
        if "saved_queries" in stmt_str or "savedquery" in stmt_str:
            filters = self._extract_filters(stmt)
            for key, sq in self.saved_queries.items():
                if key.lower() in stmt_str:
                    return MockResult([sq])
            items = list(self.saved_queries.values())
            # Apply filters (category, is_public, etc.)
            items = self._apply_filters(items, filters, 'saved_queries')
            items = self._apply_pagination(items, limit, offset)
            return MockResult(items)

        # Default empty result
        return MockResult([])

    async def commit(self):
        """Commit persists added items to the mock storage."""
        for obj in self.added_items:
            tablename = getattr(obj, '__tablename__', None) or getattr(type(obj), '__tablename__', None)
            if tablename == 'cases':
                self.case_counter += 1
                self.add_case(obj)
            elif tablename == 'evidence':
                self.add_evidence(obj)
            elif tablename == 'users':
                self.add_user(obj)
            elif tablename == 'detection_rules':
                self.add_rule(obj)
            elif tablename == 'saved_queries':
                self.add_saved_query(obj)
            elif tablename == 'custody_events':
                self.add_custody_event(obj)
        self.added_items = []

    async def refresh(self, obj):
        """Refresh populates server-generated defaults on the object."""
        now = datetime.now(timezone.utc)

        # Set id if not set
        if not hasattr(obj, 'id') or obj.id is None:
            obj.id = uuid4()

        # Set timestamps
        if hasattr(obj, 'created_at') and obj.created_at is None:
            obj.created_at = now
        if hasattr(obj, 'updated_at'):
            obj.updated_at = now

        # Set case defaults
        if hasattr(obj, 'status') and obj.status is None:
            from app.models.case import CaseStatus
            obj.status = CaseStatus.NEW

        # Set evidence list if not present
        if hasattr(obj, 'evidence') and not isinstance(obj.evidence, list):
            obj.evidence = []

    def add(self, obj):
        """Stage object for commit."""
        # Set id immediately if not set
        if not hasattr(obj, 'id') or obj.id is None:
            obj.id = uuid4()
        # Set timestamps immediately
        now = datetime.now(timezone.utc)
        if hasattr(obj, 'created_at') and obj.created_at is None:
            obj.created_at = now
        if hasattr(obj, 'updated_at') and obj.updated_at is None:
            obj.updated_at = now
        # Set default status for cases (only for mock objects)
        tablename = getattr(obj, '__tablename__', None) or getattr(type(obj), '__tablename__', None)
        if tablename == 'cases' and hasattr(obj, 'status') and obj.status is None:
            from app.models.case import CaseStatus
            obj.status = CaseStatus.NEW
        # Initialize evidence list (only for mock Case objects, not SQLAlchemy models)
        if tablename == 'cases' and isinstance(obj, MockCase):
            if hasattr(obj, 'evidence') and not isinstance(getattr(obj, 'evidence', None), list):
                obj.evidence = []
        self.added_items.append(obj)

    async def delete(self, obj):
        """Remove object from mock storage."""
        tablename = getattr(obj, '__tablename__', None) or getattr(type(obj), '__tablename__', None)
        obj_id = str(obj.id) if hasattr(obj, 'id') else None
        if obj_id:
            if tablename == 'cases':
                self.cases.pop(obj_id, None)
                if hasattr(obj, 'case_number'):
                    self.cases.pop(obj.case_number, None)
            elif tablename == 'evidence':
                self.evidence.pop(obj_id, None)
            elif tablename == 'users':
                self.users.pop(obj_id, None)
            elif tablename == 'detection_rules':
                self.detection_rules.pop(obj_id, None)

    async def rollback(self):
        self.added_items = []

    async def close(self):
        pass

    async def flush(self):
        """Flush pending changes (same as commit for mock)."""
        await self.commit()

    async def get(self, model, id):
        """Mock session.get() for direct ID lookups."""
        id_str = str(id)
        tablename = getattr(model, '__tablename__', None)
        if tablename == "users":
            return self.users.get(id_str)
        elif tablename == "cases":
            return self.cases.get(id_str)
        elif tablename == "evidence":
            return self.evidence.get(id_str)
        elif tablename == "detection_rules":
            return self.detection_rules.get(id_str)
        return None


@pytest.fixture
def mock_session_factory():
    """Create a mock session factory for configuring test data."""
    return MockSessionFactory()


@pytest.fixture
def mock_session(mock_session_factory, test_user, admin_user, inactive_user):
    """Mock database session pre-populated with test data."""
    mock_session_factory.add_user(test_user)
    mock_session_factory.add_user(admin_user)
    mock_session_factory.add_user(inactive_user)
    return mock_session_factory


@pytest.fixture
def mock_session_with_case(mock_session_factory, test_user, admin_user, test_case):
    """Mock database session with test case pre-populated."""
    mock_session_factory.add_user(test_user)
    mock_session_factory.add_user(admin_user)
    mock_session_factory.add_case(test_case)
    return mock_session_factory


@pytest.fixture
def mock_session_with_cases(mock_session_factory, test_user, admin_user, test_cases):
    """Mock database session with multiple test cases pre-populated."""
    mock_session_factory.add_user(test_user)
    mock_session_factory.add_user(admin_user)
    for case in test_cases:
        mock_session_factory.add_case(case)
    return mock_session_factory


@pytest.fixture
def mock_session_with_evidence(mock_session_factory, test_user, admin_user, test_case, test_evidence):
    """Mock database session with test evidence pre-populated."""
    mock_session_factory.add_user(test_user)
    mock_session_factory.add_user(admin_user)
    mock_session_factory.add_case(test_case)
    mock_session_factory.add_evidence(test_evidence)
    # Add any custody events from the evidence
    for event in test_evidence.custody_events:
        mock_session_factory.add_custody_event(event)
    return mock_session_factory


@pytest_asyncio.fixture
async def test_session(mock_session):
    """Provide mock session as test_session for compatibility."""
    yield mock_session


# =============================================================================
# Application Fixtures
# =============================================================================

def _create_app_fixture(mock_session_fixture):
    """Factory to create app fixture with specified mock session."""
    async def _app_fixture(test_settings, mock_elasticsearch, mock_redis, request) -> FastAPI:
        from app.main import app as main_app

        # Initialize storage adapter for tests
        await init_storage_adapter(test_settings)

        # Get the mock session from the provided fixture
        mock_session = request.getfixturevalue(mock_session_fixture)

        # Override dependencies
        async def override_get_db():
            yield mock_session

        def override_get_settings():
            return test_settings

        async def override_get_elasticsearch():
            return mock_elasticsearch

        async def override_get_redis():
            return mock_redis

        main_app.dependency_overrides[get_db] = override_get_db
        main_app.dependency_overrides[get_settings] = override_get_settings
        main_app.dependency_overrides[get_elasticsearch] = override_get_elasticsearch
        main_app.dependency_overrides[get_redis] = override_get_redis

        yield main_app

        # Clean up overrides
        main_app.dependency_overrides.clear()

    return _app_fixture


@pytest_asyncio.fixture
async def app(test_settings, mock_session, mock_elasticsearch, mock_redis) -> FastAPI:
    """Create test FastAPI application with mocked dependencies."""
    from app.main import app as main_app

    # Initialize storage adapter for tests
    await init_storage_adapter(test_settings)

    # Override dependencies
    async def override_get_db():
        yield mock_session

    def override_get_settings():
        return test_settings

    async def override_get_elasticsearch():
        return mock_elasticsearch

    async def override_get_redis():
        return mock_redis

    main_app.dependency_overrides[get_db] = override_get_db
    main_app.dependency_overrides[get_settings] = override_get_settings
    main_app.dependency_overrides[get_elasticsearch] = override_get_elasticsearch
    main_app.dependency_overrides[get_redis] = override_get_redis

    yield main_app

    # Clean up overrides
    main_app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def app_with_case(test_settings, mock_session_with_case, mock_elasticsearch, mock_redis) -> FastAPI:
    """Create test FastAPI application with test case pre-populated."""
    from app.main import app as main_app

    # Initialize storage adapter for tests
    await init_storage_adapter(test_settings)

    # Override dependencies
    async def override_get_db():
        yield mock_session_with_case

    def override_get_settings():
        return test_settings

    async def override_get_elasticsearch():
        return mock_elasticsearch

    async def override_get_redis():
        return mock_redis

    main_app.dependency_overrides[get_db] = override_get_db
    main_app.dependency_overrides[get_settings] = override_get_settings
    main_app.dependency_overrides[get_elasticsearch] = override_get_elasticsearch
    main_app.dependency_overrides[get_redis] = override_get_redis

    yield main_app

    # Clean up overrides
    main_app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def app_with_cases(test_settings, mock_session_with_cases, mock_elasticsearch, mock_redis) -> FastAPI:
    """Create test FastAPI application with multiple test cases pre-populated."""
    from app.main import app as main_app

    # Initialize storage adapter for tests
    await init_storage_adapter(test_settings)

    # Override dependencies
    async def override_get_db():
        yield mock_session_with_cases

    def override_get_settings():
        return test_settings

    async def override_get_elasticsearch():
        return mock_elasticsearch

    async def override_get_redis():
        return mock_redis

    main_app.dependency_overrides[get_db] = override_get_db
    main_app.dependency_overrides[get_settings] = override_get_settings
    main_app.dependency_overrides[get_elasticsearch] = override_get_elasticsearch
    main_app.dependency_overrides[get_redis] = override_get_redis

    yield main_app

    # Clean up overrides
    main_app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def app_with_evidence(test_settings, mock_session_with_evidence, mock_elasticsearch, mock_redis) -> FastAPI:
    """Create test FastAPI application with test evidence pre-populated."""
    from app.main import app as main_app

    # Initialize storage adapter for tests
    await init_storage_adapter(test_settings)

    # Override dependencies
    async def override_get_db():
        yield mock_session_with_evidence

    def override_get_settings():
        return test_settings

    async def override_get_elasticsearch():
        return mock_elasticsearch

    async def override_get_redis():
        return mock_redis

    main_app.dependency_overrides[get_db] = override_get_db
    main_app.dependency_overrides[get_settings] = override_get_settings
    main_app.dependency_overrides[get_elasticsearch] = override_get_elasticsearch
    main_app.dependency_overrides[get_redis] = override_get_redis

    yield main_app

    # Clean up overrides
    main_app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client(app) -> AsyncGenerator[AsyncClient, None]:
    """Create test HTTP client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest_asyncio.fixture
async def authenticated_client(client, test_user) -> AsyncClient:
    """Create authenticated test HTTP client."""
    from app.api.v1.auth import create_access_token

    token = create_access_token(
        data={"sub": test_user.username, "user_id": str(test_user.id)}
    )
    client.headers["Authorization"] = f"Bearer {token}"
    return client


@pytest_asyncio.fixture
async def admin_client(app, admin_user) -> AsyncGenerator[AsyncClient, None]:
    """Create authenticated admin test HTTP client (separate from regular client)."""
    from app.api.v1.auth import create_access_token

    token = create_access_token(
        data={"sub": admin_user.username, "user_id": str(admin_user.id)}
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as admin_cli:
        admin_cli.headers["Authorization"] = f"Bearer {token}"
        yield admin_cli


# Clients with pre-populated data
@pytest_asyncio.fixture
async def client_with_case(app_with_case) -> AsyncGenerator[AsyncClient, None]:
    """Create test HTTP client with case data."""
    transport = ASGITransport(app=app_with_case)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest_asyncio.fixture
async def authenticated_client_with_case(client_with_case, test_user) -> AsyncClient:
    """Create authenticated test HTTP client with case data."""
    from app.api.v1.auth import create_access_token

    token = create_access_token(
        data={"sub": test_user.username, "user_id": str(test_user.id)}
    )
    client_with_case.headers["Authorization"] = f"Bearer {token}"
    return client_with_case


@pytest_asyncio.fixture
async def client_with_cases(app_with_cases) -> AsyncGenerator[AsyncClient, None]:
    """Create test HTTP client with multiple cases data."""
    transport = ASGITransport(app=app_with_cases)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest_asyncio.fixture
async def authenticated_client_with_cases(client_with_cases, test_user) -> AsyncClient:
    """Create authenticated test HTTP client with multiple cases data."""
    from app.api.v1.auth import create_access_token

    token = create_access_token(
        data={"sub": test_user.username, "user_id": str(test_user.id)}
    )
    client_with_cases.headers["Authorization"] = f"Bearer {token}"
    return client_with_cases


@pytest_asyncio.fixture
async def client_with_evidence(app_with_evidence) -> AsyncGenerator[AsyncClient, None]:
    """Create test HTTP client with evidence data."""
    transport = ASGITransport(app=app_with_evidence)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest_asyncio.fixture
async def authenticated_client_with_evidence(client_with_evidence, test_user) -> AsyncClient:
    """Create authenticated test HTTP client with evidence data."""
    from app.api.v1.auth import create_access_token

    token = create_access_token(
        data={"sub": test_user.username, "user_id": str(test_user.id)}
    )
    client_with_evidence.headers["Authorization"] = f"Bearer {token}"
    return client_with_evidence


# =============================================================================
# User Fixtures
# =============================================================================

@pytest.fixture
def test_user() -> MockUser:
    """Create test user."""
    return MockUser(
        username="testuser",
        email="testuser@example.com",
        display_name="Test User",
        is_active=True,
        is_admin=False,
        roles=["analyst"],
    )


@pytest.fixture
def admin_user() -> MockUser:
    """Create admin user."""
    return MockUser(
        username="admin",
        email="admin@example.com",
        display_name="Admin User",
        is_active=True,
        is_admin=True,
        roles=["admin"],
    )


@pytest.fixture
def inactive_user() -> MockUser:
    """Create inactive user for testing."""
    return MockUser(
        username="inactive",
        email="inactive@example.com",
        display_name="Inactive User",
        is_active=False,
        is_admin=False,
        roles=["analyst"],
        password_hash=None,  # Will use default "testpassword123"
    )


# =============================================================================
# Case Fixtures
# =============================================================================

@pytest.fixture
def test_case(test_user) -> MockCase:
    """Create test case."""
    return MockCase(
        case_number="ELEANOR-2026-0001",
        title="Test Security Incident",
        description="A test security incident for unit testing",
        severity="high",
        priority="P2",
        status="new",
        created_by=test_user.id,
        tags=["test", "malware"],
        mitre_tactics=["TA0001"],
        mitre_techniques=["T1566"],
        case_metadata={"source": "test"},
    )


@pytest.fixture
def test_cases(test_user) -> list[MockCase]:
    """Create multiple test cases."""
    cases = []
    statuses = ["new", "investigating", "closed"]
    severities = ["critical", "high", "medium"]

    for i in range(3):
        case = MockCase(
            case_number=f"ELEANOR-2026-{i+2:04d}",
            title=f"Test Case {i+1}",
            description=f"Test case number {i+1}",
            severity=severities[i],
            priority="P2",
            status=statuses[i],
            created_by=test_user.id,
            tags=[f"tag{i}"],
        )
        cases.append(case)

    return cases


# =============================================================================
# Evidence Fixtures
# =============================================================================

@pytest.fixture
def test_evidence(test_case, test_user) -> MockEvidence:
    """Create test evidence."""
    evidence = MockEvidence(
        case_id=test_case.id,
        filename="malware_sample.exe",
        original_filename="suspicious_file.exe",
        file_path="/evidence/malware_sample.exe",
        file_size=1024000,
        evidence_type="malware",
        status="ready",
    )
    evidence.uploaded_by = test_user.id
    return evidence


@pytest.fixture
def test_custody_event(test_evidence, test_user):
    """Create test custody event."""
    from app.models.evidence import CustodyAction, CustodyEvent

    event = CustodyEvent(
        id=uuid4(),
        evidence_id=test_evidence.id,
        action=CustodyAction.UPLOADED,
        actor_id=test_user.id,
        actor_name=test_user.display_name,
        ip_address="127.0.0.1",
        user_agent="test-agent",
        details={"source": "test"},
    )
    # Add to mock evidence's custody_events list
    test_evidence.custody_events.append(event)
    return event


# =============================================================================
# Mock Service Fixtures
# =============================================================================

@pytest.fixture
def mock_elasticsearch():
    """Mock Elasticsearch client."""
    mock_es = AsyncMock()

    # Mock common operations
    mock_es.search = AsyncMock(return_value={
        "hits": {
            "total": {"value": 0, "relation": "eq"},
            "hits": [],
        },
        "took": 1,
    })

    mock_es.index = AsyncMock(return_value={
        "_id": str(uuid4()),
        "_index": "test-index",
        "result": "created",
    })

    mock_es.delete = AsyncMock(return_value={"result": "deleted"})

    mock_es.indices = MagicMock()
    mock_es.indices.exists = AsyncMock(return_value=True)
    mock_es.indices.create = AsyncMock(return_value={"acknowledged": True})
    mock_es.indices.delete = AsyncMock(return_value={"acknowledged": True})
    mock_es.indices.put_index_template = AsyncMock(return_value={"acknowledged": True})

    mock_es.cluster = MagicMock()
    mock_es.cluster.health = AsyncMock(return_value={
        "cluster_name": "test-cluster",
        "status": "green",
        "number_of_nodes": 1,
    })

    mock_es.close = AsyncMock()

    return mock_es


@pytest.fixture
def mock_redis():
    """Mock Redis client."""
    mock_redis = AsyncMock()

    store = {}

    async def mock_get(key):
        return store.get(key)

    async def mock_set(key, value, ex=None):
        store[key] = value
        return True

    async def mock_delete(key):
        return store.pop(key, None) is not None

    async def mock_ping():
        return True

    mock_redis.get = mock_get
    mock_redis.set = mock_set
    mock_redis.delete = mock_delete
    mock_redis.ping = mock_ping
    mock_redis.close = AsyncMock()

    return mock_redis


# =============================================================================
# Adapter Mock Fixtures
# =============================================================================

@pytest.fixture
def mock_velociraptor_adapter():
    """Mock Velociraptor adapter."""
    from tests.mocks.velociraptor import MockVelociraptorAdapter
    return MockVelociraptorAdapter()


@pytest.fixture
def mock_iris_adapter():
    """Mock IRIS adapter."""
    from tests.mocks.iris import MockIRISAdapter
    return MockIRISAdapter()


@pytest.fixture
def mock_opencti_adapter():
    """Mock OpenCTI adapter."""
    from tests.mocks.opencti import MockOpenCTIAdapter
    return MockOpenCTIAdapter()


@pytest.fixture
def mock_shuffle_adapter():
    """Mock Shuffle adapter."""
    from tests.mocks.shuffle import MockShuffleAdapter
    return MockShuffleAdapter()


@pytest.fixture
def mock_timesketch_adapter():
    """Mock Timesketch adapter."""
    from tests.mocks.timesketch import MockTimesketchAdapter
    return MockTimesketchAdapter()


@pytest.fixture
def mock_all_adapters(
    mock_velociraptor_adapter,
    mock_iris_adapter,
    mock_opencti_adapter,
    mock_shuffle_adapter,
    mock_timesketch_adapter,
):
    """Provide all mock adapters."""
    return {
        "velociraptor": mock_velociraptor_adapter,
        "iris": mock_iris_adapter,
        "opencti": mock_opencti_adapter,
        "shuffle": mock_shuffle_adapter,
        "timesketch": mock_timesketch_adapter,
    }


# =============================================================================
# Utility Fixtures
# =============================================================================

@pytest.fixture
def sample_jwt_token(test_user):
    """Generate sample JWT token."""
    from app.api.v1.auth import create_access_token

    return create_access_token(
        data={"sub": test_user.username, "user_id": str(test_user.id)}
    )


@pytest.fixture
def sample_case_data() -> dict:
    """Sample case creation data."""
    return {
        "title": "New Test Case",
        "description": "A case for testing purposes",
        "severity": "high",
        "priority": "P2",
        "tags": ["test"],
        "mitre_tactics": ["TA0001"],
        "mitre_techniques": ["T1566"],
    }


@pytest.fixture
def sample_evidence_data() -> dict:
    """Sample evidence creation data."""
    return {
        "filename": "test_file.txt",
        "file_size": 1024,
        "evidence_type": "logs",
        "source_host": "test-host",
        "description": "Test evidence file",
    }


# =============================================================================
# Pytest Configuration
# =============================================================================

def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line("markers", "unit: Unit tests (fast, mocked)")
    config.addinivalue_line("markers", "integration: Integration tests (require services)")
    config.addinivalue_line("markers", "e2e: End-to-end tests (full workflow)")
    config.addinivalue_line("markers", "health: Health check tests")
    config.addinivalue_line("markers", "slow: Slow running tests")


def pytest_collection_modifyitems(config, items):
    """Modify test collection based on markers."""
    # Skip integration tests unless --live flag is provided
    if not config.getoption("--live", default=False):
        skip_integration = pytest.mark.skip(reason="Need --live option to run integration tests")
        for item in items:
            if "integration" in item.keywords:
                item.add_marker(skip_integration)


def pytest_addoption(parser):
    """Add custom command line options."""
    parser.addoption(
        "--live",
        action="store_true",
        default=False,
        help="Run integration tests against live services",
    )
    parser.addoption(
        "--all",
        action="store_true",
        default=False,
        help="Run all tests including integration and e2e",
    )
