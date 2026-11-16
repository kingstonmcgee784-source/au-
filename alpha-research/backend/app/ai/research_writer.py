"""Interface for AI-generated research reports."""

from typing import Protocol

from app.core.config import Settings


class ResearchWriter(Protocol):
    name: str

    def write_report(self, ticker: str, context: dict[str, object]) -> str:
        """Return a Markdown report built only from the supplied context."""
        ...


def get_research_writer(settings: Settings) -> ResearchWriter | None:
    """Return the configured AI writer, or None. No AI integration exists yet."""
    _ = settings.ai_provider
    return None
