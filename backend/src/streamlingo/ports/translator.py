"""Translation boundary. Provider configuration belongs to the adapter."""

from typing import Protocol

from streamlingo.domain.models import TranslationRequest, TranslationResult


class TranslationProvider(Protocol):
    async def translate(self, request: TranslationRequest) -> TranslationResult:
        """Translate one stable segment; propagate cancellation to pending I/O.

        The application owns deadlines, bounded queues, and session identifiers.
        Adapters own provider payloads and response parsing. Implementations must
        mark synthetic output with is_mock=True.
        """
        ...
