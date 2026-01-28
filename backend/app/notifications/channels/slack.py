"""Slack notification channel.

Supports sending notifications via Slack webhooks and Bot API.
"""

import logging
from typing import Any

from app.notifications.channels.base import (
    DeliveryResult,
    DeliveryStatus,
    NotificationChannel,
    NotificationMessage,
)

logger = logging.getLogger(__name__)


class SlackChannel(NotificationChannel):
    """Slack notification channel.

    Supports two modes:
    1. Webhook mode: Simple delivery via incoming webhook URL
    2. Bot mode: Full API access with bot token (supports updates, threads, reactions)

    Webhook mode is simpler but limited. Bot mode requires a Slack app with
    appropriate OAuth scopes (chat:write, chat:write.public, reactions:write).
    """

    name = "slack"
    display_name = "Slack"
    supports_threads = True
    supports_reactions = True
    supports_attachments = True
    max_message_length = 40000  # Slack's block text limit

    def __init__(
        self,
        webhook_url: str | None = None,
        bot_token: str | None = None,
        default_channel: str | None = None,
        timeout: int = 30,
    ):
        """Initialize Slack channel.

        Args:
            webhook_url: Incoming webhook URL (for simple mode)
            bot_token: Bot OAuth token (for full API access)
            default_channel: Default channel ID for bot mode
            timeout: Request timeout in seconds
        """
        self.webhook_url = webhook_url
        self.bot_token = bot_token
        self.default_channel = default_channel
        self.timeout = timeout
        self.api_url = "https://slack.com/api"

    @property
    def mode(self) -> str:
        """Get current operating mode."""
        if self.bot_token:
            return "bot"
        elif self.webhook_url:
            return "webhook"
        return "unconfigured"

    async def send(
        self,
        message: NotificationMessage,
        recipient: str,
    ) -> DeliveryResult:
        """Send notification to Slack.

        Args:
            message: Message to send
            recipient: Channel ID, user ID, or webhook URL

        Returns:
            DeliveryResult with status
        """
        import httpx

        try:
            if self.mode == "bot":
                return await self._send_via_bot(message, recipient)
            elif self.mode == "webhook":
                return await self._send_via_webhook(message, recipient)
            else:
                return DeliveryResult(
                    message_id=None,
                    status=DeliveryStatus.FAILED,
                    recipient=recipient,
                    error="Slack channel not configured",
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
            logger.error(f"Slack send error: {e}")
            return DeliveryResult(
                message_id=None,
                status=DeliveryStatus.FAILED,
                recipient=recipient,
                error=str(e),
            )

    async def _send_via_webhook(
        self,
        message: NotificationMessage,
        recipient: str,
    ) -> DeliveryResult:
        """Send via incoming webhook."""
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

        payload = self._format_webhook_payload(message)

        async with httpx.AsyncClient() as client:
            response = await client.post(
                webhook,
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()

            # Webhook returns "ok" on success
            if response.text == "ok":
                return DeliveryResult(
                    message_id=None,  # Webhooks don't return message ID
                    status=DeliveryStatus.SENT,
                    recipient=recipient,
                )
            else:
                return DeliveryResult(
                    message_id=None,
                    status=DeliveryStatus.FAILED,
                    recipient=recipient,
                    error=response.text,
                )

    async def _send_via_bot(
        self,
        message: NotificationMessage,
        recipient: str,
    ) -> DeliveryResult:
        """Send via Bot API."""
        import httpx

        channel = recipient or self.default_channel
        if not channel:
            return DeliveryResult(
                message_id=None,
                status=DeliveryStatus.FAILED,
                recipient=recipient,
                error="No channel specified",
            )

        payload = self._format_bot_payload(message, channel)

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.api_url}/chat.postMessage",
                json=payload,
                headers={
                    "Authorization": f"Bearer {self.bot_token}",
                    "Content-Type": "application/json",
                },
                timeout=self.timeout,
            )
            response.raise_for_status()

            data = response.json()

            if data.get("ok"):
                return DeliveryResult(
                    message_id=data.get("ts"),
                    status=DeliveryStatus.SENT,
                    recipient=channel,
                    raw_response=data,
                )
            else:
                error = data.get("error", "Unknown error")

                # Handle specific errors
                if error == "channel_not_found":
                    status = DeliveryStatus.INVALID_RECIPIENT
                elif error == "rate_limited":
                    status = DeliveryStatus.RATE_LIMITED
                else:
                    status = DeliveryStatus.FAILED

                return DeliveryResult(
                    message_id=None,
                    status=status,
                    recipient=channel,
                    error=error,
                    retry_after=data.get("retry_after"),
                )

    def _format_webhook_payload(self, message: NotificationMessage) -> dict[str, Any]:
        """Format message for webhook delivery."""
        color = message.color or self._priority_to_color(message.priority)

        blocks = []

        # Header block
        if message.title:
            blocks.append(
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": self.truncate_text(message.title, 150),
                        "emoji": True,
                    },
                }
            )

        # Body section
        if message.body:
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": self.truncate_text(message.body, 3000),
                    },
                }
            )

        # Fields
        if message.fields:
            field_blocks = []
            for key, value in list(message.fields.items())[:10]:
                field_blocks.append(
                    {
                        "type": "mrkdwn",
                        "text": f"*{key}:*\n{value}",
                    }
                )

            # Split into rows of 2
            for i in range(0, len(field_blocks), 2):
                blocks.append(
                    {
                        "type": "section",
                        "fields": field_blocks[i : i + 2],
                    }
                )

        # Link button
        if message.url:
            blocks.append(
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": "View Details",
                                "emoji": True,
                            },
                            "url": message.url,
                        }
                    ],
                }
            )

        # Context (footer)
        context_elements = []
        if message.category:
            context_elements.append(
                {
                    "type": "mrkdwn",
                    "text": f"_{message.category}_",
                }
            )
        if message.timestamp:
            context_elements.append(
                {
                    "type": "mrkdwn",
                    "text": f"<!date^{int(message.timestamp.timestamp())}^{{date_short_pretty}} at {{time}}|{message.timestamp.isoformat()}>",
                }
            )
        else:
            context_elements.append(
                {
                    "type": "mrkdwn",
                    "text": f"_{message.source}_",
                }
            )

        if context_elements:
            blocks.append(
                {
                    "type": "context",
                    "elements": context_elements,
                }
            )

        # Build payload
        payload: dict[str, Any] = {"blocks": blocks}

        # Add attachment for color bar
        payload["attachments"] = [
            {
                "color": color,
                "blocks": [],
            }
        ]

        # Thread support
        if message.thread_id:
            payload["thread_ts"] = message.thread_id

        return payload

    def _format_bot_payload(
        self,
        message: NotificationMessage,
        channel: str,
    ) -> dict[str, Any]:
        """Format message for bot API delivery."""
        payload = self._format_webhook_payload(message)
        payload["channel"] = channel

        # Unfurl settings
        payload["unfurl_links"] = False
        payload["unfurl_media"] = True

        return payload

    async def update_message(
        self,
        message_id: str,
        message: NotificationMessage,
    ) -> DeliveryResult:
        """Update a previously sent message."""
        import httpx

        if self.mode != "bot":
            raise NotImplementedError("Message updates require bot mode")

        channel = self.default_channel
        if not channel:
            return DeliveryResult(
                message_id=message_id,
                status=DeliveryStatus.FAILED,
                recipient="",
                error="No channel specified",
            )

        payload = self._format_bot_payload(message, channel)
        payload["ts"] = message_id

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.api_url}/chat.update",
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {self.bot_token}",
                        "Content-Type": "application/json",
                    },
                    timeout=self.timeout,
                )
                response.raise_for_status()

                data = response.json()

                if data.get("ok"):
                    return DeliveryResult(
                        message_id=data.get("ts"),
                        status=DeliveryStatus.SENT,
                        recipient=channel,
                    )
                else:
                    return DeliveryResult(
                        message_id=message_id,
                        status=DeliveryStatus.FAILED,
                        recipient=channel,
                        error=data.get("error"),
                    )

        except Exception as e:
            return DeliveryResult(
                message_id=message_id,
                status=DeliveryStatus.FAILED,
                recipient=channel,
                error=str(e),
            )

    async def delete_message(
        self,
        message_id: str,
        recipient: str,
    ) -> bool:
        """Delete a message."""
        import httpx

        if self.mode != "bot":
            raise NotImplementedError("Message deletion requires bot mode")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.api_url}/chat.delete",
                    json={
                        "channel": recipient,
                        "ts": message_id,
                    },
                    headers={
                        "Authorization": f"Bearer {self.bot_token}",
                        "Content-Type": "application/json",
                    },
                    timeout=self.timeout,
                )
                response.raise_for_status()

                data = response.json()
                return data.get("ok", False)

        except Exception as e:
            logger.error(f"Slack delete error: {e}")
            return False

    async def add_reaction(
        self,
        message_id: str,
        reaction: str,
    ) -> bool:
        """Add reaction to a message."""
        import httpx

        if self.mode != "bot":
            raise NotImplementedError("Reactions require bot mode")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.api_url}/reactions.add",
                    json={
                        "channel": self.default_channel,
                        "timestamp": message_id,
                        "name": reaction.strip(":"),
                    },
                    headers={
                        "Authorization": f"Bearer {self.bot_token}",
                        "Content-Type": "application/json",
                    },
                    timeout=self.timeout,
                )
                response.raise_for_status()

                data = response.json()
                return data.get("ok", False)

        except Exception as e:
            logger.error(f"Slack reaction error: {e}")
            return False

    async def validate_config(self) -> bool:
        """Validate Slack configuration."""
        import httpx

        if self.mode == "bot":
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        f"{self.api_url}/auth.test",
                        headers={
                            "Authorization": f"Bearer {self.bot_token}",
                            "Content-Type": "application/json",
                        },
                        timeout=10,
                    )
                    response.raise_for_status()

                    data = response.json()
                    return data.get("ok", False)

            except Exception as e:
                logger.error(f"Slack auth test failed: {e}")
                return False

        elif self.mode == "webhook":
            # For webhooks, we just check URL format
            return bool(
                self.webhook_url and self.webhook_url.startswith("https://hooks.slack.com/")
            )

        return False

    async def validate_recipient(self, recipient: str) -> bool:
        """Validate a channel or user ID."""
        # Slack IDs start with C (channel), G (group), D (DM), U (user)
        if recipient.startswith(("C", "G", "D", "U")):
            return True
        # Or could be a webhook URL
        if recipient.startswith("https://hooks.slack.com/"):
            return True
        return False

    async def health_check(self) -> dict[str, Any]:
        """Check Slack channel health."""
        result = await super().health_check()
        result["mode"] = self.mode

        if self.mode == "bot":
            import httpx

            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        f"{self.api_url}/auth.test",
                        headers={
                            "Authorization": f"Bearer {self.bot_token}",
                            "Content-Type": "application/json",
                        },
                        timeout=10,
                    )
                    data = response.json()

                    if data.get("ok"):
                        result["bot_id"] = data.get("bot_id")
                        result["team"] = data.get("team")
                        result["user"] = data.get("user")

            except Exception as e:
                result["error"] = str(e)

        return result
