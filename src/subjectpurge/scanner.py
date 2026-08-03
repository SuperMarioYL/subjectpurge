"""Scanner — the m1 core: fan-out adapters, merge hits, write residue_map.json.

Given a subject id and a ``stores.yaml`` registry, the scanner instantiates one
adapter per registered store, asks each ``locate(subject_id) -> [ResidueHit]``,
and merges the results into a single ``ResidueMap`` (the m1 deliverable).
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path

from subjectpurge.adapters.base import Adapter
from subjectpurge.adapters.chroma_vector import ChromaAdapter
from subjectpurge.adapters.sqlite_store import SQLiteAdapter
from subjectpurge.adapters.trace_text import TraceTextAdapter
from subjectpurge.config import StoreConfig, SubjectPurgeConfig
from subjectpurge.models import ResidueHit, ResidueMap, utcnow

# kind -> adapter class. The graph-store kind is deliberately absent here
# (enterprise extension, out of scope for v0.1); build_adapter raises on it.
_ADAPTERS: dict[str, type[Adapter]] = {
    "sqlite": SQLiteAdapter,
    "chroma": ChromaAdapter,
    "trace_text": TraceTextAdapter,
}


def build_adapter(store: StoreConfig) -> Adapter:
    """Instantiate the adapter for one ``StoreConfig``."""
    cls = _ADAPTERS.get(store.kind)
    if cls is None:
        raise ValueError(
            f"no adapter registered for store kind {store.kind!r} (store id={store.id!r}). "
            "The graph-store adapter is an enterprise extension and is not in v0.1."
        )
    fields = store.model_dump(exclude={"id", "kind"})
    fields = {k: v for k, v in fields.items() if v is not None}
    return cls(store_id=store.id, **fields)


class Scanner:
    """Fan-out locator over every registered adapter."""

    def __init__(self, config: SubjectPurgeConfig) -> None:
        self.config = config

    def locate(self, subject_id: str) -> ResidueMap:
        hits: list[ResidueHit] = []
        for store in self.config.stores:
            adapter = build_adapter(store)
            try:
                hits.extend(adapter.locate(subject_id))
            finally:
                adapter.close()
        return ResidueMap(
            subject_id=subject_id,
            scanned_at=utcnow(),
            operator=self.config.operator,
            hits=hits,
        )


def write_residue_map(residue: ResidueMap, out: str | Path = "residue_map.json") -> Path:
    """Persist a ``ResidueMap`` as pretty JSON (UTF-8, sorted stores)."""
    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = residue.model_dump(mode="json")
    out_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return out_path


def scan(
    subject_id: str, config_path: str | Path, out: str | Path = "residue_map.json"
) -> ResidueMap:
    """Run the full m1 happy path: load config -> scan -> write residue_map.json."""
    config = SubjectPurgeConfig.from_yaml(config_path)
    residue = Scanner(config).locate(subject_id)
    write_residue_map(residue, out)
    return residue


def iter_stores(config: SubjectPurgeConfig) -> Iterable[tuple[StoreConfig, Adapter]]:
    """Yield (store, adapter) pairs — used by tests to assert fan-out wiring."""
    for store in config.stores:
        yield store, build_adapter(store)
