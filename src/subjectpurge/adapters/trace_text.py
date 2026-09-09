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
    required_fields = ("glob",)

    def __init__(self, store_id: str, glob: str, **_: object) -> None:
        super().__init__(store_id)
        self.glob = glob

    def locate(self, subject_id: str) -> list[ResidueHit]:
        hits: list[ResidueHit] = []
        needle = subject_id.encode("utf-8")
        if not needle:
            return hits
        for file_path in glob_module.glob(self.glob, recursive=True):
            if not os.path.isfile(file_path):
                continue
            try:
                with open(file_path, "rb") as fh:
                    raw = fh.read()
            except OSError:
                continue
            # search the raw bytes so the reported offset is a true byte offset
            # into the file (decoding with errors="replace" then re-encoding
            # would skew offsets on non-UTF-8 content)
            search_from = 0
            while True:
                idx = raw.find(needle, search_from)
                if idx == -1:
                    break
                ctx_start = max(0, idx - _EVIDENCE_CONTEXT)
                ctx_end = min(len(raw), idx + len(needle) + _EVIDENCE_CONTEXT)
                evidence = raw[ctx_start:ctx_end]
                hits.append(
                    ResidueHit(
                        store_id=self.store_id,
                        adapter=AdapterKind.trace_text,
                        locator=f"{file_path}:offset={idx}",
                        residue_kind="trace_ref",
                        confidence=1.0,
                        evidence_hash=sha256_hex(evidence),
                    )
                )
                search_from = idx + len(needle)
        return hits
