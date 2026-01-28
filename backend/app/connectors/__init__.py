"""Data connectors for streaming log ingestion.

Connectors handle the transport layer for getting logs into Eleanor,
supporting various protocols and cloud platforms.
"""

from app.connectors.base import BaseConnector, ConnectorConfig, ConnectorMetrics

__all__ = [
    "BaseConnector",
    "ConnectorConfig",
    "ConnectorMetrics",
]
