"""Memory dump parser using Volatility 3.

This parser analyzes memory dumps (raw, lime, crashdump, etc.) using Volatility 3
framework and normalizes results to ECS format for indexing.

Supported formats:
- Raw memory dumps (.raw, .mem, .bin)
- LiME format (.lime)
- Windows crash dumps (.dmp)
- VMware memory snapshots (.vmem)
- VirtualBox memory dumps (.elf)

Volatility 3 plugins used:
- Windows: pslist, pstree, cmdline, dlllist, netscan, malfind, handles, filescan
- Linux: pslist, bash, lsof, netstat, malfind, elfs
- Mac: pslist, bash, lsof, netstat, malfind
"""

import asyncio
import json
import logging
import subprocess
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.parsers.base import BaseParser, ParsedEvent, ParserMetadata
from app.parsers.registry import register_parser

logger = logging.getLogger(__name__)


@register_parser
class MemoryParser(BaseParser):
    """Parser for memory dumps using Volatility 3."""

    def __init__(self) -> None:
        super().__init__()
        self.volatility_path = self._find_volatility()
        self._os_type: str | None = None
        self._os_info: dict[str, Any] = {}

    @classmethod
    def get_metadata(cls) -> ParserMetadata:
        return ParserMetadata(
            name="memory",
            display_name="Memory Dump Parser (Volatility 3)",
            description="Analyzes memory dumps using Volatility 3 framework",
            supported_extensions=[".raw", ".mem", ".bin", ".lime", ".dmp", ".vmem", ".elf"],
            mime_types=[
                "application/octet-stream",
                "application/x-dmp",
            ],
            category="memory",
            priority=50,
        )

    def _find_volatility(self) -> str:
        """Find Volatility 3 executable."""
        # Check common locations
        paths = [
            "/usr/local/bin/vol",
            "/usr/local/bin/vol3",
            "/usr/bin/vol",
            "/usr/bin/vol3",
            "/opt/volatility3/vol.py",
        ]

        for path in paths:
            if Path(path).exists():
                return path

        # Try to find in PATH
        try:
            result = subprocess.run(
                ["which", "vol"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except Exception:
            pass

        # Default - will be validated on parse
        return "vol"

    def _run_volatility(
        self,
        memory_file: str,
        plugin: str,
        extra_args: list[str] | None = None,
        timeout: int = 300,
    ) -> dict[str, Any]:
        """Run a Volatility 3 plugin and return JSON output."""
        cmd = [
            self.volatility_path,
            "-f", memory_file,
            "-r", "json",
            plugin,
        ]

        if extra_args:
            cmd.extend(extra_args)

        logger.debug(f"Running Volatility command: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )

            if result.returncode != 0:
                logger.warning(f"Volatility plugin {plugin} failed: {result.stderr}")
                return {"error": result.stderr, "data": []}

            # Parse JSON output
            try:
                return json.loads(result.stdout)
            except json.JSONDecodeError:
                # Some plugins output line-by-line JSON
                lines = result.stdout.strip().split("\n")
                data = []
                for line in lines:
                    try:
                        data.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
                return {"data": data}

        except subprocess.TimeoutExpired:
            logger.error(f"Volatility plugin {plugin} timed out after {timeout}s")
            return {"error": "timeout", "data": []}
        except Exception as e:
            logger.error(f"Failed to run Volatility plugin {plugin}: {e}")
            return {"error": str(e), "data": []}

    def _detect_os(self, memory_file: str) -> str:
        """Detect the OS type from the memory dump."""
        # Try Windows info first
        result = self._run_volatility(memory_file, "windows.info.Info", timeout=120)
        if "data" in result and result["data"] and "error" not in result:
            self._os_info = result.get("data", [{}])[0] if result.get("data") else {}
            return "windows"

        # Try Linux info
        result = self._run_volatility(memory_file, "linux.boottime.Boottime", timeout=120)
        if "data" in result and result["data"] and "error" not in result:
            return "linux"

        # Try Mac info
        result = self._run_volatility(memory_file, "mac.pslist.PsList", timeout=120)
        if "data" in result and result["data"] and "error" not in result:
            return "mac"

        # Default to windows as most common
        logger.warning("Could not detect OS type, defaulting to Windows")
        return "windows"

    async def parse(
        self,
        file_path: Path,
        case_id: str | None = None,
        evidence_id: str | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[ParsedEvent]:
        """Parse memory dump and yield normalized events."""
        memory_file = str(file_path)

        # Detect OS type
        logger.info(f"Detecting OS type for memory dump: {file_path.name}")
        self._os_type = await asyncio.to_thread(self._detect_os, memory_file)
        logger.info(f"Detected OS type: {self._os_type}")

        # Run appropriate plugins based on OS
        if self._os_type == "windows":
            async for event in self._parse_windows(memory_file, case_id, evidence_id):
                yield event
        elif self._os_type == "linux":
            async for event in self._parse_linux(memory_file, case_id, evidence_id):
                yield event
        elif self._os_type == "mac":
            async for event in self._parse_mac(memory_file, case_id, evidence_id):
                yield event

    async def _parse_windows(
        self,
        memory_file: str,
        case_id: str | None,
        evidence_id: str | None,
    ) -> AsyncIterator[ParsedEvent]:
        """Parse Windows memory dump."""
        # Process list
        logger.info("Running windows.pslist.PsList")
        result = await asyncio.to_thread(
            self._run_volatility, memory_file, "windows.pslist.PsList"
        )
        for proc in result.get("data", []):
            yield self._process_to_event(proc, "windows", case_id, evidence_id)

        # Command lines
        logger.info("Running windows.cmdline.CmdLine")
        result = await asyncio.to_thread(
            self._run_volatility, memory_file, "windows.cmdline.CmdLine"
        )
        for cmdline in result.get("data", []):
            yield self._cmdline_to_event(cmdline, "windows", case_id, evidence_id)

        # DLL list
        logger.info("Running windows.dlllist.DllList")
        result = await asyncio.to_thread(
            self._run_volatility, memory_file, "windows.dlllist.DllList"
        )
        for dll in result.get("data", []):
            yield self._dll_to_event(dll, "windows", case_id, evidence_id)

        # Network connections
        logger.info("Running windows.netscan.NetScan")
        result = await asyncio.to_thread(
            self._run_volatility, memory_file, "windows.netscan.NetScan"
        )
        for conn in result.get("data", []):
            yield self._network_to_event(conn, "windows", case_id, evidence_id)

        # Malfind (suspicious memory regions)
        logger.info("Running windows.malfind.Malfind")
        result = await asyncio.to_thread(
            self._run_volatility, memory_file, "windows.malfind.Malfind"
        )
        for mal in result.get("data", []):
            yield self._malfind_to_event(mal, "windows", case_id, evidence_id)

        # File handles
        logger.info("Running windows.handles.Handles")
        result = await asyncio.to_thread(
            self._run_volatility, memory_file, "windows.handles.Handles",
            extra_args=["--type", "File"],
            timeout=600,
        )
        for handle in result.get("data", []):
            yield self._handle_to_event(handle, "windows", case_id, evidence_id)

        # Registry handles
        logger.info("Running windows.handles.Handles (Registry)")
        result = await asyncio.to_thread(
            self._run_volatility, memory_file, "windows.handles.Handles",
            extra_args=["--type", "Key"],
            timeout=600,
        )
        for handle in result.get("data", []):
            yield self._handle_to_event(handle, "windows", case_id, evidence_id)

        # Services
        logger.info("Running windows.svcscan.SvcScan")
        result = await asyncio.to_thread(
            self._run_volatility, memory_file, "windows.svcscan.SvcScan"
        )
        for svc in result.get("data", []):
            yield self._service_to_event(svc, "windows", case_id, evidence_id)

        # Drivers
        logger.info("Running windows.driverscan.DriverScan")
        result = await asyncio.to_thread(
            self._run_volatility, memory_file, "windows.driverscan.DriverScan"
        )
        for drv in result.get("data", []):
            yield self._driver_to_event(drv, "windows", case_id, evidence_id)

    async def _parse_linux(
        self,
        memory_file: str,
        case_id: str | None,
        evidence_id: str | None,
    ) -> AsyncIterator[ParsedEvent]:
        """Parse Linux memory dump."""
        # Process list
        logger.info("Running linux.pslist.PsList")
        result = await asyncio.to_thread(
            self._run_volatility, memory_file, "linux.pslist.PsList"
        )
        for proc in result.get("data", []):
            yield self._process_to_event(proc, "linux", case_id, evidence_id)

        # Bash history
        logger.info("Running linux.bash.Bash")
        result = await asyncio.to_thread(
            self._run_volatility, memory_file, "linux.bash.Bash"
        )
        for cmd in result.get("data", []):
            yield self._bash_to_event(cmd, case_id, evidence_id)

        # Open files
        logger.info("Running linux.lsof.Lsof")
        result = await asyncio.to_thread(
            self._run_volatility, memory_file, "linux.lsof.Lsof"
        )
        for fd in result.get("data", []):
            yield self._lsof_to_event(fd, case_id, evidence_id)

        # Network connections
        logger.info("Running linux.sockstat.Sockstat")
        result = await asyncio.to_thread(
            self._run_volatility, memory_file, "linux.sockstat.Sockstat"
        )
        for sock in result.get("data", []):
            yield self._network_to_event(sock, "linux", case_id, evidence_id)

        # Malfind
        logger.info("Running linux.malfind.Malfind")
        result = await asyncio.to_thread(
            self._run_volatility, memory_file, "linux.malfind.Malfind"
        )
        for mal in result.get("data", []):
            yield self._malfind_to_event(mal, "linux", case_id, evidence_id)

        # Loaded kernel modules
        logger.info("Running linux.lsmod.Lsmod")
        result = await asyncio.to_thread(
            self._run_volatility, memory_file, "linux.lsmod.Lsmod"
        )
        for mod in result.get("data", []):
            yield self._module_to_event(mod, "linux", case_id, evidence_id)

    async def _parse_mac(
        self,
        memory_file: str,
        case_id: str | None,
        evidence_id: str | None,
    ) -> AsyncIterator[ParsedEvent]:
        """Parse macOS memory dump."""
        # Process list
        logger.info("Running mac.pslist.PsList")
        result = await asyncio.to_thread(
            self._run_volatility, memory_file, "mac.pslist.PsList"
        )
        for proc in result.get("data", []):
            yield self._process_to_event(proc, "mac", case_id, evidence_id)

        # Bash history
        logger.info("Running mac.bash.Bash")
        result = await asyncio.to_thread(
            self._run_volatility, memory_file, "mac.bash.Bash"
        )
        for cmd in result.get("data", []):
            yield self._bash_to_event(cmd, case_id, evidence_id)

        # Open files
        logger.info("Running mac.lsof.Lsof")
        result = await asyncio.to_thread(
            self._run_volatility, memory_file, "mac.lsof.Lsof"
        )
        for fd in result.get("data", []):
            yield self._lsof_to_event(fd, case_id, evidence_id)

        # Network connections
        logger.info("Running mac.netstat.Netstat")
        result = await asyncio.to_thread(
            self._run_volatility, memory_file, "mac.netstat.Netstat"
        )
        for conn in result.get("data", []):
            yield self._network_to_event(conn, "mac", case_id, evidence_id)

        # Malfind
        logger.info("Running mac.malfind.Malfind")
        result = await asyncio.to_thread(
            self._run_volatility, memory_file, "mac.malfind.Malfind"
        )
        for mal in result.get("data", []):
            yield self._malfind_to_event(mal, "mac", case_id, evidence_id)

    def _process_to_event(
        self,
        proc: dict[str, Any],
        os_type: str,
        case_id: str | None,
        evidence_id: str | None,
    ) -> ParsedEvent:
        """Convert process info to ECS event."""
        # Extract common fields
        pid = proc.get("PID") or proc.get("pid")
        ppid = proc.get("PPID") or proc.get("ppid")
        name = proc.get("ImageFileName") or proc.get("COMM") or proc.get("comm") or "unknown"
        create_time = proc.get("CreateTime") or proc.get("create_time")

        # Parse timestamp if present
        timestamp = datetime.now(UTC)
        if create_time:
            try:
                if isinstance(create_time, str):
                    timestamp = datetime.fromisoformat(create_time.replace("Z", "+00:00"))
                elif isinstance(create_time, (int, float)):
                    timestamp = datetime.fromtimestamp(create_time, tz=UTC)
            except Exception:
                pass

        return ParsedEvent(
            id=str(uuid4()),
            timestamp=timestamp,
            message=f"Process: {name} (PID: {pid})",
            source="volatility3",
            raw_data=proc,
            normalized={
                "event": {
                    "kind": "event",
                    "category": ["process"],
                    "type": ["info"],
                    "action": "memory_process_enumeration",
                    "module": "volatility3",
                    "dataset": f"volatility3.{os_type}.pslist",
                },
                "process": {
                    "pid": pid,
                    "ppid": ppid,
                    "name": name,
                    "executable": proc.get("ImageFileName") or proc.get("path"),
                    "start": timestamp.isoformat() if create_time else None,
                    "thread": {
                        "count": proc.get("Threads") or proc.get("threads"),
                    },
                },
                "host": {
                    "os": {
                        "type": os_type,
                        "family": os_type,
                    },
                },
                "eleanor": {
                    "case_id": case_id,
                    "evidence_id": evidence_id,
                    "parser": "memory",
                    "artifact_type": "process_list",
                    "memory_offset": proc.get("OFFSET") or proc.get("offset"),
                },
            },
            case_id=case_id,
            evidence_id=evidence_id,
        )

    def _cmdline_to_event(
        self,
        cmdline: dict[str, Any],
        os_type: str,
        case_id: str | None,
        evidence_id: str | None,
    ) -> ParsedEvent:
        """Convert command line info to ECS event."""
        pid = cmdline.get("PID") or cmdline.get("pid")
        args = cmdline.get("Args") or cmdline.get("args") or ""
        name = cmdline.get("Process") or cmdline.get("process") or "unknown"

        return ParsedEvent(
            id=str(uuid4()),
            timestamp=datetime.now(UTC),
            message=f"Command line: {args[:200]}{'...' if len(str(args)) > 200 else ''}",
            source="volatility3",
            raw_data=cmdline,
            normalized={
                "event": {
                    "kind": "event",
                    "category": ["process"],
                    "type": ["info"],
                    "action": "memory_cmdline_enumeration",
                    "module": "volatility3",
                    "dataset": f"volatility3.{os_type}.cmdline",
                },
                "process": {
                    "pid": pid,
                    "name": name,
                    "command_line": args,
                    "args": args.split() if isinstance(args, str) else args,
                },
                "host": {
                    "os": {
                        "type": os_type,
                    },
                },
                "eleanor": {
                    "case_id": case_id,
                    "evidence_id": evidence_id,
                    "parser": "memory",
                    "artifact_type": "command_line",
                },
            },
            case_id=case_id,
            evidence_id=evidence_id,
        )

    def _dll_to_event(
        self,
        dll: dict[str, Any],
        os_type: str,
        case_id: str | None,
        evidence_id: str | None,
    ) -> ParsedEvent:
        """Convert DLL info to ECS event."""
        pid = dll.get("PID") or dll.get("pid")
        name = dll.get("Name") or dll.get("name") or "unknown"
        path = dll.get("Path") or dll.get("path") or name
        base = dll.get("Base") or dll.get("base")
        size = dll.get("Size") or dll.get("size")

        return ParsedEvent(
            id=str(uuid4()),
            timestamp=datetime.now(UTC),
            message=f"Loaded DLL: {path}",
            source="volatility3",
            raw_data=dll,
            normalized={
                "event": {
                    "kind": "event",
                    "category": ["process"],
                    "type": ["info"],
                    "action": "memory_dll_enumeration",
                    "module": "volatility3",
                    "dataset": f"volatility3.{os_type}.dlllist",
                },
                "process": {
                    "pid": pid,
                },
                "dll": {
                    "name": name,
                    "path": path,
                },
                "file": {
                    "name": name,
                    "path": path,
                },
                "host": {
                    "os": {
                        "type": os_type,
                    },
                },
                "eleanor": {
                    "case_id": case_id,
                    "evidence_id": evidence_id,
                    "parser": "memory",
                    "artifact_type": "loaded_dll",
                    "memory_base": base,
                    "memory_size": size,
                },
            },
            case_id=case_id,
            evidence_id=evidence_id,
        )

    def _network_to_event(
        self,
        conn: dict[str, Any],
        os_type: str,
        case_id: str | None,
        evidence_id: str | None,
    ) -> ParsedEvent:
        """Convert network connection to ECS event."""
        # Handle various field naming conventions
        local_addr = conn.get("LocalAddr") or conn.get("local_addr") or conn.get("LocalIp") or "*"
        local_port = conn.get("LocalPort") or conn.get("local_port") or 0
        remote_addr = conn.get("ForeignAddr") or conn.get("remote_addr") or conn.get("ForeignIp") or "*"
        remote_port = conn.get("ForeignPort") or conn.get("remote_port") or 0
        state = conn.get("State") or conn.get("state") or "UNKNOWN"
        proto = conn.get("Proto") or conn.get("protocol") or "tcp"
        pid = conn.get("PID") or conn.get("pid") or conn.get("Owner") or 0

        return ParsedEvent(
            id=str(uuid4()),
            timestamp=datetime.now(UTC),
            message=f"Network: {local_addr}:{local_port} -> {remote_addr}:{remote_port} ({state})",
            source="volatility3",
            raw_data=conn,
            normalized={
                "event": {
                    "kind": "event",
                    "category": ["network"],
                    "type": ["connection", "info"],
                    "action": "memory_network_enumeration",
                    "module": "volatility3",
                    "dataset": f"volatility3.{os_type}.netscan",
                },
                "source": {
                    "ip": local_addr if local_addr != "*" else None,
                    "port": int(local_port) if local_port else None,
                },
                "destination": {
                    "ip": remote_addr if remote_addr != "*" else None,
                    "port": int(remote_port) if remote_port else None,
                },
                "network": {
                    "transport": proto.lower(),
                    "type": "ipv4",
                },
                "process": {
                    "pid": pid,
                },
                "host": {
                    "os": {
                        "type": os_type,
                    },
                },
                "eleanor": {
                    "case_id": case_id,
                    "evidence_id": evidence_id,
                    "parser": "memory",
                    "artifact_type": "network_connection",
                    "connection_state": state,
                },
            },
            case_id=case_id,
            evidence_id=evidence_id,
        )

    def _malfind_to_event(
        self,
        mal: dict[str, Any],
        os_type: str,
        case_id: str | None,
        evidence_id: str | None,
    ) -> ParsedEvent:
        """Convert malfind result to ECS event (high priority - potential malware)."""
        pid = mal.get("PID") or mal.get("pid")
        name = mal.get("Process") or mal.get("process") or "unknown"
        address = mal.get("Start") or mal.get("start") or mal.get("VPN") or 0
        protection = mal.get("Protection") or mal.get("protection") or "unknown"
        disasm = mal.get("Disasm") or mal.get("disasm") or ""
        hexdump = mal.get("Hexdump") or mal.get("hexdump") or ""

        return ParsedEvent(
            id=str(uuid4()),
            timestamp=datetime.now(UTC),
            message=f"Suspicious memory region in {name} (PID: {pid}) at {hex(address) if isinstance(address, int) else address}",
            source="volatility3",
            raw_data=mal,
            normalized={
                "event": {
                    "kind": "alert",
                    "category": ["malware", "intrusion_detection"],
                    "type": ["indicator"],
                    "action": "memory_suspicious_region",
                    "module": "volatility3",
                    "dataset": f"volatility3.{os_type}.malfind",
                    "risk_score": 75,
                    "severity": 3,
                },
                "process": {
                    "pid": pid,
                    "name": name,
                },
                "threat": {
                    "indicator": {
                        "type": "memory_region",
                        "description": f"Suspicious executable memory at {hex(address) if isinstance(address, int) else address}",
                    },
                    "technique": {
                        "id": "T1055",
                        "name": "Process Injection",
                    },
                },
                "host": {
                    "os": {
                        "type": os_type,
                    },
                },
                "eleanor": {
                    "case_id": case_id,
                    "evidence_id": evidence_id,
                    "parser": "memory",
                    "artifact_type": "suspicious_memory",
                    "memory_address": hex(address) if isinstance(address, int) else str(address),
                    "memory_protection": protection,
                    "disassembly": disasm[:500] if disasm else None,
                    "hexdump": hexdump[:500] if hexdump else None,
                },
            },
            case_id=case_id,
            evidence_id=evidence_id,
        )

    def _handle_to_event(
        self,
        handle: dict[str, Any],
        os_type: str,
        case_id: str | None,
        evidence_id: str | None,
    ) -> ParsedEvent:
        """Convert handle info to ECS event."""
        pid = handle.get("PID") or handle.get("pid")
        handle_type = handle.get("Type") or handle.get("type") or "unknown"
        name = handle.get("Name") or handle.get("name") or handle.get("HandleValue") or "unnamed"

        return ParsedEvent(
            id=str(uuid4()),
            timestamp=datetime.now(UTC),
            message=f"Handle: {handle_type} - {name}",
            source="volatility3",
            raw_data=handle,
            normalized={
                "event": {
                    "kind": "event",
                    "category": ["process", "file"],
                    "type": ["info"],
                    "action": "memory_handle_enumeration",
                    "module": "volatility3",
                    "dataset": f"volatility3.{os_type}.handles",
                },
                "process": {
                    "pid": pid,
                },
                "file": {
                    "path": name if handle_type == "File" else None,
                },
                "registry": {
                    "path": name if handle_type == "Key" else None,
                },
                "host": {
                    "os": {
                        "type": os_type,
                    },
                },
                "eleanor": {
                    "case_id": case_id,
                    "evidence_id": evidence_id,
                    "parser": "memory",
                    "artifact_type": "handle",
                    "handle_type": handle_type,
                    "handle_name": name,
                },
            },
            case_id=case_id,
            evidence_id=evidence_id,
        )

    def _service_to_event(
        self,
        svc: dict[str, Any],
        os_type: str,
        case_id: str | None,
        evidence_id: str | None,
    ) -> ParsedEvent:
        """Convert Windows service info to ECS event."""
        name = svc.get("Name") or svc.get("name") or "unknown"
        display = svc.get("Display") or svc.get("display") or name
        state = svc.get("State") or svc.get("state") or "unknown"
        binary = svc.get("Binary") or svc.get("binary") or ""
        start_type = svc.get("Start") or svc.get("start") or "unknown"

        return ParsedEvent(
            id=str(uuid4()),
            timestamp=datetime.now(UTC),
            message=f"Service: {name} ({state})",
            source="volatility3",
            raw_data=svc,
            normalized={
                "event": {
                    "kind": "event",
                    "category": ["process"],
                    "type": ["info"],
                    "action": "memory_service_enumeration",
                    "module": "volatility3",
                    "dataset": f"volatility3.{os_type}.svcscan",
                },
                "service": {
                    "name": name,
                    "state": state.lower() if isinstance(state, str) else state,
                },
                "process": {
                    "executable": binary,
                },
                "host": {
                    "os": {
                        "type": os_type,
                    },
                },
                "eleanor": {
                    "case_id": case_id,
                    "evidence_id": evidence_id,
                    "parser": "memory",
                    "artifact_type": "service",
                    "service_display_name": display,
                    "service_start_type": start_type,
                    "service_binary": binary,
                },
            },
            case_id=case_id,
            evidence_id=evidence_id,
        )

    def _driver_to_event(
        self,
        drv: dict[str, Any],
        os_type: str,
        case_id: str | None,
        evidence_id: str | None,
    ) -> ParsedEvent:
        """Convert Windows driver info to ECS event."""
        name = drv.get("Name") or drv.get("name") or "unknown"
        path = drv.get("DriverName") or drv.get("driver_name") or name
        base = drv.get("Start") or drv.get("start") or drv.get("Base") or 0
        size = drv.get("Size") or drv.get("size") or 0

        return ParsedEvent(
            id=str(uuid4()),
            timestamp=datetime.now(UTC),
            message=f"Driver: {name}",
            source="volatility3",
            raw_data=drv,
            normalized={
                "event": {
                    "kind": "event",
                    "category": ["driver"],
                    "type": ["info"],
                    "action": "memory_driver_enumeration",
                    "module": "volatility3",
                    "dataset": f"volatility3.{os_type}.driverscan",
                },
                "file": {
                    "name": name,
                    "path": path,
                },
                "host": {
                    "os": {
                        "type": os_type,
                    },
                },
                "eleanor": {
                    "case_id": case_id,
                    "evidence_id": evidence_id,
                    "parser": "memory",
                    "artifact_type": "driver",
                    "driver_base": hex(base) if isinstance(base, int) else str(base),
                    "driver_size": size,
                },
            },
            case_id=case_id,
            evidence_id=evidence_id,
        )

    def _bash_to_event(
        self,
        cmd: dict[str, Any],
        case_id: str | None,
        evidence_id: str | None,
    ) -> ParsedEvent:
        """Convert bash history entry to ECS event."""
        pid = cmd.get("PID") or cmd.get("pid")
        name = cmd.get("Process") or cmd.get("process") or cmd.get("Name") or "bash"
        command = cmd.get("Command") or cmd.get("command") or ""
        timestamp_val = cmd.get("Timestamp") or cmd.get("timestamp")

        timestamp = datetime.now(UTC)
        if timestamp_val:
            try:
                if isinstance(timestamp_val, (int, float)):
                    timestamp = datetime.fromtimestamp(timestamp_val, tz=UTC)
                elif isinstance(timestamp_val, str):
                    timestamp = datetime.fromisoformat(timestamp_val.replace("Z", "+00:00"))
            except Exception:
                pass

        return ParsedEvent(
            id=str(uuid4()),
            timestamp=timestamp,
            message=f"Bash command: {command[:200]}{'...' if len(str(command)) > 200 else ''}",
            source="volatility3",
            raw_data=cmd,
            normalized={
                "event": {
                    "kind": "event",
                    "category": ["process"],
                    "type": ["info"],
                    "action": "memory_bash_history",
                    "module": "volatility3",
                    "dataset": "volatility3.linux.bash",
                },
                "process": {
                    "pid": pid,
                    "name": name,
                    "command_line": command,
                },
                "user": {
                    "name": cmd.get("User") or cmd.get("user"),
                },
                "host": {
                    "os": {
                        "type": "linux",
                    },
                },
                "eleanor": {
                    "case_id": case_id,
                    "evidence_id": evidence_id,
                    "parser": "memory",
                    "artifact_type": "bash_history",
                },
            },
            case_id=case_id,
            evidence_id=evidence_id,
        )

    def _lsof_to_event(
        self,
        fd: dict[str, Any],
        case_id: str | None,
        evidence_id: str | None,
    ) -> ParsedEvent:
        """Convert lsof entry to ECS event."""
        pid = fd.get("PID") or fd.get("pid")
        name = fd.get("Process") or fd.get("process") or fd.get("COMM") or "unknown"
        fd_num = fd.get("FD") or fd.get("fd")
        path = fd.get("Path") or fd.get("path") or fd.get("Name") or ""

        return ParsedEvent(
            id=str(uuid4()),
            timestamp=datetime.now(UTC),
            message=f"Open file: {path}",
            source="volatility3",
            raw_data=fd,
            normalized={
                "event": {
                    "kind": "event",
                    "category": ["file", "process"],
                    "type": ["info"],
                    "action": "memory_open_file",
                    "module": "volatility3",
                    "dataset": "volatility3.linux.lsof",
                },
                "process": {
                    "pid": pid,
                    "name": name,
                },
                "file": {
                    "path": path,
                },
                "host": {
                    "os": {
                        "type": "linux",
                    },
                },
                "eleanor": {
                    "case_id": case_id,
                    "evidence_id": evidence_id,
                    "parser": "memory",
                    "artifact_type": "open_file",
                    "file_descriptor": fd_num,
                },
            },
            case_id=case_id,
            evidence_id=evidence_id,
        )

    def _module_to_event(
        self,
        mod: dict[str, Any],
        os_type: str,
        case_id: str | None,
        evidence_id: str | None,
    ) -> ParsedEvent:
        """Convert kernel module info to ECS event."""
        name = mod.get("Name") or mod.get("name") or "unknown"
        size = mod.get("Size") or mod.get("size") or 0
        offset = mod.get("Offset") or mod.get("offset") or 0

        return ParsedEvent(
            id=str(uuid4()),
            timestamp=datetime.now(UTC),
            message=f"Kernel module: {name}",
            source="volatility3",
            raw_data=mod,
            normalized={
                "event": {
                    "kind": "event",
                    "category": ["driver"],
                    "type": ["info"],
                    "action": "memory_kernel_module",
                    "module": "volatility3",
                    "dataset": f"volatility3.{os_type}.lsmod",
                },
                "file": {
                    "name": name,
                },
                "host": {
                    "os": {
                        "type": os_type,
                    },
                },
                "eleanor": {
                    "case_id": case_id,
                    "evidence_id": evidence_id,
                    "parser": "memory",
                    "artifact_type": "kernel_module",
                    "module_size": size,
                    "module_offset": hex(offset) if isinstance(offset, int) else str(offset),
                },
            },
            case_id=case_id,
            evidence_id=evidence_id,
        )
