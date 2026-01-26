"""Parser registry for dynamic parser loading and selection.

The registry maintains a collection of available parsers and provides
methods to find the appropriate parser for a given input.
"""

import logging
from pathlib import Path
from typing import Type

from app.parsers.base import BaseParser, ParserCategory

logger = logging.getLogger(__name__)


class ParserRegistry:
    """Central registry for evidence parsers.

    Maintains a collection of parser classes and provides methods
    to find appropriate parsers for different input types.
    """

    def __init__(self):
        self._parsers: dict[str, Type[BaseParser]] = {}
        self._by_extension: dict[str, list[str]] = {}
        self._by_category: dict[ParserCategory, list[str]] = {}

    def register(self, parser_class: Type[BaseParser]) -> None:
        """Register a parser class.

        Args:
            parser_class: Parser class to register
        """
        parser = parser_class()
        name = parser.name

        if name in self._parsers:
            logger.warning(f"Parser '{name}' already registered, overwriting")

        self._parsers[name] = parser_class

        # Index by extension
        for ext in parser.supported_extensions:
            ext = ext.lower().lstrip(".")
            if ext not in self._by_extension:
                self._by_extension[ext] = []
            self._by_extension[ext].append(name)

        # Index by category
        category = parser.category
        if category not in self._by_category:
            self._by_category[category] = []
        self._by_category[category].append(name)

        logger.debug(f"Registered parser: {name}")

    def unregister(self, name: str) -> bool:
        """Unregister a parser by name.

        Args:
            name: Name of parser to unregister

        Returns:
            True if parser was found and removed
        """
        if name not in self._parsers:
            return False

        parser_class = self._parsers.pop(name)
        parser = parser_class()

        # Remove from extension index
        for ext in parser.supported_extensions:
            ext = ext.lower().lstrip(".")
            if ext in self._by_extension and name in self._by_extension[ext]:
                self._by_extension[ext].remove(name)

        # Remove from category index
        category = parser.category
        if category in self._by_category and name in self._by_category[category]:
            self._by_category[category].remove(name)

        return True

    def get(self, name: str) -> BaseParser | None:
        """Get a parser instance by name.

        Args:
            name: Name of parser to get

        Returns:
            Parser instance or None if not found
        """
        parser_class = self._parsers.get(name)
        return parser_class() if parser_class else None

    def get_by_extension(self, extension: str) -> list[BaseParser]:
        """Get all parsers that support a file extension.

        Args:
            extension: File extension (with or without leading dot)

        Returns:
            List of parser instances
        """
        ext = extension.lower().lstrip(".")
        names = self._by_extension.get(ext, [])
        return [self._parsers[name]() for name in names if name in self._parsers]

    def get_by_category(self, category: ParserCategory) -> list[BaseParser]:
        """Get all parsers in a category.

        Args:
            category: Parser category

        Returns:
            List of parser instances
        """
        names = self._by_category.get(category, [])
        return [self._parsers[name]() for name in names if name in self._parsers]

    def find_parser(
        self,
        file_path: Path | None = None,
        content: bytes | None = None,
        hint: str | None = None,
    ) -> BaseParser | None:
        """Find the best parser for given input.

        Uses multiple strategies:
        1. If hint provided, try that parser first
        2. Check parsers by file extension
        3. Try all parsers with can_parse()

        Args:
            file_path: Path to file to parse
            content: File content or first N bytes for detection
            hint: Parser name hint

        Returns:
            Best matching parser or None
        """
        # Strategy 1: Use hint if provided
        if hint:
            parser = self.get(hint)
            if parser and parser.can_parse(file_path, content):
                return parser

        # Strategy 2: Check by extension
        if file_path:
            ext = file_path.suffix.lower().lstrip(".")
            for parser in self.get_by_extension(ext):
                if parser.can_parse(file_path, content):
                    return parser

        # Strategy 3: Try all parsers
        for parser_class in self._parsers.values():
            parser = parser_class()
            try:
                if parser.can_parse(file_path, content):
                    return parser
            except Exception as e:
                logger.debug(f"Parser {parser.name} check failed: {e}")
                continue

        return None

    def list_parsers(self) -> list[dict]:
        """List all registered parsers.

        Returns:
            List of parser info dictionaries
        """
        result = []
        for name, parser_class in self._parsers.items():
            parser = parser_class()
            result.append({
                "name": name,
                "description": parser.description,
                "category": parser.category.value,
                "extensions": parser.supported_extensions,
                "mime_types": parser.supported_mime_types,
            })
        return result


# Global registry instance
_registry = ParserRegistry()


def get_registry() -> ParserRegistry:
    """Get the global parser registry."""
    return _registry


def register_parser(parser_class: Type[BaseParser]) -> Type[BaseParser]:
    """Decorator to register a parser class.

    Usage:
        @register_parser
        class MyParser(BaseParser):
            ...
    """
    _registry.register(parser_class)
    return parser_class


def get_parser(
    file_path: Path | None = None,
    content: bytes | None = None,
    hint: str | None = None,
) -> BaseParser | None:
    """Find a parser for the given input.

    Convenience function that uses the global registry.

    Args:
        file_path: Path to file to parse
        content: File content or first N bytes
        hint: Parser name hint

    Returns:
        Best matching parser or None
    """
    return _registry.find_parser(file_path, content, hint)


def load_builtin_parsers() -> None:
    """Load all built-in parsers.

    Called during application startup to register default parsers.
    """
    # Import parser modules to trigger registration
    from app.parsers.formats import evtx, json as json_parser  # noqa: F401

    # Import Dissect-based parsers
    try:
        from app.parsers.formats import (
            registry_hive,
            prefetch,
            mft,
            scheduled_tasks,
            browser_chrome,
            linux_auth,
            pcap,
            usn_journal,
            linux_syslog,
            browser_firefox,
        )  # noqa: F401
    except ImportError as e:
        logger.warning(f"Some parsers unavailable due to missing dependencies: {e}")

    logger.info(f"Loaded {len(_registry._parsers)} built-in parsers")
