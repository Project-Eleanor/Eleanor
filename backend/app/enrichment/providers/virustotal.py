"""VirusTotal enrichment provider.

Provides threat intelligence enrichment via the VirusTotal API v3.
"""

import logging
from datetime import UTC, datetime
from typing import Any

from app.enrichment.extractors.ioc import IOCType

logger = logging.getLogger(__name__)


# IOC type to VT endpoint mapping
VT_ENDPOINTS = {
    IOCType.IPV4: "ip_addresses",
    IOCType.IPV6: "ip_addresses",
    IOCType.DOMAIN: "domains",
    IOCType.URL: "urls",
    IOCType.MD5: "files",
    IOCType.SHA1: "files",
    IOCType.SHA256: "files",
}


class VirusTotalEnrichmentProvider:
    """Enrichment provider using VirusTotal API v3.

    Supports enrichment of:
    - File hashes (MD5, SHA1, SHA256)
    - IP addresses (IPv4, IPv6)
    - Domains
    - URLs

    Results include:
    - Detection statistics from 70+ AV engines
    - Community votes and reputation
    - Categories and tags
    - First/last seen dates
    - Related threat actors and campaigns
    """

    def __init__(
        self,
        api_key: str,
        api_url: str = "https://www.virustotal.com/api/v3",
        timeout: int = 30,
    ):
        """Initialize the VirusTotal provider.

        Args:
            api_key: VirusTotal API key
            api_url: Base API URL
            timeout: Request timeout in seconds
        """
        self.api_key = api_key
        self.api_url = api_url.rstrip("/")
        self.timeout = timeout

    async def enrich(
        self,
        indicator: str,
        indicator_type: IOCType,
    ) -> dict[str, Any] | None:
        """Enrich an indicator via VirusTotal.

        Args:
            indicator: IOC value
            indicator_type: Type of IOC

        Returns:
            Enrichment data or None if not found
        """
        import httpx

        endpoint = VT_ENDPOINTS.get(indicator_type)
        if not endpoint:
            logger.debug(f"Unsupported indicator type for VT: {indicator_type}")
            return None

        # URL needs to be base64 encoded (URL-safe)
        if indicator_type == IOCType.URL:
            import base64

            identifier = base64.urlsafe_b64encode(indicator.encode()).decode().rstrip("=")
        else:
            identifier = indicator

        url = f"{self.api_url}/{endpoint}/{identifier}"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url,
                    headers={
                        "x-apikey": self.api_key,
                        "Accept": "application/json",
                    },
                    timeout=self.timeout,
                )

                if response.status_code == 404:
                    logger.debug(f"VT: Indicator not found: {indicator}")
                    return None

                response.raise_for_status()
                data = response.json()

                return self._process_response(data, indicator_type)

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            logger.error(f"VT HTTP error: {e}")
            raise
        except httpx.HTTPError as e:
            logger.error(f"VT HTTP error: {e}")
            raise
        except Exception as e:
            logger.error(f"VT error: {e}")
            raise

    def _process_response(
        self,
        data: dict,
        indicator_type: IOCType,
    ) -> dict[str, Any]:
        """Process VT API response into enrichment result.

        Args:
            data: VT API response
            indicator_type: Type of indicator

        Returns:
            Processed enrichment data
        """
        attributes = data.get("data", {}).get("attributes", {})

        result = {
            "source": "virustotal",
            "type": indicator_type.value,
        }

        # Detection statistics
        stats = attributes.get("last_analysis_stats", {})
        malicious = stats.get("malicious", 0)
        suspicious = stats.get("suspicious", 0)
        harmless = stats.get("harmless", 0)
        undetected = stats.get("undetected", 0)
        total = malicious + suspicious + harmless + undetected

        result["detections"] = {
            "malicious": malicious,
            "suspicious": suspicious,
            "harmless": harmless,
            "undetected": undetected,
            "total": total,
        }

        # Calculate score (0-100)
        if total > 0:
            # Weight malicious higher than suspicious
            result["score"] = min(100, int(((malicious * 2) + suspicious) / total * 100))
        else:
            result["score"] = 0

        # Determine verdict
        if malicious >= 5:
            result["verdict"] = "malicious"
        elif malicious >= 1 or suspicious >= 3:
            result["verdict"] = "suspicious"
        elif total > 0 and malicious == 0 and suspicious == 0:
            result["verdict"] = "clean"
        else:
            result["verdict"] = "unknown"

        # Community votes
        votes = attributes.get("total_votes", {})
        result["community_votes"] = {
            "harmless": votes.get("harmless", 0),
            "malicious": votes.get("malicious", 0),
        }

        # Reputation score (VT's internal score, can be negative)
        if "reputation" in attributes:
            result["reputation"] = attributes["reputation"]

        # Categories (for domains/URLs)
        if "categories" in attributes:
            result["categories"] = list(attributes["categories"].values())

        # Tags
        if "tags" in attributes:
            result["tags"] = attributes["tags"]

        # Threat labels from engines
        threat_labels = set()
        last_analysis = attributes.get("last_analysis_results", {})
        for engine_result in last_analysis.values():
            if engine_result.get("category") == "malicious":
                if engine_result.get("result"):
                    threat_labels.add(engine_result["result"])
        if threat_labels:
            result["threat_labels"] = list(threat_labels)[:20]  # Limit

        # Popular threat classification
        popular_threat = attributes.get("popular_threat_classification", {})
        if popular_threat:
            suggested_label = popular_threat.get("suggested_threat_label")
            if suggested_label:
                result["threat_classification"] = suggested_label

            popular_categories = popular_threat.get("popular_threat_category", [])
            if popular_categories:
                result["threat_categories"] = [
                    c.get("value") for c in popular_categories if c.get("value")
                ]

        # Dates
        if "first_submission_date" in attributes:
            result["first_seen"] = datetime.fromtimestamp(
                attributes["first_submission_date"], tz=UTC
            ).isoformat()
        if "last_submission_date" in attributes:
            result["last_seen"] = datetime.fromtimestamp(
                attributes["last_submission_date"], tz=UTC
            ).isoformat()
        if "last_analysis_date" in attributes:
            result["last_analysis"] = datetime.fromtimestamp(
                attributes["last_analysis_date"], tz=UTC
            ).isoformat()

        # Type-specific data
        if indicator_type in (IOCType.MD5, IOCType.SHA1, IOCType.SHA256):
            result.update(self._process_file_data(attributes))
        elif indicator_type in (IOCType.IPV4, IOCType.IPV6):
            result.update(self._process_ip_data(attributes))
        elif indicator_type == IOCType.DOMAIN:
            result.update(self._process_domain_data(attributes))
        elif indicator_type == IOCType.URL:
            result.update(self._process_url_data(attributes))

        return result

    def _process_file_data(self, attributes: dict) -> dict[str, Any]:
        """Extract file-specific data."""
        result = {}

        # File metadata
        if "md5" in attributes:
            result["md5"] = attributes["md5"]
        if "sha1" in attributes:
            result["sha1"] = attributes["sha1"]
        if "sha256" in attributes:
            result["sha256"] = attributes["sha256"]
        if "size" in attributes:
            result["size"] = attributes["size"]
        if "type_description" in attributes:
            result["file_type"] = attributes["type_description"]
        if "magic" in attributes:
            result["magic"] = attributes["magic"]

        # Names
        if "names" in attributes:
            result["filenames"] = attributes["names"][:10]  # Limit

        # Signature info
        signature = attributes.get("signature_info", {})
        if signature:
            result["signature"] = {
                "verified": signature.get("verified"),
                "signers": signature.get("signers"),
                "product": signature.get("product"),
            }

        # Sandbox behavior summary
        sandbox = attributes.get("sandbox_verdicts", {})
        if sandbox:
            result["sandbox_verdicts"] = {
                name: {
                    "category": info.get("category"),
                    "sandbox_name": info.get("sandbox_name"),
                }
                for name, info in sandbox.items()
            }

        return result

    def _process_ip_data(self, attributes: dict) -> dict[str, Any]:
        """Extract IP-specific data."""
        result = {}

        if "asn" in attributes:
            result["asn"] = attributes["asn"]
        if "as_owner" in attributes:
            result["as_owner"] = attributes["as_owner"]
        if "country" in attributes:
            result["country"] = attributes["country"]
        if "continent" in attributes:
            result["continent"] = attributes["continent"]
        if "network" in attributes:
            result["network"] = attributes["network"]

        # WHOIS info
        if "whois" in attributes:
            result["whois"] = attributes["whois"][:1000]  # Limit size

        return result

    def _process_domain_data(self, attributes: dict) -> dict[str, Any]:
        """Extract domain-specific data."""
        result = {}

        if "registrar" in attributes:
            result["registrar"] = attributes["registrar"]
        if "creation_date" in attributes:
            result["creation_date"] = datetime.fromtimestamp(
                attributes["creation_date"], tz=UTC
            ).isoformat()
        if "last_update_date" in attributes:
            result["last_update_date"] = datetime.fromtimestamp(
                attributes["last_update_date"], tz=UTC
            ).isoformat()

        # DNS records
        if "last_dns_records" in attributes:
            result["dns_records"] = [
                {
                    "type": r.get("type"),
                    "value": r.get("value"),
                }
                for r in attributes["last_dns_records"][:20]
            ]

        # WHOIS
        if "whois" in attributes:
            result["whois"] = attributes["whois"][:1000]

        return result

    def _process_url_data(self, attributes: dict) -> dict[str, Any]:
        """Extract URL-specific data."""
        result = {}

        if "url" in attributes:
            result["url"] = attributes["url"]
        if "last_final_url" in attributes:
            result["final_url"] = attributes["last_final_url"]
        if "last_http_response_content_length" in attributes:
            result["response_size"] = attributes["last_http_response_content_length"]
        if "last_http_response_code" in attributes:
            result["response_code"] = attributes["last_http_response_code"]
        if "title" in attributes:
            result["title"] = attributes["title"]

        # Outgoing links
        if "outgoing_links" in attributes:
            result["outgoing_links"] = attributes["outgoing_links"][:10]

        return result

    async def get_file_behavior(
        self,
        file_hash: str,
    ) -> dict[str, Any] | None:
        """Get sandbox behavior report for a file.

        Args:
            file_hash: MD5, SHA1, or SHA256 hash

        Returns:
            Behavior data or None
        """
        import httpx

        url = f"{self.api_url}/files/{file_hash}/behaviours"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url,
                    headers={
                        "x-apikey": self.api_key,
                        "Accept": "application/json",
                    },
                    timeout=self.timeout,
                )

                if response.status_code == 404:
                    return None

                response.raise_for_status()
                data = response.json()

                behaviors = data.get("data", [])
                if not behaviors:
                    return None

                # Aggregate behavior data
                result = {
                    "sandbox_reports": len(behaviors),
                    "processes_created": [],
                    "files_written": [],
                    "files_deleted": [],
                    "registry_keys_set": [],
                    "network_connections": [],
                    "dns_queries": [],
                    "mutexes_created": [],
                }

                for behavior in behaviors[:5]:  # Limit to first 5 reports
                    attrs = behavior.get("attributes", {})

                    # Process operations
                    for proc in attrs.get("processes_created", []):
                        if proc not in result["processes_created"]:
                            result["processes_created"].append(proc)

                    for f in attrs.get("files_written", []):
                        if f not in result["files_written"]:
                            result["files_written"].append(f)

                    for f in attrs.get("files_deleted", []):
                        if f not in result["files_deleted"]:
                            result["files_deleted"].append(f)

                    for r in attrs.get("registry_keys_set", []):
                        if r not in result["registry_keys_set"]:
                            result["registry_keys_set"].append(r)

                    for conn in attrs.get("ip_traffic", []):
                        dest = f"{conn.get('destination_ip')}:{conn.get('destination_port')}"
                        if dest not in result["network_connections"]:
                            result["network_connections"].append(dest)

                    for dns in attrs.get("dns_lookups", []):
                        hostname = dns.get("hostname")
                        if hostname and hostname not in result["dns_queries"]:
                            result["dns_queries"].append(hostname)

                    for mutex in attrs.get("mutexes_created", []):
                        if mutex not in result["mutexes_created"]:
                            result["mutexes_created"].append(mutex)

                # Limit lists
                for key in result:
                    if isinstance(result[key], list) and len(result[key]) > 50:
                        result[key] = result[key][:50]

                return result

        except Exception as e:
            logger.error(f"VT behavior error: {e}")
            return None

    async def get_related_iocs(
        self,
        indicator: str,
        indicator_type: IOCType,
        relationship: str = "communicating_files",
    ) -> list[dict[str, Any]]:
        """Get related IOCs for an indicator.

        Args:
            indicator: IOC value
            indicator_type: Type of IOC
            relationship: Type of relationship to query

        Returns:
            List of related IOCs
        """
        import httpx

        endpoint = VT_ENDPOINTS.get(indicator_type)
        if not endpoint:
            return []

        if indicator_type == IOCType.URL:
            import base64

            identifier = base64.urlsafe_b64encode(indicator.encode()).decode().rstrip("=")
        else:
            identifier = indicator

        url = f"{self.api_url}/{endpoint}/{identifier}/{relationship}"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url,
                    headers={
                        "x-apikey": self.api_key,
                        "Accept": "application/json",
                    },
                    params={"limit": 20},
                    timeout=self.timeout,
                )

                if response.status_code == 404:
                    return []

                response.raise_for_status()
                data = response.json()

                related = []
                for item in data.get("data", []):
                    attrs = item.get("attributes", {})
                    related.append(
                        {
                            "id": item.get("id"),
                            "type": item.get("type"),
                            "sha256": attrs.get("sha256"),
                            "md5": attrs.get("md5"),
                            "score": attrs.get("last_analysis_stats", {}).get("malicious", 0),
                        }
                    )

                return related

        except Exception as e:
            logger.error(f"VT related IOCs error: {e}")
            return []

    async def health_check(self) -> dict[str, Any]:
        """Check VirusTotal API connectivity.

        Returns:
            Health status dictionary
        """
        import httpx

        try:
            async with httpx.AsyncClient() as client:
                # Use a simple endpoint to check connectivity
                response = await client.get(
                    f"{self.api_url}/users/current",
                    headers={
                        "x-apikey": self.api_key,
                        "Accept": "application/json",
                    },
                    timeout=10,
                )

                if response.status_code == 401:
                    return {
                        "status": "unhealthy",
                        "error": "Invalid API key",
                    }

                response.raise_for_status()
                data = response.json()

                user_data = data.get("data", {}).get("attributes", {})
                quotas = user_data.get("quotas", {})

                return {
                    "status": "healthy",
                    "user": user_data.get("user"),
                    "quotas": {
                        "daily": quotas.get("api_requests_daily", {}),
                        "hourly": quotas.get("api_requests_hourly", {}),
                        "monthly": quotas.get("api_requests_monthly", {}),
                    },
                }

        except httpx.HTTPStatusError as e:
            return {
                "status": "unhealthy",
                "error": f"HTTP {e.response.status_code}",
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
            }
