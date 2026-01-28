"""Windows Event Forwarding (WEF) connector.

PATTERN: Observer Pattern (via StreamingConnector)
Receives Windows events from WEF collector endpoints.

Provides:
- WinRM listener for forwarded events
- Event parsing and normalization
- Subscription management
"""

import asyncio
import logging
import xml.etree.ElementTree as ET
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.connectors.base import (
    ConnectorConfig,
    ConnectorMetrics,
    RawEvent,
    StreamingConnector,
)

logger = logging.getLogger(__name__)


@dataclass
class WEFConfig(ConnectorConfig):
    """Windows Event Forwarding connector configuration.

    PATTERN: Configuration Object
    Extends base ConnectorConfig with WEF-specific settings.
    """

    # Listener settings
    host: str = "0.0.0.0"
    port: int = 5985  # WinRM HTTP port
    use_https: bool = False
    https_port: int = 5986

    # Authentication
    username: str = ""
    password: str = ""
    certificate_path: str = ""
    certificate_key_path: str = ""

    # Subscriptions
    subscription_ids: list[str] = field(default_factory=list)

    # Processing
    max_batch_size: int = 100


class WEFConnector(StreamingConnector):
    """Windows Event Forwarding collector connector.

    PATTERN: Observer Pattern
    Receives forwarded Windows events from WEF-enabled hosts.

    Configuration:
        host: Listener bind address
        port: WinRM listener port
        use_https: Enable HTTPS
        username: Authentication username
        password: Authentication password

    DESIGN DECISION: Implements a WinRM listener endpoint that
    Windows clients can connect to for event forwarding.
    For production, consider using a dedicated WEF collector.
    """

    name = "wef"
    description = "Windows Event Forwarding collector"

    def __init__(self, config: WEFConfig):
        """Initialize WEF connector.

        Args:
            config: WEF connector configuration
        """
        super().__init__(config)
        self.wef_config = config

        self._server = None
        self._event_queue: asyncio.Queue[RawEvent] = asyncio.Queue(maxsize=10000)
        self._running = False
        self._metrics = ConnectorMetrics(connector_name=self.name)
        self._subscriptions: dict[str, dict[str, Any]] = {}

    async def connect(self) -> bool:
        """Start WEF listener."""
        try:
            from aiohttp import web

            app = web.Application()
            app.router.add_post("/wsman", self._handle_wsman)
            app.router.add_post("/wsman/subscriptions/{subscription_id}", self._handle_subscription)

            runner = web.AppRunner(app)
            await runner.setup()

            if self.wef_config.use_https:
                import ssl

                ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
                ssl_context.load_cert_chain(
                    self.wef_config.certificate_path,
                    self.wef_config.certificate_key_path,
                )

                site = web.TCPSite(
                    runner,
                    self.wef_config.host,
                    self.wef_config.https_port,
                    ssl_context=ssl_context,
                )
            else:
                site = web.TCPSite(
                    runner,
                    self.wef_config.host,
                    self.wef_config.port,
                )

            await site.start()

            self._running = True
            self._connected = True

            port = self.wef_config.https_port if self.wef_config.use_https else self.wef_config.port
            logger.info(
                f"WEF connector listening on {self.wef_config.host}:{port}",
                extra={"https": self.wef_config.use_https},
            )
            return True

        except Exception as error:
            logger.error(f"Failed to start WEF connector: {error}")
            return False

    async def disconnect(self) -> None:
        """Stop WEF listener."""
        self._running = False

        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

        self._connected = False
        logger.info("WEF connector stopped")

    async def stream(self) -> AsyncIterator[RawEvent]:
        """Stream events from WEF."""
        while self._running:
            try:
                event = await asyncio.wait_for(
                    self._event_queue.get(),
                    timeout=1.0,
                )
                self._metrics.events_received += 1
                yield event
            except TimeoutError:
                continue
            except Exception as error:
                logger.error(f"Error streaming WEF event: {error}")
                self._metrics.errors += 1

    async def get_metrics(self) -> ConnectorMetrics:
        """Get connector metrics."""
        self._metrics.queue_size = self._event_queue.qsize()
        return self._metrics

    async def _handle_wsman(self, request) -> Any:
        """Handle WS-Management requests.

        This handles the SOAP envelope format used by WinRM/WEF.
        """
        from aiohttp import web

        try:
            # Verify authentication if configured
            if self.wef_config.username:
                auth_header = request.headers.get("Authorization", "")
                if not self._verify_auth(auth_header):
                    return web.Response(status=401)

            body = await request.text()

            # Parse SOAP envelope
            events = self._parse_soap_envelope(body)

            for event_data in events:
                await self._enqueue_event(event_data)

            # Return success response
            return web.Response(
                text=self._create_soap_response(),
                content_type="application/soap+xml",
            )

        except Exception as error:
            logger.error(f"Error handling WS-Management request: {error}")
            self._metrics.errors += 1
            return web.Response(status=500, text=str(error))

    async def _handle_subscription(self, request) -> Any:
        """Handle subscription delivery."""
        from aiohttp import web

        subscription_id = request.match_info.get("subscription_id", "")

        try:
            body = await request.text()
            events = self._parse_subscription_events(body)

            for event_data in events:
                event_data["_subscription_id"] = subscription_id
                await self._enqueue_event(event_data)

            return web.Response(status=200)

        except Exception as error:
            logger.error(f"Error handling subscription {subscription_id}: {error}")
            self._metrics.errors += 1
            return web.Response(status=500, text=str(error))

    def _verify_auth(self, auth_header: str) -> bool:
        """Verify Basic/NTLM authentication.

        DESIGN DECISION: Supports Basic auth for simplicity.
        For production, use certificate-based or Kerberos auth.
        """
        if not auth_header:
            return False

        if auth_header.startswith("Basic "):
            import base64

            try:
                credentials = base64.b64decode(auth_header[6:]).decode()
                username, password = credentials.split(":", 1)
                return username == self.wef_config.username and password == self.wef_config.password
            except Exception:
                return False

        return False

    def _parse_soap_envelope(self, body: str) -> list[dict[str, Any]]:
        """Parse SOAP envelope containing events.

        WEF uses WS-Management protocol with SOAP envelope format.

        Args:
            body: Raw SOAP XML

        Returns:
            List of parsed event dictionaries
        """
        events = []

        try:
            # Parse XML
            root = ET.fromstring(body)

            # Define namespaces
            namespaces = {
                "s": "http://www.w3.org/2003/05/soap-envelope",
                "a": "http://schemas.xmlsoap.org/ws/2004/08/addressing",
                "e": "http://schemas.microsoft.com/wbem/wsman/1/windows/shell",
                "w": "http://schemas.dmtf.org/wbem/wsman/1/wsman.xsd",
            }

            # Find events in body
            body_element = root.find(".//s:Body", namespaces)
            if body_element is None:
                return events

            # Look for event elements
            for event_element in body_element.iter():
                if "Event" in event_element.tag:
                    event_data = self._parse_windows_event(event_element)
                    if event_data:
                        events.append(event_data)

        except ET.ParseError as error:
            logger.warning(f"Failed to parse SOAP envelope: {error}")

        return events

    def _parse_subscription_events(self, body: str) -> list[dict[str, Any]]:
        """Parse events from subscription delivery.

        Args:
            body: Raw XML body

        Returns:
            List of parsed events
        """
        events = []

        try:
            root = ET.fromstring(body)

            # Find all Event elements
            for event_element in root.iter():
                if "Event" in event_element.tag:
                    event_data = self._parse_windows_event(event_element)
                    if event_data:
                        events.append(event_data)

        except ET.ParseError as error:
            logger.warning(f"Failed to parse subscription events: {error}")

        return events

    def _parse_windows_event(self, element: ET.Element) -> dict[str, Any] | None:
        """Parse a Windows Event XML element.

        Args:
            element: XML Event element

        Returns:
            Parsed event dictionary
        """
        try:
            # Extract raw XML
            raw_xml = ET.tostring(element, encoding="unicode")

            event = {
                "_raw_xml": raw_xml,
            }

            # Parse System section
            system = element.find(
                ".//{http://schemas.microsoft.com/win/2004/08/events/event}System"
            )
            if system is None:
                # Try without namespace
                system = element.find(".//System")

            if system is not None:
                event.update(self._parse_system_element(system))

            # Parse EventData section
            event_data = element.find(
                ".//{http://schemas.microsoft.com/win/2004/08/events/event}EventData"
            )
            if event_data is None:
                event_data = element.find(".//EventData")

            if event_data is not None:
                event["event_data"] = self._parse_event_data(event_data)

            # Parse UserData section
            user_data = element.find(
                ".//{http://schemas.microsoft.com/win/2004/08/events/event}UserData"
            )
            if user_data is None:
                user_data = element.find(".//UserData")

            if user_data is not None:
                event["user_data"] = self._parse_user_data(user_data)

            return event

        except Exception as error:
            logger.warning(f"Failed to parse Windows event: {error}")
            return None

    def _parse_system_element(self, system: ET.Element) -> dict[str, Any]:
        """Parse System element from Windows Event.

        Args:
            system: System XML element

        Returns:
            Parsed system data
        """
        result: dict[str, Any] = {}

        # Provider
        provider = system.find(".//{http://schemas.microsoft.com/win/2004/08/events/event}Provider")
        if provider is None:
            provider = system.find(".//Provider")
        if provider is not None:
            result["provider_name"] = provider.get("Name", "")
            result["provider_guid"] = provider.get("Guid", "")

        # Event ID
        event_id_element = system.find(
            ".//{http://schemas.microsoft.com/win/2004/08/events/event}EventID"
        )
        if event_id_element is None:
            event_id_element = system.find(".//EventID")
        if event_id_element is not None:
            result["event_id"] = int(event_id_element.text or 0)

        # Level
        level = system.find(".//{http://schemas.microsoft.com/win/2004/08/events/event}Level")
        if level is None:
            level = system.find(".//Level")
        if level is not None:
            result["level"] = int(level.text or 0)

        # Task
        task = system.find(".//{http://schemas.microsoft.com/win/2004/08/events/event}Task")
        if task is None:
            task = system.find(".//Task")
        if task is not None:
            result["task"] = int(task.text or 0)

        # Keywords
        keywords = system.find(".//{http://schemas.microsoft.com/win/2004/08/events/event}Keywords")
        if keywords is None:
            keywords = system.find(".//Keywords")
        if keywords is not None:
            result["keywords"] = keywords.text or ""

        # TimeCreated
        time_created = system.find(
            ".//{http://schemas.microsoft.com/win/2004/08/events/event}TimeCreated"
        )
        if time_created is None:
            time_created = system.find(".//TimeCreated")
        if time_created is not None:
            result["time_created"] = time_created.get("SystemTime", "")

        # Computer
        computer = system.find(".//{http://schemas.microsoft.com/win/2004/08/events/event}Computer")
        if computer is None:
            computer = system.find(".//Computer")
        if computer is not None:
            result["computer"] = computer.text or ""

        # Channel
        channel = system.find(".//{http://schemas.microsoft.com/win/2004/08/events/event}Channel")
        if channel is None:
            channel = system.find(".//Channel")
        if channel is not None:
            result["channel"] = channel.text or ""

        return result

    def _parse_event_data(self, event_data: ET.Element) -> dict[str, Any]:
        """Parse EventData section.

        Args:
            event_data: EventData XML element

        Returns:
            Parsed event data
        """
        result: dict[str, Any] = {}

        for data_element in event_data:
            name = data_element.get("Name", "")
            value = data_element.text or ""

            if name:
                result[name] = value
            else:
                # Binary data or unnamed
                if "Binary" in data_element.tag:
                    result["Binary"] = value
                else:
                    # Collect unnamed data elements
                    if "Data" not in result:
                        result["Data"] = []
                    result["Data"].append(value)

        return result

    def _parse_user_data(self, user_data: ET.Element) -> dict[str, Any]:
        """Parse UserData section.

        Args:
            user_data: UserData XML element

        Returns:
            Parsed user data
        """
        result: dict[str, Any] = {}

        # UserData can have various structures
        for child in user_data:
            tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag

            if len(child) > 0:
                # Nested element
                result[tag] = self._element_to_dict(child)
            else:
                result[tag] = child.text or ""

        return result

    def _element_to_dict(self, element: ET.Element) -> dict[str, Any]:
        """Convert XML element to dictionary.

        Args:
            element: XML element

        Returns:
            Dictionary representation
        """
        result: dict[str, Any] = dict(element.attrib)

        for child in element:
            tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag

            if len(child) > 0:
                result[tag] = self._element_to_dict(child)
            else:
                result[tag] = child.text or ""

        return result

    async def _enqueue_event(self, event_data: dict[str, Any]) -> None:
        """Enqueue an event for processing.

        Args:
            event_data: Parsed event dictionary
        """
        # Determine timestamp
        timestamp = datetime.now(UTC)
        if "time_created" in event_data:
            try:
                timestamp = datetime.fromisoformat(
                    event_data["time_created"].replace("Z", "+00:00")
                )
            except ValueError:
                pass

        # Create source identifier
        computer = event_data.get("computer", "unknown")
        channel = event_data.get("channel", "unknown")
        source = f"{computer}/{channel}"

        raw_event = RawEvent(
            timestamp=timestamp,
            data=event_data,
            source=source,
            source_type="wef",
            metadata={
                "connector": self.name,
                "computer": computer,
                "channel": channel,
                "event_id": event_data.get("event_id"),
                "provider_name": event_data.get("provider_name"),
            },
        )

        try:
            self._event_queue.put_nowait(raw_event)
        except asyncio.QueueFull:
            self._metrics.events_dropped += 1
            logger.warning("WEF event queue full, dropping event")

    def _create_soap_response(self) -> str:
        """Create SOAP response for successful event delivery.

        Returns:
            SOAP response XML
        """
        return """<?xml version="1.0" encoding="UTF-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope">
    <s:Body>
        <wsen:EnumerateResponse xmlns:wsen="http://schemas.xmlsoap.org/ws/2004/09/enumeration">
            <wsen:EnumerationContext/>
        </wsen:EnumerateResponse>
    </s:Body>
</s:Envelope>"""


# Factory function for creating connector from dict config
def create_wef_connector(config: dict[str, Any]) -> WEFConnector:
    """Create WEF connector from dictionary configuration.

    Args:
        config: Configuration dictionary

    Returns:
        Configured WEFConnector instance
    """
    connector_config = WEFConfig(
        name=config.get("name", "wef"),
        enabled=config.get("enabled", True),
        host=config.get("host", "0.0.0.0"),
        port=config.get("port", 5985),
        use_https=config.get("use_https", False),
        https_port=config.get("https_port", 5986),
        username=config.get("username", ""),
        password=config.get("password", ""),
        certificate_path=config.get("certificate_path", ""),
        certificate_key_path=config.get("certificate_key_path", ""),
        subscription_ids=config.get("subscription_ids", []),
        max_batch_size=config.get("max_batch_size", 100),
    )
    return WEFConnector(connector_config)
