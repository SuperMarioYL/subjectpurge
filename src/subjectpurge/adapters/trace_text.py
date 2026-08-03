"""Trace-text adapter — locates a subject's PII in compressed trace logs.

Agent runtimes write compressed session traces (appended text logs, JSONL turn
logs, etc.) to a glob of files. This adapter scans every matched file for the
subject id, emitting hits with byte-offset locators (``<file>:offset=<n>``) and
``trace_ref`` residue kind. Matching is deterministic literal substring; the
optional LLM fuzzy pass for ambiguous trace references is off by default.
"""

from __future__ import annotations

import glob as glob_module
import os

from subjectpurge.adapters.base import Adapter
from subjectpurge.models import AdapterKind, ResidueHit, sha256_hex

# bytes of context captured around each match for the evidence hash
_EVIDENCE_CONTEXT = 48


class TraceTextAdapter(Adapter):
    """Reverse-locate a subject's PII residue across a glob of trace text files."""

    kind = "trace_text"

    def __init__(self, store_id: str, glob: str, **_: object) -> None:
        super().__init__(store_id)
        self.glob = glob

    def locate(self, subject_id: str) -> list[ResidueHit]:
        hits: list[ResidueHit] = []
        for file_path in glob_module.glob(self.glob, recursive=True):
            if not os.path.isfile(file_path):
                continue
            try:
                with open(file_path, "rb") as fh:
                    raw = fh.read()
            except OSError:
                continue
            text = raw.decode("utf-8", errors="replace")
            search_from = 0
            while True:
                idx = text.find(subject_id, search_from)
                if idx == -1:
                    break
                # byte offset of the match (text[:idx] -> utf-8 bytes length)
                byte_offset = len(text[:idx].encode("utf-8", errors="replace"))
                ctx_start = max(0, idx - _EVIDENCE_CONTEXT)
                ctx_end = min(len(text), idx + len(subject_id) + _EVIDENCE_CONTEXT)
                evidence = text[ctx_start:ctx_end].encode("utf-8", errors="replace")
                hits.append(
                    ResidueHit(
                        store_id=self.store_id,
                        adapter=AdapterKind.trace_text,
                        locator=f"{file_path}:offset={byte_offset}",
                        residue_kind="trace_ref",
                        confidence=1.0,
                        evidence_hash=sha256_hex(evidence),
                    )
                )
                search_from = idx + max(1, len(subject_id))
        return hits
