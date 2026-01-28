"""Notification channels for Eleanor alerts and notifications."""

from app.notifications.channels.base import (
    DeliveryResult,
    DeliveryStatus,
    NotificationChannel,
    NotificationMessage,
    NotificationPriority,
)
from app.notifications.channels.slack import SlackChannel
from app.notifications.channels.teams import TeamsChannel

__all__ = [
    "NotificationChannel",
    "NotificationMessage",
    "NotificationPriority",
    "DeliveryResult",
    "DeliveryStatus",
    "SlackChannel",
    "TeamsChannel",
]
