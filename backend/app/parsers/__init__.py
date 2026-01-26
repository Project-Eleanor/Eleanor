"""Eleanor Evidence Parser System.

Provides extensible log and artifact parsing with automatic format detection
and normalization to standard schemas (ECS, OCSF).
"""

from app.parsers.base import BaseParser, ParsedEvent, ParserResult
from app.parsers.registry import ParserRegistry, get_parser, register_parser

__all__ = [
    "BaseParser",
    "ParsedEvent",
    "ParserResult",
    "ParserRegistry",
    "get_parser",
    "register_parser",
]
