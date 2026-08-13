from __future__ import annotations

from sqlalchemy.orm import Session

from packages.search import SearchResult, search


class CareveroReadOnlyTools:
    """Explicit allowlist of model-facing retrieval operations; no SQL surface."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def search_procedures(self, query: str) -> list[SearchResult]:
        return search(self._session, query[:100], entity_type="procedure")[:8]

    def search_payers(self, query: str) -> list[SearchResult]:
        # Payers are resolved by the normalized payer layer in intent.py. This
        # placeholder keeps the tool contract explicit without exposing tables.
        return []
