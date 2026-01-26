"""IOC (Indicator of Compromise) extractor.

Extracts various types of indicators from text using regex patterns.
Supports IP addresses, domains, URLs, hashes, email addresses, and more.
"""

import re
from dataclasses import dataclass
from enum import Enum
from typing import Iterator


class IOCType(str, Enum):
    """Types of indicators of compromise."""

    IPV4 = "ipv4"
    IPV6 = "ipv6"
    DOMAIN = "domain"
    URL = "url"
    EMAIL = "email"
    MD5 = "md5"
    SHA1 = "sha1"
    SHA256 = "sha256"
    SHA512 = "sha512"
    FILENAME = "filename"
    FILEPATH = "filepath"
    CVE = "cve"
    MITRE_TECHNIQUE = "mitre_technique"
    REGISTRY_KEY = "registry_key"
    BITCOIN_ADDRESS = "bitcoin"
    YARA_RULE = "yara_rule"


@dataclass
class IOCMatch:
    """Represents a matched IOC in text."""

    value: str
    ioc_type: IOCType
    start: int
    end: int
    original: str  # Original matched text (before normalization)
    context: str = ""  # Surrounding context

    def __hash__(self):
        return hash((self.value, self.ioc_type))

    def __eq__(self, other):
        if isinstance(other, IOCMatch):
            return self.value == other.value and self.ioc_type == other.ioc_type
        return False


class IOCExtractor:
    """Extracts IOCs from text using pattern matching.

    Supports extraction of:
    - IP addresses (IPv4 and IPv6)
    - Domain names
    - URLs
    - Email addresses
    - File hashes (MD5, SHA1, SHA256, SHA512)
    - File paths (Windows and Unix)
    - CVE identifiers
    - MITRE ATT&CK technique IDs
    - Registry keys
    - Bitcoin addresses
    """

    # Pattern definitions
    PATTERNS = {
        IOCType.IPV4: re.compile(
            r"\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}"
            r"(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b"
        ),
        IOCType.IPV6: re.compile(
            r"\b(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}\b|"
            r"\b(?:[0-9a-fA-F]{1,4}:){1,7}:\b|"
            r"\b(?:[0-9a-fA-F]{1,4}:){1,6}:[0-9a-fA-F]{1,4}\b|"
            r"\b(?:[0-9a-fA-F]{1,4}:){1,5}(?::[0-9a-fA-F]{1,4}){1,2}\b|"
            r"\b(?:[0-9a-fA-F]{1,4}:){1,4}(?::[0-9a-fA-F]{1,4}){1,3}\b|"
            r"\b(?:[0-9a-fA-F]{1,4}:){1,3}(?::[0-9a-fA-F]{1,4}){1,4}\b|"
            r"\b(?:[0-9a-fA-F]{1,4}:){1,2}(?::[0-9a-fA-F]{1,4}){1,5}\b|"
            r"\b[0-9a-fA-F]{1,4}:(?::[0-9a-fA-F]{1,4}){1,6}\b|"
            r"\b:(?::[0-9a-fA-F]{1,4}){1,7}\b|"
            r"\b::(?:[fF]{4}:)?(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b"
        ),
        IOCType.MD5: re.compile(r"\b[a-fA-F0-9]{32}\b"),
        IOCType.SHA1: re.compile(r"\b[a-fA-F0-9]{40}\b"),
        IOCType.SHA256: re.compile(r"\b[a-fA-F0-9]{64}\b"),
        IOCType.SHA512: re.compile(r"\b[a-fA-F0-9]{128}\b"),
        IOCType.EMAIL: re.compile(
            r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b"
        ),
        IOCType.URL: re.compile(
            r"https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+(?::\d+)?(?:/[-\w./?%&=+#~!@$*,;:()]*)?",
            re.IGNORECASE,
        ),
        IOCType.DOMAIN: re.compile(
            r"\b(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}\b"
        ),
        IOCType.CVE: re.compile(
            r"\bCVE-\d{4}-\d{4,}\b",
            re.IGNORECASE,
        ),
        IOCType.MITRE_TECHNIQUE: re.compile(
            r"\b(?:T|TA)\d{4}(?:\.\d{3})?\b"
        ),
        IOCType.FILEPATH: re.compile(
            r'(?:[A-Za-z]:\\(?:[^\\/:*?"<>|\r\n]+\\)*[^\\/:*?"<>|\r\n]*)|'
            r"(?:/(?:[^/\0]+/)*[^/\0]+)",
        ),
        IOCType.REGISTRY_KEY: re.compile(
            r"\b(?:HKEY_(?:LOCAL_MACHINE|CURRENT_USER|CLASSES_ROOT|USERS|CURRENT_CONFIG)|"
            r"HKLM|HKCU|HKCR|HKU|HKCC)\\[^\s]+\b",
            re.IGNORECASE,
        ),
        IOCType.BITCOIN_ADDRESS: re.compile(
            r"\b(?:[13][a-km-zA-HJ-NP-Z1-9]{25,34}|"
            r"bc1[ac-hj-np-z02-9]{11,71})\b"
        ),
    }

    # TLDs for domain validation (common ones)
    VALID_TLDS = {
        "com", "org", "net", "edu", "gov", "mil", "int",
        "io", "co", "me", "info", "biz", "tv", "cc",
        "us", "uk", "ca", "au", "de", "fr", "jp", "cn", "ru", "br", "in",
        "eu", "xyz", "online", "site", "tech", "app", "dev",
    }

    # Common false positive patterns
    FALSE_POSITIVE_DOMAINS = {
        "example.com", "example.org", "example.net",
        "localhost.localdomain", "test.com", "test.local",
        "schema.org", "w3.org", "microsoft.com", "google.com",
    }

    FALSE_POSITIVE_IPS = {
        "0.0.0.0", "127.0.0.1", "255.255.255.255",
        "1.1.1.1", "8.8.8.8", "8.8.4.4",  # DNS servers
    }

    def __init__(
        self,
        include_types: list[IOCType] | None = None,
        exclude_types: list[IOCType] | None = None,
        defang: bool = True,
        filter_false_positives: bool = True,
        context_chars: int = 50,
    ):
        """Initialize the IOC extractor.

        Args:
            include_types: Only extract these IOC types (None = all)
            exclude_types: Exclude these IOC types
            defang: Automatically defang indicators (e.g., [.] -> .)
            filter_false_positives: Filter common false positives
            context_chars: Number of context characters to include
        """
        self.include_types = include_types
        self.exclude_types = exclude_types or []
        self.defang = defang
        self.filter_false_positives = filter_false_positives
        self.context_chars = context_chars

    def extract(self, text: str) -> list[IOCMatch]:
        """Extract all IOCs from text.

        Args:
            text: Text to extract IOCs from

        Returns:
            List of IOCMatch objects
        """
        # Refang text first
        if self.defang:
            text = self._refang(text)

        matches = []
        seen = set()

        for ioc_type, pattern in self.PATTERNS.items():
            # Check if type should be processed
            if self.include_types and ioc_type not in self.include_types:
                continue
            if ioc_type in self.exclude_types:
                continue

            for match_obj in pattern.finditer(text):
                value = match_obj.group()
                normalized = self._normalize(value, ioc_type)

                # Skip duplicates
                key = (normalized, ioc_type)
                if key in seen:
                    continue

                # Validate
                if not self._validate(normalized, ioc_type):
                    continue

                # Filter false positives
                if self.filter_false_positives and self._is_false_positive(normalized, ioc_type):
                    continue

                seen.add(key)

                # Extract context
                start = max(0, match_obj.start() - self.context_chars)
                end = min(len(text), match_obj.end() + self.context_chars)
                context = text[start:end]

                matches.append(IOCMatch(
                    value=normalized,
                    ioc_type=ioc_type,
                    start=match_obj.start(),
                    end=match_obj.end(),
                    original=value,
                    context=context,
                ))

        # Sort by position
        matches.sort(key=lambda m: m.start)

        return matches

    def extract_type(self, text: str, ioc_type: IOCType) -> list[IOCMatch]:
        """Extract only a specific type of IOC.

        Args:
            text: Text to extract from
            ioc_type: Type of IOC to extract

        Returns:
            List of matches of the specified type
        """
        original_include = self.include_types
        self.include_types = [ioc_type]
        try:
            return self.extract(text)
        finally:
            self.include_types = original_include

    def _refang(self, text: str) -> str:
        """Convert defanged indicators back to normal form.

        Handles common defanging patterns:
        - [.] -> .
        - hxxp -> http
        - [at] -> @
        - etc.
        """
        # Domain/URL defanging
        text = re.sub(r"\[\.\]", ".", text)
        text = re.sub(r"\[dot\]", ".", text, flags=re.IGNORECASE)
        text = re.sub(r"\(\.\)", ".", text)
        text = re.sub(r"\[:\]", ":", text)

        # Protocol defanging
        text = re.sub(r"hxxp", "http", text, flags=re.IGNORECASE)
        text = re.sub(r"hXXp", "http", text)
        text = re.sub(r"meow", "http", text, flags=re.IGNORECASE)

        # Email defanging
        text = re.sub(r"\[at\]", "@", text, flags=re.IGNORECASE)
        text = re.sub(r"\[@\]", "@", text)
        text = re.sub(r"\(at\)", "@", text, flags=re.IGNORECASE)

        return text

    def _normalize(self, value: str, ioc_type: IOCType) -> str:
        """Normalize an IOC value.

        Args:
            value: Raw IOC value
            ioc_type: Type of IOC

        Returns:
            Normalized value
        """
        if ioc_type in (IOCType.MD5, IOCType.SHA1, IOCType.SHA256, IOCType.SHA512):
            return value.lower()

        if ioc_type == IOCType.DOMAIN:
            return value.lower()

        if ioc_type == IOCType.URL:
            return value.lower()

        if ioc_type == IOCType.EMAIL:
            return value.lower()

        if ioc_type == IOCType.CVE:
            return value.upper()

        if ioc_type == IOCType.MITRE_TECHNIQUE:
            return value.upper()

        return value

    def _validate(self, value: str, ioc_type: IOCType) -> bool:
        """Validate an extracted IOC.

        Args:
            value: IOC value
            ioc_type: Type of IOC

        Returns:
            True if valid
        """
        if ioc_type == IOCType.DOMAIN:
            # Check TLD
            parts = value.split(".")
            if len(parts) < 2:
                return False
            tld = parts[-1].lower()
            # Allow common TLDs or at least 2 char country codes
            if tld not in self.VALID_TLDS and len(tld) != 2:
                return False
            # Avoid version numbers like "1.0.0"
            if all(p.isdigit() for p in parts):
                return False
            return True

        if ioc_type == IOCType.FILEPATH:
            # Minimum length
            if len(value) < 5:
                return False
            return True

        if ioc_type == IOCType.IPV4:
            # Already matched by regex, but double-check
            parts = value.split(".")
            return len(parts) == 4 and all(0 <= int(p) <= 255 for p in parts)

        return True

    def _is_false_positive(self, value: str, ioc_type: IOCType) -> bool:
        """Check if value is a known false positive.

        Args:
            value: IOC value
            ioc_type: Type of IOC

        Returns:
            True if false positive
        """
        if ioc_type == IOCType.DOMAIN:
            return value.lower() in self.FALSE_POSITIVE_DOMAINS

        if ioc_type == IOCType.IPV4:
            if value in self.FALSE_POSITIVE_IPS:
                return True
            # Private IP ranges
            parts = [int(p) for p in value.split(".")]
            if parts[0] == 10:
                return True
            if parts[0] == 172 and 16 <= parts[1] <= 31:
                return True
            if parts[0] == 192 and parts[1] == 168:
                return True
            return False

        if ioc_type in (IOCType.MD5, IOCType.SHA1, IOCType.SHA256, IOCType.SHA512):
            # Check for all zeros or all f's
            if value == "0" * len(value) or value.lower() == "f" * len(value):
                return True
            return False

        return False

    def get_summary(self, matches: list[IOCMatch]) -> dict[str, list[str]]:
        """Get a summary of IOC matches by type.

        Args:
            matches: List of IOC matches

        Returns:
            Dictionary mapping IOC type to list of values
        """
        summary: dict[str, list[str]] = {}
        for match in matches:
            type_name = match.ioc_type.value
            if type_name not in summary:
                summary[type_name] = []
            if match.value not in summary[type_name]:
                summary[type_name].append(match.value)
        return summary
