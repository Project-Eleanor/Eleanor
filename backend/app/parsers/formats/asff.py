"""AWS Security Finding Format (ASFF) parser.

Parses AWS Security Hub findings in ASFF format, which is the standard
format used by AWS security services including GuardDuty, Inspector,
Macie, IAM Access Analyzer, and third-party integrations.
"""

import json
import logging
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, BinaryIO

from app.parsers.base import BaseParser, ParsedEvent, ParserCategory
from app.parsers.registry import register_parser

logger = logging.getLogger(__name__)


# ASFF type namespace to ECS category mapping
ASFF_NAMESPACE_CATEGORY_MAP = {
    # AWS services
    "Software and Configuration Checks": ["configuration"],
    "TTPs": ["intrusion_detection"],
    "Effects": ["intrusion_detection"],
    "Unusual Behaviors": ["intrusion_detection"],
    "Sensitive Data Identifications": ["file"],
    # GuardDuty specific
    "Backdoor": ["malware"],
    "Behavior": ["intrusion_detection"],
    "CryptoCurrency": ["intrusion_detection"],
    "PenTest": ["intrusion_detection"],
    "Persistence": ["intrusion_detection"],
    "Policy": ["configuration"],
    "PrivilegeEscalation": ["intrusion_detection"],
    "Recon": ["intrusion_detection"],
    "Stealth": ["intrusion_detection"],
    "Trojan": ["malware"],
    "UnauthorizedAccess": ["authentication"],
    # Inspector
    "Vulnerabilities": ["package"],
    # Macie
    "SensitiveData": ["file"],
    # IAM
    "IAMUser": ["iam"],
}

# ASFF severity label to numeric mapping
SEVERITY_MAP = {
    "INFORMATIONAL": 10,
    "LOW": 30,
    "MEDIUM": 50,
    "HIGH": 70,
    "CRITICAL": 90,
}

# Resource type to ECS category
RESOURCE_TYPE_CATEGORY_MAP = {
    "AwsEc2Instance": ["host"],
    "AwsEc2NetworkInterface": ["network"],
    "AwsEc2SecurityGroup": ["network"],
    "AwsEc2Volume": ["file"],
    "AwsS3Bucket": ["file"],
    "AwsS3Object": ["file"],
    "AwsIamAccessKey": ["iam"],
    "AwsIamUser": ["iam"],
    "AwsIamRole": ["iam"],
    "AwsIamPolicy": ["iam"],
    "AwsLambdaFunction": ["process"],
    "AwsRdsDbInstance": ["database"],
    "AwsRdsDbCluster": ["database"],
    "AwsKmsKey": ["configuration"],
    "AwsSecretsManagerSecret": ["configuration"],
    "Container": ["host"],
}


@register_parser
class ASFFParser(BaseParser):
    """Parser for AWS Security Finding Format (ASFF) findings."""

    @property
    def name(self) -> str:
        return "asff"

    @property
    def category(self) -> ParserCategory:
        return ParserCategory.CLOUD

    @property
    def description(self) -> str:
        return "AWS Security Finding Format (ASFF) parser for Security Hub findings"

    @property
    def supported_extensions(self) -> list[str]:
        return [".json", ".jsonl"]

    @property
    def supported_mime_types(self) -> list[str]:
        return ["application/json"]

    def can_parse(self, file_path: Path | None = None, content: bytes | None = None) -> bool:
        """Check if content is ASFF format."""
        if content:
            try:
                text = content.decode("utf-8", errors="ignore")
                lines = text.strip().split("\n")

                for line in lines[:5]:
                    if not line.strip():
                        continue

                    try:
                        data = json.loads(line)
                        # ASFF has specific required fields
                        if all(f in data for f in ["SchemaVersion", "Id", "ProductArn"]):
                            return True
                        # Check for Findings array (batch export)
                        if "Findings" in data and isinstance(data["Findings"], list):
                            if data["Findings"] and "SchemaVersion" in data["Findings"][0]:
                                return True
                    except json.JSONDecodeError:
                        pass

            except Exception:
                pass

        return False

    def parse(
        self,
        source: Path | BinaryIO,
        source_name: str | None = None,
    ) -> Iterator[ParsedEvent]:
        """Parse ASFF file and yield events."""
        source_str = source_name or (str(source) if isinstance(source, Path) else "stream")

        if isinstance(source, Path):
            with open(source, encoding="utf-8", errors="replace") as f:
                yield from self._parse_file(f, source_str)
        else:
            import io

            text_stream = io.TextIOWrapper(source, encoding="utf-8", errors="replace")
            yield from self._parse_file(text_stream, source_str)

    def _parse_file(self, file_handle, source_name: str) -> Iterator[ParsedEvent]:
        """Parse file content."""
        content = file_handle.read()

        try:
            data = json.loads(content)

            # Handle batch export format
            if "Findings" in data:
                findings = data["Findings"]
            elif isinstance(data, list):
                findings = data
            else:
                findings = [data]

            for i, finding in enumerate(findings):
                try:
                    event = self._parse_finding(finding, source_name, i + 1)
                    if event:
                        yield event
                except Exception as e:
                    logger.debug(f"Error parsing finding {i + 1}: {e}")

        except json.JSONDecodeError:
            # Try JSONL format
            file_handle.seek(0)
            for line_num, line in enumerate(file_handle, 1):
                line = line.strip()
                if not line:
                    continue

                try:
                    finding = json.loads(line)
                    event = self._parse_finding(finding, source_name, line_num)
                    if event:
                        yield event
                except Exception as e:
                    logger.debug(f"Error parsing line {line_num}: {e}")

    def _parse_finding(
        self,
        finding: dict[str, Any],
        source_name: str,
        line_num: int,
    ) -> ParsedEvent | None:
        """Parse a single ASFF finding."""
        # Extract timestamp
        timestamp = self._parse_timestamp(finding)

        # Generate message
        message = self._generate_message(finding)

        # Determine product
        product_arn = finding.get("ProductArn", "")
        product_name = self._extract_product_name(product_arn)

        # Create event
        event = ParsedEvent(
            timestamp=timestamp,
            message=message,
            source_type=f"asff:{product_name}",
            source_file=source_name,
            source_line=line_num,
            event_kind="alert",
        )

        # Set action from finding type
        finding_type = finding.get("Types", ["Unknown"])[0] if finding.get("Types") else "Unknown"
        event.event_action = finding_type

        # Set categories from finding type namespace
        event.event_category = self._get_categories(finding_type, finding)
        event.event_type = ["info"]

        # Set severity
        severity = finding.get("Severity", {})
        event.event_severity = SEVERITY_MAP.get(
            severity.get("Label", "MEDIUM"), severity.get("Normalized", 50)
        )

        # Workflow status as outcome
        workflow = finding.get("Workflow", {})
        status = workflow.get("Status", finding.get("WorkflowState", ""))
        if status in ("RESOLVED", "SUPPRESSED"):
            event.event_outcome = "success"
        elif status == "NEW":
            event.event_outcome = "unknown"

        # Extract resources
        self._map_resources(event, finding)

        # Labels
        event.labels = {
            "finding_id": finding.get("Id", ""),
            "product_arn": product_arn,
            "product_name": product_name,
            "generator_id": finding.get("GeneratorId", ""),
            "aws_account": finding.get("AwsAccountId", ""),
            "region": finding.get("Region", ""),
            "record_state": finding.get("RecordState", ""),
            "workflow_status": status,
            "compliance_status": finding.get("Compliance", {}).get("Status", ""),
        }

        # Confidence and criticality
        if "Confidence" in finding:
            event.labels["confidence"] = str(finding["Confidence"])
        if "Criticality" in finding:
            event.labels["criticality"] = str(finding["Criticality"])

        # Store raw
        event.raw = finding

        return event

    def _parse_timestamp(self, finding: dict) -> datetime:
        """Parse timestamp from finding."""
        for field in ["UpdatedAt", "CreatedAt", "FirstObservedAt"]:
            if field in finding:
                try:
                    return datetime.fromisoformat(finding[field].replace("Z", "+00:00"))
                except ValueError:
                    pass

        return datetime.now(UTC)

    def _generate_message(self, finding: dict) -> str:
        """Generate human-readable message."""
        title = finding.get("Title", "Security Finding")
        severity = finding.get("Severity", {}).get("Label", "MEDIUM")
        account = finding.get("AwsAccountId", "unknown")

        # Get resource info
        resources = finding.get("Resources", [])
        resource_info = ""
        if resources:
            resource = resources[0]
            resource_type = resource.get("Type", "")
            resource_id = resource.get("Id", "")
            if resource_id:
                # Shorten long resource IDs
                if len(resource_id) > 50:
                    resource_id = "..." + resource_id[-47:]
                resource_info = f" ({resource_type}: {resource_id})"

        return f"[{severity}] {title}{resource_info} in {account}"

    def _extract_product_name(self, product_arn: str) -> str:
        """Extract product name from ARN."""
        # ARN format: arn:aws:securityhub:region:account:product/company/product-name
        if "/" in product_arn:
            parts = product_arn.split("/")
            if len(parts) >= 2:
                return parts[-1]
        return "unknown"

    def _get_categories(self, finding_type: str, finding: dict) -> list[str]:
        """Get ECS categories from finding type."""
        # Check namespace
        if "/" in finding_type:
            namespace = finding_type.split("/")[0]
            if namespace in ASFF_NAMESPACE_CATEGORY_MAP:
                return ASFF_NAMESPACE_CATEGORY_MAP[namespace]

        # Check resource type
        resources = finding.get("Resources", [])
        if resources:
            resource_type = resources[0].get("Type", "")
            if resource_type in RESOURCE_TYPE_CATEGORY_MAP:
                return RESOURCE_TYPE_CATEGORY_MAP[resource_type]

        return ["cloud"]

    def _map_resources(self, event: ParsedEvent, finding: dict) -> None:
        """Map ASFF resources to event fields."""
        resources = finding.get("Resources", [])
        if not resources:
            return

        for resource in resources:
            resource_type = resource.get("Type", "")
            resource_id = resource.get("Id", "")
            details = resource.get("Details", {})

            # EC2 Instance
            if resource_type == "AwsEc2Instance":
                instance = details.get("AwsEc2Instance", {})
                event.host_name = (
                    instance.get("IamInstanceProfileArn", "").split("/")[-1]
                    if instance.get("IamInstanceProfileArn")
                    else resource_id
                )

                if instance.get("IpV4Addresses"):
                    event.host_ip = instance["IpV4Addresses"]

                if instance.get("LaunchedAt"):
                    event.labels["instance_launched"] = instance["LaunchedAt"]

            # IAM User
            elif resource_type == "AwsIamUser":
                user = details.get("AwsIamUser", {})
                event.user_name = user.get("UserName", resource_id.split("/")[-1])
                if user.get("UserId"):
                    event.user_id = user["UserId"]

            # IAM Access Key
            elif resource_type == "AwsIamAccessKey":
                key = details.get("AwsIamAccessKey", {})
                event.user_name = key.get("PrincipalName")
                event.labels["access_key_id"] = key.get("AccessKeyId", resource_id)

            # S3 Bucket
            elif resource_type == "AwsS3Bucket":
                bucket = details.get("AwsS3Bucket", {})
                event.labels["s3_bucket"] = bucket.get("Name", resource_id.split(":")[-1])

            # S3 Object
            elif resource_type == "AwsS3Object":
                obj = details.get("AwsS3Object", {})
                event.file_path = f"s3://{obj.get('Bucket', '')}/{obj.get('Key', '')}"
                event.file_name = obj.get("Key", "").split("/")[-1] if obj.get("Key") else None

            # Lambda Function
            elif resource_type == "AwsLambdaFunction":
                func = details.get("AwsLambdaFunction", {})
                event.process_name = func.get("FunctionName", resource_id.split(":")[-1])

            # Container
            elif resource_type == "Container":
                container = details.get("Container", {})
                event.host_name = container.get("Name", resource_id)
                if container.get("ImageId"):
                    event.labels["container_image"] = container["ImageId"]

            # Network-related resources
            if resource_type in ("AwsEc2NetworkInterface", "AwsEc2SecurityGroup"):
                if "Details" in resource:
                    eni = details.get("AwsEc2NetworkInterface", {})
                    if eni.get("PublicIp"):
                        event.source_ip = eni["PublicIp"]
                    if eni.get("PrivateIpAddress"):
                        event.labels["private_ip"] = eni["PrivateIpAddress"]

        # Network-related findings often have these
        network = finding.get("Network", {})
        if network:
            if network.get("SourceIpV4"):
                event.source_ip = network["SourceIpV4"]
            if network.get("SourcePort"):
                event.source_port = network["SourcePort"]
            if network.get("DestinationIpV4"):
                event.destination_ip = network["DestinationIpV4"]
            if network.get("DestinationPort"):
                event.destination_port = network["DestinationPort"]
            if network.get("Protocol"):
                event.network_protocol = network["Protocol"].lower()
            if network.get("Direction"):
                event.network_direction = network["Direction"].lower()

        # Process info (from some findings)
        process = finding.get("Process", {})
        if process:
            if process.get("Name"):
                event.process_name = process["Name"]
            if process.get("Pid"):
                event.process_pid = process["Pid"]
            if process.get("ParentPid"):
                event.process_ppid = process["ParentPid"]
            if process.get("Path"):
                event.process_executable = process["Path"]
