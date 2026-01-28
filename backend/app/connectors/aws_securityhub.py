"""AWS Security Hub connector.

Ingests security findings from AWS Security Hub, aggregating findings
from various AWS security services including:
- GuardDuty
- Inspector
- Macie
- IAM Access Analyzer
- Firewall Manager
- Third-party integrations
"""

import logging
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

from app.connectors.base import (
    ConnectorConfig,
    PollingConnector,
    RawEvent,
)

logger = logging.getLogger(__name__)


class AWSSecurityHubConnector(PollingConnector):
    """AWS Security Hub connector.

    Polls AWS Security Hub for security findings using the GetFindings API.
    Supports filtering by severity, product, resource type, and workflow status.

    Configuration:
        region: AWS region
        access_key_id: AWS access key (optional, uses default credentials if not set)
        secret_access_key: AWS secret key
        role_arn: IAM role ARN to assume (optional)
        severity_min: Minimum severity (INFORMATIONAL, LOW, MEDIUM, HIGH, CRITICAL)
        product_arns: List of product ARNs to filter
        workflow_status: Filter by workflow status (NEW, NOTIFIED, RESOLVED, SUPPRESSED)
    """

    name = "aws_securityhub"
    description = "AWS Security Hub findings connector"

    def __init__(self, config: ConnectorConfig):
        super().__init__(config)
        self.region = config.extra.get("region", "us-east-1")
        self.access_key_id = config.extra.get("access_key_id")
        self.secret_access_key = config.extra.get("secret_access_key")
        self.role_arn = config.extra.get("role_arn")
        self.severity_min = config.extra.get("severity_min", "LOW")
        self.product_arns = config.extra.get("product_arns", [])
        self.workflow_status = config.extra.get("workflow_status", ["NEW", "NOTIFIED"])

        self._client = None
        self._last_updated: str | None = None

    async def connect(self) -> bool:
        """Connect to AWS Security Hub."""
        try:
            import boto3
            from botocore.config import Config

            boto_config = Config(
                region_name=self.region,
                retries={"max_attempts": 3, "mode": "adaptive"},
            )

            # Create session
            if self.access_key_id and self.secret_access_key:
                session = boto3.Session(
                    aws_access_key_id=self.access_key_id,
                    aws_secret_access_key=self.secret_access_key,
                    region_name=self.region,
                )
            else:
                session = boto3.Session(region_name=self.region)

            # Assume role if specified
            if self.role_arn:
                sts = session.client("sts", config=boto_config)
                assumed = sts.assume_role(
                    RoleArn=self.role_arn,
                    RoleSessionName="EleanorSecurityHub",
                )
                credentials = assumed["Credentials"]

                self._client = boto3.client(
                    "securityhub",
                    aws_access_key_id=credentials["AccessKeyId"],
                    aws_secret_access_key=credentials["SecretAccessKey"],
                    aws_session_token=credentials["SessionToken"],
                    config=boto_config,
                )
            else:
                self._client = session.client("securityhub", config=boto_config)

            # Verify connectivity
            self._client.describe_hub()

            logger.info(f"Connected to AWS Security Hub in {self.region}")
            return True

        except Exception as e:
            logger.error(f"Failed to connect to Security Hub: {e}")
            self.record_error(str(e))
            return False

    async def disconnect(self) -> None:
        """Disconnect from AWS Security Hub."""
        self._client = None

    async def health_check(self) -> dict[str, Any]:
        """Check Security Hub connectivity."""
        if not self._client:
            return {
                "status": "unhealthy",
                "error": "Not connected",
            }

        try:
            import asyncio

            hub_info = await asyncio.to_thread(self._client.describe_hub)

            return {
                "status": "healthy",
                "region": self.region,
                "hub_arn": hub_info.get("HubArn"),
                "auto_enable_controls": hub_info.get("AutoEnableControls"),
            }

        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
            }

    async def poll(self) -> AsyncIterator[RawEvent]:
        """Poll for new security findings."""
        import asyncio

        if not self._client:
            return

        try:
            filters = self._build_filters()
            next_token = None

            while True:
                # Get findings
                kwargs = {
                    "Filters": filters,
                    "MaxResults": min(self.config.batch_size, 100),
                }
                if next_token:
                    kwargs["NextToken"] = next_token

                response = await asyncio.to_thread(self._client.get_findings, **kwargs)

                for finding in response.get("Findings", []):
                    try:
                        event = self._finding_to_event(finding)
                        if event:
                            self.record_event(len(str(event.data)))
                            yield event

                            # Track last updated time
                            updated = finding.get("UpdatedAt")
                            if updated:
                                if not self._last_updated or updated > self._last_updated:
                                    self._last_updated = updated

                    except Exception as e:
                        logger.debug(f"Error processing finding: {e}")
                        self.record_error(str(e))

                # Check for more pages
                next_token = response.get("NextToken")
                if not next_token:
                    break

        except Exception as e:
            logger.error(f"Security Hub poll error: {e}")
            self.record_error(str(e))

    def _build_filters(self) -> dict[str, Any]:
        """Build Security Hub finding filters."""
        filters: dict[str, list] = {}

        # Updated time filter
        if self._last_updated:
            filters["UpdatedAt"] = [
                {
                    "Start": self._last_updated,
                    "DateRange": {"Value": 1, "Unit": "DAYS"},
                }
            ]
        else:
            # First poll - get last 24 hours
            from datetime import timedelta

            start_time = datetime.now(UTC) - timedelta(hours=24)
            filters["UpdatedAt"] = [
                {
                    "Start": start_time.isoformat(),
                    "DateRange": {"Value": 1, "Unit": "DAYS"},
                }
            ]

        # Severity filter
        severity_map = {
            "INFORMATIONAL": 0,
            "LOW": 1,
            "MEDIUM": 40,
            "HIGH": 70,
            "CRITICAL": 90,
        }
        min_severity = severity_map.get(self.severity_min, 0)
        filters["SeverityNormalized"] = [{"Gte": min_severity, "Lte": 100}]

        # Product filter
        if self.product_arns:
            filters["ProductArn"] = [
                {"Value": arn, "Comparison": "EQUALS"} for arn in self.product_arns
            ]

        # Workflow status filter
        if self.workflow_status:
            filters["WorkflowStatus"] = [
                {"Value": status, "Comparison": "EQUALS"} for status in self.workflow_status
            ]

        # Only active findings (not archived)
        filters["RecordState"] = [{"Value": "ACTIVE", "Comparison": "EQUALS"}]

        return filters

    def _finding_to_event(self, finding: dict) -> RawEvent | None:
        """Convert Security Hub finding to RawEvent."""
        try:
            # Get timestamp
            timestamp_str = finding.get("UpdatedAt") or finding.get("CreatedAt")
            if timestamp_str:
                timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            else:
                timestamp = datetime.now(UTC)

            # Get product info
            product_arn = finding.get("ProductArn", "")
            product_name = self._extract_product_name(product_arn)

            return RawEvent(
                data=finding,
                source=f"securityhub:{product_name}",
                timestamp=timestamp,
                metadata={
                    "finding_id": finding.get("Id"),
                    "product_arn": product_arn,
                    "product_name": product_name,
                    "severity": finding.get("Severity", {}).get("Label"),
                    "aws_account": finding.get("AwsAccountId"),
                    "region": finding.get("Region"),
                },
            )

        except Exception as e:
            logger.debug(f"Failed to convert finding: {e}")
            return None

    def _extract_product_name(self, product_arn: str) -> str:
        """Extract product name from ARN."""
        # ARN format: arn:aws:securityhub:region:account:product/company/product-name
        if "/" in product_arn:
            return product_arn.split("/")[-1]
        return "unknown"


# ASFF severity mapping
ASFF_SEVERITY_MAP = {
    "INFORMATIONAL": 10,
    "LOW": 30,
    "MEDIUM": 50,
    "HIGH": 70,
    "CRITICAL": 90,
}

# ASFF type to ECS category mapping
ASFF_TYPE_CATEGORY_MAP = {
    "Software and Configuration Checks": ["configuration"],
    "TTPs": ["intrusion_detection"],
    "Effects": ["intrusion_detection"],
    "Unusual Behaviors": ["intrusion_detection"],
    "Sensitive Data Identifications": ["file"],
}
