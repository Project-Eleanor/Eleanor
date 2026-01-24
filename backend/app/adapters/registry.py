"""Adapter registry for discovering and managing integrations.

The registry provides a centralized way to:
- Load and configure adapters at startup
- Check adapter health status
- Access adapters by name throughout the application
"""

import logging
from typing import Any, Optional, Type

from app.adapters.base import (
    AdapterConfig,
    AdapterHealth,
    AdapterStatus,
    BaseAdapter,
    CaseManagementAdapter,
    CollectionAdapter,
    SOARAdapter,
    ThreatIntelAdapter,
    TimelineAdapter,
)

logger = logging.getLogger(__name__)


class AdapterRegistry:
    """Registry for managing Eleanor adapters.

    Usage:
        registry = AdapterRegistry()

        # Register adapters
        registry.register("velociraptor", VelociraptorAdapter)
        registry.register("iris", IRISAdapter)

        # Configure and initialize
        await registry.configure_from_settings(settings)

        # Access adapters
        velo = registry.get("velociraptor")
        if velo:
            endpoints = await velo.list_endpoints()
    """

    def __init__(self):
        """Initialize empty registry."""
        self._adapter_classes: dict[str, Type[BaseAdapter]] = {}
        self._adapters: dict[str, BaseAdapter] = {}
        self._configs: dict[str, AdapterConfig] = {}

    def register(
        self,
        name: str,
        adapter_class: Type[BaseAdapter],
    ) -> None:
        """Register an adapter class.

        Args:
            name: Unique adapter name.
            adapter_class: The adapter class (not instance).
        """
        if name in self._adapter_classes:
            logger.warning("Overwriting existing adapter registration: %s", name)
        self._adapter_classes[name] = adapter_class
        logger.debug("Registered adapter: %s", name)

    def configure(
        self,
        name: str,
        config: AdapterConfig,
    ) -> None:
        """Configure an adapter.

        Args:
            name: Adapter name (must be registered).
            config: Adapter configuration.

        Raises:
            ValueError: If adapter is not registered.
        """
        if name not in self._adapter_classes:
            raise ValueError(f"Unknown adapter: {name}")

        self._configs[name] = config

        if config.enabled:
            adapter_class = self._adapter_classes[name]
            self._adapters[name] = adapter_class(config)
            logger.info("Configured adapter: %s", name)
        else:
            # Remove instance if disabled
            self._adapters.pop(name, None)
            logger.debug("Adapter disabled: %s", name)

    async def configure_from_settings(self, settings: Any) -> None:
        """Configure all adapters from application settings.

        Expects settings to have adapter-specific configuration attributes.
        """
        adapter_settings = {
            "velociraptor": AdapterConfig(
                enabled=getattr(settings, "velociraptor_enabled", False),
                url=getattr(settings, "velociraptor_url", ""),
                api_key=getattr(settings, "velociraptor_api_key", ""),
                verify_ssl=getattr(settings, "velociraptor_verify_ssl", True),
                extra={
                    "client_cert": getattr(settings, "velociraptor_client_cert", ""),
                    "client_key": getattr(settings, "velociraptor_client_key", ""),
                },
            ),
            "iris": AdapterConfig(
                enabled=getattr(settings, "iris_enabled", False),
                url=getattr(settings, "iris_url", ""),
                api_key=getattr(settings, "iris_api_key", ""),
                verify_ssl=getattr(settings, "iris_verify_ssl", True),
            ),
            "opencti": AdapterConfig(
                enabled=getattr(settings, "opencti_enabled", False),
                url=getattr(settings, "opencti_url", ""),
                api_key=getattr(settings, "opencti_api_key", ""),
                verify_ssl=getattr(settings, "opencti_verify_ssl", True),
            ),
            "shuffle": AdapterConfig(
                enabled=getattr(settings, "shuffle_enabled", False),
                url=getattr(settings, "shuffle_url", ""),
                api_key=getattr(settings, "shuffle_api_key", ""),
                verify_ssl=getattr(settings, "shuffle_verify_ssl", True),
            ),
            "timesketch": AdapterConfig(
                enabled=getattr(settings, "timesketch_enabled", False),
                url=getattr(settings, "timesketch_url", ""),
                api_key=getattr(settings, "timesketch_api_key", ""),
                verify_ssl=getattr(settings, "timesketch_verify_ssl", True),
                extra={
                    "username": getattr(settings, "timesketch_username", ""),
                    "password": getattr(settings, "timesketch_password", ""),
                },
            ),
        }

        for name, config in adapter_settings.items():
            if name in self._adapter_classes:
                self.configure(name, config)

    def get(self, name: str) -> Optional[BaseAdapter]:
        """Get an adapter instance by name.

        Returns:
            Adapter instance if enabled, None otherwise.
        """
        return self._adapters.get(name)

    def get_collection(self) -> Optional[CollectionAdapter]:
        """Get the configured collection adapter."""
        adapter = self.get("velociraptor")
        if adapter and isinstance(adapter, CollectionAdapter):
            return adapter
        return None

    def get_case_management(self) -> Optional[CaseManagementAdapter]:
        """Get the configured case management adapter."""
        adapter = self.get("iris")
        if adapter and isinstance(adapter, CaseManagementAdapter):
            return adapter
        return None

    def get_threat_intel(self) -> Optional[ThreatIntelAdapter]:
        """Get the configured threat intel adapter."""
        adapter = self.get("opencti")
        if adapter and isinstance(adapter, ThreatIntelAdapter):
            return adapter
        return None

    def get_soar(self) -> Optional[SOARAdapter]:
        """Get the configured SOAR adapter."""
        adapter = self.get("shuffle")
        if adapter and isinstance(adapter, SOARAdapter):
            return adapter
        return None

    def get_timeline(self) -> Optional[TimelineAdapter]:
        """Get the configured timeline adapter."""
        adapter = self.get("timesketch")
        if adapter and isinstance(adapter, TimelineAdapter):
            return adapter
        return None

    def list_registered(self) -> list[str]:
        """List all registered adapter names."""
        return list(self._adapter_classes.keys())

    def list_enabled(self) -> list[str]:
        """List enabled adapter names."""
        return list(self._adapters.keys())

    async def health_check_all(self) -> dict[str, AdapterHealth]:
        """Check health of all enabled adapters.

        Returns:
            Dictionary mapping adapter name to health status.
        """
        results = {}

        for name, adapter in self._adapters.items():
            try:
                health = await adapter.health_check()
                results[name] = health
            except Exception as e:
                logger.error("Health check failed for %s: %s", name, e)
                results[name] = AdapterHealth(
                    adapter_name=name,
                    status=AdapterStatus.ERROR,
                    message=str(e),
                )

        # Include disabled adapters as disconnected
        for name in self._adapter_classes:
            if name not in results:
                config = self._configs.get(name)
                results[name] = AdapterHealth(
                    adapter_name=name,
                    status=AdapterStatus.DISCONNECTED,
                    message="Adapter not enabled" if not config or not config.enabled else "Not configured",
                )

        return results

    async def connect_all(self) -> dict[str, bool]:
        """Connect all enabled adapters.

        Returns:
            Dictionary mapping adapter name to connection success.
        """
        results = {}

        for name, adapter in self._adapters.items():
            try:
                results[name] = await adapter.connect()
            except Exception as e:
                logger.error("Connection failed for %s: %s", name, e)
                results[name] = False

        return results

    async def disconnect_all(self) -> None:
        """Disconnect all adapters."""
        for name, adapter in self._adapters.items():
            try:
                await adapter.disconnect()
            except Exception as e:
                logger.error("Disconnect failed for %s: %s", name, e)


# Global registry instance
_registry: Optional[AdapterRegistry] = None


def get_registry() -> AdapterRegistry:
    """Get the global adapter registry instance."""
    global _registry
    if _registry is None:
        _registry = AdapterRegistry()
    return _registry


async def init_adapters(settings: Any) -> AdapterRegistry:
    """Initialize adapters from settings.

    This should be called during application startup.
    """
    registry = get_registry()

    # Import and register adapters (lazy import to avoid circular deps)
    try:
        from app.adapters.velociraptor import VelociraptorAdapter

        registry.register("velociraptor", VelociraptorAdapter)
    except ImportError:
        logger.debug("Velociraptor adapter not available")

    try:
        from app.adapters.iris import IRISAdapter

        registry.register("iris", IRISAdapter)
    except ImportError:
        logger.debug("IRIS adapter not available")

    try:
        from app.adapters.opencti import OpenCTIAdapter

        registry.register("opencti", OpenCTIAdapter)
    except ImportError:
        logger.debug("OpenCTI adapter not available")

    try:
        from app.adapters.shuffle import ShuffleAdapter

        registry.register("shuffle", ShuffleAdapter)
    except ImportError:
        logger.debug("Shuffle adapter not available")

    try:
        from app.adapters.timesketch import TimesketchAdapter

        registry.register("timesketch", TimesketchAdapter)
    except ImportError:
        logger.debug("Timesketch adapter not available")

    # Configure from settings
    await registry.configure_from_settings(settings)

    # Connect enabled adapters
    await registry.connect_all()

    return registry
