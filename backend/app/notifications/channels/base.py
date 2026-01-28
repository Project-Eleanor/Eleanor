"""Base notification channel interface.

Defines the abstract interface for all notification delivery channels
(Slack, Teams, email, webhooks, etc.).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID


class NotificationPriority(str, Enum):
    """Priority levels for notifications."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class DeliveryStatus(str, Enum):
    """Status of notification delivery."""

    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    RATE_LIMITED = "rate_limited"
    INVALID_RECIPIENT = "invalid_recipient"


@dataclass
class NotificationMessage:
    """Message to be delivered via notification channel.

    Provides a channel-agnostic message format that can be
    rendered appropriately for each delivery channel.
    """

    # Core content
    title: str
    body: str

    # Optional rich content
    summary: str | None = None  # Short version for mobile/preview
    html_body: str | None = None  # HTML version if supported

    # Metadata
    priority: NotificationPriority = NotificationPriority.NORMAL
    category: str | None = None  # alert, case_update, workflow, etc.
    source: str = "eleanor"

    # Linking
    url: str | None = None  # Link to related resource
    case_id: UUID | None = None
    evidence_id: UUID | None = None

    # Attachments (for channels that support them)
    attachments: list[dict[str, Any]] = field(default_factory=list)

    # Custom fields for channel-specific formatting
    fields: dict[str, str] = field(default_factory=dict)

    # Color/severity indicator (hex color or severity name)
    color: str | None = None

    # Threading (for reply/update scenarios)
    thread_id: str | None = None
    reply_to: str | None = None

    # Timestamp override
    timestamp: datetime | None = None

    # Tags for filtering
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "title": self.title,
            "body": self.body,
            "summary": self.summary,
            "priority": self.priority.value,
            "category": self.category,
            "source": self.source,
            "url": self.url,
            "case_id": str(self.case_id) if self.case_id else None,
            "evidence_id": str(self.evidence_id) if self.evidence_id else None,
            "fields": self.fields,
            "color": self.color,
            "thread_id": self.thread_id,
            "tags": self.tags,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }


@dataclass
class DeliveryResult:
    """Result of a notification delivery attempt."""

    message_id: str | None  # Channel-specific message ID
    status: DeliveryStatus
    recipient: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    error: str | None = None
    retry_after: int | None = None  # Seconds until retry allowed
    raw_response: dict[str, Any] | None = None

    @property
    def success(self) -> bool:
        """Check if delivery was successful."""
        return self.status in (DeliveryStatus.SENT, DeliveryStatus.DELIVERED)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "message_id": self.message_id,
            "status": self.status.value,
            "recipient": self.recipient,
            "timestamp": self.timestamp.isoformat(),
            "error": self.error,
            "retry_after": self.retry_after,
        }


class NotificationChannel(ABC):
    """Abstract base class for notification delivery channels.

    All notification channels (Slack, Teams, email, etc.) must implement
    this interface to provide consistent notification delivery.
    """

    name: str = "base"
    display_name: str = "Base Channel"
    supports_threads: bool = False
    supports_reactions: bool = False
    supports_attachments: bool = False
    max_message_length: int = 4000

    @abstractmethod
    async def send(
        self,
        message: NotificationMessage,
        recipient: str,
    ) -> DeliveryResult:
        """Send a notification message.

        Args:
            message: The message to send
            recipient: Channel-specific recipient identifier
                      (channel ID, email, webhook URL, etc.)

        Returns:
            DeliveryResult with status and details
        """
        ...

    async def send_batch(
        self,
        messages: list[tuple[NotificationMessage, str]],
    ) -> list[DeliveryResult]:
        """Send multiple notifications.

        Default implementation sends sequentially. Override for
        channels that support batch operations.

        Args:
            messages: List of (message, recipient) tuples

        Returns:
            List of DeliveryResults in same order
        """
        results = []
        for message, recipient in messages:
            result = await self.send(message, recipient)
            results.append(result)
        return results

    @abstractmethod
    async def validate_config(self) -> bool:
        """Validate channel configuration.

        Returns:
            True if configuration is valid and channel is operational
        """
        ...

    async def validate_recipient(self, recipient: str) -> bool:
        """Validate a recipient identifier.

        Override for channels that can validate recipients.

        Args:
            recipient: Recipient identifier to validate

        Returns:
            True if recipient appears valid
        """
        return bool(recipient)

    async def update_message(
        self,
        message_id: str,
        message: NotificationMessage,
    ) -> DeliveryResult:
        """Update a previously sent message.

        Not all channels support this. Default raises NotImplementedError.

        Args:
            message_id: ID of message to update
            message: Updated message content

        Returns:
            DeliveryResult with status
        """
        raise NotImplementedError(f"{self.name} does not support message updates")

    async def delete_message(
        self,
        message_id: str,
        recipient: str,
    ) -> bool:
        """Delete a previously sent message.

        Not all channels support this. Default raises NotImplementedError.

        Args:
            message_id: ID of message to delete
            recipient: Channel/recipient where message was sent

        Returns:
            True if deleted successfully
        """
        raise NotImplementedError(f"{self.name} does not support message deletion")

    async def add_reaction(
        self,
        message_id: str,
        reaction: str,
    ) -> bool:
        """Add a reaction to a message.

        Only supported by some channels (Slack, Discord, etc.).

        Args:
            message_id: ID of message to react to
            reaction: Reaction emoji name

        Returns:
            True if reaction added successfully
        """
        raise NotImplementedError(f"{self.name} does not support reactions")

    def format_message(self, message: NotificationMessage) -> Any:
        """Format message for this channel.

        Override to customize message formatting. Default returns
        the message as-is.

        Args:
            message: Message to format

        Returns:
            Channel-specific formatted message
        """
        return message

    def truncate_text(self, text: str, max_length: int | None = None) -> str:
        """Truncate text to maximum length.

        Args:
            text: Text to truncate
            max_length: Maximum length (default: channel max)

        Returns:
            Truncated text with ellipsis if needed
        """
        max_len = max_length or self.max_message_length
        if len(text) <= max_len:
            return text
        return text[: max_len - 3] + "..."

    def _priority_to_color(self, priority: NotificationPriority) -> str:
        """Map priority to color code.

        Args:
            priority: Notification priority

        Returns:
            Hex color code
        """
        colors = {
            NotificationPriority.LOW: "#2196F3",  # Blue
            NotificationPriority.NORMAL: "#4CAF50",  # Green
            NotificationPriority.HIGH: "#FF9800",  # Orange
            NotificationPriority.CRITICAL: "#F44336",  # Red
        }
        return colors.get(priority, "#9E9E9E")

    async def health_check(self) -> dict[str, Any]:
        """Check channel health.

        Returns:
            Health status dictionary
        """
        try:
            is_valid = await self.validate_config()
            return {
                "status": "healthy" if is_valid else "unhealthy",
                "channel": self.name,
                "configured": is_valid,
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "channel": self.name,
                "error": str(e),
            }
