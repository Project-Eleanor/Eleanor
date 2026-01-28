"""Sigma rule engine for log-based detection.

PATTERN: Strategy Pattern
Provides Sigma rule processing and detection for log events.

Provides:
- Rule loading and parsing
- Rule conversion to various backends (ES, Splunk, etc.)
- Event matching against rules
- Detection result processing
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, UTC
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class SigmaRule:
    """Representation of a Sigma detection rule.

    PATTERN: Data Transfer Object (DTO)
    Contains rule definition and metadata.
    """

    rule_id: str
    title: str
    description: str = ""
    author: str = ""
    date: str = ""
    status: str = "experimental"  # experimental, test, stable
    level: str = "medium"  # informational, low, medium, high, critical
    logsource: dict[str, str] = field(default_factory=dict)
    detection: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    references: list[str] = field(default_factory=list)
    falsepositives: list[str] = field(default_factory=list)
    source_file: str | None = None

    @property
    def severity(self) -> str:
        """Get severity from level."""
        return self.level

    @property
    def product(self) -> str:
        """Get product from logsource."""
        return self.logsource.get("product", "")

    @property
    def category(self) -> str:
        """Get category from logsource."""
        return self.logsource.get("category", "")

    @property
    def service(self) -> str:
        """Get service from logsource."""
        return self.logsource.get("service", "")


@dataclass
class SigmaMatch:
    """Representation of a Sigma rule match.

    PATTERN: Data Transfer Object (DTO)
    Contains match details and triggering event.
    """

    rule: SigmaRule
    event: dict[str, Any]
    match_time: datetime = field(default_factory=lambda: datetime.now(UTC))
    matched_fields: dict[str, Any] = field(default_factory=dict)

    @property
    def severity(self) -> str:
        """Get severity from rule."""
        return self.rule.level


@dataclass
class ConversionResult:
    """Result of converting a Sigma rule.

    PATTERN: Data Transfer Object (DTO)
    Contains converted query and metadata.
    """

    rule_id: str
    backend: str
    query: str
    error: str | None = None
    index_pattern: str | None = None


class SigmaEngine:
    """Sigma rule detection engine.

    PATTERN: Facade Pattern
    Provides a simplified interface for Sigma rule operations.

    Configuration:
        rules_path: Path to Sigma rules directory
        pipeline: Processing pipeline for field mapping

    DESIGN DECISION: Uses pySigma for rule parsing and conversion,
    with custom matching logic for real-time detection.
    """

    def __init__(
        self,
        rules_path: str | Path | None = None,
        pipeline: str = "ecs_windows",
    ):
        """Initialize Sigma engine.

        Args:
            rules_path: Path to Sigma rules directory
            pipeline: Field mapping pipeline name
        """
        self.rules_path = Path(rules_path) if rules_path else None
        self.pipeline_name = pipeline

        self._rules: dict[str, SigmaRule] = {}
        self._compiled_rules: dict[str, Any] = {}
        self._pipeline = None
        self._last_loaded: datetime | None = None

    async def load_rules(self) -> int:
        """Load Sigma rules from directory.

        Returns:
            Number of rules loaded
        """
        if not self.rules_path:
            raise ValueError("No rules path configured")

        if not self.rules_path.exists():
            raise ValueError(f"Rules path does not exist: {self.rules_path}")

        self._rules.clear()
        self._compiled_rules.clear()

        # Load rules from YAML files
        for rule_file in self.rules_path.rglob("*.yml"):
            try:
                rules = await self._load_rule_file(rule_file)
                for rule in rules:
                    self._rules[rule.rule_id] = rule
            except Exception as error:
                logger.warning(f"Failed to load rule {rule_file}: {error}")

        for rule_file in self.rules_path.rglob("*.yaml"):
            try:
                rules = await self._load_rule_file(rule_file)
                for rule in rules:
                    self._rules[rule.rule_id] = rule
            except Exception as error:
                logger.warning(f"Failed to load rule {rule_file}: {error}")

        self._last_loaded = datetime.now(UTC)

        logger.info(f"Loaded {len(self._rules)} Sigma rules from {self.rules_path}")
        return len(self._rules)

    async def _load_rule_file(self, file_path: Path) -> list[SigmaRule]:
        """Load rules from a YAML file.

        Args:
            file_path: Path to YAML file

        Returns:
            List of parsed rules
        """
        import yaml

        with open(file_path, encoding="utf-8") as file_handle:
            content = file_handle.read()

        # Handle multiple YAML documents in one file
        rules = []
        for doc in yaml.safe_load_all(content):
            if doc is None:
                continue

            rule = self._parse_rule_dict(doc, str(file_path))
            if rule:
                rules.append(rule)

        return rules

    def _parse_rule_dict(self, data: dict[str, Any], source_file: str) -> SigmaRule | None:
        """Parse rule from dictionary.

        Args:
            data: Rule dictionary
            source_file: Source file path

        Returns:
            Parsed SigmaRule or None
        """
        if "title" not in data or "detection" not in data:
            return None

        from uuid import uuid4

        return SigmaRule(
            rule_id=data.get("id", str(uuid4())),
            title=data.get("title", ""),
            description=data.get("description", ""),
            author=data.get("author", ""),
            date=data.get("date", ""),
            status=data.get("status", "experimental"),
            level=data.get("level", "medium"),
            logsource=data.get("logsource", {}),
            detection=data.get("detection", {}),
            tags=data.get("tags", []),
            references=data.get("references", []),
            falsepositives=data.get("falsepositives", []),
            source_file=source_file,
        )

    async def match_event(
        self,
        event: dict[str, Any],
        rules: list[str] | None = None,
    ) -> list[SigmaMatch]:
        """Match an event against Sigma rules.

        Args:
            event: Event to match
            rules: Optional list of rule IDs to check (None = all)

        Returns:
            List of matching rules
        """
        matches = []

        rules_to_check = (
            [self._rules[rule_id] for rule_id in rules if rule_id in self._rules]
            if rules
            else list(self._rules.values())
        )

        for rule in rules_to_check:
            if self._event_matches_rule(event, rule):
                matched_fields = self._extract_matched_fields(event, rule)
                matches.append(
                    SigmaMatch(
                        rule=rule,
                        event=event,
                        matched_fields=matched_fields,
                    )
                )

        return matches

    def _event_matches_rule(self, event: dict[str, Any], rule: SigmaRule) -> bool:
        """Check if event matches a rule.

        DESIGN DECISION: Implements basic Sigma matching logic.
        For production use, consider using pySigma's full implementation.

        Args:
            event: Event to check
            rule: Rule to match against

        Returns:
            True if event matches
        """
        detection = rule.detection

        # Get condition
        condition = detection.get("condition", "")
        if not condition:
            return False

        # Evaluate detection blocks
        detection_results = {}
        for key, value in detection.items():
            if key == "condition":
                continue

            if isinstance(value, list):
                # List of alternative conditions
                detection_results[key] = any(
                    self._match_detection_item(event, item) for item in value
                )
            elif isinstance(value, dict):
                detection_results[key] = self._match_detection_item(event, value)
            else:
                detection_results[key] = False

        # Evaluate condition
        return self._evaluate_condition(condition, detection_results)

    def _match_detection_item(
        self,
        event: dict[str, Any],
        detection_item: dict[str, Any],
    ) -> bool:
        """Match event against a single detection item.

        Args:
            event: Event to check
            detection_item: Detection conditions

        Returns:
            True if all conditions match
        """
        for field, pattern in detection_item.items():
            event_value = self._get_field_value(event, field)

            if event_value is None:
                return False

            if not self._match_pattern(event_value, pattern):
                return False

        return True

    def _get_field_value(self, event: dict[str, Any], field: str) -> Any:
        """Get field value from event, supporting nested fields.

        Args:
            event: Event dictionary
            field: Field name (supports dot notation)

        Returns:
            Field value or None
        """
        parts = field.split(".")
        value = event

        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
            else:
                return None

            if value is None:
                return None

        return value

    def _match_pattern(self, value: Any, pattern: Any) -> bool:
        """Match a value against a pattern.

        Supports:
        - Exact match
        - Wildcard patterns (* and ?)
        - Lists of patterns (OR)
        - Modifiers (|endswith, |startswith, |contains, |re)

        Args:
            value: Value to check
            pattern: Pattern to match

        Returns:
            True if matches
        """
        if isinstance(pattern, list):
            return any(self._match_pattern(value, p) for p in pattern)

        if pattern is None:
            return value is None

        # Convert to string for pattern matching
        str_value = str(value).lower()
        str_pattern = str(pattern).lower()

        # Handle modifiers in field name
        if "|" in str_pattern:
            modifier, pattern_value = str_pattern.rsplit("|", 1)
            if modifier == "endswith":
                return str_value.endswith(pattern_value)
            elif modifier == "startswith":
                return str_value.startswith(pattern_value)
            elif modifier == "contains":
                return pattern_value in str_value
            elif modifier == "re":
                import re

                return bool(re.search(pattern_value, str_value, re.IGNORECASE))

        # Wildcard matching
        if "*" in str_pattern or "?" in str_pattern:
            import fnmatch

            return fnmatch.fnmatch(str_value, str_pattern)

        # Exact match
        return str_value == str_pattern

    def _evaluate_condition(
        self,
        condition: str,
        detection_results: dict[str, bool],
    ) -> bool:
        """Evaluate a Sigma condition expression.

        Supports basic operators: and, or, not, all of, 1 of

        Args:
            condition: Condition expression
            detection_results: Results of detection block evaluation

        Returns:
            True if condition is satisfied
        """
        # Normalize condition
        condition = condition.lower().strip()

        # Handle "all of them"
        if condition == "all of them":
            return all(detection_results.values())

        # Handle "1 of them"
        if condition == "1 of them":
            return any(detection_results.values())

        # Handle "all of <pattern>"
        if condition.startswith("all of "):
            pattern = condition[7:].strip()
            matching_keys = [
                key for key in detection_results if self._key_matches_pattern(key, pattern)
            ]
            return all(detection_results.get(key, False) for key in matching_keys)

        # Handle "1 of <pattern>"
        if condition.startswith("1 of "):
            pattern = condition[5:].strip()
            matching_keys = [
                key for key in detection_results if self._key_matches_pattern(key, pattern)
            ]
            return any(detection_results.get(key, False) for key in matching_keys)

        # Simple evaluation for single selection
        if condition in detection_results:
            return detection_results[condition]

        # Handle basic and/or/not
        # This is a simplified implementation
        if " and " in condition:
            parts = condition.split(" and ")
            return all(self._evaluate_condition(part.strip(), detection_results) for part in parts)

        if " or " in condition:
            parts = condition.split(" or ")
            return any(self._evaluate_condition(part.strip(), detection_results) for part in parts)

        if condition.startswith("not "):
            inner = condition[4:].strip()
            return not self._evaluate_condition(inner, detection_results)

        return False

    def _key_matches_pattern(self, key: str, pattern: str) -> bool:
        """Check if key matches pattern (for all of/1 of).

        Args:
            key: Detection block key
            pattern: Pattern (supports * wildcard)

        Returns:
            True if matches
        """
        import fnmatch

        return fnmatch.fnmatch(key.lower(), pattern.lower())

    def _extract_matched_fields(
        self,
        event: dict[str, Any],
        rule: SigmaRule,
    ) -> dict[str, Any]:
        """Extract fields that matched the rule.

        Args:
            event: Matched event
            rule: Matching rule

        Returns:
            Dictionary of matched fields and values
        """
        matched = {}

        for key, detection_item in rule.detection.items():
            if key == "condition":
                continue

            if isinstance(detection_item, dict):
                for field in detection_item.keys():
                    value = self._get_field_value(event, field)
                    if value is not None:
                        matched[field] = value
            elif isinstance(detection_item, list):
                for item in detection_item:
                    if isinstance(item, dict):
                        for field in item.keys():
                            value = self._get_field_value(event, field)
                            if value is not None:
                                matched[field] = value

        return matched

    async def convert_rule(
        self,
        rule_id: str,
        backend: str = "elasticsearch",
    ) -> ConversionResult:
        """Convert a Sigma rule to a backend query.

        Args:
            rule_id: Rule ID to convert
            backend: Target backend (elasticsearch, splunk, etc.)

        Returns:
            Conversion result with query
        """
        if rule_id not in self._rules:
            return ConversionResult(
                rule_id=rule_id,
                backend=backend,
                query="",
                error=f"Rule not found: {rule_id}",
            )

        rule = self._rules[rule_id]

        try:
            from sigma.backends.elasticsearch import LuceneBackend
            from sigma.collection import SigmaCollection
            from sigma.pipelines.elasticsearch import ecs_windows

            # Create Sigma rule from our internal representation
            sigma_yaml = self._rule_to_yaml(rule)

            # Parse with pySigma
            collection = SigmaCollection.from_yaml(sigma_yaml)

            # Get backend and pipeline
            pipeline = ecs_windows()
            backend_instance = LuceneBackend(pipeline)

            # Convert
            queries = backend_instance.convert(collection)
            query = queries[0] if queries else ""

            return ConversionResult(
                rule_id=rule_id,
                backend=backend,
                query=query,
                index_pattern=self._get_index_pattern(rule),
            )

        except ImportError:
            # Fallback without pySigma
            return ConversionResult(
                rule_id=rule_id,
                backend=backend,
                query="",
                error="pySigma not available for conversion",
            )

        except Exception as error:
            return ConversionResult(
                rule_id=rule_id,
                backend=backend,
                query="",
                error=str(error),
            )

    def _rule_to_yaml(self, rule: SigmaRule) -> str:
        """Convert internal rule to YAML string.

        Args:
            rule: Internal SigmaRule

        Returns:
            YAML string
        """
        import yaml

        data = {
            "id": rule.rule_id,
            "title": rule.title,
            "description": rule.description,
            "status": rule.status,
            "level": rule.level,
            "logsource": rule.logsource,
            "detection": rule.detection,
            "tags": rule.tags,
        }

        if rule.author:
            data["author"] = rule.author
        if rule.date:
            data["date"] = rule.date
        if rule.references:
            data["references"] = rule.references
        if rule.falsepositives:
            data["falsepositives"] = rule.falsepositives

        return yaml.dump(data)

    def _get_index_pattern(self, rule: SigmaRule) -> str:
        """Get appropriate index pattern for rule.

        Args:
            rule: Sigma rule

        Returns:
            Index pattern string
        """
        product = rule.product.lower()
        category = rule.category.lower()

        if product == "windows":
            return "winlogbeat-*"
        elif product == "linux":
            return "filebeat-*"
        elif category == "firewall":
            return "firewall-*"
        elif category == "webserver":
            return "webserver-*"
        else:
            return "logs-*"

    def list_rules(
        self,
        level: str | None = None,
        product: str | None = None,
        category: str | None = None,
    ) -> list[SigmaRule]:
        """List loaded rules with optional filtering.

        Args:
            level: Filter by level
            product: Filter by logsource product
            category: Filter by logsource category

        Returns:
            List of matching rules
        """
        rules = list(self._rules.values())

        if level:
            rules = [r for r in rules if r.level == level]

        if product:
            rules = [r for r in rules if r.product.lower() == product.lower()]

        if category:
            rules = [r for r in rules if r.category.lower() == category.lower()]

        return rules

    def get_rule(self, rule_id: str) -> SigmaRule | None:
        """Get a specific rule by ID.

        Args:
            rule_id: Rule ID

        Returns:
            Rule or None
        """
        return self._rules.get(rule_id)

    def get_info(self) -> dict[str, Any]:
        """Get information about loaded rules.

        Returns:
            Engine information dictionary
        """
        # Count by level
        level_counts = {}
        for rule in self._rules.values():
            level_counts[rule.level] = level_counts.get(rule.level, 0) + 1

        # Count by product
        product_counts = {}
        for rule in self._rules.values():
            product = rule.product or "unknown"
            product_counts[product] = product_counts.get(product, 0) + 1

        return {
            "rules_path": str(self.rules_path) if self.rules_path else None,
            "pipeline": self.pipeline_name,
            "rules_loaded": len(self._rules),
            "last_loaded": self._last_loaded.isoformat() if self._last_loaded else None,
            "level_counts": level_counts,
            "product_counts": product_counts,
        }


# Factory function for creating engine from dict config
def create_sigma_engine(config: dict[str, Any]) -> SigmaEngine:
    """Create Sigma engine from dictionary configuration.

    Args:
        config: Configuration dictionary

    Returns:
        Configured SigmaEngine instance
    """
    return SigmaEngine(
        rules_path=config.get("rules_path"),
        pipeline=config.get("pipeline", "ecs_windows"),
    )
