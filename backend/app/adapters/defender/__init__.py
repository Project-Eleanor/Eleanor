"""Microsoft Defender for Endpoint adapter for Eleanor.

Provides integration with Microsoft Defender for Endpoint for:
- Device inventory and management
- Alert retrieval and management
- Response actions (isolation, antivirus scan, investigation package)
- Live response capabilities
"""

from app.adapters.defender.adapter import DefenderAdapter
from app.adapters.defender.schemas import (
    DefenderAlert,
    DefenderDevice,
    DefenderAction,
    DefenderInvestigation,
)

__all__ = [
    "DefenderAdapter",
    "DefenderAlert",
    "DefenderDevice",
    "DefenderAction",
    "DefenderInvestigation",
]
