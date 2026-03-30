"""Data source registry — aligned with §9.2."""

from app.sources.base import PaperSource


class SourceRegistry:
    """Registry for managing all available PaperSource instances.

    Supports registering, enabling/disabling, and querying data sources.
    The Search Agent retrieves enabled sources at runtime without hard-coding.
    """

    def __init__(self) -> None:
        self._sources: dict[str, PaperSource] = {}
        self._enabled: set[str] = set()

    def register(
        self, name: str, source: PaperSource, enabled: bool = True
    ) -> None:
        """Register a data source instance."""
        self._sources[name] = source
        if enabled:
            self._enabled.add(name)

    def unregister(self, name: str) -> None:
        """Remove a data source."""
        self._sources.pop(name, None)
        self._enabled.discard(name)

    def enable(self, name: str) -> None:
        """Enable a registered data source."""
        if name in self._sources:
            self._enabled.add(name)

    def disable(self, name: str) -> None:
        """Disable a data source (kept registered, just excluded from searches)."""
        self._enabled.discard(name)

    def get_enabled_sources(self) -> list[tuple[str, PaperSource]]:
        """Return all currently enabled data sources."""
        return [
            (name, self._sources[name])
            for name in self._enabled
            if name in self._sources
        ]

    def get_source(self, name: str) -> PaperSource | None:
        """Get a specific data source by name."""
        return self._sources.get(name)
