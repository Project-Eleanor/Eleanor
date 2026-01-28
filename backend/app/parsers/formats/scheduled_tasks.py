"""Windows Scheduled Tasks parser.

Parses Windows Scheduled Task XML files from System32\\Tasks directory.
"""

import logging
import xml.etree.ElementTree as ET
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, BinaryIO

from app.parsers.base import BaseParser, ParsedEvent, ParserCategory
from app.parsers.registry import register_parser

logger = logging.getLogger(__name__)


@register_parser
class WindowsScheduledTasksParser(BaseParser):
    """Parser for Windows Scheduled Task XML files."""

    @property
    def name(self) -> str:
        return "windows_scheduled_tasks"

    @property
    def category(self) -> ParserCategory:
        return ParserCategory.ARTIFACTS

    @property
    def description(self) -> str:
        return "Windows Scheduled Task XML parser (persistence mechanism)"

    @property
    def supported_extensions(self) -> list[str]:
        return [".xml", ".job"]

    @property
    def supported_mime_types(self) -> list[str]:
        return ["application/xml", "text/xml"]

    def can_parse(self, file_path: Path | None = None, content: bytes | None = None) -> bool:
        """Check for scheduled task XML structure."""
        if content:
            try:
                content_str = content.decode("utf-8", errors="ignore")
                if "<Task" in content_str and "xmlns" in content_str:
                    if "schemas.microsoft.com/windows" in content_str:
                        return True
            except Exception:
                pass

        if file_path:
            # Check if in Tasks directory
            path_str = str(file_path).lower()
            if "tasks" in path_str or "system32" in path_str:
                if file_path.suffix.lower() == ".xml":
                    return True

        return False

    def parse(
        self,
        source: Path | BinaryIO,
        source_name: str | None = None,
    ) -> Iterator[ParsedEvent]:
        """Parse scheduled task XML file."""
        source_str = source_name or (str(source) if isinstance(source, Path) else "stream")

        try:
            # Read content
            if isinstance(source, Path):
                with open(source, "rb") as f:
                    content = f.read()
            else:
                content = source.read()

            # Parse XML
            root = ET.fromstring(content)

            # Handle namespace
            ns = {}
            if root.tag.startswith("{"):
                ns_uri = root.tag.split("}")[0] + "}"
                ns["t"] = ns_uri[1:-1]

            # Extract task information
            task_name = source_str
            if isinstance(source, Path):
                task_name = source.stem

            # Get registration info
            reg_info = root.find(".//RegistrationInfo", ns) or root.find(".//{*}RegistrationInfo")
            author = self._get_text(reg_info, "Author", ns) or self._get_text(reg_info, "{*}Author")
            description = self._get_text(reg_info, "Description", ns) or self._get_text(reg_info, "{*}Description")
            date_str = self._get_text(reg_info, "Date", ns) or self._get_text(reg_info, "{*}Date")

            registration_date = datetime.now(UTC)
            if date_str:
                try:
                    registration_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                except Exception:
                    pass

            # Get triggers
            triggers = []
            triggers_elem = root.find(".//Triggers", ns) or root.find(".//{*}Triggers")
            if triggers_elem is not None:
                for trigger in triggers_elem:
                    trigger_info = self._parse_trigger(trigger)
                    if trigger_info:
                        triggers.append(trigger_info)

            # Get actions
            actions = []
            actions_elem = root.find(".//Actions", ns) or root.find(".//{*}Actions")
            if actions_elem is not None:
                for action in actions_elem:
                    action_info = self._parse_action(action)
                    if action_info:
                        actions.append(action_info)

            # Get principal (security context)
            principal = root.find(".//Principal", ns) or root.find(".//{*}Principal")
            user_id = self._get_text(principal, "UserId", ns) or self._get_text(principal, "{*}UserId")
            run_level = self._get_text(principal, "RunLevel", ns) or self._get_text(principal, "{*}RunLevel")

            # Get settings
            settings = root.find(".//Settings", ns) or root.find(".//{*}Settings")
            hidden = self._get_text(settings, "Hidden", ns) or self._get_text(settings, "{*}Hidden")
            enabled = self._get_text(settings, "Enabled", ns) or self._get_text(settings, "{*}Enabled")

            # Build message
            action_summary = ""
            if actions:
                first_action = actions[0]
                if "command" in first_action:
                    action_summary = first_action["command"]
                    if first_action.get("arguments"):
                        action_summary += f" {first_action['arguments']}"
                elif "path" in first_action:
                    action_summary = first_action["path"]

            message = f"Scheduled task: {task_name}"
            if action_summary:
                message += f" -> {action_summary[:100]}"

            # Build raw data
            raw = {
                "task_name": task_name,
                "author": author,
                "description": description,
                "registration_date": str(registration_date),
                "user_id": user_id,
                "run_level": run_level,
                "hidden": hidden,
                "enabled": enabled,
                "triggers": triggers,
                "actions": actions,
            }

            # Determine risk indicators
            tags = ["persistence", "scheduled_task"]
            risk_indicators = []

            if run_level and "highest" in run_level.lower():
                risk_indicators.append("runs_as_admin")
                tags.append("elevated_privileges")

            if hidden and hidden.lower() == "true":
                risk_indicators.append("hidden_task")
                tags.append("hidden")

            for action in actions:
                cmd = action.get("command", "").lower()
                args = action.get("arguments", "").lower()
                full_cmd = f"{cmd} {args}"

                # Check for suspicious patterns
                suspicious_patterns = [
                    "powershell", "cmd.exe", "wscript", "cscript", "mshta",
                    "regsvr32", "rundll32", "certutil", "bitsadmin",
                    "-enc", "-encoded", "-noprofile", "hidden",
                    "downloadstring", "invoke-expression", "iex",
                ]
                for pattern in suspicious_patterns:
                    if pattern in full_cmd:
                        risk_indicators.append(f"suspicious_command_{pattern}")
                        if "suspicious_execution" not in tags:
                            tags.append("suspicious_execution")
                        break

            if risk_indicators:
                raw["risk_indicators"] = risk_indicators

            # Extract executable info from first action
            process_name = None
            process_command_line = None
            process_executable = None

            if actions:
                first_action = actions[0]
                process_executable = first_action.get("command")
                if process_executable:
                    process_name = Path(process_executable).name
                    args = first_action.get("arguments", "")
                    process_command_line = f"{process_executable} {args}".strip()

            yield ParsedEvent(
                timestamp=registration_date,
                message=message,
                source_type="windows_scheduled_tasks",
                source_file=source_str,
                event_kind="event",
                event_category=["configuration", "process"],
                event_type=["creation", "info"],
                event_action="scheduled_task_created",
                user_name=user_id,
                process_name=process_name,
                process_executable=process_executable,
                process_command_line=process_command_line,
                raw=raw,
                labels={
                    "task_name": task_name,
                    "author": author or "",
                },
                tags=tags,
            )

        except ET.ParseError as e:
            logger.error(f"Failed to parse XML {source_str}: {e}")
        except Exception as e:
            logger.error(f"Failed to parse scheduled task {source_str}: {e}")
            raise

    def _get_text(self, parent: Any, tag: str, ns: dict | None = None) -> str | None:
        """Safely get text from XML element."""
        if parent is None:
            return None

        if ns:
            elem = parent.find(tag, ns)
        else:
            elem = parent.find(tag)

        if elem is None and "{*}" in tag:
            # Try wildcard namespace
            for child in parent:
                if child.tag.endswith(tag.replace("{*}", "")):
                    return child.text

        return elem.text if elem is not None else None

    def _parse_trigger(self, trigger_elem: Any) -> dict | None:
        """Parse a trigger element."""
        try:
            trigger_type = trigger_elem.tag.split("}")[-1] if "}" in trigger_elem.tag else trigger_elem.tag

            trigger_info = {"type": trigger_type}

            # Get start boundary
            for child in trigger_elem:
                tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
                if tag == "StartBoundary" and child.text:
                    trigger_info["start_boundary"] = child.text
                elif tag == "Enabled":
                    trigger_info["enabled"] = child.text

            return trigger_info
        except Exception:
            return None

    def _parse_action(self, action_elem: Any) -> dict | None:
        """Parse an action element."""
        try:
            action_type = action_elem.tag.split("}")[-1] if "}" in action_elem.tag else action_elem.tag

            action_info = {"type": action_type}

            for child in action_elem:
                tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
                if tag == "Command" and child.text:
                    action_info["command"] = child.text
                elif tag == "Arguments" and child.text:
                    action_info["arguments"] = child.text
                elif tag == "WorkingDirectory" and child.text:
                    action_info["working_directory"] = child.text
                elif tag == "Path" and child.text:
                    action_info["path"] = child.text

            return action_info
        except Exception:
            return None
