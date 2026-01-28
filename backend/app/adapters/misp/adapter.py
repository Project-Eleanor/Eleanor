"""MISP adapter for threat intelligence sharing.

Provides integration with MISP (Malware Information Sharing Platform)
for threat intelligence sharing and IOC management.
"""

import logging
from datetime import datetime
from typing import Any

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

logger = logging.getLogger(__name__)


# MISP attribute type to IndicatorType mapping
MISP_TYPE_MAP = {
    "ip-src": IndicatorType.IPV4,
    "ip-dst": IndicatorType.IPV4,
    "ip-src|port": IndicatorType.IPV4,
    "ip-dst|port": IndicatorType.IPV4,
    "domain": IndicatorType.DOMAIN,
    "hostname": IndicatorType.DOMAIN,
    "url": IndicatorType.URL,
    "email-src": IndicatorType.EMAIL,
    "email-dst": IndicatorType.EMAIL,
    "md5": IndicatorType.FILE_HASH_MD5,
    "sha1": IndicatorType.FILE_HASH_SHA1,
    "sha256": IndicatorType.FILE_HASH_SHA256,
    "filename": IndicatorType.FILE_NAME,
    "regkey": IndicatorType.REGISTRY_KEY,
    "mutex": IndicatorType.MUTEX,
    "user-agent": IndicatorType.USER_AGENT,
    "vulnerability": IndicatorType.CVE,
}


class MISPAdapter(ThreatIntelAdapter):
    """MISP threat intelligence adapter.

    Provides:
    - IOC enrichment from MISP events
    - Threat actor and campaign information
    - Attribute search and correlation
    - Event and indicator submission

    Configuration:
        url: MISP instance URL
        api_key: MISP API key
        verify_ssl: Verify SSL certificates
    """

    name = "misp"
    description = "MISP threat intelligence sharing platform"

    def __init__(self, config: AdapterConfig):
        super().__init__(config)
        self.url = config.url.rstrip("/")
        self.api_key = config.api_key
        self.verify_ssl = config.verify_ssl
        self.timeout = config.timeout

    async def health_check(self) -> AdapterHealth:
        """Check MISP connectivity."""
        import httpx

        try:
            async with httpx.AsyncClient(verify=self.verify_ssl) as client:
                response = await client.get(
                    f"{self.url}/servers/getVersion",
                    headers=self._get_headers(),
                    timeout=10,
                )

                if response.status_code == 200:
                    data = response.json()
                    return AdapterHealth(
                        adapter_name=self.name,
                        status=AdapterStatus.CONNECTED,
                        version=data.get("version", "unknown"),
                        message="Connected to MISP",
                        details={
                            "perm_sync": data.get("perm_sync"),
                            "perm_sighting": data.get("perm_sighting"),
                        },
                    )
                else:
                    return AdapterHealth(
                        adapter_name=self.name,
                        status=AdapterStatus.ERROR,
                        message=f"HTTP {response.status_code}",
                    )

        except Exception as e:
            return AdapterHealth(
                adapter_name=self.name,
                status=AdapterStatus.ERROR,
                message=str(e),
            )

    async def get_config(self) -> dict[str, Any]:
        """Get sanitized configuration."""
        return {
            "url": self.url,
            "api_key_configured": bool(self.api_key),
            "verify_ssl": self.verify_ssl,
        }

    def _get_headers(self) -> dict[str, str]:
        """Get API request headers."""
        return {
            "Authorization": self.api_key,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    async def enrich_indicator(
        self,
        value: str,
        indicator_type: IndicatorType,
    ) -> EnrichmentResult:
        """Enrich an indicator via MISP."""
        import httpx

        try:
            # Search for the indicator
            async with httpx.AsyncClient(verify=self.verify_ssl) as client:
                response = await client.post(
                    f"{self.url}/attributes/restSearch",
                    headers=self._get_headers(),
                    json={
                        "returnFormat": "json",
                        "value": value,
                        "includeEventTags": True,
                        "includeContext": True,
                    },
                    timeout=self.timeout,
                )
                response.raise_for_status()
                data = response.json()

            attributes = data.get("response", {}).get("Attribute", [])

            if not attributes:
                # Not found
                indicator = ThreatIndicator(
                    value=value,
                    indicator_type=indicator_type,
                )
                return EnrichmentResult(
                    indicator=indicator,
                    risk_score=0,
                    verdict="unknown",
                )

            # Process first matching attribute
            attr = attributes[0]
            event = attr.get("Event", {})

            # Build indicator
            indicator = ThreatIndicator(
                value=value,
                indicator_type=indicator_type,
                score=self._calculate_score(attr, event),
                first_seen=self._parse_timestamp(attr.get("first_seen") or event.get("date")),
                last_seen=self._parse_timestamp(attr.get("last_seen")),
                sources=["misp"],
                tags=self._extract_tags(attr, event),
                description=attr.get("comment") or event.get("info"),
            )

            # Determine verdict
            threat_level = event.get("threat_level_id", "4")
            if threat_level == "1":  # High
                verdict = "malicious"
            elif threat_level == "2":  # Medium
                verdict = "suspicious"
            elif threat_level == "3":  # Low
                verdict = "suspicious"
            else:
                verdict = "unknown"

            # Get related indicators
            related = await self._get_related_attributes(event.get("id"))

            return EnrichmentResult(
                indicator=indicator,
                risk_score=indicator.score,
                verdict=verdict,
                related_indicators=related,
                raw_data={
                    "event_id": event.get("id"),
                    "event_info": event.get("info"),
                    "attribute_id": attr.get("id"),
                    "threat_level": threat_level,
                    "analysis": event.get("analysis"),
                },
            )

        except Exception as e:
            logger.error(f"MISP enrichment error: {e}")
            indicator = ThreatIndicator(value=value, indicator_type=indicator_type)
            return EnrichmentResult(
                indicator=indicator,
                risk_score=0,
                verdict="unknown",
                raw_data={"error": str(e)},
            )

    async def bulk_enrich(
        self,
        indicators: list[tuple[str, IndicatorType]],
    ) -> list[EnrichmentResult]:
        """Bulk enrich multiple indicators."""
        import asyncio

        tasks = [self.enrich_indicator(value, ioc_type) for value, ioc_type in indicators]
        return await asyncio.gather(*tasks)

    async def get_threat_actor(self, name: str) -> ThreatActor | None:
        """Get threat actor by name."""
        import httpx

        try:
            async with httpx.AsyncClient(verify=self.verify_ssl) as client:
                response = await client.post(
                    f"{self.url}/galaxies/restSearch",
                    headers=self._get_headers(),
                    json={
                        "namespace": "misp",
                        "type": "threat-actor",
                        "value": name,
                    },
                    timeout=self.timeout,
                )
                response.raise_for_status()
                data = response.json()

            galaxies = data.get("response", [])
            if not galaxies:
                return None

            galaxy = galaxies[0]
            cluster = galaxy.get("GalaxyCluster", [{}])[0] if galaxy.get("GalaxyCluster") else {}

            return ThreatActor(
                external_id=cluster.get("uuid", ""),
                name=cluster.get("value", name),
                aliases=cluster.get("meta", {}).get("synonyms", []),
                description=cluster.get("description"),
                motivation=", ".join(cluster.get("meta", {}).get("cfr-suspected-victims", [])),
                country=", ".join(cluster.get("meta", {}).get("country", [])),
            )

        except Exception as e:
            logger.error(f"MISP threat actor lookup error: {e}")
            return None

    async def search_threat_actors(
        self,
        query: str,
        limit: int = 20,
    ) -> list[ThreatActor]:
        """Search threat actors."""
        import httpx

        try:
            async with httpx.AsyncClient(verify=self.verify_ssl) as client:
                response = await client.post(
                    f"{self.url}/galaxies/restSearch",
                    headers=self._get_headers(),
                    json={
                        "namespace": "misp",
                        "type": "threat-actor",
                        "value": query,
                    },
                    timeout=self.timeout,
                )
                response.raise_for_status()
                data = response.json()

            actors = []
            for galaxy in data.get("response", [])[:limit]:
                for cluster in galaxy.get("GalaxyCluster", []):
                    actors.append(
                        ThreatActor(
                            external_id=cluster.get("uuid", ""),
                            name=cluster.get("value", ""),
                            description=cluster.get("description"),
                        )
                    )

            return actors

        except Exception as e:
            logger.error(f"MISP threat actor search error: {e}")
            return []

    async def get_campaign(self, name: str) -> Campaign | None:
        """Get campaign by name."""
        import httpx

        try:
            async with httpx.AsyncClient(verify=self.verify_ssl) as client:
                response = await client.post(
                    f"{self.url}/events/restSearch",
                    headers=self._get_headers(),
                    json={
                        "returnFormat": "json",
                        "eventinfo": name,
                        "limit": 1,
                    },
                    timeout=self.timeout,
                )
                response.raise_for_status()
                data = response.json()

            events = data.get("response", [])
            if not events:
                return None

            event = events[0].get("Event", {})

            return Campaign(
                external_id=event.get("uuid", ""),
                name=event.get("info", name),
                description=event.get("info"),
                first_seen=self._parse_timestamp(event.get("date")),
            )

        except Exception as e:
            logger.error(f"MISP campaign lookup error: {e}")
            return None

    async def search_campaigns(
        self,
        query: str,
        limit: int = 20,
    ) -> list[Campaign]:
        """Search campaigns/events."""
        import httpx

        try:
            async with httpx.AsyncClient(verify=self.verify_ssl) as client:
                response = await client.post(
                    f"{self.url}/events/restSearch",
                    headers=self._get_headers(),
                    json={
                        "returnFormat": "json",
                        "eventinfo": query,
                        "limit": limit,
                    },
                    timeout=self.timeout,
                )
                response.raise_for_status()
                data = response.json()

            campaigns = []
            for item in data.get("response", []):
                event = item.get("Event", {})
                campaigns.append(
                    Campaign(
                        external_id=event.get("uuid", ""),
                        name=event.get("info", ""),
                        first_seen=self._parse_timestamp(event.get("date")),
                    )
                )

            return campaigns

        except Exception as e:
            logger.error(f"MISP campaign search error: {e}")
            return []

    async def get_related_indicators(
        self,
        value: str,
        indicator_type: IndicatorType,
        limit: int = 50,
    ) -> list[ThreatIndicator]:
        """Get indicators related to the given indicator."""
        import httpx

        try:
            # First, find the event containing this indicator
            async with httpx.AsyncClient(verify=self.verify_ssl) as client:
                response = await client.post(
                    f"{self.url}/attributes/restSearch",
                    headers=self._get_headers(),
                    json={
                        "returnFormat": "json",
                        "value": value,
                        "limit": 1,
                    },
                    timeout=self.timeout,
                )
                response.raise_for_status()
                data = response.json()

            attributes = data.get("response", {}).get("Attribute", [])
            if not attributes:
                return []

            event_id = attributes[0].get("event_id")
            return await self._get_related_attributes(event_id, limit)

        except Exception as e:
            logger.error(f"MISP related indicators error: {e}")
            return []

    async def submit_indicator(
        self,
        value: str,
        indicator_type: IndicatorType,
        description: str | None = None,
        tags: list[str] | None = None,
        confidence: int = 50,
    ) -> ThreatIndicator:
        """Submit a new indicator to MISP."""
        import httpx

        # Map indicator type to MISP type
        misp_type = self._indicator_type_to_misp(indicator_type)

        try:
            async with httpx.AsyncClient(verify=self.verify_ssl) as client:
                # Create an event
                event_response = await client.post(
                    f"{self.url}/events/add",
                    headers=self._get_headers(),
                    json={
                        "info": f"Eleanor submission: {value}",
                        "distribution": 0,  # Organization only
                        "threat_level_id": 3,  # Low
                        "analysis": 0,  # Initial
                    },
                    timeout=self.timeout,
                )
                event_response.raise_for_status()
                event_data = event_response.json()
                event_id = event_data.get("Event", {}).get("id")

                # Add attribute to event
                attr_response = await client.post(
                    f"{self.url}/attributes/add/{event_id}",
                    headers=self._get_headers(),
                    json={
                        "type": misp_type,
                        "value": value,
                        "comment": description or "Submitted from Eleanor",
                        "to_ids": True,
                    },
                    timeout=self.timeout,
                )
                attr_response.raise_for_status()

                return ThreatIndicator(
                    value=value,
                    indicator_type=indicator_type,
                    score=confidence,
                    sources=["eleanor"],
                    tags=tags or [],
                    description=description,
                )

        except Exception as e:
            logger.error(f"MISP submit error: {e}")
            raise

    async def _get_related_attributes(
        self,
        event_id: str | None,
        limit: int = 50,
    ) -> list[ThreatIndicator]:
        """Get attributes from an event."""
        import httpx

        if not event_id:
            return []

        try:
            async with httpx.AsyncClient(verify=self.verify_ssl) as client:
                response = await client.get(
                    f"{self.url}/events/view/{event_id}",
                    headers=self._get_headers(),
                    timeout=self.timeout,
                )
                response.raise_for_status()
                data = response.json()

            event = data.get("Event", {})
            indicators = []

            for attr in event.get("Attribute", [])[:limit]:
                ioc_type = MISP_TYPE_MAP.get(attr.get("type"))
                if ioc_type:
                    indicators.append(
                        ThreatIndicator(
                            value=attr.get("value", ""),
                            indicator_type=ioc_type,
                            sources=["misp"],
                            description=attr.get("comment"),
                        )
                    )

            return indicators

        except Exception as e:
            logger.error(f"MISP get event attributes error: {e}")
            return []

    def _calculate_score(self, attribute: dict, event: dict) -> int:
        """Calculate threat score from MISP data."""
        score = 50  # Base score

        # Threat level adjustment
        threat_level = event.get("threat_level_id", "4")
        if threat_level == "1":  # High
            score += 30
        elif threat_level == "2":  # Medium
            score += 15
        elif threat_level == "3":  # Low
            score += 5

        # IDS flag
        if attribute.get("to_ids"):
            score += 10

        # Sightings
        sighting_count = int(attribute.get("sightings", {}).get("count", 0) or 0)
        if sighting_count > 0:
            score += min(sighting_count * 2, 10)

        return min(score, 100)

    def _extract_tags(self, attribute: dict, event: dict) -> list[str]:
        """Extract tags from attribute and event."""
        tags = []

        # Attribute tags
        for tag in attribute.get("Tag", []):
            tags.append(tag.get("name", ""))

        # Event tags
        for tag in event.get("Tag", []):
            tags.append(tag.get("name", ""))

        return [t for t in tags if t]

    def _parse_timestamp(self, value: str | None) -> datetime | None:
        """Parse MISP timestamp."""
        if not value:
            return None

        try:
            # Try ISO format
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            pass

        try:
            # Try date only format
            return datetime.strptime(value, "%Y-%m-%d")
        except ValueError:
            pass

        return None

    def _indicator_type_to_misp(self, ioc_type: IndicatorType) -> str:
        """Convert IndicatorType to MISP attribute type."""
        reverse_map = {v: k for k, v in MISP_TYPE_MAP.items()}
        return reverse_map.get(ioc_type, "text")
