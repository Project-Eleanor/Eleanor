"""MISP enrichment provider.

Provides threat intelligence enrichment via the MISP REST API.
"""

import logging
from typing import Any

from app.enrichment.extractors.ioc import IOCType

logger = logging.getLogger(__name__)


# IOC type to MISP attribute type mapping
IOC_TO_MISP_TYPE = {
    IOCType.IPV4: ["ip-src", "ip-dst"],
    IOCType.IPV6: ["ip-src", "ip-dst"],
    IOCType.DOMAIN: ["domain", "hostname"],
    IOCType.URL: ["url", "link"],
    IOCType.EMAIL: ["email-src", "email-dst"],
    IOCType.MD5: ["md5"],
    IOCType.SHA1: ["sha1"],
    IOCType.SHA256: ["sha256"],
    IOCType.FILENAME: ["filename"],
    IOCType.FILEPATH: ["filename"],
}


class MISPEnrichmentProvider:
    """Enrichment provider using MISP threat intel platform.

    Queries the MISP REST API to enrich indicators with:
    - Event context and threat level
    - Related IOCs from the same event
    - Galaxy clusters (threat actors, malware, etc.)
    - Tags and classifications
    """

    def __init__(
        self,
        url: str,
        api_key: str,
        verify_ssl: bool = True,
    ):
        """Initialize the MISP provider.

        Args:
            url: MISP instance URL
            api_key: MISP API key
            verify_ssl: Verify SSL certificates
        """
        self.url = url.rstrip("/")
        self.api_key = api_key
        self.verify_ssl = verify_ssl

    async def enrich(
        self,
        indicator: str,
        indicator_type: IOCType,
    ) -> dict[str, Any] | None:
        """Enrich an indicator via MISP.

        Args:
            indicator: IOC value
            indicator_type: Type of IOC

        Returns:
            Enrichment data or None if not found
        """
        import httpx

        try:
            async with httpx.AsyncClient(verify=self.verify_ssl) as client:
                response = await client.post(
                    f"{self.url}/attributes/restSearch",
                    headers={
                        "Authorization": self.api_key,
                        "Accept": "application/json",
                        "Content-Type": "application/json",
                    },
                    json={
                        "returnFormat": "json",
                        "value": indicator,
                        "includeEventTags": True,
                        "includeContext": True,
                    },
                    timeout=30.0,
                )
                response.raise_for_status()
                data = response.json()

            attributes = data.get("response", {}).get("Attribute", [])

            if not attributes:
                return None

            # Process results
            return self._process_attributes(attributes, indicator)

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            logger.error(f"MISP HTTP error: {e}")
            raise
        except Exception as e:
            logger.error(f"MISP error: {e}")
            raise

    def _process_attributes(
        self,
        attributes: list[dict],
        indicator: str,
    ) -> dict[str, Any]:
        """Process MISP attribute results."""
        result = {
            "source": "misp",
            "indicator": indicator,
            "events": [],
            "tags": set(),
            "threat_actors": set(),
            "malware": set(),
            "campaigns": set(),
        }

        threat_levels = []
        sighting_count = 0

        for attr in attributes:
            event = attr.get("Event", {})

            # Track events
            event_info = {
                "id": event.get("id"),
                "uuid": event.get("uuid"),
                "info": event.get("info"),
                "date": event.get("date"),
                "threat_level_id": event.get("threat_level_id"),
                "analysis": event.get("analysis"),
            }
            result["events"].append(event_info)

            # Threat level
            tl = event.get("threat_level_id")
            if tl:
                threat_levels.append(int(tl))

            # Sightings
            sightings = attr.get("Sighting", [])
            sighting_count += len(sightings)

            # Tags from attribute
            for tag in attr.get("Tag", []):
                tag_name = tag.get("name", "")
                result["tags"].add(tag_name)

                # Extract threat actor from galaxy tags
                if "threat-actor=" in tag_name.lower():
                    result["threat_actors"].add(tag_name.split("=")[-1].strip('"'))
                elif "misp-galaxy:threat-actor" in tag_name.lower():
                    result["threat_actors"].add(tag_name.split("=")[-1].strip('"'))
                elif "misp-galaxy:malware" in tag_name.lower():
                    result["malware"].add(tag_name.split("=")[-1].strip('"'))
                elif "misp-galaxy:tool" in tag_name.lower():
                    result["malware"].add(tag_name.split("=")[-1].strip('"'))

            # Tags from event
            for tag in event.get("Tag", []):
                tag_name = tag.get("name", "")
                result["tags"].add(tag_name)

        # Convert sets to lists
        result["tags"] = list(result["tags"])
        result["threat_actors"] = list(result["threat_actors"])
        result["malware"] = list(result["malware"])
        result["campaigns"] = list(result["campaigns"])

        # Calculate score
        if threat_levels:
            avg_threat = sum(threat_levels) / len(threat_levels)
            # Threat level 1=high, 4=undefined, so invert
            result["score"] = int((5 - avg_threat) * 25)
        else:
            result["score"] = 50

        # Boost score for sightings
        if sighting_count > 0:
            result["score"] = min(100, result["score"] + min(sighting_count * 5, 20))

        # Determine verdict
        if threat_levels:
            min_level = min(threat_levels)
            if min_level == 1:
                result["verdict"] = "malicious"
            elif min_level == 2:
                result["verdict"] = "suspicious"
            elif min_level == 3:
                result["verdict"] = "suspicious"
            else:
                result["verdict"] = "unknown"
        else:
            result["verdict"] = "unknown"

        # First/last seen
        dates = [e["date"] for e in result["events"] if e.get("date")]
        if dates:
            result["first_seen"] = min(dates)
            result["last_seen"] = max(dates)

        result["sighting_count"] = sighting_count
        result["event_count"] = len(result["events"])

        return result

    async def search_events(
        self,
        query: str,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Search MISP events.

        Args:
            query: Search query
            limit: Maximum results

        Returns:
            List of matching events
        """
        import httpx

        try:
            async with httpx.AsyncClient(verify=self.verify_ssl) as client:
                response = await client.post(
                    f"{self.url}/events/restSearch",
                    headers={
                        "Authorization": self.api_key,
                        "Accept": "application/json",
                        "Content-Type": "application/json",
                    },
                    json={
                        "returnFormat": "json",
                        "searchall": query,
                        "limit": limit,
                    },
                    timeout=30.0,
                )
                response.raise_for_status()
                data = response.json()

            events = []
            for item in data.get("response", []):
                event = item.get("Event", {})
                events.append(
                    {
                        "id": event.get("id"),
                        "uuid": event.get("uuid"),
                        "info": event.get("info"),
                        "date": event.get("date"),
                        "threat_level": event.get("threat_level_id"),
                        "attribute_count": event.get("attribute_count"),
                    }
                )

            return events

        except Exception as e:
            logger.error(f"MISP search error: {e}")
            return []

    async def health_check(self) -> dict[str, Any]:
        """Check MISP connectivity."""
        import httpx

        try:
            async with httpx.AsyncClient(verify=self.verify_ssl) as client:
                response = await client.get(
                    f"{self.url}/servers/getVersion",
                    headers={
                        "Authorization": self.api_key,
                        "Accept": "application/json",
                    },
                    timeout=10.0,
                )
                response.raise_for_status()
                data = response.json()

                return {
                    "status": "healthy",
                    "version": data.get("version"),
                    "pymisp_recommended": data.get("pymisp_recommended"),
                }

        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
            }
