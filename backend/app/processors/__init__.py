"""Eleanor Case Processor System.

Provides automated case processing capabilities including:
- Auto-enrichment of IOCs on case creation
- Timeline sync to Timesketch on evidence upload
- Severity calculation based on IOCs and TTPs
"""

from app.processors.base import BaseProcessor, ProcessorResult, ProcessorTrigger
from app.processors.runner import ProcessorRunner, get_runner

__all__ = [
    "BaseProcessor",
    "ProcessorResult",
    "ProcessorTrigger",
    "ProcessorRunner",
    "get_runner",
]
