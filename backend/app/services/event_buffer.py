"""Event buffer using Redis Streams for real-time event processing.

This module provides a high-performance event buffer that:
- Receives events from parsers and connectors
- Buffers events in Redis Streams for real-time rule processing
- Supports consumer groups for scalable processing
- Provides backpressure handling and dead letter queues
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, AsyncIterator, Callable
from uuid import uuid4

import redis.asyncio as redis
from redis.exceptions import ResponseError

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Stream and consumer group names
EVENT_STREAM = "eleanor:events"
ALERT_STREAM = "eleanor:alerts"
CORRELATION_STREAM = "eleanor:correlation"
DEAD_LETTER_STREAM = "eleanor:dlq"

CONSUMER_GROUP = "eleanor-processors"


class EventBuffer:
    """High-performance event buffer using Redis Streams.

    Provides event ingestion, buffering, and consumption for
    real-time detection and correlation processing.
    """

    def __init__(self, redis_url: str | None = None):
        """Initialize event buffer.

        Args:
            redis_url: Redis connection URL (defaults to settings)
        """
        self.redis_url = redis_url or settings.redis_url
        self._redis: redis.Redis | None = None
        self._consumer_name = f"consumer-{uuid4().hex[:8]}"

    async def connect(self) -> None:
        """Connect to Redis and initialize streams."""
        self._redis = await redis.from_url(
            self.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )

        # Create consumer groups for each stream
        for stream in [EVENT_STREAM, ALERT_STREAM, CORRELATION_STREAM]:
            try:
                await self._redis.xgroup_create(
                    stream,
                    CONSUMER_GROUP,
                    id="0",
                    mkstream=True,
                )
                logger.info("Created consumer group for stream: %s", stream)
            except ResponseError as e:
                if "BUSYGROUP" not in str(e):
                    raise
                # Group already exists

    async def disconnect(self) -> None:
        """Disconnect from Redis."""
        if self._redis:
            await self._redis.close()
            self._redis = None

    @property
    def redis(self) -> redis.Redis:
        """Get Redis client, raising if not connected."""
        if self._redis is None:
            raise RuntimeError("EventBuffer not connected. Call connect() first.")
        return self._redis

    async def publish_event(
        self,
        event: dict[str, Any],
        stream: str = EVENT_STREAM,
        maxlen: int = 100000,
    ) -> str:
        """Publish an event to a stream.

        Args:
            event: Event data to publish
            stream: Target stream name
            maxlen: Maximum stream length (approximate)

        Returns:
            Message ID
        """
        # Serialize nested objects
        serialized = {
            k: json.dumps(v) if isinstance(v, (dict, list)) else str(v)
            for k, v in event.items()
        }

        # Add metadata
        serialized["_published_at"] = datetime.utcnow().isoformat()

        message_id = await self.redis.xadd(
            stream,
            serialized,
            maxlen=maxlen,
            approximate=True,
        )

        return message_id

    async def publish_events_batch(
        self,
        events: list[dict[str, Any]],
        stream: str = EVENT_STREAM,
        maxlen: int = 100000,
    ) -> list[str]:
        """Publish multiple events in a pipeline.

        Args:
            events: List of events to publish
            stream: Target stream name
            maxlen: Maximum stream length

        Returns:
            List of message IDs
        """
        pipe = self.redis.pipeline()

        for event in events:
            serialized = {
                k: json.dumps(v) if isinstance(v, (dict, list)) else str(v)
                for k, v in event.items()
            }
            serialized["_published_at"] = datetime.utcnow().isoformat()

            pipe.xadd(stream, serialized, maxlen=maxlen, approximate=True)

        results = await pipe.execute()
        return results

    async def consume_events(
        self,
        stream: str = EVENT_STREAM,
        count: int = 100,
        block_ms: int = 5000,
    ) -> list[tuple[str, dict[str, Any]]]:
        """Consume events from a stream using consumer group.

        Args:
            stream: Stream to consume from
            count: Maximum messages to read
            block_ms: Block timeout in milliseconds

        Returns:
            List of (message_id, event) tuples
        """
        messages = await self.redis.xreadgroup(
            groupname=CONSUMER_GROUP,
            consumername=self._consumer_name,
            streams={stream: ">"},
            count=count,
            block=block_ms,
        )

        events = []
        for stream_name, stream_messages in messages or []:
            for message_id, data in stream_messages:
                # Deserialize JSON fields
                event = {}
                for k, v in data.items():
                    if k.startswith("_"):
                        event[k] = v
                    else:
                        try:
                            event[k] = json.loads(v)
                        except (json.JSONDecodeError, TypeError):
                            event[k] = v

                events.append((message_id, event))

        return events

    async def acknowledge(
        self,
        message_ids: list[str],
        stream: str = EVENT_STREAM,
    ) -> int:
        """Acknowledge processed messages.

        Args:
            message_ids: List of message IDs to acknowledge
            stream: Stream name

        Returns:
            Number of acknowledged messages
        """
        if not message_ids:
            return 0

        return await self.redis.xack(stream, CONSUMER_GROUP, *message_ids)

    async def claim_pending(
        self,
        stream: str = EVENT_STREAM,
        min_idle_ms: int = 60000,
        count: int = 100,
    ) -> list[tuple[str, dict[str, Any]]]:
        """Claim pending messages from other consumers.

        Used for recovering messages from failed consumers.

        Args:
            stream: Stream to check
            min_idle_ms: Minimum idle time to claim
            count: Maximum messages to claim

        Returns:
            List of claimed (message_id, event) tuples
        """
        # Get pending messages
        pending = await self.redis.xpending_range(
            stream,
            CONSUMER_GROUP,
            min="-",
            max="+",
            count=count,
        )

        if not pending:
            return []

        # Filter by idle time and claim
        claimable = [
            p["message_id"]
            for p in pending
            if p["time_since_delivered"] >= min_idle_ms
        ]

        if not claimable:
            return []

        claimed = await self.redis.xclaim(
            stream,
            CONSUMER_GROUP,
            self._consumer_name,
            min_idle_time=min_idle_ms,
            message_ids=claimable,
        )

        events = []
        for message_id, data in claimed:
            if data is None:
                continue

            event = {}
            for k, v in data.items():
                if k.startswith("_"):
                    event[k] = v
                else:
                    try:
                        event[k] = json.loads(v)
                    except (json.JSONDecodeError, TypeError):
                        event[k] = v

            events.append((message_id, event))

        return events

    async def move_to_dlq(
        self,
        message_id: str,
        event: dict[str, Any],
        error: str,
        source_stream: str = EVENT_STREAM,
    ) -> str:
        """Move a failed message to dead letter queue.

        Args:
            message_id: Original message ID
            event: Event data
            error: Error message
            source_stream: Source stream name

        Returns:
            DLQ message ID
        """
        dlq_event = {
            "original_message_id": message_id,
            "source_stream": source_stream,
            "error": error,
            "failed_at": datetime.utcnow().isoformat(),
            "event": json.dumps(event),
        }

        dlq_id = await self.redis.xadd(
            DEAD_LETTER_STREAM,
            dlq_event,
            maxlen=10000,
            approximate=True,
        )

        # Acknowledge original message
        await self.acknowledge([message_id], source_stream)

        return dlq_id

    async def stream_events(
        self,
        stream: str = EVENT_STREAM,
        batch_size: int = 100,
        block_ms: int = 5000,
    ) -> AsyncIterator[list[tuple[str, dict[str, Any]]]]:
        """Async generator for continuous event consumption.

        Yields batches of events for processing.

        Args:
            stream: Stream to consume
            batch_size: Events per batch
            block_ms: Block timeout

        Yields:
            Batches of (message_id, event) tuples
        """
        while True:
            events = await self.consume_events(
                stream=stream,
                count=batch_size,
                block_ms=block_ms,
            )

            if events:
                yield events

    async def get_stream_info(self, stream: str = EVENT_STREAM) -> dict[str, Any]:
        """Get stream statistics.

        Args:
            stream: Stream name

        Returns:
            Stream info including length, pending, etc.
        """
        try:
            info = await self.redis.xinfo_stream(stream)
            groups = await self.redis.xinfo_groups(stream)

            return {
                "stream": stream,
                "length": info.get("length", 0),
                "first_entry": info.get("first-entry"),
                "last_entry": info.get("last-entry"),
                "groups": [
                    {
                        "name": g["name"],
                        "consumers": g["consumers"],
                        "pending": g["pending"],
                        "last_delivered_id": g["last-delivered-id"],
                    }
                    for g in groups
                ],
            }
        except ResponseError:
            return {
                "stream": stream,
                "length": 0,
                "error": "Stream does not exist",
            }

    async def trim_stream(
        self,
        stream: str,
        maxlen: int | None = None,
        minid: str | None = None,
    ) -> int:
        """Trim stream to specified length or minimum ID.

        Args:
            stream: Stream to trim
            maxlen: Maximum entries to keep
            minid: Minimum message ID to keep

        Returns:
            Number of entries removed
        """
        if maxlen is not None:
            return await self.redis.xtrim(stream, maxlen=maxlen, approximate=True)
        elif minid is not None:
            return await self.redis.xtrim(stream, minid=minid)
        return 0


# Global event buffer instance
_event_buffer: EventBuffer | None = None


async def get_event_buffer() -> EventBuffer:
    """Get the global event buffer instance.

    Returns:
        Connected event buffer
    """
    global _event_buffer
    if _event_buffer is None:
        _event_buffer = EventBuffer()
        await _event_buffer.connect()
    return _event_buffer


async def shutdown_event_buffer() -> None:
    """Shutdown the global event buffer."""
    global _event_buffer
    if _event_buffer:
        await _event_buffer.disconnect()
        _event_buffer = None
