"""Mock OpenCTI adapter for testing."""

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


class MockOpenCTIAdapter:
    """Mock implementation of OpenCTI adapter for testing."""

    def __init__(self):
        self.name = "opencti"
        self.connected = False
        self._indicators = self._generate_sample_indicators()
        self._threat_actors = self._generate_sample_threat_actors()
        self._campaigns = self._generate_sample_campaigns()

    def _generate_sample_indicators(self) -> dict:
        """Generate sample indicator data."""
        return {
            "malicious.example.com": {
                "id": str(uuid4()),
                "value": "malicious.example.com",
                "type": "domain",
                "confidence": 85,
                "labels": ["malware", "c2"],
                "description": "Known command and control domain",
                "created_at": "2024-01-15T10:00:00Z",
                "valid_from": "2024-01-15T00:00:00Z",
                "valid_until": "2025-01-15T00:00:00Z",
                "revoked": False,
                "threat_actors": ["APT29"],
                "campaigns": ["Operation Midnight"],
                "tlp": "amber",
            },
            "198.51.100.50": {
                "id": str(uuid4()),
                "value": "198.51.100.50",
                "type": "ipv4",
                "confidence": 90,
                "labels": ["malware", "exfiltration"],
                "description": "Data exfiltration server",
                "created_at": "2024-01-10T08:00:00Z",
                "valid_from": "2024-01-10T00:00:00Z",
                "valid_until": "2025-01-10T00:00:00Z",
                "revoked": False,
                "threat_actors": ["APT29"],
                "campaigns": ["Operation Midnight"],
                "tlp": "red",
            },
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855": {
                "id": str(uuid4()),
                "value": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                "type": "sha256",
                "confidence": 95,
                "labels": ["malware", "trojan"],
                "description": "Known malware sample hash",
                "created_at": "2024-01-12T14:00:00Z",
                "valid_from": "2024-01-12T00:00:00Z",
                "valid_until": None,
                "revoked": False,
                "threat_actors": ["FIN7"],
                "campaigns": [],
                "tlp": "amber",
            },
        }

    def _generate_sample_threat_actors(self) -> dict:
        """Generate sample threat actor data."""
        return {
            "APT29": {
                "id": str(uuid4()),
                "name": "APT29",
                "aliases": ["Cozy Bear", "The Dukes", "YTTRIUM"],
                "description": "APT29 is a threat group attributed to Russia's Foreign Intelligence Service (SVR).",
                "sophistication": "expert",
                "resource_level": "government",
                "primary_motivation": "espionage",
                "goals": ["Intelligence gathering", "Political espionage"],
                "country": "Russia",
                "first_seen": "2008-01-01T00:00:00Z",
                "last_seen": datetime.now(timezone.utc).isoformat(),
                "ttps": ["T1566", "T1059", "T1055", "T1003"],
                "target_sectors": ["Government", "Think Tanks", "Political Organizations"],
            },
            "FIN7": {
                "id": str(uuid4()),
                "name": "FIN7",
                "aliases": ["Carbanak", "Navigator Group"],
                "description": "FIN7 is a financially motivated threat group.",
                "sophistication": "expert",
                "resource_level": "organization",
                "primary_motivation": "financial-gain",
                "goals": ["Financial theft", "Credit card data"],
                "country": "Unknown",
                "first_seen": "2015-01-01T00:00:00Z",
                "last_seen": datetime.now(timezone.utc).isoformat(),
                "ttps": ["T1566", "T1059", "T1055"],
                "target_sectors": ["Retail", "Hospitality", "Financial"],
            },
        }

    def _generate_sample_campaigns(self) -> dict:
        """Generate sample campaign data."""
        return {
            "Operation Midnight": {
                "id": str(uuid4()),
                "name": "Operation Midnight",
                "description": "Large-scale espionage campaign targeting government entities",
                "first_seen": "2024-01-01T00:00:00Z",
                "last_seen": datetime.now(timezone.utc).isoformat(),
                "attribution": ["APT29"],
                "objectives": ["Intelligence gathering", "Data exfiltration"],
                "target_sectors": ["Government", "Defense"],
                "indicators_count": 150,
            },
        }

    async def connect(self) -> bool:
        """Simulate connection."""
        self.connected = True
        return True

    async def disconnect(self) -> None:
        """Simulate disconnection."""
        self.connected = False

    async def health_check(self) -> dict:
        """Return mock health status."""
        return {
            "status": "healthy",
            "connected": self.connected,
            "version": "5.12.0",
            "server_url": "http://opencti.local:8080",
            "indicators_count": len(self._indicators),
            "threat_actors_count": len(self._threat_actors),
        }

    async def enrich_indicator(self, value: str, indicator_type: str) -> dict | None:
        """Return mock enrichment data for an indicator."""
        if value in self._indicators:
            return self._indicators[value]

        # Return unknown indicator response
        return {
            "id": None,
            "value": value,
            "type": indicator_type,
            "confidence": 0,
            "labels": [],
            "description": "No threat intelligence data available",
            "found": False,
        }

    async def bulk_enrich(self, indicators: list[dict]) -> list[dict]:
        """Return mock bulk enrichment results."""
        results = []
        for ind in indicators:
            result = await self.enrich_indicator(ind["value"], ind["type"])
            results.append(result)
        return results

    async def get_threat_actor(self, name: str) -> dict | None:
        """Return mock threat actor details."""
        return self._threat_actors.get(name)

    async def search_threat_actors(self, query: str, limit: int = 10) -> list[dict]:
        """Search threat actors by name or alias."""
        query_lower = query.lower()
        results = []
        for actor in self._threat_actors.values():
            if query_lower in actor["name"].lower():
                results.append(actor)
            elif any(query_lower in alias.lower() for alias in actor.get("aliases", [])):
                results.append(actor)
        return results[:limit]

    async def get_campaign(self, name: str) -> dict | None:
        """Return mock campaign details."""
        return self._campaigns.get(name)

    async def search_campaigns(self, query: str, limit: int = 10) -> list[dict]:
        """Search campaigns by name."""
        query_lower = query.lower()
        return [
            c for c in self._campaigns.values()
            if query_lower in c["name"].lower()
        ][:limit]

    async def get_related_indicators(
        self,
        value: str,
        indicator_type: str,
        limit: int = 100,
    ) -> list[dict]:
        """Return related indicators."""
        if value in self._indicators:
            indicator = self._indicators[value]
            # Return other indicators from same threat actors
            related = []
            for ind in self._indicators.values():
                if ind["value"] != value:
                    # Check if they share threat actors
                    if set(ind.get("threat_actors", [])) & set(indicator.get("threat_actors", [])):
                        related.append(ind)
            return related[:limit]
        return []

    async def submit_indicator(
        self,
        value: str,
        indicator_type: str,
        description: str | None = None,
        labels: list[str] | None = None,
        confidence: int = 50,
        tlp: str = "white",
    ) -> dict:
        """Submit a new indicator to OpenCTI."""
        indicator_id = str(uuid4())
        indicator = {
            "id": indicator_id,
            "value": value,
            "type": indicator_type,
            "confidence": confidence,
            "labels": labels or [],
            "description": description or "",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "valid_from": datetime.now(timezone.utc).isoformat(),
            "valid_until": None,
            "revoked": False,
            "threat_actors": [],
            "campaigns": [],
            "tlp": tlp,
        }
        self._indicators[value] = indicator
        return indicator


class MockOpenCTIEnrichment:
    """Helper class for mock OpenCTI enrichment data."""

    @staticmethod
    def create_malicious_domain() -> dict:
        """Create a sample malicious domain indicator."""
        return {
            "id": str(uuid4()),
            "value": "evil-domain.com",
            "type": "domain",
            "confidence": 90,
            "labels": ["malware", "phishing"],
            "description": "Known phishing domain",
            "threat_actors": ["APT29"],
            "campaigns": [],
            "tlp": "amber",
            "found": True,
        }

    @staticmethod
    def create_clean_indicator() -> dict:
        """Create a sample clean/unknown indicator."""
        return {
            "id": None,
            "value": "legitimate-site.com",
            "type": "domain",
            "confidence": 0,
            "labels": [],
            "description": "No threat intelligence data available",
            "found": False,
        }
