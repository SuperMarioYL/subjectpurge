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
import re

from subjectpurge.adapters.base import Adapter
from subjectpurge.models import AdapterKind, ResidueHit, sha256_hex

# bytes of context captured around each match for the evidence hash
_EVIDENCE_CONTEXT = 48

# First glob metacharacter — everything before it is a literal path.
_GLOB_MAGIC = re.compile(r"[*?\[]")


def _static_root(pattern: str) -> str | None:
    """Deepest literal path before the first glob metacharacter.

    Used to tell a misregistered path (root missing -> fail loud) from a
    legitimately empty store (root exists, no matching files -> 0 hits).
    """
    match = _GLOB_MAGIC.search(pattern)
    if match is None:
        return pattern  # exact path — it must exist
    return os.path.dirname(pattern[: match.start()]) or None


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
        pattern = os.path.expanduser(self.glob)
        root = _static_root(pattern)
        if root is not None and not os.path.exists(root):
            # Fail loudly on a typo'd path: an empty match would otherwise read
            # as a false-clean 0-hit store (same rule as the sqlite/chroma
            # adapters). A root that exists with no files stays a clean store.
            raise FileNotFoundError(
                f"trace store {self.store_id!r}: no path at {root!r} (glob {self.glob!r})"
            )
        for file_path in glob_module.glob(pattern, recursive=True):
            if not os.path.isfile(file_path):
                continue
            try:
                with open(file_path, "rb") as fh:
                    raw = fh.read()
            except OSError as exc:
                # A matched file we cannot read is evidence we failed to
                # examine — it must never be silently skipped.
                raise OSError(
                    f"trace store {self.store_id!r}: cannot read {file_path!r}: {exc}"
                ) from exc
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
