"""WebSocket API endpoint for real-time updates."""

import json
import logging

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from jose import JWTError, jwt

from app.config import get_settings
from app.websocket import EventType, WebSocketMessage, get_manager

router = APIRouter()
settings = get_settings()
logger = logging.getLogger(__name__)


async def get_user_from_token(token: str | None) -> str | None:
    """Extract user ID from JWT token."""
    if not token:
        return None

    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
        return payload.get("sub")
    except JWTError:
        return None


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str | None = Query(None),
):
    """WebSocket endpoint for real-time updates.

    Connect with optional token for authenticated access:
    ws://host/api/v1/ws?token=<jwt_token>

    Message format (send):
    {
        "action": "subscribe" | "unsubscribe" | "ping",
        "topic": "cases" | "case:{id}" | "workflows" | "alerts"
    }

    Message format (receive):
    {
        "id": "uuid",
        "type": "event_type",
        "data": {...},
        "timestamp": "ISO8601"
    }
    """
    manager = get_manager()

    # Authenticate user if token provided
    user_id = await get_user_from_token(token)

    # Accept connection
    connection_id = await manager.connect(websocket, user_id)

    try:
        while True:
            # Receive and process messages
            data = await websocket.receive_text()

            try:
                message = json.loads(data)
                action = message.get("action")
                topic = message.get("topic")

                if action == "ping":
                    # Respond to ping with pong
                    await manager.send_personal(
                        connection_id,
                        WebSocketMessage(
                            event_type=EventType.PONG,
                            data={},
                        ),
                    )

                elif action == "subscribe" and topic:
                    # Subscribe to topic
                    await manager.subscribe(connection_id, topic)
                    await manager.send_personal(
                        connection_id,
                        WebSocketMessage(
                            event_type=EventType.NOTIFICATION,
                            data={
                                "title": "Subscribed",
                                "body": f"Subscribed to {topic}",
                                "severity": "info",
                            },
                        ),
                    )

                elif action == "unsubscribe" and topic:
                    # Unsubscribe from topic
                    await manager.unsubscribe(connection_id, topic)

                else:
                    logger.debug("Unknown action: %s", action)

            except json.JSONDecodeError:
                logger.warning("Invalid JSON received: %s", data[:100])

    except WebSocketDisconnect:
        await manager.disconnect(connection_id)
    except Exception as e:
        logger.error("WebSocket error: %s", e)
        await manager.disconnect(connection_id)


@router.get("/ws/stats")
async def websocket_stats():
    """Get WebSocket connection statistics."""
    manager = get_manager()

    return {
        "active_connections": manager.get_connection_count(),
        "topics": list(manager.topic_subscriptions.keys()),
        "users_connected": len(manager.user_connections),
    }
