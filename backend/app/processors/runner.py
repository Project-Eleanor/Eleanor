"""Processor runner for executing case processors.

Manages registration, scheduling, and execution of processors
in response to case events.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Type
from uuid import UUID

from app.processors.base import (
    BaseProcessor,
    ProcessorContext,
    ProcessorResult,
    ProcessorStatus,
    ProcessorTrigger,
)

logger = logging.getLogger(__name__)


class ProcessorRunner:
    """Manages and executes case processors.

    Responsibilities:
    - Register/unregister processors
    - Match processors to events
    - Execute processors with error handling
    - Track execution history
    """

    def __init__(
        self,
        max_concurrent: int = 5,
        default_timeout: int = 60,
    ):
        """Initialize the processor runner.

        Args:
            max_concurrent: Maximum concurrent processor executions
            default_timeout: Default execution timeout in seconds
        """
        self._processors: dict[str, BaseProcessor] = {}
        self._by_trigger: dict[ProcessorTrigger, list[str]] = {}
        self._execution_history: list[ProcessorResult] = []
        self._max_history = 1000
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._default_timeout = default_timeout

    def register(self, processor: BaseProcessor) -> None:
        """Register a processor.

        Args:
            processor: Processor instance to register
        """
        name = processor.name

        if name in self._processors:
            logger.warning(f"Processor '{name}' already registered, replacing")

        self._processors[name] = processor

        # Index by trigger
        for trigger in processor.triggers:
            if trigger not in self._by_trigger:
                self._by_trigger[trigger] = []
            if name not in self._by_trigger[trigger]:
                self._by_trigger[trigger].append(name)

        logger.info(f"Registered processor: {name}")

    def register_class(self, processor_class: Type[BaseProcessor]) -> None:
        """Register a processor class (instantiates it).

        Args:
            processor_class: Processor class to register
        """
        self.register(processor_class())

    def unregister(self, name: str) -> bool:
        """Unregister a processor.

        Args:
            name: Processor name

        Returns:
            True if processor was found and removed
        """
        if name not in self._processors:
            return False

        processor = self._processors.pop(name)

        # Remove from trigger index
        for trigger in processor.triggers:
            if trigger in self._by_trigger and name in self._by_trigger[trigger]:
                self._by_trigger[trigger].remove(name)

        return True

    def get(self, name: str) -> BaseProcessor | None:
        """Get a processor by name.

        Args:
            name: Processor name

        Returns:
            Processor instance or None
        """
        return self._processors.get(name)

    def list_processors(self) -> list[dict[str, Any]]:
        """List all registered processors.

        Returns:
            List of processor info dictionaries
        """
        return [
            {
                "name": processor.name,
                "description": processor.description,
                "triggers": [trigger.value for trigger in processor.triggers],
                "enabled": processor.enabled,
                "priority": processor.priority,
                "timeout": processor.timeout_seconds,
            }
            for processor in sorted(
                self._processors.values(),
                key=lambda proc: proc.priority
            )
        ]

    def get_processors_for_trigger(self, trigger: ProcessorTrigger) -> list[BaseProcessor]:
        """Get all processors that respond to a trigger.

        Args:
            trigger: The trigger event

        Returns:
            List of matching processors, sorted by priority
        """
        names = self._by_trigger.get(trigger, [])
        processors = [
            self._processors[name]
            for name in names
            if name in self._processors and self._processors[name].enabled
        ]
        return sorted(processors, key=lambda x: x.priority)

    async def trigger_event(
        self,
        trigger: ProcessorTrigger,
        case_id: UUID | None = None,
        evidence_id: UUID | None = None,
        user_id: UUID | None = None,
        event_data: dict | None = None,
        db_session=None,
        redis_client=None,
        elasticsearch_client=None,
        adapter_registry=None,
    ) -> list[ProcessorResult]:
        """Trigger processors for an event.

        Args:
            trigger: The trigger event
            case_id: Related case ID
            evidence_id: Related evidence ID
            user_id: User who triggered the event
            event_data: Additional event data
            db_session: Database session
            redis_client: Redis client
            elasticsearch_client: Elasticsearch client
            adapter_registry: Adapter registry

        Returns:
            List of processor results
        """
        processors = self.get_processors_for_trigger(trigger)

        if not processors:
            logger.debug(f"No processors registered for trigger: {trigger.value}")
            return []

        context = ProcessorContext(
            trigger=trigger,
            case_id=case_id,
            evidence_id=evidence_id,
            user_id=user_id,
            event_data=event_data or {},
            db_session=db_session,
            redis_client=redis_client,
            elasticsearch_client=elasticsearch_client,
            adapter_registry=adapter_registry,
        )

        # Execute processors
        results = []
        for processor in processors:
            if processor.should_run(context):
                result = await self._execute_processor(processor, context)
                results.append(result)

        return results

    async def _execute_processor(
        self,
        processor: BaseProcessor,
        context: ProcessorContext,
    ) -> ProcessorResult:
        """Execute a single processor with error handling.

        Args:
            processor: Processor to execute
            context: Execution context

        Returns:
            ProcessorResult
        """
        started_at = datetime.now(timezone.utc)
        timeout = processor.timeout_seconds or self._default_timeout

        logger.info(f"Executing processor: {processor.name}")

        try:
            async with self._semaphore:
                result = await asyncio.wait_for(
                    processor.process(context),
                    timeout=timeout,
                )

        except asyncio.TimeoutError:
            logger.error(f"Processor {processor.name} timed out after {timeout}s")
            result = ProcessorResult(
                processor_name=processor.name,
                status=ProcessorStatus.FAILED,
                started_at=started_at,
                completed_at=datetime.now(timezone.utc),
                message=f"Timeout after {timeout} seconds",
                errors=[f"Execution timed out after {timeout}s"],
            )
            await processor.on_error(context, TimeoutError(f"Timed out after {timeout}s"))

        except Exception as e:
            logger.exception(f"Processor {processor.name} failed: {e}")
            result = ProcessorResult(
                processor_name=processor.name,
                status=ProcessorStatus.FAILED,
                started_at=started_at,
                completed_at=datetime.now(timezone.utc),
                message=f"Error: {str(e)}",
                errors=[str(e)],
            )
            await processor.on_error(context, e)

        # Calculate duration if not set
        if result.duration_ms is None:
            now = datetime.now(timezone.utc)
            result.duration_ms = int((now - started_at).total_seconds() * 1000)

        # Track history
        self._add_to_history(result)

        logger.info(f"Processor {processor.name} completed: {result.status.value}")

        return result

    async def run_processor(
        self,
        name: str,
        context: ProcessorContext,
    ) -> ProcessorResult | None:
        """Run a specific processor by name.

        Args:
            name: Processor name
            context: Execution context

        Returns:
            ProcessorResult or None if processor not found
        """
        processor = self.get(name)
        if not processor:
            logger.warning(f"Processor not found: {name}")
            return None

        return await self._execute_processor(processor, context)

    def _add_to_history(self, result: ProcessorResult) -> None:
        """Add result to execution history.

        Args:
            result: Processor result to add
        """
        self._execution_history.append(result)

        # Trim history if needed
        if len(self._execution_history) > self._max_history:
            self._execution_history = self._execution_history[-self._max_history:]

    def get_history(
        self,
        processor_name: str | None = None,
        status: ProcessorStatus | None = None,
        limit: int = 100,
    ) -> list[ProcessorResult]:
        """Get processor execution history.

        Args:
            processor_name: Filter by processor name
            status: Filter by status
            limit: Maximum results to return

        Returns:
            List of ProcessorResults
        """
        results = self._execution_history.copy()

        if processor_name:
            results = [r for r in results if r.processor_name == processor_name]

        if status:
            results = [r for r in results if r.status == status]

        # Return most recent first
        return list(reversed(results[-limit:]))

    def get_stats(self) -> dict[str, Any]:
        """Get runner statistics.

        Returns:
            Statistics dictionary
        """
        stats = {
            "registered_processors": len(self._processors),
            "enabled_processors": sum(1 for p in self._processors.values() if p.enabled),
            "history_size": len(self._execution_history),
        }

        # Count by status
        for status in ProcessorStatus:
            count = sum(1 for r in self._execution_history if r.status == status)
            stats[f"executions_{status.value}"] = count

        return stats


# Global runner instance
_runner: ProcessorRunner | None = None


def get_runner() -> ProcessorRunner:
    """Get the global processor runner."""
    global _runner
    if _runner is None:
        _runner = ProcessorRunner()
    return _runner


def load_builtin_processors() -> None:
    """Load all built-in processors.

    Called during application startup.
    """
    from app.processors.builtin import auto_enrich  # noqa: F401

    runner = get_runner()
    logger.info(f"Loaded {len(runner._processors)} built-in processors")
