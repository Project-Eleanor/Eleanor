"""MITRE ATT&CK service for technique mapping and coverage analysis.

Provides:
- Full ATT&CK matrix data
- Detection rule coverage mapping
- Coverage gap analysis
- Navigator layer import/export
"""

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tenant_context import get_current_tenant_id
from app.models.alert import Alert
from app.models.analytics import DetectionRule, RuleStatus

logger = logging.getLogger(__name__)

# MITRE ATT&CK STIX data URLs
ATTACK_ENTERPRISE_URL = (
    "https://raw.githubusercontent.com/mitre/cti/master/enterprise-attack/enterprise-attack.json"
)
ATTACK_CACHE_PATH = Path(__file__).parent.parent / "data" / "mitre_attack.json"


class MitreAttackService:
    """Service for MITRE ATT&CK operations."""

    def __init__(self):
        """Initialize the service."""
        self._attack_data: dict[str, Any] | None = None
        self._techniques: dict[str, dict[str, Any]] = {}
        self._tactics: list[dict[str, Any]] = []
        self._matrix: list[dict[str, Any]] = []

    async def initialize(self) -> None:
        """Load ATT&CK data from cache or download."""
        if self._attack_data is not None:
            return

        # Try loading from cache
        if ATTACK_CACHE_PATH.exists():
            try:
                logger.info("Loading MITRE ATT&CK data from cache")
                with open(ATTACK_CACHE_PATH) as f:
                    self._attack_data = json.load(f)
                self._parse_attack_data()
                return
            except Exception as e:
                logger.warning("Failed to load cache: %s", e)

        # Download fresh data
        await self._download_attack_data()

    async def _download_attack_data(self) -> None:
        """Download ATT&CK data from MITRE GitHub."""
        logger.info("Downloading MITRE ATT&CK data")
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.get(ATTACK_ENTERPRISE_URL)
                response.raise_for_status()
                self._attack_data = response.json()

            # Save to cache
            ATTACK_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(ATTACK_CACHE_PATH, "w") as f:
                json.dump(self._attack_data, f)

            self._parse_attack_data()
            logger.info("MITRE ATT&CK data downloaded and cached")

        except Exception as e:
            logger.error("Failed to download ATT&CK data: %s", e)
            # Use minimal embedded data as fallback
            self._load_embedded_data()

    def _parse_attack_data(self) -> None:
        """Parse STIX bundle into usable structures."""
        if not self._attack_data:
            return

        objects = self._attack_data.get("objects", [])

        # Extract tactics
        tactics_map = {}
        for obj in objects:
            if obj.get("type") == "x-mitre-tactic":
                tactic = {
                    "id": obj.get("x_mitre_shortname", ""),
                    "name": obj.get("name", ""),
                    "description": obj.get("description", ""),
                    "external_id": self._get_external_id(obj),
                }
                tactics_map[obj.get("id")] = tactic

        # Define tactic order (kill chain phases)
        tactic_order = [
            "reconnaissance",
            "resource-development",
            "initial-access",
            "execution",
            "persistence",
            "privilege-escalation",
            "defense-evasion",
            "credential-access",
            "discovery",
            "lateral-movement",
            "collection",
            "command-and-control",
            "exfiltration",
            "impact",
        ]

        self._tactics = [
            tactics_map[tid] for tid in tactics_map if tactics_map[tid]["id"] in tactic_order
        ]
        self._tactics.sort(
            key=lambda t: tactic_order.index(t["id"]) if t["id"] in tactic_order else 999
        )

        # Extract techniques
        for obj in objects:
            if obj.get("type") == "attack-pattern" and not obj.get("revoked", False):
                technique_id = self._get_external_id(obj)
                if not technique_id:
                    continue

                # Get kill chain phases (tactics)
                kill_chain = obj.get("kill_chain_phases", [])
                technique_tactics = [
                    p["phase_name"]
                    for p in kill_chain
                    if p.get("kill_chain_name") == "mitre-attack"
                ]

                # Check if subtechnique
                is_subtechnique = obj.get("x_mitre_is_subtechnique", False)
                parent_id = None
                if is_subtechnique and "." in technique_id:
                    parent_id = technique_id.split(".")[0]

                technique = {
                    "id": technique_id,
                    "name": obj.get("name", ""),
                    "description": obj.get("description", ""),
                    "tactics": technique_tactics,
                    "platforms": obj.get("x_mitre_platforms", []),
                    "data_sources": obj.get("x_mitre_data_sources", []),
                    "detection": obj.get("x_mitre_detection", ""),
                    "is_subtechnique": is_subtechnique,
                    "parent_id": parent_id,
                    "url": f"https://attack.mitre.org/techniques/{technique_id.replace('.', '/')}/",
                    "subtechniques": [],
                }
                self._techniques[technique_id] = technique

        # Link subtechniques to parents
        for tech_id, tech in self._techniques.items():
            if tech["parent_id"] and tech["parent_id"] in self._techniques:
                self._techniques[tech["parent_id"]]["subtechniques"].append(tech_id)

        # Build matrix structure
        self._build_matrix()

    def _build_matrix(self) -> None:
        """Build matrix structure organized by tactics."""
        self._matrix = []
        for tactic in self._tactics:
            column = {"tactic": tactic, "techniques": []}

            for tech_id, tech in self._techniques.items():
                if tactic["id"] in tech["tactics"] and not tech["is_subtechnique"]:
                    column["techniques"].append(
                        {
                            "id": tech["id"],
                            "name": tech["name"],
                            "subtechniques": [
                                {"id": sub_id, "name": self._techniques[sub_id]["name"]}
                                for sub_id in tech["subtechniques"]
                                if sub_id in self._techniques
                            ],
                        }
                    )

            # Sort techniques by ID
            column["techniques"].sort(key=lambda t: t["id"])
            self._matrix.append(column)

    def _get_external_id(self, obj: dict[str, Any]) -> str:
        """Extract MITRE external ID (e.g., T1059)."""
        for ref in obj.get("external_references", []):
            if ref.get("source_name") == "mitre-attack":
                return ref.get("external_id", "")
        return ""

    def _load_embedded_data(self) -> None:
        """Load minimal embedded data as fallback."""
        # Minimal fallback with common techniques
        self._tactics = [
            {
                "id": "initial-access",
                "name": "Initial Access",
                "description": "",
                "external_id": "TA0001",
            },
            {"id": "execution", "name": "Execution", "description": "", "external_id": "TA0002"},
            {
                "id": "persistence",
                "name": "Persistence",
                "description": "",
                "external_id": "TA0003",
            },
            {
                "id": "privilege-escalation",
                "name": "Privilege Escalation",
                "description": "",
                "external_id": "TA0004",
            },
            {
                "id": "defense-evasion",
                "name": "Defense Evasion",
                "description": "",
                "external_id": "TA0005",
            },
            {
                "id": "credential-access",
                "name": "Credential Access",
                "description": "",
                "external_id": "TA0006",
            },
            {"id": "discovery", "name": "Discovery", "description": "", "external_id": "TA0007"},
            {
                "id": "lateral-movement",
                "name": "Lateral Movement",
                "description": "",
                "external_id": "TA0008",
            },
            {"id": "collection", "name": "Collection", "description": "", "external_id": "TA0009"},
            {
                "id": "command-and-control",
                "name": "Command and Control",
                "description": "",
                "external_id": "TA0011",
            },
            {
                "id": "exfiltration",
                "name": "Exfiltration",
                "description": "",
                "external_id": "TA0010",
            },
            {"id": "impact", "name": "Impact", "description": "", "external_id": "TA0040"},
        ]
        self._matrix = [{"tactic": t, "techniques": []} for t in self._tactics]

    # =========================================================================
    # Public API Methods
    # =========================================================================

    async def get_matrix(self) -> dict[str, Any]:
        """Get full MITRE ATT&CK matrix."""
        await self.initialize()
        return {
            "tactics": self._tactics,
            "matrix": self._matrix,
            "technique_count": len(
                [t for t in self._techniques.values() if not t["is_subtechnique"]]
            ),
            "subtechnique_count": len(
                [t for t in self._techniques.values() if t["is_subtechnique"]]
            ),
            "last_updated": datetime.now(UTC).isoformat(),
        }

    async def get_technique(self, technique_id: str) -> dict[str, Any] | None:
        """Get details for a specific technique."""
        await self.initialize()
        return self._techniques.get(technique_id)

    async def search_techniques(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        """Search techniques by name or ID."""
        await self.initialize()
        query_lower = query.lower()
        results = []

        for tech_id, tech in self._techniques.items():
            if query_lower in tech_id.lower() or query_lower in tech["name"].lower():
                results.append(
                    {
                        "id": tech["id"],
                        "name": tech["name"],
                        "tactics": tech["tactics"],
                        "is_subtechnique": tech["is_subtechnique"],
                    }
                )
                if len(results) >= limit:
                    break

        return results

    async def get_coverage(
        self,
        db: AsyncSession,
    ) -> dict[str, Any]:
        """Get detection coverage analysis."""
        await self.initialize()
        tenant_id = get_current_tenant_id()

        # Get all enabled rules with MITRE mappings
        query = (
            select(DetectionRule)
            .where(DetectionRule.status == RuleStatus.ENABLED)
            .where(DetectionRule.mitre_techniques != None)  # noqa: E711
            .where(func.array_length(DetectionRule.mitre_techniques, 1) > 0)
        )

        if tenant_id:
            query = query.where(DetectionRule.tenant_id == tenant_id)

        result = await db.execute(query)
        rules = result.scalars().all()

        # Build coverage map
        coverage: dict[str, dict[str, Any]] = {}
        for rule in rules:
            for tech_id in rule.mitre_techniques or []:
                if tech_id not in coverage:
                    coverage[tech_id] = {
                        "technique_id": tech_id,
                        "technique_name": self._techniques.get(tech_id, {}).get("name", tech_id),
                        "rule_count": 0,
                        "rules": [],
                    }
                coverage[tech_id]["rule_count"] += 1
                coverage[tech_id]["rules"].append(
                    {
                        "id": str(rule.id),
                        "name": rule.name,
                        "severity": rule.severity.value,
                    }
                )

        # Calculate coverage statistics
        total_techniques = len([t for t in self._techniques.values() if not t["is_subtechnique"]])
        covered_techniques = len(
            [
                c
                for c in coverage.values()
                if not self._techniques.get(c["technique_id"], {}).get("is_subtechnique", False)
            ]
        )

        return {
            "coverage_map": list(coverage.values()),
            "statistics": {
                "total_techniques": total_techniques,
                "covered_techniques": covered_techniques,
                "coverage_percent": round((covered_techniques / max(total_techniques, 1)) * 100, 1),
                "total_rules": len(rules),
            },
            "by_tactic": self._calculate_tactic_coverage(coverage),
        }

    def _calculate_tactic_coverage(
        self, coverage: dict[str, dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Calculate coverage per tactic."""
        tactic_stats = []

        for tactic in self._tactics:
            tactic_techniques = [
                t
                for t in self._techniques.values()
                if tactic["id"] in t["tactics"] and not t["is_subtechnique"]
            ]
            covered = sum(1 for t in tactic_techniques if t["id"] in coverage)

            tactic_stats.append(
                {
                    "tactic_id": tactic["id"],
                    "tactic_name": tactic["name"],
                    "total_techniques": len(tactic_techniques),
                    "covered_techniques": covered,
                    "coverage_percent": round((covered / max(len(tactic_techniques), 1)) * 100, 1),
                }
            )

        return tactic_stats

    async def get_coverage_gaps(
        self,
        db: AsyncSession,
        priority: str = "high",
    ) -> list[dict[str, Any]]:
        """Get techniques without detection coverage."""
        await self.initialize()
        coverage = await self.get_coverage(db)
        covered_ids = {c["technique_id"] for c in coverage["coverage_map"]}

        gaps = []
        for tech_id, tech in self._techniques.items():
            if tech_id not in covered_ids and not tech["is_subtechnique"]:
                # Determine priority based on prevalence (simplified)
                gap = {
                    "technique_id": tech["id"],
                    "technique_name": tech["name"],
                    "tactics": tech["tactics"],
                    "platforms": tech["platforms"],
                    "data_sources": tech["data_sources"],
                    "detection_guidance": tech["detection"][:500] if tech["detection"] else None,
                    "url": tech["url"],
                }
                gaps.append(gap)

        # Sort by number of tactics (more tactics = higher priority)
        gaps.sort(key=lambda g: len(g["tactics"]), reverse=True)

        return gaps

    async def get_heatmap(
        self,
        db: AsyncSession,
        time_range: str = "7d",
    ) -> dict[str, Any]:
        """Get heatmap data based on alerts/incidents."""
        await self.initialize()
        tenant_id = get_current_tenant_id()

        # Parse time range
        from datetime import timedelta

        range_map = {
            "24h": timedelta(hours=24),
            "7d": timedelta(days=7),
            "30d": timedelta(days=30),
        }
        delta = range_map.get(time_range, timedelta(days=7))
        since = datetime.now(UTC) - delta

        # Get alerts with MITRE mappings
        query = (
            select(Alert.mitre_techniques, func.count(Alert.id))
            .where(Alert.created_at >= since)
            .where(Alert.mitre_techniques != None)  # noqa: E711
            .group_by(Alert.mitre_techniques)
        )

        if tenant_id:
            query = query.where(Alert.tenant_id == tenant_id)

        result = await db.execute(query)
        rows = result.all()

        # Aggregate counts by technique
        technique_counts: dict[str, int] = {}
        for techniques, count in rows:
            if techniques:
                for tech_id in techniques:
                    technique_counts[tech_id] = technique_counts.get(tech_id, 0) + count

        # Build heatmap data
        heatmap_data = []
        max_count = max(technique_counts.values()) if technique_counts else 1

        for tech_id, count in technique_counts.items():
            tech = self._techniques.get(tech_id, {})
            heatmap_data.append(
                {
                    "technique_id": tech_id,
                    "technique_name": tech.get("name", tech_id),
                    "count": count,
                    "intensity": round(count / max_count, 2),
                    "tactics": tech.get("tactics", []),
                }
            )

        # Sort by count
        heatmap_data.sort(key=lambda x: x["count"], reverse=True)

        return {
            "heatmap": heatmap_data,
            "time_range": time_range,
            "total_alerts": sum(technique_counts.values()),
            "unique_techniques": len(technique_counts),
        }

    # =========================================================================
    # Navigator Layer Import/Export
    # =========================================================================

    async def export_layer(
        self,
        db: AsyncSession,
        layer_name: str = "Eleanor Coverage",
        include_rules: bool = True,
    ) -> dict[str, Any]:
        """Export detection coverage as Navigator layer."""
        await self.initialize()
        coverage = await self.get_coverage(db)

        # Build Navigator layer format
        techniques = []
        for cov in coverage["coverage_map"]:
            tech = {
                "techniqueID": cov["technique_id"],
                "score": min(cov["rule_count"], 100),  # Cap at 100
                "color": self._score_to_color(cov["rule_count"]),
                "enabled": True,
                "showSubtechniques": True,
            }
            if include_rules:
                tech["comment"] = f"Rules: {', '.join(r['name'] for r in cov['rules'][:5])}"
                if len(cov["rules"]) > 5:
                    tech["comment"] += f" (+{len(cov['rules']) - 5} more)"
            techniques.append(tech)

        layer = {
            "name": layer_name,
            "versions": {"attack": "14", "navigator": "4.9.1", "layer": "4.5"},
            "domain": "enterprise-attack",
            "description": f"Eleanor detection coverage - {coverage['statistics']['coverage_percent']}% techniques covered",
            "filters": {
                "platforms": [
                    "Windows",
                    "Linux",
                    "macOS",
                    "Azure AD",
                    "Office 365",
                    "SaaS",
                    "IaaS",
                    "Google Workspace",
                ]
            },
            "sorting": 0,
            "layout": {
                "layout": "side",
                "aggregateFunction": "average",
                "showID": True,
                "showName": True,
                "showAggregateScores": True,
                "countUnscored": False,
            },
            "hideDisabled": False,
            "techniques": techniques,
            "gradient": {
                "colors": ["#ff6666", "#ffe766", "#8ec843"],
                "minValue": 0,
                "maxValue": 10,
            },
            "legendItems": [
                {"label": "No coverage", "color": "#ffffff"},
                {"label": "1 rule", "color": "#ffcccc"},
                {"label": "2-3 rules", "color": "#ffe766"},
                {"label": "4+ rules", "color": "#8ec843"},
            ],
            "metadata": [],
            "showTacticRowBackground": True,
            "tacticRowBackground": "#dddddd",
            "selectTechniquesAcrossTactics": True,
            "selectSubtechniquesWithParent": False,
        }

        return layer

    def _score_to_color(self, rule_count: int) -> str:
        """Convert rule count to Navigator color."""
        if rule_count == 0:
            return "#ffffff"
        elif rule_count == 1:
            return "#ffcccc"
        elif rule_count <= 3:
            return "#ffe766"
        else:
            return "#8ec843"

    async def import_layer(
        self,
        layer_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Parse Navigator layer and return technique mappings."""
        await self.initialize()

        techniques = layer_data.get("techniques", [])
        imported = []

        for tech in techniques:
            tech_id = tech.get("techniqueID", "")
            if tech_id in self._techniques:
                imported.append(
                    {
                        "technique_id": tech_id,
                        "technique_name": self._techniques[tech_id]["name"],
                        "score": tech.get("score", 0),
                        "color": tech.get("color"),
                        "comment": tech.get("comment"),
                        "enabled": tech.get("enabled", True),
                    }
                )

        return {
            "layer_name": layer_data.get("name", "Imported Layer"),
            "description": layer_data.get("description", ""),
            "technique_count": len(imported),
            "techniques": imported,
        }


# Module-level singleton
_mitre_service: MitreAttackService | None = None


async def get_mitre_service() -> MitreAttackService:
    """Get the MITRE service singleton."""
    global _mitre_service
    if _mitre_service is None:
        _mitre_service = MitreAttackService()
        await _mitre_service.initialize()
    return _mitre_service
