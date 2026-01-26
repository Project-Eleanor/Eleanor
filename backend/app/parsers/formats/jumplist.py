"""Windows Jump List parser.

Jump Lists store recent/frequent files accessed by applications.
Two types:
- AutomaticDestinations: System-maintained lists (*.automaticDestinations-ms)
- CustomDestinations: Application-maintained lists (*.customDestinations-ms)

Location: %APPDATA%\Microsoft\Windows\Recent\AutomaticDestinations\
          %APPDATA%\Microsoft\Windows\Recent\CustomDestinations\
"""

import logging
import struct
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncIterator
from uuid import uuid4

from app.parsers.base import BaseParser, ParsedEvent, ParserMetadata
from app.parsers.registry import register_parser

logger = logging.getLogger(__name__)

try:
    from dissect.ole import OLE
    DISSECT_OLE_AVAILABLE = True
except ImportError:
    DISSECT_OLE_AVAILABLE = False

try:
    from dissect.shellitem import lnk
    DISSECT_LNK_AVAILABLE = True
except ImportError:
    DISSECT_LNK_AVAILABLE = False


# Known AppIDs for Jump Lists
KNOWN_APP_IDS = {
    "1b4dd67f29cb1962": "Windows Explorer",
    "5f7b5f1e01b83767": "Quick Access",
    "9b9cdc69c1c24e2b": "Notepad",
    "918e0ecb43d17e23": "Notepad++",
    "adecfb853d77462a": "Microsoft Word",
    "a7bd71699cd38d1c": "Microsoft Excel",
    "d00655d2aa12ff6d": "Microsoft PowerPoint",
    "5d696d521de238c3": "Google Chrome",
    "ebd8c95c5d5e8d8e": "Mozilla Firefox",
    "28c8b86deab549a1": "Internet Explorer / Edge Legacy",
    "9839aec31243a928": "Microsoft Edge",
    "7e4dca80246863e3": "Control Panel",
    "1cf97c38a5881255": "Task Manager",
    "290532160612e071": "Windows Media Player",
    "f01b4d95cf55d32a": "Windows Media Center",
    "969252ce11249fdd": "Media Player (Classic)",
    "bc0c37e84e063727": "Command Prompt (cmd.exe)",
    "b91050d8b077a4e8": "PowerShell",
    "0a1d19afe5a80f80": "FileZilla",
    "cfb56c56fa0f0a54": "PuTTY",
    "6824f4a902c78fbd": "WinSCP",
    "5b186fc4a0b40504": "Downloader",
    "c765823d986857ba": "WinRAR",
    "bc03160ee1a59fc1": "7-Zip",
    "a8c43ef36da523b1": "Sublime Text",
    "2b53c4ddf69195fc": "Visual Studio Code",
}


@register_parser
class JumpListParser(BaseParser):
    """Parser for Windows Jump List files."""

    @classmethod
    def get_metadata(cls) -> ParserMetadata:
        return ParserMetadata(
            name="jumplist",
            display_name="Windows Jump List Parser",
            description="Parses Windows Jump List files for recent/frequent file access",
            supported_extensions=[".automaticDestinations-ms", ".customDestinations-ms"],
            mime_types=["application/octet-stream"],
            category="windows",
            priority=75,
        )

    async def parse(
        self,
        file_path: Path,
        case_id: str | None = None,
        evidence_id: str | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[ParsedEvent]:
        """Parse Jump List file."""
        filename = file_path.name.lower()

        if "automaticdestinations" in filename:
            async for event in self._parse_automatic(file_path, case_id, evidence_id):
                yield event
        elif "customdestinations" in filename:
            async for event in self._parse_custom(file_path, case_id, evidence_id):
                yield event
        else:
            logger.warning(f"Unknown Jump List format: {file_path}")

    async def _parse_automatic(
        self,
        file_path: Path,
        case_id: str | None,
        evidence_id: str | None,
    ) -> AsyncIterator[ParsedEvent]:
        """Parse AutomaticDestinations Jump List (OLE compound file)."""
        if not DISSECT_OLE_AVAILABLE:
            logger.warning("dissect.ole required for AutomaticDestinations parsing")
            return

        try:
            # Extract AppID from filename
            app_id = file_path.stem.split(".")[0].lower()
            app_name = KNOWN_APP_IDS.get(app_id, f"Unknown ({app_id})")

            with open(file_path, "rb") as f:
                ole = OLE(f)

            # Each stream in the OLE file is an LNK entry
            for stream in ole.listdir():
                stream_name = stream[-1] if isinstance(stream, list) else stream

                # Skip non-entry streams
                if stream_name in ("DestList", "Root Entry"):
                    continue

                try:
                    stream_data = ole.openstream(stream).read()

                    if DISSECT_LNK_AVAILABLE:
                        entry = self._parse_lnk_stream(stream_data, app_id, app_name)
                    else:
                        entry = self._parse_lnk_manual(stream_data, app_id, app_name)

                    if entry:
                        entry["stream_name"] = stream_name
                        entry["jumplist_path"] = str(file_path)
                        yield self._create_event(entry, case_id, evidence_id)

                except Exception as e:
                    logger.debug(f"Failed to parse stream {stream_name}: {e}")

            # Parse DestList for additional metadata
            try:
                destlist = ole.openstream("DestList").read()
                async for event in self._parse_destlist(
                    destlist, app_id, app_name, file_path, case_id, evidence_id
                ):
                    yield event
            except Exception:
                pass

        except Exception as e:
            logger.error(f"Failed to parse AutomaticDestinations: {e}")
            raise

    async def _parse_custom(
        self,
        file_path: Path,
        case_id: str | None,
        evidence_id: str | None,
    ) -> AsyncIterator[ParsedEvent]:
        """Parse CustomDestinations Jump List (LNK stream file)."""
        try:
            app_id = file_path.stem.split(".")[0].lower()
            app_name = KNOWN_APP_IDS.get(app_id, f"Unknown ({app_id})")

            with open(file_path, "rb") as f:
                data = f.read()

            # CustomDestinations contain multiple LNK entries separated by specific headers
            offset = 0
            entry_num = 0

            while offset < len(data) - 4:
                # Look for LNK signature
                if data[offset:offset+4] == b"\x4c\x00\x00\x00":
                    # Find end of this LNK (next signature or end of file)
                    next_lnk = data.find(b"\x4c\x00\x00\x00", offset + 4)
                    if next_lnk == -1:
                        lnk_data = data[offset:]
                    else:
                        lnk_data = data[offset:next_lnk]

                    try:
                        if DISSECT_LNK_AVAILABLE:
                            entry = self._parse_lnk_stream(lnk_data, app_id, app_name)
                        else:
                            entry = self._parse_lnk_manual(lnk_data, app_id, app_name)

                        if entry:
                            entry["entry_number"] = entry_num
                            entry["jumplist_path"] = str(file_path)
                            yield self._create_event(entry, case_id, evidence_id)
                            entry_num += 1

                    except Exception as e:
                        logger.debug(f"Failed to parse LNK entry at offset {offset}: {e}")

                    offset = next_lnk if next_lnk != -1 else len(data)
                else:
                    offset += 1

        except Exception as e:
            logger.error(f"Failed to parse CustomDestinations: {e}")
            raise

    def _parse_lnk_stream(
        self,
        data: bytes,
        app_id: str,
        app_name: str,
    ) -> dict[str, Any] | None:
        """Parse LNK data using dissect."""
        try:
            from io import BytesIO
            lnk_file = lnk.Lnk(BytesIO(data))

            return {
                "app_id": app_id,
                "app_name": app_name,
                "target_path": str(lnk_file.target) if lnk_file.target else None,
                "arguments": lnk_file.arguments,
                "working_dir": lnk_file.working_dir,
                "creation_time": lnk_file.creation_time,
                "modification_time": lnk_file.modification_time,
                "access_time": lnk_file.access_time,
                "file_size": lnk_file.file_size,
                "machine_id": lnk_file.machine_id,
            }

        except Exception as e:
            logger.debug(f"Failed to parse LNK stream: {e}")
            return None

    def _parse_lnk_manual(
        self,
        data: bytes,
        app_id: str,
        app_name: str,
    ) -> dict[str, Any] | None:
        """Manually parse LNK data without dissect."""
        if len(data) < 76:
            return None

        try:
            entry = {
                "app_id": app_id,
                "app_name": app_name,
            }

            # Parse timestamps from header
            entry["creation_time"] = self._filetime_to_datetime(
                struct.unpack("<Q", data[28:36])[0]
            )
            entry["access_time"] = self._filetime_to_datetime(
                struct.unpack("<Q", data[36:44])[0]
            )
            entry["modification_time"] = self._filetime_to_datetime(
                struct.unpack("<Q", data[44:52])[0]
            )
            entry["file_size"] = struct.unpack("<I", data[52:56])[0]

            return entry

        except Exception as e:
            logger.debug(f"Failed to manually parse LNK: {e}")
            return None

    async def _parse_destlist(
        self,
        data: bytes,
        app_id: str,
        app_name: str,
        file_path: Path,
        case_id: str | None,
        evidence_id: str | None,
    ) -> AsyncIterator[ParsedEvent]:
        """Parse DestList stream for additional entry metadata."""
        # DestList contains entry metadata like access counts and timestamps
        # Format varies by Windows version
        if len(data) < 32:
            return

        try:
            # Header
            version = struct.unpack("<I", data[0:4])[0]
            num_entries = struct.unpack("<I", data[4:8])[0]
            pinned_entries = struct.unpack("<I", data[8:12])[0]

            offset = 32  # Skip header

            for i in range(min(num_entries, 1000)):
                if offset + 114 > len(data):  # Minimum entry size
                    break

                try:
                    # Entry structure (Windows 10 format)
                    entry_hash = data[offset:offset+8].hex()
                    filetime = struct.unpack("<Q", data[offset+100:offset+108])[0]
                    access_count = struct.unpack("<I", data[offset+8:offset+12])[0]

                    # Path starts at offset 130 (variable length, null-terminated UTF-16)
                    path_start = offset + 130
                    if path_start < len(data):
                        path_end = data.find(b"\x00\x00", path_start)
                        if path_end > path_start:
                            path = data[path_start:path_end+1].decode("utf-16-le", errors="ignore")
                        else:
                            path = None
                    else:
                        path = None

                    entry = {
                        "app_id": app_id,
                        "app_name": app_name,
                        "target_path": path,
                        "entry_hash": entry_hash,
                        "access_count": access_count,
                        "access_time": self._filetime_to_datetime(filetime),
                        "jumplist_path": str(file_path),
                        "destlist_entry": True,
                    }

                    if path:
                        yield self._create_event(entry, case_id, evidence_id)

                    # Move to next entry (entry size is at offset 112-114)
                    entry_size = struct.unpack("<H", data[offset+112:offset+114])[0]
                    offset += 130 + entry_size * 2 + 4

                except Exception as e:
                    logger.debug(f"Failed to parse DestList entry {i}: {e}")
                    break

        except Exception as e:
            logger.debug(f"Failed to parse DestList: {e}")

    def _create_event(
        self,
        entry: dict[str, Any],
        case_id: str | None,
        evidence_id: str | None,
    ) -> ParsedEvent:
        """Create ECS event from Jump List entry."""
        target_path = entry.get("target_path", "unknown")
        app_name = entry.get("app_name", "unknown")
        access_time = entry.get("access_time") or entry.get("modification_time") or datetime.now(timezone.utc)

        return ParsedEvent(
            id=str(uuid4()),
            timestamp=access_time,
            message=f"JumpList ({app_name}): {target_path}",
            source="jumplist",
            raw_data=entry,
            normalized={
                "event": {
                    "kind": "event",
                    "category": ["file"],
                    "type": ["access"],
                    "action": "file_accessed",
                    "module": "jumplist",
                    "dataset": "windows.jumplist",
                },
                "file": {
                    "path": target_path,
                    "name": Path(target_path).name if target_path and target_path != "unknown" else None,
                    "accessed": access_time.isoformat() if access_time else None,
                },
                "process": {
                    "name": app_name,
                },
                "host": {
                    "os": {"type": "windows"},
                    "name": entry.get("machine_id"),
                },
                "eleanor": {
                    "case_id": case_id,
                    "evidence_id": evidence_id,
                    "parser": "jumplist",
                    "artifact_type": "jumplist",
                    "app_id": entry.get("app_id"),
                    "access_count": entry.get("access_count"),
                    "arguments": entry.get("arguments"),
                    "working_dir": entry.get("working_dir"),
                    "jumplist_path": entry.get("jumplist_path"),
                    "is_destlist": entry.get("destlist_entry", False),
                },
            },
            case_id=case_id,
            evidence_id=evidence_id,
        )

    def _filetime_to_datetime(self, filetime: int) -> datetime | None:
        """Convert Windows FILETIME to datetime."""
        try:
            if filetime == 0:
                return None
            epoch_diff = 116444736000000000
            timestamp = (filetime - epoch_diff) / 10000000
            if timestamp < 0 or timestamp > 4102444800:
                return None
            return datetime.fromtimestamp(timestamp, tz=timezone.utc)
        except Exception:
            return None
