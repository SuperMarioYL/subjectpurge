"""清痕 SubjectPurge — per-subject deletion-lineage mapper.

Locate a data subject's PII residue across heterogeneous agent-memory stores
(SQLite / Chroma vector / compressed trace text), so a deletion request can be
answered surgically and audited. Reverse direction (recall -> delete), scoped per
subject, on-prem only (数据不出境).

m1 milestone: the **locate / scan** core — scanner fans out to registered
adapters and emits ``residue_map.json``. ``purge`` (m2: per-hit deletion +
hash-chained lineage) and ``audit``/``verify`` (m3: ed25519 signed 等保2.0
proof) are scaffolded as clearly-marked, not-yet-implemented stubs.
"""

from __future__ import annotations

__version__ = "0.1.0"

__all__ = ["__version__"]
