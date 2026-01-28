"""Fluentd/Fluent Bit connector for log ingestion.

PATTERN: Observer Pattern (via StreamingConnector)
Receives log events from Fluentd/Fluent Bit via HTTP or TCP forward protocol.

Provides:
- HTTP endpoint for Fluentd http output
- Forward protocol support for native Fluentd forwarding
- Event batching and processing
"""

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from app.connectors.base import (
    ConnectorConfig,
    ConnectorMetrics,
    RawEvent,
    StreamingConnector,
)

logger = logging.getLogger(__name__)


@dataclass
class FluentdConfig(ConnectorConfig):
    """Fluentd connector configuration.

    PATTERN: Configuration Object
    Extends base ConnectorConfig with Fluentd-specific settings.
    """

    # HTTP server settings
    http_enabled: bool = True
    http_host: str = "0.0.0.0"
    http_port: int = 8888

    # Forward protocol settings
    forward_enabled: bool = False
    forward_host: str = "0.0.0.0"
    forward_port: int = 24224

    # Authentication
    shared_key: str = ""

    # Processing
    tag_prefix: str = ""
    max_batch_size: int = 1000


class FluentdConnector(StreamingConnector):
    """Fluentd/Fluent Bit log ingestion connector.

    PATTERN: Observer Pattern
    Receives streaming log events from Fluentd via HTTP or forward protocol.

    Configuration:
        http_enabled: Enable HTTP endpoint for fluentd http output
        http_port: HTTP server port (default: 8888)
        forward_enabled: Enable forward protocol
        forward_port: Forward protocol port (default: 24224)
        shared_key: Optional shared key for authentication

    DESIGN DECISION: Supports both HTTP and forward protocol to accommodate
    different Fluentd/Fluent Bit deployment scenarios.
    """

    name = "fluentd"
    description = "Fluentd/Fluent Bit log collector"

    def __init__(self, config: FluentdConfig):
        """Initialize Fluentd connector.

        Args:
            config: Fluentd connector configuration
        """
        super().__init__(config)
        self.fluentd_config = config

        self._http_server = None
        self._forward_server = None
        self._event_queue: asyncio.Queue[RawEvent] = asyncio.Queue(maxsize=10000)
        self._running = False
        self._metrics = ConnectorMetrics(connector_name=self.name)

    async def connect(self) -> bool:
        """Start Fluentd servers."""
        try:
            if self.fluentd_config.http_enabled:
                await self._start_http_server()

            if self.fluentd_config.forward_enabled:
                await self._start_forward_server()

            self._running = True
            self._connected = True

            logger.info(
                "Fluentd connector started",
                extra={
                    "http_enabled": self.fluentd_config.http_enabled,
                    "http_port": self.fluentd_config.http_port,
                    "forward_enabled": self.fluentd_config.forward_enabled,
                    "forward_port": self.fluentd_config.forward_port,
                },
            )
            return True

        except Exception as error:
            logger.error(f"Failed to start Fluentd connector: {error}")
            return False

    async def disconnect(self) -> None:
        """Stop Fluentd servers."""
        self._running = False

        if self._http_server:
            self._http_server.close()
            await self._http_server.wait_closed()
            self._http_server = None

        if self._forward_server:
            self._forward_server.close()
            await self._forward_server.wait_closed()
            self._forward_server = None

        self._connected = False
        logger.info("Fluentd connector stopped")

    async def stream(self) -> AsyncIterator[RawEvent]:
        """Stream events from Fluentd."""
        while self._running:
            try:
                event = await asyncio.wait_for(
                    self._event_queue.get(),
                    timeout=1.0,
                )
                self._metrics.events_received += 1
                yield event
            except TimeoutError:
                continue
            except Exception as error:
                logger.error(f"Error streaming Fluentd event: {error}")
                self._metrics.errors += 1

    async def get_metrics(self) -> ConnectorMetrics:
        """Get connector metrics."""
        self._metrics.queue_size = self._event_queue.qsize()
        return self._metrics

    async def _start_http_server(self) -> None:
        """Start HTTP server for receiving events."""
        from aiohttp import web

        app = web.Application()
        app.router.add_post("/", self._handle_http_event)
        app.router.add_post("/{tag:.*}", self._handle_http_event)

        runner = web.AppRunner(app)
        await runner.setup()

        site = web.TCPSite(
            runner,
            self.fluentd_config.http_host,
            self.fluentd_config.http_port,
        )
        await site.start()

        logger.info(
            f"Fluentd HTTP server listening on "
            f"{self.fluentd_config.http_host}:{self.fluentd_config.http_port}"
        )

    async def _handle_http_event(self, request) -> Any:
        """Handle HTTP event from Fluentd."""
        from aiohttp import web

        try:
            # Get tag from URL or header
            tag = request.match_info.get("tag", "")
            if not tag:
                tag = request.headers.get("X-Fluentd-Tag", "unknown")

            if self.fluentd_config.tag_prefix:
                tag = f"{self.fluentd_config.tag_prefix}.{tag}"

            # Parse body
            content_type = request.content_type

            if content_type == "application/json":
                body = await request.json()
            elif content_type == "application/msgpack":
                import msgpack

                raw_body = await request.read()
                body = msgpack.unpackb(raw_body, raw=False)
            else:
                # Try JSON as default
                try:
                    body = await request.json()
                except Exception:
                    body = {"message": await request.text()}

            # Process events
            await self._process_events(tag, body)

            return web.Response(text="ok", status=200)

        except Exception as error:
            logger.error(f"Error handling Fluentd HTTP event: {error}")
            self._metrics.errors += 1
            return web.Response(text=str(error), status=500)

    async def _start_forward_server(self) -> None:
        """Start forward protocol server."""
        self._forward_server = await asyncio.start_server(
            self._handle_forward_connection,
            self.fluentd_config.forward_host,
            self.fluentd_config.forward_port,
        )

        logger.info(
            f"Fluentd forward server listening on "
            f"{self.fluentd_config.forward_host}:{self.fluentd_config.forward_port}"
        )

    async def _handle_forward_connection(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        """Handle forward protocol connection."""
        import msgpack

        peer = writer.get_extra_info("peername")
        logger.debug(f"Forward connection from {peer}")

        unpacker = msgpack.Unpacker(raw=False)

        try:
            while self._running:
                data = await reader.read(4096)
                if not data:
                    break

                unpacker.feed(data)

                for message in unpacker:
                    await self._process_forward_message(message)

        except Exception as error:
            logger.error(f"Error handling forward connection: {error}")
            self._metrics.errors += 1
        finally:
            writer.close()
            await writer.wait_closed()

    async def _process_forward_message(self, message: Any) -> None:
        """Process a forward protocol message.

        Forward protocol message formats:
        - Message: [tag, time, record]
        - Forward: [tag, [[time, record], [time, record], ...]]
        - PackedForward: [tag, msgpack_binary]
        """
        import msgpack

        if not isinstance(message, (list, tuple)) or len(message) < 2:
            return

        tag = message[0]

        if self.fluentd_config.tag_prefix:
            tag = f"{self.fluentd_config.tag_prefix}.{tag}"

        # Determine message type
        if len(message) == 3 and isinstance(message[2], dict):
            # Message mode: [tag, time, record]
            timestamp = message[1]
            record = message[2]
            await self._enqueue_event(tag, timestamp, record)

        elif len(message) >= 2:
            entries = message[1]

            if isinstance(entries, bytes):
                # PackedForward mode: msgpack binary
                unpacker = msgpack.Unpacker(raw=False)
                unpacker.feed(entries)
                for entry in unpacker:
                    if isinstance(entry, (list, tuple)) and len(entry) >= 2:
                        timestamp, record = entry[0], entry[1]
                        await self._enqueue_event(tag, timestamp, record)

            elif isinstance(entries, list):
                # Forward mode: array of [time, record]
                for entry in entries:
                    if isinstance(entry, (list, tuple)) and len(entry) >= 2:
                        timestamp, record = entry[0], entry[1]
                        await self._enqueue_event(tag, timestamp, record)

    async def _process_events(self, tag: str, body: Any) -> None:
        """Process HTTP events."""
        timestamp = datetime.now(UTC)

        if isinstance(body, list):
            for item in body:
                await self._enqueue_event(tag, timestamp, item)
        elif isinstance(body, dict):
            await self._enqueue_event(tag, timestamp, body)

    async def _enqueue_event(
        self,
        tag: str,
        timestamp: datetime | int | float,
        record: dict[str, Any],
    ) -> None:
        """Enqueue an event for processing."""
        # Convert timestamp
        if isinstance(timestamp, (int, float)):
            event_time = datetime.fromtimestamp(timestamp, tz=UTC)
        else:
            event_time = timestamp

        # Extract message
        message = record.get("message", record.get("log", json.dumps(record)))

        event = RawEvent(
            timestamp=event_time,
            data=record,
            source=tag,
            source_type="fluentd",
            metadata={
                "tag": tag,
                "connector": self.name,
            },
        )

        try:
            self._event_queue.put_nowait(event)
        except asyncio.QueueFull:
            self._metrics.events_dropped += 1
            logger.warning("Fluentd event queue full, dropping event")


# Factory function for creating connector from dict config
def create_fluentd_connector(config: dict[str, Any]) -> FluentdConnector:
    """Create Fluentd connector from dictionary configuration.

    Args:
        config: Configuration dictionary

    Returns:
        Configured FluentdConnector instance
    """
    connector_config = FluentdConfig(
        name=config.get("name", "fluentd"),
        enabled=config.get("enabled", True),
        http_enabled=config.get("http_enabled", True),
        http_host=config.get("http_host", "0.0.0.0"),
        http_port=config.get("http_port", 8888),
        forward_enabled=config.get("forward_enabled", False),
        forward_host=config.get("forward_host", "0.0.0.0"),
        forward_port=config.get("forward_port", 24224),
        shared_key=config.get("shared_key", ""),
        tag_prefix=config.get("tag_prefix", ""),
        max_batch_size=config.get("max_batch_size", 1000),
    )
    return FluentdConnector(connector_config)
