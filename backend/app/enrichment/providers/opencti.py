"""OpenCTI enrichment provider.

Provides threat intelligence enrichment via the OpenCTI GraphQL API.
"""

import logging
from typing import Any

from app.enrichment.extractors.ioc import IOCType

logger = logging.getLogger(__name__)


# GraphQL queries for different indicator types
STIX_INDICATOR_QUERY = """
query GetIndicator($value: String!) {
  indicators(filters: {
    mode: and,
    filters: [{ key: "pattern", values: [$value], operator: contains }],
    filterGroups: []
  }, first: 10) {
    edges {
      node {
        id
        name
        description
        pattern
        pattern_type
        valid_from
        valid_until
        x_opencti_score
        x_opencti_detection
        created
        modified
        createdBy {
          ... on Identity {
            name
          }
        }
        objectLabel {
          id
          value
          color
        }
        objectMarking {
          id
          definition
        }
        killChainPhases {
          kill_chain_name
          phase_name
        }
        externalReferences {
          source_name
          url
        }
      }
    }
  }
}
"""

STIX_OBSERVABLE_QUERY = """
query GetObservable($value: String!) {
  stixCyberObservables(filters: {
    mode: and,
    filters: [{ key: "value", values: [$value] }],
    filterGroups: []
  }, first: 10) {
    edges {
      node {
        id
        entity_type
        observable_value
        x_opencti_score
        x_opencti_description
        created_at
        updated_at
        createdBy {
          ... on Identity {
            name
          }
        }
        objectLabel {
          id
          value
          color
        }
        objectMarking {
          id
          definition
        }
        indicators {
          edges {
            node {
              id
              name
              pattern
              x_opencti_score
            }
          }
        }
        stixCoreRelationships {
          edges {
            node {
              relationship_type
              to {
                ... on BasicObject {
                  id
                  entity_type
                }
                ... on StixObject {
                  x_opencti_stix_ids
                }
                ... on ThreatActor {
                  name
                }
                ... on IntrusionSet {
                  name
                }
                ... on Malware {
                  name
                }
                ... on AttackPattern {
                  name
                  x_mitre_id
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


class OpenCTIEnrichmentProvider:
    """Enrichment provider using OpenCTI threat intelligence platform.

    Queries the OpenCTI GraphQL API to enrich indicators with:
    - Threat scores
    - Labels/tags
    - Related threat actors
    - Related malware families
    - MITRE ATT&CK techniques
    - Kill chain phases
    """

    def __init__(
        self,
        url: str,
        api_key: str,
        verify_ssl: bool = True,
    ):
        """Initialize the OpenCTI provider.

        Args:
            url: OpenCTI API URL
            api_key: OpenCTI API key
            verify_ssl: Whether to verify SSL certificates
        """
        self.url = url.rstrip("/")
        self.api_key = api_key
        self.verify_ssl = verify_ssl
        self.graphql_url = f"{self.url}/graphql"

    async def enrich(
        self,
        indicator: str,
        indicator_type: IOCType,
    ) -> dict[str, Any] | None:
        """Enrich an indicator via OpenCTI.

        Args:
            indicator: IOC value
            indicator_type: Type of IOC

        Returns:
            Enrichment data or None if not found
        """
        import httpx

        # Try both indicator and observable queries
        results = []

        try:
            async with httpx.AsyncClient(verify=self.verify_ssl) as client:
                # Query for STIX indicators
                indicator_result = await self._query_indicators(client, indicator)
                if indicator_result:
                    results.append(indicator_result)

                # Query for STIX observables
                observable_result = await self._query_observables(client, indicator)
                if observable_result:
                    results.append(observable_result)

        except httpx.HTTPError as e:
            logger.error(f"OpenCTI HTTP error: {e}")
            raise
        except Exception as e:
            logger.error(f"OpenCTI error: {e}")
            raise

        if not results:
            return None

        # Merge results
        return self._merge_results(results)

    async def _query_indicators(
        self,
        client,
        value: str,
    ) -> dict[str, Any] | None:
        """Query OpenCTI for matching indicators."""
        response = await client.post(
            self.graphql_url,
            json={
                "query": STIX_INDICATOR_QUERY,
                "variables": {"value": value},
            },
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )

        response.raise_for_status()
        data = response.json()

        if "errors" in data:
            logger.warning(f"OpenCTI GraphQL errors: {data['errors']}")
            return None

        edges = data.get("data", {}).get("indicators", {}).get("edges", [])
        if not edges:
            return None

        # Process first matching indicator
        node = edges[0]["node"]
        return self._process_indicator_node(node)

    async def _query_observables(
        self,
        client,
        value: str,
    ) -> dict[str, Any] | None:
        """Query OpenCTI for matching observables."""
        response = await client.post(
            self.graphql_url,
            json={
                "query": STIX_OBSERVABLE_QUERY,
                "variables": {"value": value},
            },
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )

        response.raise_for_status()
        data = response.json()

        if "errors" in data:
            logger.warning(f"OpenCTI GraphQL errors: {data['errors']}")
            return None

        edges = data.get("data", {}).get("stixCyberObservables", {}).get("edges", [])
        if not edges:
            return None

        # Process first matching observable
        node = edges[0]["node"]
        return self._process_observable_node(node)

    def _process_indicator_node(self, node: dict) -> dict[str, Any]:
        """Process an indicator node from GraphQL response."""
        result = {
            "source": "opencti",
            "type": "indicator",
            "id": node.get("id"),
            "name": node.get("name"),
            "description": node.get("description"),
            "pattern": node.get("pattern"),
            "pattern_type": node.get("pattern_type"),
            "score": node.get("x_opencti_score"),
            "detection": node.get("x_opencti_detection", False),
            "created": node.get("created"),
            "modified": node.get("modified"),
            "valid_from": node.get("valid_from"),
            "valid_until": node.get("valid_until"),
        }

        # Extract labels
        labels = node.get("objectLabel", [])
        if labels:
            result["labels"] = [label.get("value") for label in labels if label.get("value")]

        # Extract markings (TLP)
        markings = node.get("objectMarking", [])
        if markings:
            result["markings"] = [m.get("definition") for m in markings if m.get("definition")]

        # Extract kill chain phases
        phases = node.get("killChainPhases", [])
        if phases:
            result["kill_chain"] = [
                {"chain": phase.get("kill_chain_name"), "phase": phase.get("phase_name")}
                for phase in phases
            ]

        # Extract external references
        refs = node.get("externalReferences", [])
        if refs:
            result["references"] = [
                {"source": reference.get("source_name"), "url": reference.get("url")}
                for reference in refs
            ]

        # Created by
        created_by = node.get("createdBy")
        if created_by:
            result["created_by"] = created_by.get("name")

        # Determine verdict based on score
        score = result.get("score")
        if score is not None:
            if score >= 70:
                result["verdict"] = "malicious"
            elif score >= 40:
                result["verdict"] = "suspicious"
            else:
                result["verdict"] = "unknown"

        return result

    def _process_observable_node(self, node: dict) -> dict[str, Any]:
        """Process an observable node from GraphQL response."""
        result = {
            "source": "opencti",
            "type": "observable",
            "id": node.get("id"),
            "entity_type": node.get("entity_type"),
            "value": node.get("observable_value"),
            "score": node.get("x_opencti_score"),
            "description": node.get("x_opencti_description"),
            "created": node.get("created_at"),
            "modified": node.get("updated_at"),
        }

        # Extract labels
        labels = node.get("objectLabel", [])
        if labels:
            result["labels"] = [label.get("value") for label in labels if label.get("value")]

        # Extract related indicators
        indicator_edges = node.get("indicators", {}).get("edges", [])
        if indicator_edges:
            result["related_indicators"] = [
                {
                    "id": edge["node"].get("id"),
                    "name": edge["node"].get("name"),
                    "score": edge["node"].get("x_opencti_score"),
                }
                for edge in indicator_edges
            ]

        # Extract relationships (threat actors, malware, etc.)
        rel_edges = node.get("stixCoreRelationships", {}).get("edges", [])
        threat_actors = []
        malware = []
        attack_patterns = []

        for edge in rel_edges:
            rel_node = edge.get("node", {})
            to_obj = rel_node.get("to", {})
            entity_type = to_obj.get("entity_type", "")
            name = to_obj.get("name")

            if entity_type in ("Threat-Actor", "Intrusion-Set") and name:
                threat_actors.append(name)
            elif entity_type == "Malware" and name:
                malware.append(name)
            elif entity_type == "Attack-Pattern" and name:
                attack_patterns.append({
                    "name": name,
                    "mitre_id": to_obj.get("x_mitre_id"),
                })

        if threat_actors:
            result["threat_actors"] = list(set(threat_actors))
        if malware:
            result["malware_families"] = list(set(malware))
        if attack_patterns:
            result["attack_patterns"] = attack_patterns

        # Determine verdict
        score = result.get("score")
        if score is not None:
            if score >= 70:
                result["verdict"] = "malicious"
            elif score >= 40:
                result["verdict"] = "suspicious"
            else:
                result["verdict"] = "unknown"
        elif threat_actors or malware:
            result["verdict"] = "malicious"

        return result

    def _merge_results(self, results: list[dict]) -> dict[str, Any]:
        """Merge multiple results into one."""
        if len(results) == 1:
            return results[0]

        # Use first result as base
        merged = results[0].copy()

        for other in results[1:]:
            # Take higher score
            if other.get("score") and (not merged.get("score") or other["score"] > merged["score"]):
                merged["score"] = other["score"]

            # Merge labels
            other_labels = other.get("labels", [])
            if other_labels:
                merged_labels = set(merged.get("labels", []))
                merged_labels.update(other_labels)
                merged["labels"] = list(merged_labels)

            # Merge threat actors
            if other.get("threat_actors"):
                merged_ta = set(merged.get("threat_actors", []))
                merged_ta.update(other["threat_actors"])
                merged["threat_actors"] = list(merged_ta)

            # Merge malware
            if other.get("malware_families"):
                merged_mw = set(merged.get("malware_families", []))
                merged_mw.update(other["malware_families"])
                merged["malware_families"] = list(merged_mw)

            # Take verdict from higher score result
            if other.get("verdict") == "malicious":
                merged["verdict"] = "malicious"
            elif other.get("verdict") == "suspicious" and merged.get("verdict") != "malicious":
                merged["verdict"] = "suspicious"

        return merged

    async def health_check(self) -> dict[str, Any]:
        """Check OpenCTI connectivity.

        Returns:
            Health status dictionary
        """
        import httpx

        try:
            async with httpx.AsyncClient(verify=self.verify_ssl) as client:
                response = await client.post(
                    self.graphql_url,
                    json={"query": "{ about { version } }"},
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    timeout=10.0,
                )
                response.raise_for_status()
                data = response.json()

                version = data.get("data", {}).get("about", {}).get("version", "unknown")
                return {
                    "status": "healthy",
                    "version": version,
                }

        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
            }
