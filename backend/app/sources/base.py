"""Abstract base class for all academic paper data sources — aligned with §9.1."""

from abc import ABC, abstractmethod

from app.schemas.paper import PaperMetadata


class PaperSource(ABC):
    """Unified abstract interface for academic data sources.

    All data sources must implement this interface. The Search Agent calls
    these methods via the SourceRegistry without knowing the concrete source.
    """

    @abstractmethod
    async def search(
        self, query: str, filters: dict | None = None
    ) -> list[PaperMetadata]:
        """Search for papers by keyword query.

        Args:
            query: Search query string.
            filters: Optional filters (year_range, min_citations, etc.).

        Returns:
            List of matching paper metadata.
        """
        ...

    @abstractmethod
    async def get_paper(self, paper_id: str) -> PaperMetadata | None:
        """Get detailed metadata for a single paper.

        Args:
            paper_id: Source-specific paper identifier.

        Returns:
            Paper metadata, or None if not found.
        """
        ...

    @abstractmethod
    async def get_citations(self, paper_id: str) -> list[PaperMetadata]:
        """Get papers that cite this paper.

        Args:
            paper_id: Source-specific paper identifier.

        Returns:
            List of citing paper metadata.
        """
        ...

    @abstractmethod
    async def get_references(self, paper_id: str) -> list[PaperMetadata]:
        """Get papers referenced by this paper.

        Args:
            paper_id: Source-specific paper identifier.

        Returns:
            List of referenced paper metadata.
        """
        ...
