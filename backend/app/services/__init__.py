"""Eleanor services package.

Contains business logic services for:
- Detection engine: Rule execution and scheduling
- Alert generator: Alert creation from rule matches
"""

from app.services.alert_generator import AlertGenerator, get_alert_generator
from app.services.detection_engine import DetectionEngine, get_detection_engine

__all__ = [
    "DetectionEngine",
    "get_detection_engine",
    "AlertGenerator",
    "get_alert_generator",
]
