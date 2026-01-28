"""Azure Event Hub connector for log ingestion.

PATTERN: Observer Pattern (via StreamingConnector)
Receives events from Azure Event Hub for processing.

Provides:
- Event Hub streaming with checkpointing
- Consumer group support
- Batch processing
- Partition management
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
class AzureEventHubConfig(ConnectorConfig):
    """Azure Event Hub connector configuration.

    PATTERN: Configuration Object
    Extends base ConnectorConfig with Event Hub-specific settings.
    """

    # Connection
    connection_string: str = ""
    eventhub_name: str = ""
    consumer_group: str = "$Default"

    # Checkpoint storage (Azure Blob)
    checkpoint_connection_string: str = ""
    checkpoint_container: str = "eventhub-checkpoints"

    # Processing
    max_batch_size: int = 100
    max_wait_time: float = 5.0
    prefetch_count: int = 300

    # Starting position
    starting_position: str = "latest"  # "latest", "earliest", or ISO timestamp


class AzureEventHubConnector(StreamingConnector):
    """Azure Event Hub streaming connector.

    PATTERN: Observer Pattern
    Receives streaming events from Azure Event Hub with checkpointing
    for reliable at-least-once delivery.

    Configuration:
        connection_string: Event Hub namespace connection string
        eventhub_name: Event Hub name
        consumer_group: Consumer group name
        checkpoint_connection_string: Blob storage connection string
        checkpoint_container: Container for checkpoint data

    DESIGN DECISION: Uses azure-eventhub SDK with BlobCheckpointStore
    for reliable checkpointing and partition balancing.
    """

    name = "azure_eventhub"
    description = "Azure Event Hub event streaming"

    def __init__(self, config: AzureEventHubConfig):
        """Initialize Azure Event Hub connector.

        Args:
            config: Event Hub connector configuration
        """
        super().__init__(config)
        self.eventhub_config = config

        self._consumer = None
        self._checkpoint_store = None
        self._event_queue: asyncio.Queue[RawEvent] = asyncio.Queue(maxsize=10000)
        self._running = False
        self._metrics = ConnectorMetrics(connector_name=self.name)
        self._receive_task = None

    async def connect(self) -> bool:
        """Connect to Event Hub and start receiving."""
        try:
            from azure.eventhub.aio import EventHubConsumerClient
            from azure.eventhub.extensions.checkpointstorageblob.aio import (
                BlobCheckpointStore,
            )

            # Create checkpoint store if configured
            if self.eventhub_config.checkpoint_connection_string:
                self._checkpoint_store = BlobCheckpointStore.from_connection_string(
                    self.eventhub_config.checkpoint_connection_string,
                    self.eventhub_config.checkpoint_container,
                )

            # Create consumer client
            self._consumer = EventHubConsumerClient.from_connection_string(
                self.eventhub_config.connection_string,
                consumer_group=self.eventhub_config.consumer_group,
                eventhub_name=self.eventhub_config.eventhub_name,
                checkpoint_store=self._checkpoint_store,
            )

            self._running = True
            self._connected = True

            # Start receiving in background
            self._receive_task = asyncio.create_task(self._receive_events())

            logger.info(
                "Connected to Azure Event Hub",
                extra={
                    "eventhub_name": self.eventhub_config.eventhub_name,
                    "consumer_group": self.eventhub_config.consumer_group,
                },
            )
            return True

        except Exception as error:
            logger.error(f"Failed to connect to Event Hub: {error}")
            return False

    async def disconnect(self) -> None:
        """Disconnect from Event Hub."""
        self._running = False

        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass
            self._receive_task = None

        if self._consumer:
            await self._consumer.close()
            self._consumer = None

        if self._checkpoint_store:
            await self._checkpoint_store.close()
            self._checkpoint_store = None

        self._connected = False
        logger.info("Disconnected from Azure Event Hub")

    async def stream(self) -> AsyncIterator[RawEvent]:
        """Stream events from Event Hub."""
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
                logger.error(f"Error streaming Event Hub event: {error}")
                self._metrics.errors += 1

    async def get_metrics(self) -> ConnectorMetrics:
        """Get connector metrics."""
        self._metrics.queue_size = self._event_queue.qsize()
        return self._metrics

    async def _receive_events(self) -> None:
        """Receive events from all partitions."""
        from azure.eventhub import EventData

        async def on_event(partition_context, event: EventData) -> None:
            """Handle received event."""
            if event is None:
                return

            try:
                # Parse event body
                body = event.body_as_str()

                try:
                    data = json.loads(body)
                except json.JSONDecodeError:
                    data = {"message": body}

                # Determine timestamp
                if event.enqueued_time:
                    timestamp = event.enqueued_time
                else:
                    timestamp = datetime.now(UTC)

                # Create raw event
                raw_event = RawEvent(
                    timestamp=timestamp,
                    data=data,
                    source=partition_context.partition_id,
                    source_type="azure_eventhub",
                    metadata={
                        "partition_id": partition_context.partition_id,
                        "consumer_group": partition_context.consumer_group,
                        "eventhub_name": partition_context.eventhub_name,
                        "sequence_number": event.sequence_number,
                        "offset": event.offset,
                        "properties": dict(event.properties) if event.properties else {},
                        "system_properties": (
                            dict(event.system_properties) if event.system_properties else {}
                        ),
                    },
                )

                try:
                    self._event_queue.put_nowait(raw_event)
                except asyncio.QueueFull:
                    self._metrics.events_dropped += 1
                    logger.warning("Event Hub queue full, dropping event")
                    return

                # Checkpoint periodically
                if event.sequence_number and event.sequence_number % 100 == 0:
                    await partition_context.update_checkpoint(event)

            except Exception as error:
                logger.error(f"Error processing Event Hub event: {error}")
                self._metrics.errors += 1

        async def on_error(partition_context, error: Exception) -> None:
            """Handle partition error."""
            if partition_context:
                logger.error(
                    f"Event Hub partition error: {error}",
                    extra={"partition_id": partition_context.partition_id},
                )
            else:
                logger.error(f"Event Hub error: {error}")
            self._metrics.errors += 1

        async def on_partition_initialize(partition_context) -> None:
            """Handle partition initialization."""
            logger.info(
                f"Partition initialized: {partition_context.partition_id}",
                extra={"eventhub_name": partition_context.eventhub_name},
            )

        async def on_partition_close(partition_context, reason) -> None:
            """Handle partition close."""
            logger.info(
                f"Partition closed: {partition_context.partition_id}",
                extra={"reason": str(reason)},
            )

        # Determine starting position
        starting_position = self.eventhub_config.starting_position
        if starting_position == "latest":
            from azure.eventhub import STARTING_POSITION_LATEST

            start_pos = STARTING_POSITION_LATEST
        elif starting_position == "earliest":
            from azure.eventhub import STARTING_POSITION_EARLIEST

            start_pos = STARTING_POSITION_EARLIEST
        else:
            # Assume ISO timestamp
            try:
                start_pos = datetime.fromisoformat(starting_position.replace("Z", "+00:00"))
            except ValueError:
                from azure.eventhub import STARTING_POSITION_LATEST

                start_pos = STARTING_POSITION_LATEST

        # Start receiving
        try:
            await self._consumer.receive(
                on_event=on_event,
                on_error=on_error,
                on_partition_initialize=on_partition_initialize,
                on_partition_close=on_partition_close,
                starting_position=start_pos,
                max_batch_size=self.eventhub_config.max_batch_size,
                max_wait_time=self.eventhub_config.max_wait_time,
                prefetch=self.eventhub_config.prefetch_count,
            )
        except asyncio.CancelledError:
            pass
        except Exception as error:
            if self._running:
                logger.error(f"Event Hub receive error: {error}")
                self._metrics.errors += 1


# Batch processing support


class AzureEventHubBatchConnector(AzureEventHubConnector):
    """Azure Event Hub connector with batch processing support.

    PATTERN: Observer Pattern with Batching
    Extends base connector to receive events in batches for
    more efficient processing.
    """

    async def stream_batches(
        self,
        batch_size: int = 100,
        max_wait: float = 5.0,
    ) -> AsyncIterator[list[RawEvent]]:
        """Stream events in batches.

        Args:
            batch_size: Maximum events per batch
            max_wait: Maximum seconds to wait for batch

        Yields:
            Batches of events
        """
        batch: list[RawEvent] = []
        last_yield = datetime.now(UTC)

        while self._running:
            try:
                # Calculate remaining wait time
                elapsed = (datetime.now(UTC) - last_yield).total_seconds()
                remaining = max(0.1, max_wait - elapsed)

                try:
                    event = await asyncio.wait_for(
                        self._event_queue.get(),
                        timeout=remaining,
                    )
                    batch.append(event)
                    self._metrics.events_received += 1
                except TimeoutError:
                    pass

                # Yield batch if full or timeout
                if len(batch) >= batch_size or (
                    batch and (datetime.now(UTC) - last_yield).total_seconds() >= max_wait
                ):
                    yield batch
                    batch = []
                    last_yield = datetime.now(UTC)

            except Exception as error:
                logger.error(f"Error in batch streaming: {error}")
                self._metrics.errors += 1

        # Yield remaining events
        if batch:
            yield batch


# Factory function for creating connector from dict config
def create_eventhub_connector(config: dict[str, Any]) -> AzureEventHubConnector:
    """Create Azure Event Hub connector from dictionary configuration.

    Args:
        config: Configuration dictionary

    Returns:
        Configured AzureEventHubConnector instance
    """
    connector_config = AzureEventHubConfig(
        name=config.get("name", "azure_eventhub"),
        enabled=config.get("enabled", True),
        connection_string=config.get("connection_string", ""),
        eventhub_name=config.get("eventhub_name", ""),
        consumer_group=config.get("consumer_group", "$Default"),
        checkpoint_connection_string=config.get("checkpoint_connection_string", ""),
        checkpoint_container=config.get("checkpoint_container", "eventhub-checkpoints"),
        max_batch_size=config.get("max_batch_size", 100),
        max_wait_time=config.get("max_wait_time", 5.0),
        prefetch_count=config.get("prefetch_count", 300),
        starting_position=config.get("starting_position", "latest"),
    )

    if config.get("batch_mode", False):
        return AzureEventHubBatchConnector(connector_config)
    return AzureEventHubConnector(connector_config)
