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

from app.config import Settings, get_settings
from app.database import get_db, get_elasticsearch, get_redis


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
        self.auth_provider = "sam"
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
        self.evidence_type = evidence_type
        self.status = status
        self.source_host = "test-host"
        self.collected_at = datetime.now(timezone.utc)
        self.collected_by = "Test Collector"
        self.uploaded_by = None
        self.uploaded_at = datetime.now(timezone.utc)
        self.description = "Test evidence"
        self.evidence_metadata = {}


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


class MockSessionFactory:
    """Factory for creating mock sessions with pre-configured data."""

    def __init__(self):
        self.users = {}
        self.cases = {}
        self.evidence = {}
        self.detection_rules = {}
        self.saved_queries = {}
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

    async def execute(self, stmt):
        """Mock execute that returns appropriate results based on query."""
        stmt_str = str(stmt).lower()

        # Count queries - check for count(*) or count( patterns
        is_count_query = "count(*)" in stmt_str or "count(" in stmt_str
        if is_count_query:
            if "cases" in stmt_str:
                # Return actual count of cases in the mock, not just counter
                return MockResult([len(set(self.cases.values()))])
            if "detection_rules" in stmt_str or "detectionrule" in stmt_str:
                return MockResult([len(self.detection_rules)])
            if "evidence" in stmt_str:
                return MockResult([len(self.evidence)])
            if "saved_queries" in stmt_str or "savedquery" in stmt_str:
                return MockResult([len(self.saved_queries)])
            return MockResult([0])

        # User queries
        if "users" in stmt_str:
            for username, user in self.users.items():
                if username.lower() in stmt_str or str(user.id).lower() in stmt_str:
                    return MockResult([user])
            return MockResult([])

        # Case queries
        if "cases" in stmt_str:
            for key, case in self.cases.items():
                if key.lower() in stmt_str:
                    return MockResult([case])
            return MockResult(list(set(self.cases.values())))

        # Evidence queries
        if "evidence" in stmt_str:
            for key, ev in self.evidence.items():
                if key.lower() in stmt_str:
                    return MockResult([ev])
            return MockResult(list(self.evidence.values()))

        # Detection rules queries
        if "detection_rules" in stmt_str or "detectionrule" in stmt_str:
            for key, rule in self.detection_rules.items():
                if key.lower() in stmt_str:
                    return MockResult([rule])
            return MockResult(list(self.detection_rules.values()))

        # Saved queries
        if "saved_queries" in stmt_str or "savedquery" in stmt_str:
            for key, sq in self.saved_queries.items():
                if key.lower() in stmt_str:
                    return MockResult([sq])
            return MockResult(list(self.saved_queries.values()))

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
        # Set default status for cases
        if hasattr(obj, 'status') and obj.status is None:
            from app.models.case import CaseStatus
            obj.status = CaseStatus.NEW
        # Initialize evidence list
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
def mock_session(mock_session_factory, test_user, admin_user):
    """Mock database session pre-populated with test data."""
    mock_session_factory.add_user(test_user)
    mock_session_factory.add_user(admin_user)
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
async def admin_client(client, admin_user) -> AsyncClient:
    """Create authenticated admin test HTTP client."""
    from app.api.v1.auth import create_access_token

    token = create_access_token(
        data={"sub": admin_user.username, "user_id": str(admin_user.id)}
    )
    client.headers["Authorization"] = f"Bearer {token}"
    return client


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
