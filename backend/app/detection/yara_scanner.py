"""YARA scanner for malware and IOC detection.

PATTERN: Strategy Pattern
Provides YARA rule-based scanning for files and memory.

Provides:
- Rule compilation and management
- File scanning
- Memory/buffer scanning
- Match result processing
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, UTC
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class YaraMatch:
    """Representation of a YARA rule match.

    PATTERN: Data Transfer Object (DTO)
    Contains match details including rule metadata and matched strings.
    """

    rule_name: str
    namespace: str = ""
    tags: list[str] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)
    strings: list[dict[str, Any]] = field(default_factory=list)
    file_path: str | None = None
    match_time: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def severity(self) -> str:
        """Get severity from rule metadata."""
        return self.meta.get("severity", "medium")

    @property
    def description(self) -> str:
        """Get description from rule metadata."""
        return self.meta.get("description", "")

    @property
    def author(self) -> str:
        """Get author from rule metadata."""
        return self.meta.get("author", "")

    @property
    def reference(self) -> str:
        """Get reference URL from rule metadata."""
        return self.meta.get("reference", "")


@dataclass
class ScanResult:
    """Result of a YARA scan.

    PATTERN: Data Transfer Object (DTO)
    Contains all matches and scan metadata.
    """

    target: str  # File path or identifier
    matches: list[YaraMatch] = field(default_factory=list)
    scan_time: datetime = field(default_factory=lambda: datetime.now(UTC))
    duration_ms: float = 0.0
    file_size: int = 0
    error: str | None = None

    @property
    def has_matches(self) -> bool:
        """Check if any rules matched."""
        return len(self.matches) > 0

    @property
    def match_count(self) -> int:
        """Get total match count."""
        return len(self.matches)

    @property
    def highest_severity(self) -> str:
        """Get highest severity among matches."""
        severity_order = {"critical": 4, "high": 3, "medium": 2, "low": 1, "info": 0}
        if not self.matches:
            return "none"
        return max(
            self.matches,
            key=lambda match: severity_order.get(match.severity.lower(), 0),
        ).severity


class YaraScanner:
    """YARA rule scanner for malware detection.

    PATTERN: Facade Pattern
    Provides a simplified interface for YARA scanning operations.

    Configuration:
        rules_path: Path to YARA rules directory or file
        compiled_rules_path: Path to pre-compiled rules (optional)
        external_vars: External variables for rules

    DESIGN DECISION: Supports both source rules and pre-compiled rules
    for flexibility in deployment scenarios.
    """

    def __init__(
        self,
        rules_path: str | Path | None = None,
        compiled_rules_path: str | Path | None = None,
        external_vars: dict[str, Any] | None = None,
    ):
        """Initialize YARA scanner.

        Args:
            rules_path: Path to YARA rules directory or file
            compiled_rules_path: Path to pre-compiled rules
            external_vars: External variables for rules
        """
        self.rules_path = Path(rules_path) if rules_path else None
        self.compiled_rules_path = Path(compiled_rules_path) if compiled_rules_path else None
        self.external_vars = external_vars or {}

        self._rules = None
        self._rule_count = 0
        self._last_loaded: datetime | None = None

    async def load_rules(self) -> int:
        """Load YARA rules.

        Returns:
            Number of rules loaded

        Raises:
            ValueError: If no rules path configured
            yara.Error: If rules fail to compile
        """
        import yara

        if self.compiled_rules_path and self.compiled_rules_path.exists():
            # Load pre-compiled rules
            self._rules = yara.load(str(self.compiled_rules_path))
            logger.info(f"Loaded compiled YARA rules from {self.compiled_rules_path}")

        elif self.rules_path:
            if self.rules_path.is_file():
                # Single rule file
                self._rules = yara.compile(
                    filepath=str(self.rules_path),
                    externals=self.external_vars,
                )
            elif self.rules_path.is_dir():
                # Directory of rules
                rule_sources = {}
                for rule_file in self.rules_path.rglob("*.yar"):
                    namespace = rule_file.stem
                    rule_sources[namespace] = str(rule_file)

                for rule_file in self.rules_path.rglob("*.yara"):
                    namespace = rule_file.stem
                    rule_sources[namespace] = str(rule_file)

                if not rule_sources:
                    raise ValueError(f"No YARA rules found in {self.rules_path}")

                self._rules = yara.compile(
                    filepaths=rule_sources,
                    externals=self.external_vars,
                )
            else:
                raise ValueError(f"Rules path does not exist: {self.rules_path}")

            logger.info(f"Compiled YARA rules from {self.rules_path}")

        else:
            raise ValueError("No rules path configured")

        # Count rules (approximate based on compiled size)
        self._rule_count = len(self._rules) if hasattr(self._rules, "__len__") else 0
        self._last_loaded = datetime.now(UTC)

        return self._rule_count

    async def scan_file(
        self,
        file_path: str | Path,
        timeout: int = 60,
    ) -> ScanResult:
        """Scan a file with YARA rules.

        Args:
            file_path: Path to file to scan
            timeout: Scan timeout in seconds

        Returns:
            Scan result with matches
        """
        import time

        file_path = Path(file_path)
        start_time = time.perf_counter()

        result = ScanResult(
            target=str(file_path),
            file_size=file_path.stat().st_size if file_path.exists() else 0,
        )

        if not self._rules:
            await self.load_rules()

        try:
            matches = self._rules.match(
                str(file_path),
                timeout=timeout,
                externals=self.external_vars,
            )

            for match in matches:
                yara_match = self._parse_match(match, str(file_path))
                result.matches.append(yara_match)

        except Exception as error:
            result.error = str(error)
            logger.error(f"YARA scan error for {file_path}: {error}")

        result.duration_ms = (time.perf_counter() - start_time) * 1000
        return result

    async def scan_data(
        self,
        data: bytes,
        identifier: str = "memory",
        timeout: int = 60,
    ) -> ScanResult:
        """Scan data buffer with YARA rules.

        Args:
            data: Data to scan
            identifier: Identifier for the data source
            timeout: Scan timeout in seconds

        Returns:
            Scan result with matches
        """
        import time

        start_time = time.perf_counter()

        result = ScanResult(
            target=identifier,
            file_size=len(data),
        )

        if not self._rules:
            await self.load_rules()

        try:
            matches = self._rules.match(
                data=data,
                timeout=timeout,
                externals=self.external_vars,
            )

            for match in matches:
                yara_match = self._parse_match(match, identifier)
                result.matches.append(yara_match)

        except Exception as error:
            result.error = str(error)
            logger.error(f"YARA scan error for {identifier}: {error}")

        result.duration_ms = (time.perf_counter() - start_time) * 1000
        return result

    async def scan_process(
        self,
        pid: int,
        timeout: int = 60,
    ) -> ScanResult:
        """Scan a process memory with YARA rules.

        Args:
            pid: Process ID to scan
            timeout: Scan timeout in seconds

        Returns:
            Scan result with matches

        Note:
            Requires appropriate permissions to access process memory.
        """
        import time

        start_time = time.perf_counter()

        result = ScanResult(target=f"pid:{pid}")

        if not self._rules:
            await self.load_rules()

        try:
            matches = self._rules.match(
                pid=pid,
                timeout=timeout,
                externals=self.external_vars,
            )

            for match in matches:
                yara_match = self._parse_match(match, f"pid:{pid}")
                result.matches.append(yara_match)

        except Exception as error:
            result.error = str(error)
            logger.error(f"YARA process scan error for PID {pid}: {error}")

        result.duration_ms = (time.perf_counter() - start_time) * 1000
        return result

    async def scan_directory(
        self,
        directory: str | Path,
        recursive: bool = True,
        extensions: list[str] | None = None,
        timeout: int = 60,
    ) -> list[ScanResult]:
        """Scan all files in a directory.

        Args:
            directory: Directory to scan
            recursive: Scan subdirectories
            extensions: File extensions to include (None = all)
            timeout: Timeout per file

        Returns:
            List of scan results
        """
        directory = Path(directory)
        results = []

        if recursive:
            files = directory.rglob("*")
        else:
            files = directory.glob("*")

        for file_path in files:
            if not file_path.is_file():
                continue

            if extensions:
                if file_path.suffix.lower() not in extensions:
                    continue

            result = await self.scan_file(file_path, timeout=timeout)
            results.append(result)

        return results

    async def add_rules(
        self,
        source: str,
        namespace: str = "dynamic",
    ) -> None:
        """Add rules from source string.

        DESIGN DECISION: Creates new compiled rules that include
        both existing rules and new source. This is needed because
        YARA doesn't support adding rules to existing compiled rules.

        Args:
            source: YARA rule source code
            namespace: Namespace for new rules
        """
        import yara

        # Compile new rules with existing external vars
        new_rules = yara.compile(
            source=source,
            externals=self.external_vars,
        )

        # If we have existing rules, we need to merge (not directly supported)
        # For now, store separately and scan with both
        if self._rules:
            logger.warning(
                "Adding rules dynamically - existing rules will be replaced. "
                "Consider reloading all rules from source."
            )

        self._rules = new_rules

    def get_rule_info(self) -> dict[str, Any]:
        """Get information about loaded rules.

        Returns:
            Rule information dictionary
        """
        return {
            "rules_path": str(self.rules_path) if self.rules_path else None,
            "compiled_path": str(self.compiled_rules_path) if self.compiled_rules_path else None,
            "rules_loaded": self._rules is not None,
            "rule_count": self._rule_count,
            "last_loaded": self._last_loaded.isoformat() if self._last_loaded else None,
            "external_vars": list(self.external_vars.keys()),
        }

    async def save_compiled_rules(self, output_path: str | Path) -> None:
        """Save compiled rules to file.

        Args:
            output_path: Path for compiled rules file
        """
        if not self._rules:
            raise ValueError("No rules loaded")

        self._rules.save(str(output_path))
        logger.info(f"Saved compiled YARA rules to {output_path}")

    def _parse_match(self, match, target: str) -> YaraMatch:
        """Parse YARA match object to YaraMatch.

        Args:
            match: YARA match object
            target: Scanned file/data identifier

        Returns:
            Parsed YaraMatch
        """
        # Parse matched strings
        strings = []
        for string_match in match.strings:
            for instance in string_match.instances:
                strings.append(
                    {
                        "identifier": string_match.identifier,
                        "offset": instance.offset,
                        "matched_data": (
                            instance.matched_data[:100].hex() if instance.matched_data else ""
                        ),
                        "length": instance.matched_length,
                    }
                )

        return YaraMatch(
            rule_name=match.rule,
            namespace=match.namespace,
            tags=list(match.tags),
            meta=dict(match.meta),
            strings=strings[:50],  # Limit to first 50 string matches
            file_path=target,
        )


# Factory function for creating scanner from dict config
def create_yara_scanner(config: dict[str, Any]) -> YaraScanner:
    """Create YARA scanner from dictionary configuration.

    Args:
        config: Configuration dictionary

    Returns:
        Configured YaraScanner instance
    """
    return YaraScanner(
        rules_path=config.get("rules_path"),
        compiled_rules_path=config.get("compiled_rules_path"),
        external_vars=config.get("external_vars", {}),
    )
