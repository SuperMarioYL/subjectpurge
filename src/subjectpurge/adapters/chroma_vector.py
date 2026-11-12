"""Chroma vector adapter — locates a subject's PII in a persisted vector store.

Agent-memory runtimes persist embeddings + documents + metadata in a local Chroma
collection (PersistentClient, file-based, no server). This adapter scans every
record's document text and metadata values for the subject id and classifies hits
as ``embedded`` (id lives in the document) or ``summarized`` (id lives only in a
``summary``-ish metadata key, i.e. a derived/encoded residue — the load-bearing
case the lawyer gate must clear).

``chromadb`` is an optional extra (heavy native deps): ``pip install
subjectpurge[chroma]``. The import is lazy so the core package and the SQLite /
trace adapters work without it.
"""

from __future__ import annotations

import os

from subjectpurge.adapters.base import Adapter
from subjectpurge.models import AdapterKind, ResidueHit, sha256_hex

# Metadata keys whose presence signals a *derived/summarised* residue rather than
# a raw embedded one (the case 个保法/网信办 guidance may or may not cover).
_SUMMARY_META_HINTS = ("summary", "summarised", "summarized", "abstract", "digest")


class ChromaAdapter(Adapter):
    """Reverse-locate a subject's PII residue in a persisted Chroma collection."""

    kind = "chroma"
    required_fields = ("path",)

    def __init__(
        self,
        store_id: str,
        path: str,
        collection: str = "sessions",
        **_: object,
    ) -> None:
        super().__init__(store_id)
        self.path = path
        self.collection_name = collection

    def _client(self):  # type: ignore[no-untyped-def]
        # Fail loudly on a typo'd path: PersistentClient would silently create
        # the directory and the scan would report a false-clean 0-hit store.
        if not os.path.isdir(self.path):
            raise FileNotFoundError(
                f"chroma store {self.store_id!r}: no directory at {self.path!r}"
            )
        try:
            import chromadb  # noqa: PLC0415 — lazy, optional extra
        except ImportError as exc:  # exercised by the missing-extra test
            raise ValueError(
                f"chroma store {self.store_id!r}: Chroma support requires the "
                "optional 'chroma' extra (pip install subjectpurge[chroma])"
            ) from exc
        return chromadb.PersistentClient(path=self.path)

    def locate(self, subject_id: str) -> list[ResidueHit]:
        client = self._client()
        try:
            # list first: a broken backend must fail here, not read as "clean".
            # Only a genuinely absent collection means "no residue in this store".
            present = {getattr(c, "name", c) for c in client.list_collections()}
            if self.collection_name not in present:
                return []
            collection = client.get_collection(self.collection_name)
            res = collection.get()
        except Exception as exc:
            # A backend failure is a false "store is clean" if swallowed — the
            # worst failure mode for a deletion-request tool. Name the store and
            # let the CLI render it as one error line.
            raise ValueError(
                f"chroma store {self.store_id!r}: cannot read collection "
                f"{self.collection_name!r} at {self.path!r}: {exc}"
            ) from exc
        ids: list[str] = res.get("ids", []) or []
        docs: list[str | None] = res.get("documents", []) or []
        metas: list[dict] = res.get("metadatas", []) or []
        hits: list[ResidueHit] = []
        for i, doc in enumerate(docs):
            meta = metas[i] if i < len(metas) else {}
            doc_text = doc or ""
            meta_text = " ".join(str(v) for v in (meta or {}).values()) if meta else ""
            blob = f"{doc_text} {meta_text}".strip()
            if subject_id not in blob:
                continue
            # derived/summarised residue if id appears only in a summary-ish meta key
            in_summary_meta = (
                any(
                    subject_id in str(meta.get(k, ""))
                    for k in _SUMMARY_META_HINTS
                    if isinstance(meta, dict)
                )
                and subject_id not in doc_text
            )
            residue_kind = "summarized" if in_summary_meta else "embedded"
            vector_id = ids[i] if i < len(ids) else f"idx{i}"
            hits.append(
                ResidueHit(
                    store_id=self.store_id,
                    adapter=AdapterKind.chroma,
                    locator=f"{self.collection_name}:id={vector_id}",
                    residue_kind=residue_kind,
                    confidence=1.0,
                    evidence_hash=sha256_hex(blob.encode("utf-8")),
                )
            )
        return hits
