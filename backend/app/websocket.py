"""WebSocket manager for real-time updates."""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    """WebSocket event types."""

    # Connection events
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    PING = "ping"
    PONG = "pong"

    # Case events
    CASE_CREATED = "case_created"
    CASE_UPDATED = "case_updated"
    CASE_DELETED = "case_deleted"
    CASE_ASSIGNED = "case_assigned"

    # Evidence events
    EVIDENCE_UPLOADED = "evidence_uploaded"
    EVIDENCE_PROCESSED = "evidence_processed"

    # Workflow events
    WORKFLOW_STARTED = "workflow_started"
    WORKFLOW_COMPLETED = "workflow_completed"
    WORKFLOW_FAILED = "workflow_failed"
    APPROVAL_REQUIRED = "approval_required"
    APPROVAL_RESOLVED = "approval_resolved"

    # Alert events
    ALERT_CREATED = "alert_created"
    DETECTION_HIT = "detection_hit"

    # System events
    NOTIFICATION = "notification"
    SYSTEM_ALERT = "system_alert"
    INTEGRATION_STATUS = "integration_status"


@dataclass
class WebSocketMessage:
    """WebSocket message structure."""

    event_type: EventType
    data: dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.utcnow)
    message_id: str = field(default_factory=lambda: str(uuid4()))

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.message_id,
            "type": self.event_type.value,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
        }

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), default=str)


@dataclass
class Connection:
    """WebSocket connection with metadata."""

    websocket: WebSocket
    user_id: str | None = None
    subscriptions: set[str] = field(default_factory=set)
    connected_at: datetime = field(default_factory=datetime.utcnow)


class ConnectionManager:
    """Manages WebSocket connections and message broadcasting."""

    def __init__(self):
        # All active connections: connection_id -> Connection
        self.active_connections: dict[str, Connection] = {}
        # User connections: user_id -> set of connection_ids
        self.user_connections: dict[str, set[str]] = {}
        # Topic subscriptions: topic -> set of connection_ids
        self.topic_subscriptions: dict[str, set[str]] = {}
        # Lock for thread safety
        self._lock = asyncio.Lock()

    async def connect(
        self, websocket: WebSocket, user_id: str | None = None
    ) -> str:
        """Accept a new WebSocket connection."""
        await websocket.accept()
        connection_id = str(uuid4())

        async with self._lock:
            self.active_connections[connection_id] = Connection(
                websocket=websocket,
                user_id=user_id,
            )

            if user_id:
                if user_id not in self.user_connections:
                    self.user_connections[user_id] = set()
                self.user_connections[user_id].add(connection_id)

        logger.info(
            "WebSocket connected: %s (user: %s)", connection_id, user_id or "anonymous"
        )

        # Send connection confirmation
        await self.send_personal(
            connection_id,
            WebSocketMessage(
                event_type=EventType.CONNECTED,
                data={"connection_id": connection_id},
            ),
        )

        return connection_id

    async def disconnect(self, connection_id: str) -> None:
        """Disconnect a WebSocket connection."""
        async with self._lock:
            if connection_id not in self.active_connections:
                return

            connection = self.active_connections[connection_id]

            # Remove from user connections
            if connection.user_id and connection.user_id in self.user_connections:
                self.user_connections[connection.user_id].discard(connection_id)
                if not self.user_connections[connection.user_id]:
                    del self.user_connections[connection.user_id]

            # Remove from topic subscriptions
            for topic in list(connection.subscriptions):
                if topic in self.topic_subscriptions:
                    self.topic_subscriptions[topic].discard(connection_id)
                    if not self.topic_subscriptions[topic]:
                        del self.topic_subscriptions[topic]

            del self.active_connections[connection_id]

        logger.info("WebSocket disconnected: %s", connection_id)

    async def subscribe(self, connection_id: str, topic: str) -> None:
        """Subscribe a connection to a topic."""
        async with self._lock:
            if connection_id not in self.active_connections:
                return

            self.active_connections[connection_id].subscriptions.add(topic)

            if topic not in self.topic_subscriptions:
                self.topic_subscriptions[topic] = set()
            self.topic_subscriptions[topic].add(connection_id)

        logger.debug("Connection %s subscribed to %s", connection_id, topic)

    async def unsubscribe(self, connection_id: str, topic: str) -> None:
        """Unsubscribe a connection from a topic."""
        async with self._lock:
            if connection_id in self.active_connections:
                self.active_connections[connection_id].subscriptions.discard(topic)

            if topic in self.topic_subscriptions:
                self.topic_subscriptions[topic].discard(connection_id)
                if not self.topic_subscriptions[topic]:
                    del self.topic_subscriptions[topic]

    async def send_personal(
        self, connection_id: str, message: WebSocketMessage
    ) -> bool:
        """Send a message to a specific connection."""
        if connection_id not in self.active_connections:
            return False

        try:
            await self.active_connections[connection_id].websocket.send_text(
                message.to_json()
            )
            return True
        except Exception as e:
            logger.warning("Failed to send message to %s: %s", connection_id, e)
            await self.disconnect(connection_id)
            return False

    async def send_to_user(self, user_id: str, message: WebSocketMessage) -> int:
        """Send a message to all connections of a specific user."""
        if user_id not in self.user_connections:
            return 0

        sent_count = 0
        connection_ids = list(self.user_connections.get(user_id, set()))

        for connection_id in connection_ids:
            if await self.send_personal(connection_id, message):
                sent_count += 1

        return sent_count

    async def broadcast(self, message: WebSocketMessage) -> int:
        """Broadcast a message to all connected clients."""
        sent_count = 0
        connection_ids = list(self.active_connections.keys())

        for connection_id in connection_ids:
            if await self.send_personal(connection_id, message):
                sent_count += 1

        return sent_count

    async def broadcast_to_topic(self, topic: str, message: WebSocketMessage) -> int:
        """Broadcast a message to all subscribers of a topic."""
        if topic not in self.topic_subscriptions:
            return 0

        sent_count = 0
        connection_ids = list(self.topic_subscriptions.get(topic, set()))

        for connection_id in connection_ids:
            if await self.send_personal(connection_id, message):
                sent_count += 1

        return sent_count

    def get_connection_count(self) -> int:
        """Get the number of active connections."""
        return len(self.active_connections)

    def get_user_connection_count(self, user_id: str) -> int:
        """Get the number of active connections for a user."""
        return len(self.user_connections.get(user_id, set()))


# Global connection manager instance
manager = ConnectionManager()


def get_manager() -> ConnectionManager:
    """Get the global connection manager."""
    return manager


# =============================================================================
# Helper functions for publishing events
# =============================================================================


async def publish_case_event(
    event_type: EventType,
    case_id: str,
    data: dict[str, Any],
    user_id: str | None = None,
) -> None:
    """Publish a case-related event."""
    message = WebSocketMessage(
        event_type=event_type,
        data={"case_id": case_id, **data},
    )

    # Broadcast to case topic subscribers
    await manager.broadcast_to_topic(f"case:{case_id}", message)

    # Also broadcast to general cases topic
    await manager.broadcast_to_topic("cases", message)


async def publish_workflow_event(
    event_type: EventType,
    workflow_id: str,
    execution_id: str,
    data: dict[str, Any],
) -> None:
    """Publish a workflow-related event."""
    message = WebSocketMessage(
        event_type=event_type,
        data={
            "workflow_id": workflow_id,
            "execution_id": execution_id,
            **data,
        },
    )

    # Broadcast to workflow subscribers
    await manager.broadcast_to_topic("workflows", message)
    await manager.broadcast_to_topic(f"workflow:{workflow_id}", message)


async def publish_alert(
    alert_type: EventType,
    data: dict[str, Any],
    user_id: str | None = None,
) -> None:
    """Publish an alert to users."""
    message = WebSocketMessage(event_type=alert_type, data=data)

    if user_id:
        await manager.send_to_user(user_id, message)
    else:
        await manager.broadcast(message)


async def publish_notification(
    title: str,
    body: str,
    severity: str = "info",
    user_id: str | None = None,
    link: str | None = None,
) -> None:
    """Publish a user notification."""
    message = WebSocketMessage(
        event_type=EventType.NOTIFICATION,
        data={
            "title": title,
            "body": body,
            "severity": severity,
            "link": link,
        },
    )

    if user_id:
        await manager.send_to_user(user_id, message)
    else:
        await manager.broadcast(message)
