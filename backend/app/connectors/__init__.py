"""Data connectors for streaming log ingestion.

Connectors handle the transport layer for getting logs into Eleanor,
supporting various protocols and cloud platforms.
"""

from app.connectors.aws_securityhub import AWSSecurityHubConnector
from app.connectors.azure_eventhub import AzureEventHubConnector
from app.connectors.base import (
    BaseConnector,
    ConnectorConfig,
    ConnectorMetrics,
    PollingConnector,
    RawEvent,
    StreamingConnector,
)
from app.connectors.fluentd import FluentdConnector
from app.connectors.gcp import GCPCloudLoggingConnector
from app.connectors.wef import WEFConnector

__all__ = [
    # Base classes
    "BaseConnector",
    "ConnectorConfig",
    "ConnectorMetrics",
    "PollingConnector",
    "RawEvent",
    "StreamingConnector",
    # Implementations
    "AWSSecurityHubConnector",
    "AzureEventHubConnector",
    "FluentdConnector",
    "GCPCloudLoggingConnector",
    "WEFConnector",
]
