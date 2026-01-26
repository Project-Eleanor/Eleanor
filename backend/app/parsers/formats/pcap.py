"""PCAP network capture parser.

Parses PCAP and PCAPNG network capture files to extract connection metadata.
Uses scapy for packet parsing.
"""

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, BinaryIO, Iterator

from app.parsers.base import BaseParser, ParsedEvent, ParserCategory
from app.parsers.registry import register_parser

logger = logging.getLogger(__name__)

# PCAP magic numbers
PCAP_MAGIC_LE = b"\xd4\xc3\xb2\xa1"  # Little endian
PCAP_MAGIC_BE = b"\xa1\xb2\xc3\xd4"  # Big endian
PCAP_MAGIC_NS_LE = b"\x4d\x3c\xb2\xa1"  # Nanosecond little endian
PCAP_MAGIC_NS_BE = b"\xa1\xb2\x3c\x4d"  # Nanosecond big endian
PCAPNG_MAGIC = b"\x0a\x0d\x0d\x0a"  # PCAPNG section header


@register_parser
class PcapParser(BaseParser):
    """Parser for PCAP and PCAPNG network capture files."""

    @property
    def name(self) -> str:
        return "pcap"

    @property
    def category(self) -> ParserCategory:
        return ParserCategory.NETWORK

    @property
    def description(self) -> str:
        return "PCAP/PCAPNG network capture metadata parser"

    @property
    def supported_extensions(self) -> list[str]:
        return [".pcap", ".pcapng", ".cap"]

    @property
    def supported_mime_types(self) -> list[str]:
        return [
            "application/vnd.tcpdump.pcap",
            "application/x-pcap",
            "application/pcap",
            "application/x-pcapng",
        ]

    def can_parse(self, file_path: Path | None = None, content: bytes | None = None) -> bool:
        """Check for PCAP/PCAPNG magic bytes."""
        if content and len(content) >= 4:
            if content[:4] in (PCAP_MAGIC_LE, PCAP_MAGIC_BE, PCAP_MAGIC_NS_LE, PCAP_MAGIC_NS_BE):
                return True
            if content[:4] == PCAPNG_MAGIC:
                return True

        if file_path:
            if file_path.suffix.lower() in (".pcap", ".pcapng", ".cap"):
                return True

        return False

    def parse(
        self,
        source: Path | BinaryIO,
        source_name: str | None = None,
    ) -> Iterator[ParsedEvent]:
        """Parse PCAP file and yield network events."""
        source_str = source_name or (str(source) if isinstance(source, Path) else "stream")

        try:
            from scapy.all import rdpcap, IP, TCP, UDP, DNS, ICMP, Ether

            # Read packets
            if isinstance(source, Path):
                packets = rdpcap(str(source))
            else:
                # Save to temp file for scapy
                import tempfile
                with tempfile.NamedTemporaryFile(suffix=".pcap", delete=False) as tmp:
                    tmp.write(source.read())
                    tmp_path = tmp.name
                try:
                    packets = rdpcap(tmp_path)
                finally:
                    Path(tmp_path).unlink(missing_ok=True)

            logger.info(f"Parsing {len(packets)} packets from {source_str}")

            # Track connections for aggregation
            connections = {}

            for pkt_num, pkt in enumerate(packets, 1):
                try:
                    event = self._parse_packet(pkt, source_str, pkt_num, connections)
                    if event:
                        yield event
                except Exception as e:
                    logger.debug(f"Failed to parse packet {pkt_num}: {e}")
                    continue

            # Yield connection summary events
            for conn_key, conn_info in connections.items():
                yield self._create_connection_summary(conn_info, source_str)

        except ImportError:
            logger.error("scapy not installed. Install with: pip install scapy")
            raise
        except Exception as e:
            logger.error(f"Failed to parse PCAP {source_str}: {e}")
            raise

    def _parse_packet(
        self,
        pkt,
        source_name: str,
        pkt_num: int,
        connections: dict,
    ) -> ParsedEvent | None:
        """Parse a single packet."""
        from scapy.all import IP, TCP, UDP, DNS, ICMP, HTTP, Raw

        # Get timestamp
        timestamp = datetime.fromtimestamp(float(pkt.time), tz=timezone.utc)

        # Skip non-IP packets for now
        if not pkt.haslayer(IP):
            return None

        ip_layer = pkt[IP]
        src_ip = ip_layer.src
        dst_ip = ip_layer.dst

        # Get transport layer info
        protocol = "ip"
        src_port = None
        dst_port = None

        if pkt.haslayer(TCP):
            protocol = "tcp"
            tcp_layer = pkt[TCP]
            src_port = tcp_layer.sport
            dst_port = tcp_layer.dport

            # Track TCP connections
            conn_key = self._get_connection_key(src_ip, src_port, dst_ip, dst_port)
            self._update_connection(connections, conn_key, pkt, timestamp)

        elif pkt.haslayer(UDP):
            protocol = "udp"
            udp_layer = pkt[UDP]
            src_port = udp_layer.sport
            dst_port = udp_layer.dport

        elif pkt.haslayer(ICMP):
            protocol = "icmp"

        # Determine if this is a significant packet to report
        # (SYN, DNS, HTTP, etc.)
        is_significant = False
        event_action = "packet"
        message = f"Network packet: {src_ip} -> {dst_ip}"
        raw = {
            "packet_number": pkt_num,
            "length": len(pkt),
        }

        # Check for DNS
        if pkt.haslayer(DNS):
            is_significant = True
            dns = pkt[DNS]
            if dns.qr == 0:  # Query
                event_action = "dns_query"
                if dns.qd:
                    query_name = dns.qd.qname.decode() if isinstance(dns.qd.qname, bytes) else str(dns.qd.qname)
                    message = f"DNS query: {query_name}"
                    raw["dns_query"] = query_name
            else:  # Response
                event_action = "dns_response"
                answers = []
                for i in range(dns.ancount):
                    try:
                        if hasattr(dns.an[i], "rdata"):
                            answers.append(str(dns.an[i].rdata))
                    except Exception:
                        pass
                message = f"DNS response: {len(answers)} answers"
                raw["dns_answers"] = answers[:10]

        # Check for TCP connection establishment
        elif pkt.haslayer(TCP):
            tcp_flags = pkt[TCP].flags
            if tcp_flags == "S":  # SYN
                is_significant = True
                event_action = "tcp_connection_start"
                message = f"TCP SYN: {src_ip}:{src_port} -> {dst_ip}:{dst_port}"
            elif tcp_flags == "SA":  # SYN-ACK
                is_significant = True
                event_action = "tcp_connection_accept"
                message = f"TCP SYN-ACK: {src_ip}:{src_port} -> {dst_ip}:{dst_port}"
            elif tcp_flags == "F" or tcp_flags == "FA":  # FIN
                is_significant = True
                event_action = "tcp_connection_end"
                message = f"TCP FIN: {src_ip}:{src_port} -> {dst_ip}:{dst_port}"
            elif tcp_flags == "R" or tcp_flags == "RA":  # RST
                is_significant = True
                event_action = "tcp_connection_reset"
                message = f"TCP RST: {src_ip}:{src_port} -> {dst_ip}:{dst_port}"

        # Check for HTTP (basic detection)
        if pkt.haslayer(Raw):
            payload = bytes(pkt[Raw].load)
            if payload[:4] in (b"GET ", b"POST", b"PUT ", b"HEAD", b"DELE", b"HTTP"):
                is_significant = True
                event_action = "http_request" if not payload.startswith(b"HTTP") else "http_response"
                try:
                    first_line = payload.split(b"\r\n")[0].decode("utf-8", errors="ignore")
                    message = f"HTTP: {first_line[:100]}"
                    raw["http_first_line"] = first_line
                except Exception:
                    message = f"HTTP traffic: {src_ip}:{src_port} -> {dst_ip}:{dst_port}"

        # Only return event for significant packets
        if not is_significant:
            return None

        # Determine network direction
        direction = None
        # Basic heuristic: if dst port is a well-known service, it's outbound
        if dst_port and dst_port < 1024:
            direction = "outbound"
        elif src_port and src_port < 1024:
            direction = "inbound"

        # Add well-known port info
        port_service = self._get_service_name(dst_port or src_port)
        if port_service:
            raw["service"] = port_service

        return ParsedEvent(
            timestamp=timestamp,
            message=message,
            source_type="pcap",
            source_file=source_name,
            source_line=pkt_num,
            event_kind="event",
            event_category=["network"],
            event_type=["connection", "info"],
            event_action=event_action,
            source_ip=src_ip,
            source_port=src_port,
            destination_ip=dst_ip,
            destination_port=dst_port,
            network_protocol=protocol,
            network_direction=direction,
            raw=raw,
            labels={
                "protocol": protocol,
                "service": port_service or "",
            },
            tags=["network", "pcap"],
        )

    def _get_connection_key(self, src_ip: str, src_port: int, dst_ip: str, dst_port: int) -> str:
        """Create a unique key for a TCP connection."""
        # Sort to handle bidirectional traffic
        endpoints = sorted([(src_ip, src_port), (dst_ip, dst_port)])
        return f"{endpoints[0][0]}:{endpoints[0][1]}-{endpoints[1][0]}:{endpoints[1][1]}"

    def _update_connection(self, connections: dict, key: str, pkt, timestamp: datetime) -> None:
        """Update connection tracking info."""
        from scapy.all import IP, TCP

        if key not in connections:
            connections[key] = {
                "key": key,
                "src_ip": pkt[IP].src,
                "src_port": pkt[TCP].sport,
                "dst_ip": pkt[IP].dst,
                "dst_port": pkt[TCP].dport,
                "first_seen": timestamp,
                "last_seen": timestamp,
                "packet_count": 0,
                "bytes_total": 0,
            }

        conn = connections[key]
        conn["last_seen"] = timestamp
        conn["packet_count"] += 1
        conn["bytes_total"] += len(pkt)

    def _create_connection_summary(self, conn_info: dict, source_name: str) -> ParsedEvent:
        """Create a summary event for a connection."""
        duration = (conn_info["last_seen"] - conn_info["first_seen"]).total_seconds()

        message = (
            f"TCP connection: {conn_info['src_ip']}:{conn_info['src_port']} -> "
            f"{conn_info['dst_ip']}:{conn_info['dst_port']} "
            f"({conn_info['packet_count']} packets, {conn_info['bytes_total']} bytes)"
        )

        service = self._get_service_name(conn_info["dst_port"])

        return ParsedEvent(
            timestamp=conn_info["first_seen"],
            message=message,
            source_type="pcap",
            source_file=source_name,
            event_kind="event",
            event_category=["network"],
            event_type=["connection", "info"],
            event_action="tcp_connection_summary",
            source_ip=conn_info["src_ip"],
            source_port=conn_info["src_port"],
            destination_ip=conn_info["dst_ip"],
            destination_port=conn_info["dst_port"],
            network_protocol="tcp",
            raw={
                "duration_seconds": duration,
                "packet_count": conn_info["packet_count"],
                "bytes_total": conn_info["bytes_total"],
                "first_seen": str(conn_info["first_seen"]),
                "last_seen": str(conn_info["last_seen"]),
            },
            labels={
                "protocol": "tcp",
                "service": service or "",
                "event_type": "connection_summary",
            },
            tags=["network", "pcap", "connection_summary"],
        )

    def _get_service_name(self, port: int | None) -> str | None:
        """Get well-known service name for port."""
        if not port:
            return None

        services = {
            20: "ftp-data",
            21: "ftp",
            22: "ssh",
            23: "telnet",
            25: "smtp",
            53: "dns",
            80: "http",
            110: "pop3",
            143: "imap",
            443: "https",
            445: "smb",
            993: "imaps",
            995: "pop3s",
            1433: "mssql",
            1521: "oracle",
            3306: "mysql",
            3389: "rdp",
            5432: "postgresql",
            5900: "vnc",
            6379: "redis",
            8080: "http-proxy",
            8443: "https-alt",
            27017: "mongodb",
        }

        return services.get(port)
