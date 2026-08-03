"""Adapter plugins — one per agent-runtime store kind.

An adapter is the *reverse-direction* primitive: ``locate(subject) -> [hits]``
and (m2) ``purge(hit) -> bool``. The scanner fan-outs to every registered
adapter; results are merged into ``residue_map.json``.
"""

from __future__ import annotations

from subjectpurge.adapters.base import Adapter
from subjectpurge.adapters.chroma_vector import ChromaAdapter
from subjectpurge.adapters.sqlite_store import SQLiteAdapter
from subjectpurge.adapters.trace_text import TraceTextAdapter

__all__ = ["Adapter", "SQLiteAdapter", "ChromaAdapter", "TraceTextAdapter"]
