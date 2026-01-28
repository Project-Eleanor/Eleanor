"""Auto-enrichment processor.

Automatically enriches IOCs when cases are created or updated.
"""

import logging
from datetime import UTC, datetime

from app.processors.base import (
    BaseProcessor,
    ProcessorContext,
    ProcessorResult,
    ProcessorStatus,
    ProcessorTrigger,
)
from app.processors.runner import get_runner

logger = logging.getLogger(__name__)


class AutoEnrichProcessor(BaseProcessor):
    """Automatically enrich IOCs in case descriptions and evidence.

    Triggers on:
    - Case creation: Enriches IOCs found in case description
    - Case update: Enriches new IOCs added to description
    - Evidence upload: Enriches IOCs found in parsed evidence

    Features:
    - Extracts IOCs from text using pattern matching
    - Enriches via configured threat intel sources (OpenCTI, etc.)
    - Updates case with enrichment results
    - Caches results to avoid duplicate enrichment
    """

    @property
    def name(self) -> str:
        return "auto_enrich"

    @property
    def description(self) -> str:
        return "Automatically enrich IOCs in cases and evidence"

    @property
    def triggers(self) -> list[ProcessorTrigger]:
        return [
            ProcessorTrigger.CASE_CREATED,
            ProcessorTrigger.CASE_UPDATED,
            ProcessorTrigger.EVIDENCE_PROCESSED,
        ]

    @property
    def priority(self) -> int:
        return 50  # Run early to provide enrichment for other processors

    @property
    def timeout_seconds(self) -> int:
        return 120  # Allow more time for external API calls

    def should_run(self, context: ProcessorContext) -> bool:
        """Only run if enrichment is configured and case has content."""
        if not super().should_run(context):
            return False

        # Need case ID
        if not context.case_id:
            return False

        return True

    async def process(self, context: ProcessorContext) -> ProcessorResult:
        """Execute auto-enrichment.

        Args:
            context: Execution context

        Returns:
            ProcessorResult with enrichment data
        """
        started_at = datetime.now(UTC)
        changes = []
        errors = []
        enrichment_data = {
            "iocs_found": 0,
            "iocs_enriched": 0,
            "sources_queried": [],
        }

        try:
            # Import here to avoid circular imports
            from app.enrichment import EnrichmentPipeline, IOCExtractor
            from app.enrichment.providers.opencti import OpenCTIEnrichmentProvider

            # Get case data
            case = await self._get_case(context)
            if not case:
                return self._create_result(
                    ProcessorStatus.SKIPPED,
                    started_at,
                    message="Case not found",
                )

            # Extract IOCs from case description
            extractor = IOCExtractor()
            text_to_analyze = []

            if case.description:
                text_to_analyze.append(case.description)

            if case.title:
                text_to_analyze.append(case.title)

            # Also check event data for additional text
            if context.event_data.get("added_text"):
                text_to_analyze.append(context.event_data["added_text"])

            combined_text = "\n".join(text_to_analyze)
            ioc_matches = extractor.extract(combined_text)

            if not ioc_matches:
                return self._create_result(
                    ProcessorStatus.COMPLETED,
                    started_at,
                    message="No IOCs found to enrich",
                    data=enrichment_data,
                )

            enrichment_data["iocs_found"] = len(ioc_matches)
            logger.info(f"Found {len(ioc_matches)} IOCs in case {context.case_id}")

            # Create enrichment pipeline
            pipeline = EnrichmentPipeline(redis_client=context.redis_client)

            # Register providers if configured
            # In production, this would check settings for enabled providers
            # For now, we'll try OpenCTI if adapter registry has it
            if context.adapter_registry:
                try:
                    opencti_adapter = await self._get_opencti_adapter(context)
                    if opencti_adapter:
                        provider = OpenCTIEnrichmentProvider(
                            url=opencti_adapter.url,
                            api_key=opencti_adapter.api_key,
                            verify_ssl=opencti_adapter.verify_ssl,
                        )
                        pipeline.register_provider("opencti", provider)
                        enrichment_data["sources_queried"].append("opencti")
                except Exception as e:
                    logger.warning(f"Could not configure OpenCTI provider: {e}")

            # Enrich IOCs
            enriched_results = []
            for match in ioc_matches:
                try:
                    result = await pipeline.enrich_indicator(match.value, match.ioc_type)
                    if result and result.sources:
                        enriched_results.append(result)
                        enrichment_data["iocs_enriched"] += 1
                except Exception as e:
                    logger.warning(f"Failed to enrich {match.value}: {e}")
                    errors.append(f"Enrichment failed for {match.value}: {str(e)}")

            # Update case with enrichment results
            if enriched_results:
                await self._update_case_enrichment(context, case, enriched_results)
                changes.append(f"Added enrichment for {len(enriched_results)} IOCs")

            # Calculate aggregate threat score
            scores = [r.score for r in enriched_results if r.score is not None]
            if scores:
                avg_score = sum(scores) / len(scores)
                enrichment_data["average_threat_score"] = round(avg_score, 1)

                # Update severity if score indicates high threat
                if avg_score >= 70 and case.severity not in ("critical", "high"):
                    await self._suggest_severity_upgrade(context, case, avg_score)
                    changes.append(f"Suggested severity upgrade (threat score: {avg_score})")

            # Add found threat actors and malware
            threat_actors = set()
            malware_families = set()
            for result in enriched_results:
                for source_data in result.sources.values():
                    if ta := source_data.get("threat_actors"):
                        threat_actors.update(ta)
                    if mw := source_data.get("malware_families"):
                        malware_families.update(mw)

            if threat_actors:
                enrichment_data["threat_actors"] = list(threat_actors)
            if malware_families:
                enrichment_data["malware_families"] = list(malware_families)

            return self._create_result(
                ProcessorStatus.COMPLETED,
                started_at,
                message=f"Enriched {enrichment_data['iocs_enriched']} of {enrichment_data['iocs_found']} IOCs",
                data=enrichment_data,
                errors=errors if errors else None,
                changes=changes,
            )

        except Exception as e:
            logger.exception(f"Auto-enrich processor failed: {e}")
            return self._create_result(
                ProcessorStatus.FAILED,
                started_at,
                message=f"Processor error: {str(e)}",
                errors=[str(e)],
            )

    async def _get_case(self, context: ProcessorContext):
        """Retrieve case from database.

        Args:
            context: Execution context

        Returns:
            Case object or None
        """
        if not context.db_session or not context.case_id:
            return None

        try:
            from sqlalchemy import select

            from app.models.case import Case

            stmt = select(Case).where(Case.id == context.case_id)
            result = await context.db_session.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Failed to get case: {e}")
            return None

    async def _get_opencti_adapter(self, context: ProcessorContext):
        """Get OpenCTI adapter if configured.

        Args:
            context: Execution context

        Returns:
            OpenCTI adapter or None
        """
        if not context.adapter_registry:
            return None

        try:
            return context.adapter_registry.get("opencti")
        except Exception:
            return None

    async def _update_case_enrichment(self, context: ProcessorContext, case, results):
        """Update case with enrichment results.

        Args:
            context: Execution context
            case: Case object
            results: List of enrichment results
        """
        if not context.db_session:
            return

        try:
            # Store enrichment in case metadata
            enrichment_summary = []
            for result in results:
                summary = {
                    "indicator": result.indicator,
                    "type": result.indicator_type.value,
                    "verdict": result.verdict,
                    "score": result.score,
                    "tags": result.tags[:10],  # Limit tags
                }
                if result.sources:
                    summary["sources"] = list(result.sources.keys())
                enrichment_summary.append(summary)

            # Update case metadata
            current_metadata = case.case_metadata or {}
            current_metadata["enrichment"] = {
                "last_run": datetime.now(UTC).isoformat(),
                "results": enrichment_summary,
            }
            case.case_metadata = current_metadata

            # Add enrichment tags to case
            enrichment_tags = set(case.tags or [])
            for result in results:
                if result.verdict == "malicious":
                    enrichment_tags.add("enriched:malicious")
                elif result.verdict == "suspicious":
                    enrichment_tags.add("enriched:suspicious")
                for tag in result.tags[:5]:  # Add top 5 tags
                    enrichment_tags.add(f"ti:{tag}")

            case.tags = list(enrichment_tags)

            await context.db_session.commit()

        except Exception as e:
            logger.error(f"Failed to update case enrichment: {e}")
            await context.db_session.rollback()

    async def _suggest_severity_upgrade(self, context: ProcessorContext, case, score):
        """Log suggestion to upgrade case severity.

        In production, this could create a notification or auto-update.

        Args:
            context: Execution context
            case: Case object
            score: Threat score
        """
        logger.warning(
            f"Case {case.case_number} has high threat score ({score}) "
            f"but severity is only '{case.severity}'. Consider upgrading."
        )


# Register the processor
get_runner().register(AutoEnrichProcessor())
