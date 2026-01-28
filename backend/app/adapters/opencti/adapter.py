"""OpenCTI adapter implementation.

Provides integration with OpenCTI for:
- Indicator enrichment (IPs, domains, hashes)
- Threat actor lookup
- Campaign information
- Related indicator discovery

OpenCTI uses a GraphQL API for all operations.
"""

import logging
from typing import Any

import httpx

from app.adapters.base import (
    AdapterConfig,
    AdapterHealth,
    AdapterStatus,
    Campaign,
    EnrichmentResult,
    IndicatorType,
    ThreatActor,
    ThreatIndicator,
    ThreatIntelAdapter,
)
from app.adapters.opencti.schemas import (
    OpenCTICampaign,
    OpenCTIThreatActor,
)

logger = logging.getLogger(__name__)


# Map Eleanor indicator types to OpenCTI observable types
INDICATOR_TYPE_MAP = {
    IndicatorType.IPV4: "IPv4-Addr",
    IndicatorType.IPV6: "IPv6-Addr",
    IndicatorType.DOMAIN: "Domain-Name",
    IndicatorType.URL: "Url",
    IndicatorType.EMAIL: "Email-Addr",
    IndicatorType.FILE_HASH_MD5: "StixFile",
    IndicatorType.FILE_HASH_SHA1: "StixFile",
    IndicatorType.FILE_HASH_SHA256: "StixFile",
    IndicatorType.FILE_NAME: "StixFile",
    IndicatorType.REGISTRY_KEY: "Windows-Registry-Key",
}


class OpenCTIAdapter(ThreatIntelAdapter):
    """Adapter for OpenCTI threat intelligence platform."""

    name = "opencti"
    description = "OpenCTI threat intelligence enrichment"

    def __init__(self, config: AdapterConfig):
        """Initialize OpenCTI adapter."""
        super().__init__(config)
        self._client: httpx.AsyncClient | None = None
        self._version: str | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.config.url.rstrip("/"),
                timeout=self.config.timeout,
                verify=self.config.verify_ssl,
                headers={
                    "Authorization": f"Bearer {self.config.api_key}",
                    "Content-Type": "application/json",
                },
            )
        return self._client

    async def _graphql(
        self,
        query: str,
        variables: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute GraphQL query."""
        client = await self._get_client()
        response = await client.post(
            "/graphql",
            json={
                "query": query,
                "variables": variables or {},
            },
        )
        response.raise_for_status()
        result = response.json()

        if "errors" in result:
            raise Exception(f"GraphQL errors: {result['errors']}")

        return result.get("data", {})

    async def health_check(self) -> AdapterHealth:
        """Check OpenCTI connectivity."""
        try:
            # Query platform version
            query = """
            query {
                about {
                    version
                    dependencies {
                        name
                        version
                    }
                }
            }
            """
            result = await self._graphql(query)
            self._version = result.get("about", {}).get("version", "unknown")
            self._status = AdapterStatus.CONNECTED

            return AdapterHealth(
                adapter_name=self.name,
                status=AdapterStatus.CONNECTED,
                version=self._version,
                message="Connected to OpenCTI",
            )
        except httpx.HTTPError as e:
            logger.error("OpenCTI health check failed: %s", e)
            self._status = AdapterStatus.ERROR
            return AdapterHealth(
                adapter_name=self.name,
                status=AdapterStatus.ERROR,
                message=f"HTTP error: {e}",
            )
        except Exception as e:
            logger.error("OpenCTI health check failed: %s", e)
            self._status = AdapterStatus.ERROR
            return AdapterHealth(
                adapter_name=self.name,
                status=AdapterStatus.ERROR,
                message=str(e),
            )

    async def get_config(self) -> dict[str, Any]:
        """Get adapter configuration (sanitized)."""
        return {
            "url": self.config.url,
            "verify_ssl": self.config.verify_ssl,
            "has_api_key": bool(self.config.api_key),
        }

    # =========================================================================
    # Indicator Enrichment
    # =========================================================================

    async def enrich_indicator(
        self,
        value: str,
        indicator_type: IndicatorType,
    ) -> EnrichmentResult:
        """Enrich an indicator with OpenCTI data."""
        INDICATOR_TYPE_MAP.get(indicator_type, "Unknown")

        # Query for observable and related indicators
        query = """
        query SearchObservable($filters: FilterGroup) {
            stixCyberObservables(filters: $filters, first: 1) {
                edges {
                    node {
                        id
                        standard_id
                        entity_type
                        observable_value
                        x_opencti_score
                        createdBy {
                            name
                        }
                        objectLabel {
                            value
                        }
                        indicators {
                            edges {
                                node {
                                    id
                                    name
                                    description
                                    pattern
                                    x_opencti_score
                                    valid_from
                                    valid_until
                                }
                            }
                        }
                        stixCoreRelationships {
                            edges {
                                node {
                                    relationship_type
                                    to {
                                        ... on ThreatActor {
                                            id
                                            name
                                            aliases
                                            description
                                        }
                                        ... on Campaign {
                                            id
                                            name
                                            description
                                        }
                                        ... on Malware {
                                            id
                                            name
                                            description
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
        """

        filters = {
            "mode": "and",
            "filters": [
                {"key": "observable_value", "values": [value]},
            ],
            "filterGroups": [],
        }

        result = await self._graphql(query, {"filters": filters})
        edges = result.get("stixCyberObservables", {}).get("edges", [])

        if not edges:
            # No data found
            return EnrichmentResult(
                indicator=ThreatIndicator(
                    value=value,
                    indicator_type=indicator_type,
                    score=0,
                ),
                risk_score=0,
                verdict="unknown",
            )

        node = edges[0]["node"]

        # Build indicator
        score = node.get("x_opencti_score", 0)
        labels = [label["value"] for label in node.get("objectLabel", [])]

        indicator = ThreatIndicator(
            value=value,
            indicator_type=indicator_type,
            score=score,
            tags=labels,
            sources=["OpenCTI"],
            metadata={
                "opencti_id": node.get("id"),
                "standard_id": node.get("standard_id"),
            },
        )

        # Extract related threat actors and campaigns
        threat_actors = []
        campaigns = []
        relationships = node.get("stixCoreRelationships", {}).get("edges", [])

        for rel_edge in relationships:
            rel_node = rel_edge.get("node", {})
            target = rel_node.get("to", {})

            if "ThreatActor" in str(target.get("__typename", "")):
                threat_actors.append(
                    ThreatActor(
                        external_id=target.get("id", ""),
                        name=target.get("name", ""),
                        aliases=target.get("aliases", []),
                        description=target.get("description"),
                    )
                )
            elif "Campaign" in str(target.get("__typename", "")):
                campaigns.append(
                    Campaign(
                        external_id=target.get("id", ""),
                        name=target.get("name", ""),
                        description=target.get("description"),
                    )
                )

        # Determine verdict based on score
        if score >= 75:
            verdict = "malicious"
        elif score >= 50:
            verdict = "suspicious"
        elif score > 0:
            verdict = "suspicious"
        else:
            verdict = "clean" if not threat_actors and not campaigns else "suspicious"

        return EnrichmentResult(
            indicator=indicator,
            risk_score=score,
            verdict=verdict,
            threat_actors=threat_actors,
            campaigns=campaigns,
            raw_data=node,
        )

    async def bulk_enrich(
        self,
        indicators: list[tuple[str, IndicatorType]],
    ) -> list[EnrichmentResult]:
        """Bulk enrich multiple indicators."""
        results = []
        for value, indicator_type in indicators:
            try:
                result = await self.enrich_indicator(value, indicator_type)
                results.append(result)
            except Exception as e:
                logger.error("Failed to enrich %s: %s", value, e)
                results.append(
                    EnrichmentResult(
                        indicator=ThreatIndicator(
                            value=value,
                            indicator_type=indicator_type,
                            score=0,
                        ),
                        risk_score=0,
                        verdict="unknown",
                    )
                )
        return results

    # =========================================================================
    # Threat Actor Operations
    # =========================================================================

    async def get_threat_actor(self, name: str) -> ThreatActor | None:
        """Get threat actor by name."""
        query = """
        query GetThreatActor($filters: FilterGroup) {
            threatActors(filters: $filters, first: 1) {
                edges {
                    node {
                        id
                        standard_id
                        name
                        description
                        aliases
                        first_seen
                        last_seen
                        sophistication
                        resource_level
                        primary_motivation
                        goals
                        roles
                        objectLabel {
                            value
                        }
                    }
                }
            }
        }
        """

        filters = {
            "mode": "or",
            "filters": [
                {"key": "name", "values": [name]},
                {"key": "aliases", "values": [name]},
            ],
            "filterGroups": [],
        }

        result = await self._graphql(query, {"filters": filters})
        edges = result.get("threatActors", {}).get("edges", [])

        if not edges:
            return None

        node = edges[0]["node"]
        opencti_actor = OpenCTIThreatActor(**node)

        return ThreatActor(
            external_id=opencti_actor.id,
            name=opencti_actor.name,
            aliases=opencti_actor.aliases,
            description=opencti_actor.description,
            motivation=opencti_actor.primary_motivation,
            sophistication=opencti_actor.sophistication,
            first_seen=opencti_actor.first_seen,
            last_seen=opencti_actor.last_seen,
            metadata={
                "standard_id": opencti_actor.standard_id,
                "resource_level": opencti_actor.resource_level,
                "goals": opencti_actor.goals,
            },
        )

    async def search_threat_actors(
        self,
        query: str,
        limit: int = 20,
    ) -> list[ThreatActor]:
        """Search threat actors."""
        gql_query = """
        query SearchThreatActors($search: String, $first: Int) {
            threatActors(search: $search, first: $first) {
                edges {
                    node {
                        id
                        name
                        description
                        aliases
                        first_seen
                        last_seen
                        sophistication
                        primary_motivation
                    }
                }
            }
        }
        """

        result = await self._graphql(gql_query, {"search": query, "first": limit})
        edges = result.get("threatActors", {}).get("edges", [])

        return [
            ThreatActor(
                external_id=edge["node"]["id"],
                name=edge["node"]["name"],
                aliases=edge["node"].get("aliases", []),
                description=edge["node"].get("description"),
                motivation=edge["node"].get("primary_motivation"),
                sophistication=edge["node"].get("sophistication"),
                first_seen=edge["node"].get("first_seen"),
                last_seen=edge["node"].get("last_seen"),
            )
            for edge in edges
        ]

    # =========================================================================
    # Campaign Operations
    # =========================================================================

    async def get_campaign(self, name: str) -> Campaign | None:
        """Get campaign by name."""
        query = """
        query GetCampaign($filters: FilterGroup) {
            campaigns(filters: $filters, first: 1) {
                edges {
                    node {
                        id
                        standard_id
                        name
                        description
                        aliases
                        first_seen
                        last_seen
                        objective
                    }
                }
            }
        }
        """

        filters = {
            "mode": "or",
            "filters": [
                {"key": "name", "values": [name]},
                {"key": "aliases", "values": [name]},
            ],
            "filterGroups": [],
        }

        result = await self._graphql(query, {"filters": filters})
        edges = result.get("campaigns", {}).get("edges", [])

        if not edges:
            return None

        node = edges[0]["node"]
        opencti_campaign = OpenCTICampaign(**node)

        return Campaign(
            external_id=opencti_campaign.id,
            name=opencti_campaign.name,
            description=opencti_campaign.description,
            first_seen=opencti_campaign.first_seen,
            last_seen=opencti_campaign.last_seen,
            metadata={
                "standard_id": opencti_campaign.standard_id,
                "objective": opencti_campaign.objective,
                "aliases": opencti_campaign.aliases,
            },
        )

    async def search_campaigns(
        self,
        query: str,
        limit: int = 20,
    ) -> list[Campaign]:
        """Search campaigns."""
        gql_query = """
        query SearchCampaigns($search: String, $first: Int) {
            campaigns(search: $search, first: $first) {
                edges {
                    node {
                        id
                        name
                        description
                        first_seen
                        last_seen
                        objective
                    }
                }
            }
        }
        """

        result = await self._graphql(gql_query, {"search": query, "first": limit})
        edges = result.get("campaigns", {}).get("edges", [])

        return [
            Campaign(
                external_id=edge["node"]["id"],
                name=edge["node"]["name"],
                description=edge["node"].get("description"),
                first_seen=edge["node"].get("first_seen"),
                last_seen=edge["node"].get("last_seen"),
            )
            for edge in edges
        ]

    # =========================================================================
    # Related Indicators
    # =========================================================================

    async def get_related_indicators(
        self,
        value: str,
        indicator_type: IndicatorType,
        limit: int = 50,
    ) -> list[ThreatIndicator]:
        """Get indicators related to the given indicator."""
        # First get the observable ID
        query = """
        query GetObservableRelations($filters: FilterGroup, $first: Int) {
            stixCyberObservables(filters: $filters, first: 1) {
                edges {
                    node {
                        stixCoreRelationships(first: $first) {
                            edges {
                                node {
                                    to {
                                        ... on StixCyberObservable {
                                            id
                                            entity_type
                                            observable_value
                                            x_opencti_score
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
        """

        filters = {
            "mode": "and",
            "filters": [{"key": "observable_value", "values": [value]}],
            "filterGroups": [],
        }

        result = await self._graphql(query, {"filters": filters, "first": limit})
        edges = result.get("stixCyberObservables", {}).get("edges", [])

        if not edges:
            return []

        relationships = edges[0]["node"].get("stixCoreRelationships", {}).get("edges", [])

        # Map OpenCTI types back to our types
        type_reverse = {v: k for k, v in INDICATOR_TYPE_MAP.items()}

        indicators = []
        for rel in relationships:
            target = rel.get("node", {}).get("to", {})
            if target and "observable_value" in target:
                target_type = type_reverse.get(
                    target.get("entity_type", ""),
                    IndicatorType.FILE_HASH_SHA256,
                )
                indicators.append(
                    ThreatIndicator(
                        value=target["observable_value"],
                        indicator_type=target_type,
                        score=target.get("x_opencti_score", 0),
                        sources=["OpenCTI"],
                    )
                )

        return indicators

    # =========================================================================
    # Submit Indicator
    # =========================================================================

    async def submit_indicator(
        self,
        value: str,
        indicator_type: IndicatorType,
        description: str | None = None,
        tags: list[str] | None = None,
        confidence: int = 50,
    ) -> ThreatIndicator:
        """Submit a new indicator to OpenCTI."""
        observable_type = INDICATOR_TYPE_MAP.get(indicator_type, "Unknown")

        # Create observable mutation
        mutation = """
        mutation CreateObservable($input: StixCyberObservableAddInput!) {
            stixCyberObservableAdd(input: $input) {
                id
                standard_id
                entity_type
                observable_value
                x_opencti_score
            }
        }
        """

        input_data = {
            "type": observable_type,
            "observable_value": value,
            "x_opencti_score": confidence,
        }

        if description:
            input_data["x_opencti_description"] = description

        result = await self._graphql(mutation, {"input": input_data})
        created = result.get("stixCyberObservableAdd", {})

        return ThreatIndicator(
            value=value,
            indicator_type=indicator_type,
            score=confidence,
            tags=tags or [],
            sources=["Eleanor"],
            description=description,
            metadata={
                "opencti_id": created.get("id"),
                "standard_id": created.get("standard_id"),
            },
        )

    async def disconnect(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
        await super().disconnect()
