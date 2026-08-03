"""Adapter base — the reverse-direction plugin contract.

Every store kind implements ``locate(subject_id) -> list[ResidueHit]``. The
``purge`` half (m2: per-hit deletion + hash-chained lineage) is declared on the
contract but raises ``NotImplementedError`` in this m1 build — adapters ship the
locate direction now and gain the delete direction at m2.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from subjectpurge.models import ResidueHit


class Adapter(ABC):
    """Reverse-direction agent-runtime store adapter."""

    kind: str = "base"

    def __init__(self, store_id: str, **opts: object) -> None:
        self.store_id = store_id
        self.opts = opts

    @abstractmethod
    def locate(self, subject_id: str) -> list[ResidueHit]:
        """Return every PII residue of ``subject_id`` found in this store."""
        raise NotImplementedError

    def purge(self, hit: ResidueHit) -> bool:
        """m2: delete one located residue and return True if a row was removed.

        Not in this m1 build — the deletion + hash-chained lineage pipeline is
        the m2 milestone. Adapters declare the contract now so m2 can fill it in
        without touching the scanner.
        """
        raise NotImplementedError(
            f"purge() for {self.kind!r} is the m2 milestone (per-hit deletion + "
            "hash-chained lineage.jsonl). Not implemented in this m1 build."
        )

    def close(self) -> None:
        """Release any file handles / connections. Default: no-op."""
        return None

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"<{type(self).__name__} store_id={self.store_id!r} kind={self.kind!r}>"
