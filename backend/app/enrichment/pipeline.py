"""Enrichment pipeline orchestrator.

Coordinates IOC extraction and multi-source enrichment with caching
and rate limiting support.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from app.enrichment.extractors.ioc import IOCExtractor, IOCType

logger = logging.getLogger(__name__)


class EnrichmentStatus(str, Enum):
    """Status of an enrichment operation."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CACHED = "cached"
    NOT_FOUND = "not_found"


@dataclass
class EnrichmentResult:
    """Result of enriching a single indicator."""

    indicator: str
    indicator_type: IOCType
    status: EnrichmentStatus
    sources: dict[str, dict[str, Any]] = field(default_factory=dict)
    score: int | None = None  # 0-100 threat score
    verdict: str | None = None  # malicious, suspicious, clean, unknown
    tags: list[str] = field(default_factory=list)
    first_seen: datetime | None = None
    last_seen: datetime | None = None
    enriched_at: datetime | None = None
    cache_hit: bool = False
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "indicator": self.indicator,
            "indicator_type": self.indicator_type.value,
            "status": self.status.value,
            "sources": self.sources,
            "score": self.score,
            "verdict": self.verdict,
            "tags": self.tags,
            "first_seen": self.first_seen.isoformat() if self.first_seen else None,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
            "enriched_at": self.enriched_at.isoformat() if self.enriched_at else None,
            "cache_hit": self.cache_hit,
            "errors": self.errors,
        }


@dataclass
class EnrichmentConfig:
    """Configuration for enrichment pipeline."""

    # Cache settings
    cache_ttl_seconds: int = 3600  # 1 hour
    cache_negative_ttl_seconds: int = 300  # 5 minutes for "not found"

    # Rate limiting
    max_concurrent_requests: int = 10
    requests_per_minute: int = 60

    # Timeouts
    request_timeout_seconds: int = 30

    # Enabled providers
    enabled_providers: list[str] = field(default_factory=lambda: ["opencti"])


class EnrichmentPipeline:
    """Orchestrates IOC enrichment from multiple sources.

    Features:
    - Automatic IOC extraction from text
    - Multi-source enrichment (OpenCTI, VirusTotal, etc.)
    - Redis-based result caching
    - Rate limiting and concurrent request management
    - Aggregated scoring and verdict
    """

    def __init__(
        self,
        redis_client=None,
        config: EnrichmentConfig | None = None,
    ):
        """Initialize the enrichment pipeline.

        Args:
            redis_client: Redis client for caching (optional)
            config: Pipeline configuration
        """
        self.redis = redis_client
        self.config = config or EnrichmentConfig()
        self.extractor = IOCExtractor()
        self._providers: dict[str, Any] = {}
        self._semaphore = asyncio.Semaphore(self.config.max_concurrent_requests)

    def register_provider(self, name: str, provider) -> None:
        """Register an enrichment provider.

        Args:
            name: Provider identifier
            provider: Provider instance with enrich() method
        """
        self._providers[name] = provider
        logger.info(f"Registered enrichment provider: {name}")

    async def extract_and_enrich(
        self,
        text: str,
        case_id: str | None = None,
    ) -> list[EnrichmentResult]:
        """Extract IOCs from text and enrich them.

        Args:
            text: Text to extract IOCs from
            case_id: Optional case ID for tracking

        Returns:
            List of enrichment results for each extracted IOC
        """
        # Extract IOCs
        matches = self.extractor.extract(text)

        if not matches:
            logger.debug("No IOCs extracted from text")
            return []

        logger.info(f"Extracted {len(matches)} IOCs, enriching...")

        # Deduplicate
        unique_iocs = {(m.value, m.ioc_type): m for m in matches}

        # Enrich each IOC
        results = await asyncio.gather(
            *[self.enrich_indicator(match.value, match.ioc_type) for match in unique_iocs.values()]
        )

        return list(results)

    async def enrich_indicator(
        self,
        indicator: str,
        indicator_type: IOCType,
    ) -> EnrichmentResult:
        """Enrich a single indicator.

        Args:
            indicator: The IOC value
            indicator_type: Type of IOC

        Returns:
            EnrichmentResult with data from all sources
        """
        result = EnrichmentResult(
            indicator=indicator,
            indicator_type=indicator_type,
            status=EnrichmentStatus.PENDING,
        )

        # Check cache first
        cached = await self._get_cached(indicator, indicator_type)
        if cached:
            return cached

        result.status = EnrichmentStatus.IN_PROGRESS

        # Query all enabled providers
        async with self._semaphore:
            provider_tasks = []
            for name, provider in self._providers.items():
                if name in self.config.enabled_providers:
                    provider_tasks.append(
                        self._query_provider(name, provider, indicator, indicator_type)
                    )

            if provider_tasks:
                provider_results = await asyncio.gather(*provider_tasks, return_exceptions=True)

                for name, data in zip(self._providers.keys(), provider_results):
                    if isinstance(data, Exception):
                        result.errors.append(f"{name}: {str(data)}")
                    elif data:
                        result.sources[name] = data

        # Aggregate results
        self._aggregate_results(result)

        # Cache result
        await self._cache_result(result)

        result.enriched_at = datetime.now(UTC)

        if result.sources:
            result.status = EnrichmentStatus.COMPLETED
        elif result.errors:
            result.status = EnrichmentStatus.FAILED
        else:
            result.status = EnrichmentStatus.NOT_FOUND

        return result

    async def enrich_batch(
        self,
        indicators: list[tuple[str, IOCType]],
        max_concurrent: int | None = None,
    ) -> list[EnrichmentResult]:
        """Enrich multiple indicators in batch.

        Args:
            indicators: List of (indicator, type) tuples
            max_concurrent: Override max concurrent requests

        Returns:
            List of enrichment results
        """
        if max_concurrent:
            semaphore = asyncio.Semaphore(max_concurrent)
        else:
            semaphore = self._semaphore

        async def enrich_with_semaphore(indicator: str, ioc_type: IOCType):
            async with semaphore:
                return await self.enrich_indicator(indicator, ioc_type)

        tasks = [enrich_with_semaphore(indicator, ioc_type) for indicator, ioc_type in indicators]

        return await asyncio.gather(*tasks)

    async def _query_provider(
        self,
        name: str,
        provider,
        indicator: str,
        indicator_type: IOCType,
    ) -> dict[str, Any] | None:
        """Query a single provider with timeout.

        Args:
            name: Provider name
            provider: Provider instance
            indicator: IOC value
            indicator_type: IOC type

        Returns:
            Provider response data or None
        """
        try:
            result = await asyncio.wait_for(
                provider.enrich(indicator, indicator_type),
                timeout=self.config.request_timeout_seconds,
            )
            return result
        except TimeoutError:
            logger.warning(f"Provider {name} timed out for {indicator}")
            return None
        except Exception as e:
            logger.error(f"Provider {name} error for {indicator}: {e}")
            raise

    def _aggregate_results(self, result: EnrichmentResult) -> None:
        """Aggregate results from multiple sources into final verdict.

        Args:
            result: EnrichmentResult to aggregate
        """
        if not result.sources:
            result.verdict = "unknown"
            return

        scores = []
        verdicts = []
        all_tags = set()
        first_seen_dates = []
        last_seen_dates = []

        for source_name, source_data in result.sources.items():
            # Collect scores
            if "score" in source_data:
                scores.append(source_data["score"])

            # Collect verdicts
            if "verdict" in source_data:
                verdicts.append(source_data["verdict"])
            elif "malicious" in source_data:
                verdicts.append("malicious" if source_data["malicious"] else "clean")

            # Collect tags
            if "tags" in source_data:
                all_tags.update(source_data["tags"])
            if "labels" in source_data:
                all_tags.update(source_data["labels"])

            # Collect dates
            if "first_seen" in source_data:
                try:
                    dt = datetime.fromisoformat(source_data["first_seen"].replace("Z", "+00:00"))
                    first_seen_dates.append(dt)
                except Exception:
                    pass
            if "last_seen" in source_data:
                try:
                    dt = datetime.fromisoformat(source_data["last_seen"].replace("Z", "+00:00"))
                    last_seen_dates.append(dt)
                except Exception:
                    pass

        # Calculate aggregate score
        if scores:
            result.score = int(sum(scores) / len(scores))

        # Determine aggregate verdict
        if verdicts:
            if "malicious" in verdicts:
                result.verdict = "malicious"
            elif "suspicious" in verdicts:
                result.verdict = "suspicious"
            elif all(v == "clean" for v in verdicts):
                result.verdict = "clean"
            else:
                result.verdict = "unknown"
        else:
            result.verdict = "unknown"

        # Merge tags
        result.tags = list(all_tags)

        # Set dates
        if first_seen_dates:
            result.first_seen = min(first_seen_dates)
        if last_seen_dates:
            result.last_seen = max(last_seen_dates)

    async def _get_cached(
        self,
        indicator: str,
        indicator_type: IOCType,
    ) -> EnrichmentResult | None:
        """Get cached enrichment result.

        Args:
            indicator: IOC value
            indicator_type: IOC type

        Returns:
            Cached result or None
        """
        if not self.redis:
            return None

        cache_key = f"enrichment:{indicator_type.value}:{indicator}"

        try:
            import json

            cached_data = await self.redis.get(cache_key)
            if cached_data:
                data = json.loads(cached_data)
                result = EnrichmentResult(
                    indicator=data["indicator"],
                    indicator_type=IOCType(data["indicator_type"]),
                    status=EnrichmentStatus.CACHED,
                    sources=data.get("sources", {}),
                    score=data.get("score"),
                    verdict=data.get("verdict"),
                    tags=data.get("tags", []),
                    cache_hit=True,
                )
                if data.get("enriched_at"):
                    result.enriched_at = datetime.fromisoformat(data["enriched_at"])
                return result
        except Exception as e:
            logger.debug(f"Cache read error: {e}")

        return None

    async def _cache_result(self, result: EnrichmentResult) -> None:
        """Cache an enrichment result.

        Args:
            result: Result to cache
        """
        if not self.redis:
            return

        cache_key = f"enrichment:{result.indicator_type.value}:{result.indicator}"

        # Determine TTL
        if result.status == EnrichmentStatus.NOT_FOUND:
            ttl = self.config.cache_negative_ttl_seconds
        else:
            ttl = self.config.cache_ttl_seconds

        try:
            import json

            await self.redis.set(
                cache_key,
                json.dumps(result.to_dict()),
                ex=ttl,
            )
        except Exception as e:
            logger.debug(f"Cache write error: {e}")

    async def clear_cache(self, pattern: str = "enrichment:*") -> int:
        """Clear cached enrichment results.

        Args:
            pattern: Redis key pattern to clear

        Returns:
            Number of keys deleted
        """
        if not self.redis:
            return 0

        try:
            keys = []
            async for key in self.redis.scan_iter(pattern):
                keys.append(key)

            if keys:
                return await self.redis.delete(*keys)
            return 0
        except Exception as e:
            logger.error(f"Cache clear error: {e}")
            return 0

    def get_stats(self) -> dict[str, Any]:
        """Get pipeline statistics.

        Returns:
            Dictionary with pipeline stats
        """
        return {
            "providers": list(self._providers.keys()),
            "enabled_providers": self.config.enabled_providers,
            "max_concurrent": self.config.max_concurrent_requests,
            "cache_enabled": self.redis is not None,
            "cache_ttl": self.config.cache_ttl_seconds,
        }
