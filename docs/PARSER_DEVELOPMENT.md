# Parser Development Guide

This guide explains how to create custom parsers for Eleanor to parse new evidence formats.

## Overview

Eleanor's parser system converts raw evidence files (logs, artifacts, memory dumps) into normalized events following the Elastic Common Schema (ECS). Parsers are automatically discovered and can be selected based on file type or content.

## Parser Architecture

```
app/parsers/
├── __init__.py           # Parser registry and discovery
├── base.py               # BaseParser, ParsedEvent, ParserCategory
├── registry.py           # Parser registration utilities
└── formats/              # Individual parser implementations
    ├── evtx.py           # Windows Event Logs
    ├── prefetch.py       # Windows Prefetch
    ├── browser_chrome.py # Chrome History
    ├── mft.py            # NTFS MFT
    └── ...
```

## Creating a Parser

### Step 1: Create the Parser File

Create a new file in `app/parsers/formats/`:

```python
# app/parsers/formats/myformat.py
"""Parser for MyFormat evidence files."""

from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO, Iterator

from app.parsers.base import BaseParser, ParsedEvent, ParserCategory
from app.parsers.registry import register_parser


@register_parser
class MyFormatParser(BaseParser):
    """Parser for MyFormat files."""

    @property
    def name(self) -> str:
        return "myformat"

    @property
    def category(self) -> ParserCategory:
        return ParserCategory.ARTIFACTS

    @property
    def description(self) -> str:
        return "Parses MyFormat evidence files"

    @property
    def supported_extensions(self) -> list[str]:
        return [".myf", ".myformat"]

    @property
    def supported_mime_types(self) -> list[str]:
        return ["application/x-myformat"]

    def can_parse(
        self,
        file_path: Path | None = None,
        content: bytes | None = None
    ) -> bool:
        """Check if this parser can handle the input."""
        # Check magic bytes
        if content and len(content) >= 4:
            if content[:4] == b"MYFT":
                return True

        # Fall back to extension check
        if file_path:
            return file_path.suffix.lower() in self.supported_extensions

        return False

    def parse(
        self,
        source: Path | BinaryIO,
        source_name: str | None = None
    ) -> Iterator[ParsedEvent]:
        """Parse the input and yield events."""
        # Handle both file paths and file-like objects
        if isinstance(source, Path):
            file_path = source
            source_name = source_name or source.name
            with open(source, "rb") as f:
                yield from self._parse_content(f, source_name)
        else:
            yield from self._parse_content(source, source_name or "unknown")

    def _parse_content(
        self,
        f: BinaryIO,
        source_name: str
    ) -> Iterator[ParsedEvent]:
        """Parse file content and yield events."""
        # Your parsing logic here
        # Example: read records and convert to ParsedEvent

        for record in self._read_records(f):
            yield ParsedEvent(
                timestamp=record.timestamp,
                message=f"MyFormat event: {record.description}",
                source_type=self.name,
                source_file=source_name,

                # ECS fields
                event_kind="event",
                event_category=["process"],  # or file, network, etc.
                event_action="my_action",

                # Populate relevant fields
                process_name=record.process_name,
                user_name=record.user,

                # Store additional data
                raw={
                    "field1": record.field1,
                    "field2": record.field2,
                },
                tags=["myformat"],
                labels={"parser": "myformat"},
            )
```

### Step 2: Register the Parser

The `@register_parser` decorator automatically registers your parser. Alternatively, add it to the parser registry in `app/parsers/__init__.py`:

```python
from app.parsers.formats.myformat import MyFormatParser
```

### Step 3: Write Tests

Create tests in `tests/unit/parsers/test_myformat_parser.py`:

```python
"""Unit tests for MyFormat parser."""

import pytest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

pytestmark = pytest.mark.unit


class TestMyFormatParser:
    """Tests for MyFormatParser class."""

    @pytest.fixture
    def parser(self):
        from app.parsers.formats.myformat import MyFormatParser
        return MyFormatParser()

    def test_parser_name(self, parser):
        assert parser.name == "myformat"

    def test_parser_category(self, parser):
        from app.parsers.base import ParserCategory
        assert parser.category == ParserCategory.ARTIFACTS

    def test_supported_extensions(self, parser):
        assert ".myf" in parser.supported_extensions

    def test_can_parse_by_magic_bytes(self, parser):
        valid_content = b"MYFT" + b"\x00" * 100
        assert parser.can_parse(content=valid_content) is True

    def test_can_parse_invalid_content(self, parser):
        invalid_content = b"NOTMYFORMAT"
        assert parser.can_parse(content=invalid_content) is False

    def test_can_parse_by_extension(self, parser, tmp_path):
        test_file = tmp_path / "test.myf"
        test_file.write_bytes(b"")
        assert parser.can_parse(file_path=test_file) is True


class TestMyFormatParsing:
    """Tests for parsing functionality."""

    @pytest.fixture
    def parser(self):
        from app.parsers.formats.myformat import MyFormatParser
        return MyFormatParser()

    @pytest.fixture
    def sample_file(self, tmp_path):
        """Create a sample MyFormat file."""
        file_path = tmp_path / "test.myf"
        # Write test data in your format
        file_path.write_bytes(b"MYFT" + b"\x00" * 100)
        return file_path

    def test_parse_events(self, parser, sample_file):
        events = list(parser.parse(sample_file))
        assert len(events) >= 1

    def test_event_fields(self, parser, sample_file):
        events = list(parser.parse(sample_file))
        event = events[0]

        assert event.source_type == "myformat"
        assert event.event_kind == "event"
        assert "myformat" in event.tags
```

---

## ParsedEvent Fields

The `ParsedEvent` dataclass provides ECS-compliant fields:

### Core Fields

| Field | Type | Description |
|-------|------|-------------|
| `timestamp` | `datetime` | Event timestamp (required) |
| `message` | `str` | Human-readable event description |
| `source_type` | `str` | Parser name |
| `source_file` | `str` | Original file name |
| `source_line` | `int` | Line number (if applicable) |

### Event Fields (ECS)

| Field | Type | Description |
|-------|------|-------------|
| `event_kind` | `str` | event, alert, metric, state |
| `event_category` | `list[str]` | authentication, file, network, process |
| `event_type` | `list[str]` | access, change, creation, deletion |
| `event_action` | `str` | Specific action (process_created, file_modified) |
| `event_outcome` | `str` | success, failure, unknown |
| `event_severity` | `int` | 0-100 severity score |

### Host Fields

| Field | Type | Description |
|-------|------|-------------|
| `host_name` | `str` | Hostname |
| `host_ip` | `list[str]` | Host IP addresses |
| `host_mac` | `list[str]` | MAC addresses |
| `host_os_name` | `str` | Operating system name |
| `host_os_version` | `str` | OS version |

### User Fields

| Field | Type | Description |
|-------|------|-------------|
| `user_name` | `str` | Username |
| `user_domain` | `str` | User domain |
| `user_id` | `str` | User SID or UID |

### Process Fields

| Field | Type | Description |
|-------|------|-------------|
| `process_name` | `str` | Process name |
| `process_pid` | `int` | Process ID |
| `process_ppid` | `int` | Parent process ID |
| `process_command_line` | `str` | Full command line |
| `process_executable` | `str` | Executable path |

### File Fields

| Field | Type | Description |
|-------|------|-------------|
| `file_name` | `str` | File name |
| `file_path` | `str` | Full file path |
| `file_hash_sha256` | `str` | SHA-256 hash |
| `file_hash_sha1` | `str` | SHA-1 hash |
| `file_hash_md5` | `str` | MD5 hash |

### Network Fields

| Field | Type | Description |
|-------|------|-------------|
| `source_ip` | `str` | Source IP address |
| `source_port` | `int` | Source port |
| `destination_ip` | `str` | Destination IP |
| `destination_port` | `int` | Destination port |
| `network_protocol` | `str` | Protocol (tcp, udp, http) |
| `network_direction` | `str` | inbound, outbound, internal |

### URL Fields

| Field | Type | Description |
|-------|------|-------------|
| `url_full` | `str` | Full URL |
| `url_domain` | `str` | Domain/hostname from URL |

### Custom Fields

| Field | Type | Description |
|-------|------|-------------|
| `raw` | `dict` | Additional parsed data |
| `labels` | `dict[str, str]` | Key-value labels |
| `tags` | `list[str]` | String tags |

---

## Parser Categories

Use the appropriate category for your parser:

```python
class ParserCategory(str, Enum):
    LOGS = "logs"        # Log files (syslog, event logs)
    ARTIFACTS = "artifacts"  # System artifacts (prefetch, registry)
    MEMORY = "memory"    # Memory dumps
    DISK = "disk"        # Disk images, file systems
    NETWORK = "network"  # Network captures
    CLOUD = "cloud"      # Cloud logs and data
```

---

## Alternative: Metadata Pattern

Instead of defining properties, you can use the metadata pattern:

```python
from app.parsers.base import BaseParser, ParsedEvent, ParserMetadata
from app.parsers.registry import register_parser


@register_parser
class MyFormatParser(BaseParser):
    """Parser using metadata pattern."""

    @classmethod
    def get_metadata(cls) -> ParserMetadata:
        return ParserMetadata(
            name="myformat",
            display_name="My Format Parser",
            description="Parses MyFormat evidence files",
            supported_extensions=[".myf", ".myformat"],
            mime_types=["application/x-myformat"],
            category="artifacts",
            priority=50,  # Higher = preferred when multiple match
        )

    def can_parse(self, file_path=None, content=None) -> bool:
        # Magic byte detection
        if content and content[:4] == b"MYFT":
            return True
        return super().can_parse(file_path, content)

    def parse(self, source, source_name=None):
        # Implementation
        pass
```

---

## Best Practices

### 1. Magic Byte Detection

Always implement magic byte detection for reliable format identification:

```python
def can_parse(self, file_path=None, content=None) -> bool:
    # Primary: Check magic bytes
    if content:
        if len(content) >= 8:
            # EVTX magic: "ElfFile\x00"
            if content[:8] == b"ElfFile\x00":
                return True

    # Secondary: Check file extension
    if file_path:
        if file_path.suffix.lower() == ".evtx":
            return True

    return False
```

### 2. Handle Large Files

Use generators to yield events one at a time:

```python
def parse(self, source, source_name=None):
    for record in self._read_records(source):
        # Process one record at a time
        yield self._record_to_event(record)
```

### 3. Error Handling

Handle parsing errors gracefully:

```python
def _parse_record(self, record_data: bytes) -> ParsedEvent | None:
    try:
        # Parse logic
        return ParsedEvent(...)
    except ValueError as e:
        # Log warning but continue parsing
        self.logger.warning(f"Failed to parse record: {e}")
        return None
```

### 4. Timezone Handling

Always use timezone-aware datetimes:

```python
from datetime import datetime, timezone

# Good: Timezone-aware
timestamp = datetime.fromtimestamp(unix_ts, tz=timezone.utc)

# Bad: Naive datetime
timestamp = datetime.fromtimestamp(unix_ts)  # Don't do this
```

### 5. ECS Compliance

Map your data to appropriate ECS fields:

```python
# For process execution events
event = ParsedEvent(
    timestamp=record.time,
    message=f"Process {record.name} executed",
    event_kind="event",
    event_category=["process"],
    event_type=["start"],
    event_action="process_created",
    process_name=record.name,
    process_pid=record.pid,
    process_command_line=record.cmdline,
)

# For authentication events
event = ParsedEvent(
    timestamp=record.time,
    message=f"User {record.user} logged in",
    event_kind="event",
    event_category=["authentication"],
    event_type=["start"],
    event_action="logon",
    event_outcome="success" if record.success else "failure",
    user_name=record.user,
    source_ip=record.client_ip,
)
```

### 6. Use Labels and Tags

Add searchable metadata:

```python
event = ParsedEvent(
    ...,
    tags=["execution_evidence", "windows_artifact"],
    labels={
        "parser": "prefetch",
        "execution_count": str(record.run_count),
        "evidence_type": "prefetch",
    },
)
```

---

## Example: Windows Prefetch Parser

Here's a complete example based on the actual Eleanor parser:

```python
"""Windows Prefetch file parser."""

from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO, Iterator

from app.parsers.base import BaseParser, ParsedEvent, ParserCategory
from app.parsers.registry import register_parser


@register_parser
class WindowsPrefetchParser(BaseParser):
    """Parser for Windows Prefetch files (.pf)."""

    # Magic bytes for different Prefetch versions
    MAGIC_SCCA = b"SCCA"  # Signature at offset 4
    MAGIC_MAM = b"MAM\x04"  # Compressed prefetch (Win10)

    @property
    def name(self) -> str:
        return "windows_prefetch"

    @property
    def category(self) -> ParserCategory:
        return ParserCategory.ARTIFACTS

    @property
    def description(self) -> str:
        return "Windows Prefetch execution evidence"

    @property
    def supported_extensions(self) -> list[str]:
        return [".pf"]

    @property
    def supported_mime_types(self) -> list[str]:
        return ["application/x-ms-prefetch"]

    def can_parse(self, file_path=None, content=None) -> bool:
        if content and len(content) >= 8:
            # Check for SCCA signature at offset 4
            if content[4:8] == self.MAGIC_SCCA:
                return True
            # Check for MAM compressed format
            if content[:4] == self.MAGIC_MAM:
                return True

        if file_path:
            return file_path.suffix.lower() == ".pf"

        return False

    def parse(self, source, source_name=None) -> Iterator[ParsedEvent]:
        if isinstance(source, Path):
            source_name = source_name or source.name
            with open(source, "rb") as f:
                yield from self._parse_prefetch(f, source_name)
        else:
            yield from self._parse_prefetch(source, source_name or "unknown")

    def _parse_prefetch(self, f: BinaryIO, source_name: str) -> Iterator[ParsedEvent]:
        try:
            import prefetch  # Third-party library
            pf = prefetch.Prefetch(f)
        except Exception as e:
            return

        event = self._parse_record(pf, source_name)
        if event:
            yield event

    def _parse_record(self, pf, source_name: str) -> ParsedEvent | None:
        # Get last run time
        if pf.last_run_times:
            timestamp = pf.last_run_times[0]
        else:
            timestamp = datetime.now(timezone.utc)

        # Extract executable name
        exe_name = pf.executable_name
        if "\\" in exe_name:
            exe_name = exe_name.rsplit("\\", 1)[-1]

        return ParsedEvent(
            timestamp=timestamp,
            message=f"Prefetch: {exe_name} (run count: {pf.run_count})",
            source_type=self.name,
            source_file=source_name,

            event_kind="event",
            event_category=["process"],
            event_type=["info"],
            event_action="process_executed",

            process_name=exe_name,
            process_executable=pf.executable_name,

            raw={
                "executable_name": pf.executable_name,
                "run_count": pf.run_count,
                "last_run_times": [t.isoformat() for t in pf.last_run_times],
                "prefetch_hash": hex(pf.prefetch_hash),
                "file_reference_count": len(pf.filenames),
                "file_references": pf.filenames[:50],  # Limit
            },
            tags=["execution_evidence", "windows_prefetch"],
            labels={
                "run_count": str(pf.run_count),
                "execution_evidence": "prefetch",
            },
        )

    def _get_transition_type(self, transition: int) -> str:
        """Convert transition code to string."""
        types = {
            0: "link",
            1: "typed",
            2: "auto_bookmark",
            7: "form_submit",
            8: "reload",
        }
        return types.get(transition & 0xFF, f"unknown_{transition}")
```

---

## Testing Your Parser

### Run Tests

```bash
# Run all parser tests
docker exec eleanor-backend pytest tests/unit/parsers/ -v

# Run specific parser test
docker exec eleanor-backend pytest tests/unit/parsers/test_myformat_parser.py -v

# Run with coverage
docker exec eleanor-backend pytest tests/unit/parsers/ --cov=app.parsers
```

### Test File Creation

For complex formats, create synthetic test files:

```python
@pytest.fixture
def sample_prefetch_file(tmp_path):
    """Create a minimal valid prefetch file."""
    pf_path = tmp_path / "CMD.EXE-12345678.pf"

    # Version 23 header (Windows Vista/7)
    header = b"\x17\x00\x00\x00"  # Version
    header += b"SCCA"  # Signature
    header += b"\x00" * 100  # Padding

    pf_path.write_bytes(header)
    return pf_path
```

---

## Registering in API

Your parser is automatically available via the parsing API:

```bash
# List available parsers
curl http://localhost:8000/api/v1/parsing/parsers \
  -H "Authorization: Bearer $TOKEN"

# Submit evidence for parsing
curl -X POST http://localhost:8000/api/v1/parsing/submit \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "evidence_id": "...",
    "parser_hint": "myformat"
  }'
```

---

## Common Parsing Libraries

| Format | Library | Install |
|--------|---------|---------|
| Windows EVTX | `python-evtx` | `pip install python-evtx` |
| Windows Registry | `python-registry` | `pip install python-registry` |
| Windows Prefetch | `prefetch` | `pip install prefetch` |
| SQLite (browsers) | `sqlite3` | Built-in |
| PE files | `pefile` | `pip install pefile` |
| JSON logs | `json` | Built-in |
| CSV logs | `csv` | Built-in |
| PCAP | `scapy` | `pip install scapy` |

---

## Troubleshooting

### Parser Not Discovered

1. Check the `@register_parser` decorator is present
2. Verify the import in `app/parsers/__init__.py`
3. Restart the backend container

### Magic Bytes Not Matching

1. Use a hex editor to verify actual file format
2. Log the first N bytes: `print(content[:20].hex())`
3. Check for compressed or encrypted variants

### Events Not Indexed

1. Check Celery worker logs: `docker logs eleanor-worker`
2. Verify Elasticsearch connectivity
3. Check event timestamp is timezone-aware
