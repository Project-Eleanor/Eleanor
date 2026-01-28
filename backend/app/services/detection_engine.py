"""Detection engine service for executing rules against Elasticsearch.

This service handles:
- Scheduled rule execution
- Manual rule triggering
- Query execution against Elasticsearch
- Result processing and threshold checking
"""

import logging
from datetime import datetime, timedelta
from typing import Any

from elasticsearch import AsyncElasticsearch
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_elasticsearch
from app.models.analytics import DetectionRule, RuleExecution, RuleStatus

logger = logging.getLogger(__name__)
settings = get_settings()


class DetectionEngine:
    """Detection rule execution engine.

    Executes detection rules against Elasticsearch and returns matches.
    Supports both KQL and ES|QL query languages.
    """

    def __init__(self, es: AsyncElasticsearch):
        """Initialize detection engine.

        Args:
            es: Elasticsearch client
        """
        self.es = es
        self.index_prefix = settings.elasticsearch_index_prefix

    async def execute_rule(
        self,
        rule: DetectionRule,
        execution: RuleExecution,
        db: AsyncSession,
    ) -> dict[str, Any]:
        """Execute a single detection rule.

        Args:
            rule: The detection rule to execute
            execution: The execution record to update
            db: Database session

        Returns:
            Execution results including hits and metadata
        """
        start_time = datetime.utcnow()

        try:
            # Determine time range from lookback period
            lookback_minutes = rule.lookback_period or 15
            time_from = datetime.utcnow() - timedelta(minutes=lookback_minutes)

            # Build and execute query
            if rule.query_language.lower() == "esql":
                hits = await self._execute_esql(rule, time_from)
            else:  # KQL or Lucene
                hits = await self._execute_kql(rule, time_from)

            # Calculate execution time
            end_time = datetime.utcnow()
            duration_ms = int((end_time - start_time).total_seconds() * 1000)

            # Check threshold
            threshold_exceeded = self._check_threshold(rule, len(hits))

            # Update execution record
            execution.completed_at = end_time
            execution.duration_ms = duration_ms
            execution.hits_count = len(hits)
            execution.events_scanned = len(hits)  # Approximate
            execution.status = "completed"

            # Update rule statistics
            if len(hits) > 0:
                rule.hit_count += len(hits)
            rule.last_run_at = end_time

            await db.commit()

            logger.info(
                "Rule %s executed: %d hits in %dms",
                rule.name,
                len(hits),
                duration_ms,
            )

            return {
                "rule_id": str(rule.id),
                "execution_id": str(execution.id),
                "hits": hits,
                "hits_count": len(hits),
                "threshold_exceeded": threshold_exceeded,
                "duration_ms": duration_ms,
                "status": "completed",
            }

        except Exception as e:
            logger.error("Rule execution failed for %s: %s", rule.name, str(e))

            # Update execution with error
            execution.completed_at = datetime.utcnow()
            execution.status = "failed"
            execution.error_message = str(e)

            await db.commit()

            return {
                "rule_id": str(rule.id),
                "execution_id": str(execution.id),
                "hits": [],
                "hits_count": 0,
                "threshold_exceeded": False,
                "status": "failed",
                "error": str(e),
            }

    async def _execute_esql(
        self,
        rule: DetectionRule,
        time_from: datetime,
    ) -> list[dict[str, Any]]:
        """Execute an ES|QL query.

        Args:
            rule: Detection rule with ES|QL query
            time_from: Start time for query range

        Returns:
            List of matching documents
        """
        # ES|QL queries are executed via the esql.query API
        query = rule.query

        # Add time filter if not already present
        if "@timestamp" not in query.lower() and "where" in query.lower():
            # Insert time filter after WHERE clause
            time_filter = f'@timestamp >= "{time_from.isoformat()}"'
            query = query.replace(" WHERE ", f" WHERE {time_filter} AND ", 1)
        elif "@timestamp" not in query.lower():
            # Append WHERE clause
            time_filter = f' | WHERE @timestamp >= "{time_from.isoformat()}"'
            query = query + time_filter

        try:
            response = await self.es.esql.query(query=query)

            # Parse ES|QL response format
            columns = response.get("columns", [])
            values = response.get("values", [])

            # Convert to list of dicts
            hits = []
            for row in values:
                doc = {}
                for i, col in enumerate(columns):
                    doc[col["name"]] = row[i] if i < len(row) else None
                hits.append(doc)

            return hits

        except Exception as e:
            logger.error("ES|QL query failed: %s", str(e))
            raise

    async def _execute_kql(
        self,
        rule: DetectionRule,
        time_from: datetime,
    ) -> list[dict[str, Any]]:
        """Execute a KQL/Lucene query.

        Args:
            rule: Detection rule with KQL query
            time_from: Start time for query range

        Returns:
            List of matching documents
        """
        # Build index pattern
        indices = rule.indices or [f"{self.index_prefix}-events-*"]
        index_pattern = ",".join(indices)

        # Build query body
        query_body = {
            "bool": {
                "must": [
                    {"query_string": {"query": rule.query}},
                    {
                        "range": {
                            "@timestamp": {
                                "gte": time_from.isoformat(),
                                "lte": "now",
                            }
                        }
                    },
                ]
            }
        }

        try:
            response = await self.es.search(
                index=index_pattern,
                query=query_body,
                size=1000,  # Limit results
                sort=[{"@timestamp": "desc"}],
            )

            # Extract hits
            hits = [
                {
                    "_id": hit["_id"],
                    "_index": hit["_index"],
                    **hit["_source"],
                }
                for hit in response["hits"]["hits"]
            ]

            return hits

        except Exception as e:
            logger.error("KQL query failed: %s", str(e))
            raise

    def _check_threshold(self, rule: DetectionRule, hit_count: int) -> bool:
        """Check if hit count exceeds rule threshold.

        Args:
            rule: Detection rule with threshold config
            hit_count: Number of hits from query

        Returns:
            True if threshold exceeded
        """
        if rule.threshold_count is None:
            # No threshold = any hit triggers
            return hit_count > 0

        return hit_count >= rule.threshold_count

    async def run_enabled_rules(self, db: AsyncSession) -> list[dict[str, Any]]:
        """Run all enabled scheduled rules.

        This is called by the scheduler to execute rules on their schedule.

        Args:
            db: Database session

        Returns:
            List of execution results
        """
        # Get enabled scheduled rules
        query = select(DetectionRule).where(
            DetectionRule.status == RuleStatus.ENABLED,
        )
        result = await db.execute(query)
        rules = result.scalars().all()

        results = []
        now = datetime.utcnow()

        for rule in rules:
            # Check if rule should run based on schedule
            if rule.schedule_interval and rule.last_run_at:
                next_run = rule.last_run_at + timedelta(minutes=rule.schedule_interval)
                if now < next_run:
                    continue  # Not time to run yet

            # Create execution record
            execution = RuleExecution(
                rule_id=rule.id,
                status="running",
            )
            db.add(execution)
            await db.flush()

            # Execute rule
            exec_result = await self.execute_rule(rule, execution, db)
            results.append(exec_result)

        return results


# Global detection engine instance
_detection_engine: DetectionEngine | None = None


async def get_detection_engine() -> DetectionEngine:
    """Get the detection engine instance.

    Returns:
        Configured detection engine
    """
    global _detection_engine
    if _detection_engine is None:
        es = await get_elasticsearch()
        _detection_engine = DetectionEngine(es)
    return _detection_engine
