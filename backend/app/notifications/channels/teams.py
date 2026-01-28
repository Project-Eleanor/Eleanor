"""Microsoft Teams notification channel.

Supports sending notifications via Teams incoming webhooks and
Adaptive Cards format.
"""

import logging
from datetime import datetime
from typing import Any

from app.notifications.channels.base import (
    DeliveryResult,
    DeliveryStatus,
    NotificationChannel,
    NotificationMessage,
    NotificationPriority,
)

logger = logging.getLogger(__name__)


class TeamsChannel(NotificationChannel):
    """Microsoft Teams notification channel.

    Supports sending rich notifications via incoming webhooks using
    Adaptive Cards format. Adaptive Cards provide rich formatting
    including headers, sections, facts, and action buttons.

    Note: Teams webhooks don't support message updates, deletion,
    or threading like Slack does.
    """

    name = "teams"
    display_name = "Microsoft Teams"
    supports_threads = False
    supports_reactions = False
    supports_attachments = True
    max_message_length = 28000  # Teams card payload limit

    def __init__(
        self,
        webhook_url: str | None = None,
        timeout: int = 30,
    ):
        """Initialize Teams channel.

        Args:
            webhook_url: Teams incoming webhook URL
            timeout: Request timeout in seconds
        """
        self.webhook_url = webhook_url
        self.timeout = timeout

    async def send(
        self,
        message: NotificationMessage,
        recipient: str,
    ) -> DeliveryResult:
        """Send notification to Teams.

        Args:
            message: Message to send
            recipient: Webhook URL (or use default)

        Returns:
            DeliveryResult with status
        """
        import httpx

        # Use provided webhook or default
        webhook = recipient if recipient.startswith("http") else self.webhook_url

        if not webhook:
            return DeliveryResult(
                message_id=None,
                status=DeliveryStatus.FAILED,
                recipient=recipient,
                error="No webhook URL configured",
            )

        try:
            payload = self._format_adaptive_card(message)

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    webhook,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=self.timeout,
                )

                # Teams returns 200 with "1" on success
                if response.status_code == 200:
                    return DeliveryResult(
                        message_id=None,  # Teams webhooks don't return ID
                        status=DeliveryStatus.SENT,
                        recipient=recipient,
                    )
                else:
                    return DeliveryResult(
                        message_id=None,
                        status=DeliveryStatus.FAILED,
                        recipient=recipient,
                        error=f"HTTP {response.status_code}: {response.text}",
                    )

        except httpx.HTTPStatusError as e:
            status = DeliveryStatus.FAILED
            error = f"HTTP {e.response.status_code}"

            if e.response.status_code == 429:
                status = DeliveryStatus.RATE_LIMITED
                retry_after = int(e.response.headers.get("Retry-After", 60))
                return DeliveryResult(
                    message_id=None,
                    status=status,
                    recipient=recipient,
                    error="Rate limited",
                    retry_after=retry_after,
                )

            return DeliveryResult(
                message_id=None,
                status=status,
                recipient=recipient,
                error=error,
            )

        except Exception as e:
            logger.error(f"Teams send error: {e}")
            return DeliveryResult(
                message_id=None,
                status=DeliveryStatus.FAILED,
                recipient=recipient,
                error=str(e),
            )

    def _format_adaptive_card(self, message: NotificationMessage) -> dict[str, Any]:
        """Format message as Adaptive Card.

        Uses Adaptive Card schema for rich formatting in Teams.
        """
        message.color or self._priority_to_color(message.priority)

        # Build card body
        body = []

        # Title with color indicator
        if message.title:
            body.append(
                {
                    "type": "TextBlock",
                    "text": message.title,
                    "weight": "Bolder",
                    "size": "Large",
                    "wrap": True,
                    "color": self._priority_to_teams_color(message.priority),
                }
            )

        # Category badge
        if message.category:
            body.append(
                {
                    "type": "TextBlock",
                    "text": message.category.upper(),
                    "size": "Small",
                    "weight": "Lighter",
                    "color": "Accent",
                    "spacing": "None",
                }
            )

        # Separator
        body.append(
            {
                "type": "TextBlock",
                "text": " ",
                "spacing": "Small",
                "separator": True,
            }
        )

        # Body text
        if message.body:
            body.append(
                {
                    "type": "TextBlock",
                    "text": self.truncate_text(message.body, 3000),
                    "wrap": True,
                }
            )

        # Fields as FactSet
        if message.fields:
            facts = []
            for key, value in list(message.fields.items())[:10]:
                facts.append(
                    {
                        "title": key,
                        "value": str(value)[:200],
                    }
                )

            body.append(
                {
                    "type": "FactSet",
                    "facts": facts,
                    "spacing": "Medium",
                }
            )

        # Timestamp
        timestamp = message.timestamp or datetime.utcnow()
        body.append(
            {
                "type": "TextBlock",
                "text": f"_{message.source} • {timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}_",
                "size": "Small",
                "weight": "Lighter",
                "spacing": "Medium",
                "isSubtle": True,
            }
        )

        # Actions
        actions = []
        if message.url:
            actions.append(
                {
                    "type": "Action.OpenUrl",
                    "title": "View Details",
                    "url": message.url,
                }
            )

        # Build the Adaptive Card
        card = {
            "type": "AdaptiveCard",
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "version": "1.4",
            "body": body,
        }

        if actions:
            card["actions"] = actions

        # Wrap in message format for webhook
        return {
            "type": "message",
            "attachments": [
                {
                    "contentType": "application/vnd.microsoft.card.adaptive",
                    "content": card,
                }
            ],
        }

    def _format_message_card(self, message: NotificationMessage) -> dict[str, Any]:
        """Format message as legacy MessageCard.

        Fallback format if Adaptive Cards aren't supported.
        """
        color = message.color or self._priority_to_color(message.priority)

        sections = []

        # Main section
        main_section: dict[str, Any] = {
            "activityTitle": message.title,
            "activitySubtitle": message.category or message.source,
        }

        if message.body:
            main_section["text"] = self.truncate_text(message.body, 3000)

        # Facts
        if message.fields:
            main_section["facts"] = [
                {"name": k, "value": str(v)[:200]} for k, v in list(message.fields.items())[:10]
            ]

        sections.append(main_section)

        # Build card
        card: dict[str, Any] = {
            "@type": "MessageCard",
            "@context": "http://schema.org/extensions",
            "themeColor": color.lstrip("#"),
            "summary": message.summary or message.title,
            "sections": sections,
        }

        # Actions
        if message.url:
            card["potentialAction"] = [
                {
                    "@type": "OpenUri",
                    "name": "View Details",
                    "targets": [{"os": "default", "uri": message.url}],
                }
            ]

        return card

    def _priority_to_teams_color(self, priority: NotificationPriority) -> str:
        """Map priority to Teams color name."""
        colors = {
            NotificationPriority.LOW: "Default",
            NotificationPriority.NORMAL: "Good",
            NotificationPriority.HIGH: "Warning",
            NotificationPriority.CRITICAL: "Attention",
        }
        return colors.get(priority, "Default")

    async def validate_config(self) -> bool:
        """Validate Teams configuration."""
        if not self.webhook_url:
            return False

        # Check URL format
        valid_domains = [
            "outlook.office.com",
            "outlook.office365.com",
            ".webhook.office.com",
        ]

        return any(domain in self.webhook_url for domain in valid_domains)

    async def validate_recipient(self, recipient: str) -> bool:
        """Validate a webhook URL."""
        if not recipient:
            return bool(self.webhook_url)

        valid_domains = [
            "outlook.office.com",
            "outlook.office365.com",
            ".webhook.office.com",
        ]

        return any(domain in recipient for domain in valid_domains)

    async def send_batch(
        self,
        messages: list[tuple[NotificationMessage, str]],
    ) -> list[DeliveryResult]:
        """Send multiple notifications.

        Teams webhooks are rate limited, so we add small delays.
        """
        import asyncio

        results = []
        for i, (message, recipient) in enumerate(messages):
            if i > 0:
                # Small delay to avoid rate limits
                await asyncio.sleep(0.5)
            result = await self.send(message, recipient)
            results.append(result)
        return results

    async def health_check(self) -> dict[str, Any]:
        """Check Teams channel health."""
        result = await super().health_check()

        if self.webhook_url:
            # Extract team info from URL if possible
            try:
                # URL format includes tenant and team info
                if "webhook.office.com" in self.webhook_url:
                    result["webhook_configured"] = True
            except Exception:
                pass

        return result


class TeamsAdaptiveCardBuilder:
    """Helper class for building complex Adaptive Cards.

    Provides a fluent interface for building cards programmatically.
    """

    def __init__(self):
        self.body = []
        self.actions = []

    def add_text(
        self,
        text: str,
        size: str = "Default",
        weight: str = "Default",
        color: str = "Default",
        wrap: bool = True,
    ) -> "TeamsAdaptiveCardBuilder":
        """Add a text block."""
        self.body.append(
            {
                "type": "TextBlock",
                "text": text,
                "size": size,
                "weight": weight,
                "color": color,
                "wrap": wrap,
            }
        )
        return self

    def add_heading(self, text: str) -> "TeamsAdaptiveCardBuilder":
        """Add a heading."""
        return self.add_text(text, size="Large", weight="Bolder")

    def add_facts(self, facts: dict[str, str]) -> "TeamsAdaptiveCardBuilder":
        """Add a fact set."""
        self.body.append(
            {
                "type": "FactSet",
                "facts": [{"title": k, "value": v} for k, v in facts.items()],
            }
        )
        return self

    def add_image(
        self,
        url: str,
        alt_text: str = "",
        size: str = "Auto",
    ) -> "TeamsAdaptiveCardBuilder":
        """Add an image."""
        self.body.append(
            {
                "type": "Image",
                "url": url,
                "altText": alt_text,
                "size": size,
            }
        )
        return self

    def add_column_set(
        self,
        columns: list[dict],
    ) -> "TeamsAdaptiveCardBuilder":
        """Add a column set for side-by-side content."""
        self.body.append(
            {
                "type": "ColumnSet",
                "columns": columns,
            }
        )
        return self

    def add_action_url(
        self,
        title: str,
        url: str,
    ) -> "TeamsAdaptiveCardBuilder":
        """Add an action button that opens a URL."""
        self.actions.append(
            {
                "type": "Action.OpenUrl",
                "title": title,
                "url": url,
            }
        )
        return self

    def add_separator(self) -> "TeamsAdaptiveCardBuilder":
        """Add a separator."""
        if self.body:
            self.body[-1]["separator"] = True
        return self

    def build(self) -> dict[str, Any]:
        """Build the final Adaptive Card."""
        card = {
            "type": "AdaptiveCard",
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "version": "1.4",
            "body": self.body,
        }

        if self.actions:
            card["actions"] = self.actions

        return {
            "type": "message",
            "attachments": [
                {
                    "contentType": "application/vnd.microsoft.card.adaptive",
                    "content": card,
                }
            ],
        }
