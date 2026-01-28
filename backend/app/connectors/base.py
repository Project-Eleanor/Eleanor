"""Base connector interface for data ingestion.

Defines the abstract interface for all data connectors that stream
logs into Eleanor from various sources.
"""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class ConnectorState(str, Enum):
    """Connector operational state."""

    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"
    PAUSED = "paused"


@dataclass
class ConnectorConfig:
    """Configuration for a data connector."""

    # Identity
    name: str
    connector_type: str

    # Connection
    enabled: bool = True
    poll_interval: int = 60  # seconds for polling connectors

    # Data routing
    target_index: str | None = None
    data_type: str | None = None

    # Filtering
    include_patterns: list[str] = field(default_factory=list)
    exclude_patterns: list[str] = field(default_factory=list)

    # Batching
    batch_size: int = 1000
    flush_interval: int = 10  # seconds

    # Connection-specific settings
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class ConnectorMetrics:
    """Runtime metrics for a connector."""

    events_received: int = 0
    events_processed: int = 0
    events_failed: int = 0
    bytes_received: int = 0
    last_event_at: datetime | None = None
    last_error_at: datetime | None = None
    last_error: str | None = None
    uptime_seconds: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "events_received": self.events_received,
            "events_processed": self.events_processed,
            "events_failed": self.events_failed,
            "bytes_received": self.bytes_received,
            "last_event_at": self.last_event_at.isoformat() if self.last_event_at else None,
            "last_error_at": self.last_error_at.isoformat() if self.last_error_at else None,
            "last_error": self.last_error,
            "uptime_seconds": self.uptime_seconds,
        }


@dataclass
class RawEvent:
    """Raw event from a connector before parsing."""

    data: bytes | str | dict
    source: str
    timestamp: datetime
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseConnector(ABC):
    """Abstract base class for data connectors.

    Connectors are responsible for:
    1. Connecting to external data sources
    2. Receiving/polling for events
    3. Providing raw events for parsing
    4. Tracking ingestion metrics
    """

    name: str = "base"
    description: str = "Base connector"

    def __init__(self, config: ConnectorConfig):
        """Initialize connector with configuration."""
        self.config = config
        self._state = ConnectorState.STOPPED
        self._metrics = ConnectorMetrics()
        self._started_at: datetime | None = None

    @property
    def state(self) -> ConnectorState:
        """Get current connector state."""
        return self._state

    @property
    def metrics(self) -> ConnectorMetrics:
        """Get current metrics."""
        if self._started_at:
            self._metrics.uptime_seconds = int(
                (datetime.utcnow() - self._started_at).total_seconds()
            )
        return self._metrics

    @abstractmethod
    async def connect(self) -> bool:
        """Establish connection to the data source.

        Returns:
            True if connection successful
        """
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection and cleanup resources."""
        ...

    @abstractmethod
    async def health_check(self) -> dict[str, Any]:
        """Check connector health and connectivity.

        Returns:
            Health status dictionary
        """
        ...

    @abstractmethod
    async def stream(self) -> AsyncIterator[RawEvent]:
        """Stream events from the data source.

        For push-based connectors, this listens for incoming events.
        For polling connectors, this polls at configured intervals.

        Yields:
            RawEvent objects for processing
        """
        ...

    async def start(self) -> bool:
        """Start the connector.

        Returns:
            True if started successfully
        """
        if self._state != ConnectorState.STOPPED:
            return False

        self._state = ConnectorState.STARTING

        try:
            if await self.connect():
                self._state = ConnectorState.RUNNING
                self._started_at = datetime.utcnow()
                return True
            else:
                self._state = ConnectorState.ERROR
                return False
        except Exception as e:
            self._state = ConnectorState.ERROR
            self._metrics.last_error = str(e)
            self._metrics.last_error_at = datetime.utcnow()
            return False

    async def stop(self) -> None:
        """Stop the connector."""
        if self._state not in (ConnectorState.RUNNING, ConnectorState.PAUSED):
            return

        self._state = ConnectorState.STOPPING

        try:
            await self.disconnect()
        finally:
            self._state = ConnectorState.STOPPED
            self._started_at = None

    async def pause(self) -> None:
        """Pause event collection."""
        if self._state == ConnectorState.RUNNING:
            self._state = ConnectorState.PAUSED

    async def resume(self) -> None:
        """Resume event collection."""
        if self._state == ConnectorState.PAUSED:
            self._state = ConnectorState.RUNNING

    def record_event(self, size: int = 0) -> None:
        """Record a received event for metrics."""
        self._metrics.events_received += 1
        self._metrics.bytes_received += size
        self._metrics.last_event_at = datetime.utcnow()

    def record_processed(self) -> None:
        """Record a successfully processed event."""
        self._metrics.events_processed += 1

    def record_error(self, error: str) -> None:
        """Record a processing error."""
        self._metrics.events_failed += 1
        self._metrics.last_error = error
        self._metrics.last_error_at = datetime.utcnow()

    def should_include(self, source: str) -> bool:
        """Check if a source matches include/exclude filters.

        Args:
            source: Source identifier to check

        Returns:
            True if source should be included
        """
        import fnmatch

        # Check exclude patterns first
        for pattern in self.config.exclude_patterns:
            if fnmatch.fnmatch(source, pattern):
                return False

        # If no include patterns, include all
        if not self.config.include_patterns:
            return True

        # Check include patterns
        for pattern in self.config.include_patterns:
            if fnmatch.fnmatch(source, pattern):
                return True

        return False


class PollingConnector(BaseConnector):
    """Base class for polling-based connectors.

    Provides common infrastructure for connectors that periodically
    poll an API or data source for new events.
    """

    async def stream(self) -> AsyncIterator[RawEvent]:
        """Poll for events at configured intervals."""
        import asyncio

        while self._state == ConnectorState.RUNNING:
            try:
                async for event in self.poll():
                    yield event
            except Exception as e:
                self.record_error(str(e))

            # Wait for next poll interval
            await asyncio.sleep(self.config.poll_interval)

    @abstractmethod
    async def poll(self) -> AsyncIterator[RawEvent]:
        """Poll for new events.

        Override this method to implement polling logic.

        Yields:
            RawEvent objects for new events since last poll
        """
        ...


class StreamingConnector(BaseConnector):
    """Base class for streaming/push-based connectors.

    For connectors that receive events in real-time via
    webhooks, message queues, or persistent connections.
    """

    @abstractmethod
    async def stream(self) -> AsyncIterator[RawEvent]:
        """Stream events as they arrive.

        Override this to implement the streaming receiver.
        """
        ...
