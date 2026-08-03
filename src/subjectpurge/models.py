"""Core data model — the per-subject deletion-lineage primitive.

See ``mvp_plan.md`` §2. The novel noun here is the *per-subject deletion-lineage
record*: a typed, append-only, hash-chained ledger binding a subject id to a list
of (store, locator, residue_kind, purged_at, prior_hash, evidence_hash) tuples,
sealed in a signed audit envelope.

The models themselves are real and shared across m1/m2/m3 — the *writing* of the
chained lineage (``lineage.jsonl``) is the m2 milestone, and the *signing* is m3.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# --------------------------------------------------------------------------- #
# enums / literals
# --------------------------------------------------------------------------- #


class AdapterKind(str, Enum):
    """Which agent-runtime store a residue hit lives in."""

    sqlite = "sqlite"
    chroma = "chroma"
    trace_text = "trace_text"
    # enterprise extension (graph store) — out of scope for v0.1; declared so a
    # future adapter can register without a model change.
    graph = "graph"


ResidueKind = Literal["direct_pii", "embedded", "summarized", "trace_ref"]

LawRef = Literal["PIPL-47", "CCPA-1798.105", "GDPR-17"]

# Genesis hash for the head of a fresh lineage chain (no prior record).
GENESIS_HASH = "0" * 64


# --------------------------------------------------------------------------- #
# hashing helpers
# --------------------------------------------------------------------------- #


def sha256_hex(data: bytes | str) -> str:
    """Stable sha256 hex digest used for evidence + chain hashing."""
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def utcnow() -> datetime:
    """TZ-aware UTC ``now`` — pydantic serialises this to ISO-8601 on dump."""
    return datetime.now(timezone.utc)


# --------------------------------------------------------------------------- #
# records
# --------------------------------------------------------------------------- #


class ResidueHit(BaseModel):
    """One located PII residue of a subject, in one store, pre-purge.

    ``locator`` is store-specific: ``<table>:rowid=<n>:<col>`` for SQLite,
    ``<collection>:id=<vector_id>`` for Chroma, ``<file>:offset=<bytes>`` for
    trace text. ``evidence_hash`` is the sha256 of the matched bytes *as found*
    (pre-purge) so an auditor can later prove what was deleted.
    """

    model_config = ConfigDict(use_enum_values=True)

    store_id: str
    adapter: AdapterKind
    locator: str
    residue_kind: ResidueKind
    confidence: float = 1.0
    evidence_hash: str


class ResidueMap(BaseModel):
    """Output of ``scan`` (m1) — the per-subject location map.

    This is the m1 deliverable: every located residue, by store, ready to hand
    to ``purge`` (m2) and ``audit`` (m3).
    """

    model_config = ConfigDict(use_enum_values=True)

    subject_id: str
    scanned_at: datetime
    operator: str
    hits: list[ResidueHit] = Field(default_factory=list)
    schema_version: str = "1"

    @property
    def total(self) -> int:
        return len(self.hits)

    def by_store(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for hit in self.hits:
            counts[hit.store_id] = counts.get(hit.store_id, 0) + 1
        return dict(sorted(counts.items()))


class PurgeRecord(BaseModel):
    """One append-only entry in the hash-chained ``lineage.jsonl`` (m2).

    ``prior_hash`` links to the previous record's ``self_hash`` (genesis = all
    zeros); ``self_hash`` is recomputed over the canonical serialisation of the
    record *minus* its own ``self_hash`` field, so the chain is tamper-evident.
    """

    model_config = ConfigDict(use_enum_values=True)

    subject_id: str
    hits: list[ResidueHit]
    purged_at: datetime
    operator: str
    prior_hash: str = GENESIS_HASH
    self_hash: str = ""

    def chain_payload(self) -> str:
        """Canonical payload over which ``self_hash`` is computed."""
        data = self.model_dump(mode="json", exclude={"self_hash"})
        # stable key order for a deterministic hash
        import json

        return json.dumps(data, ensure_ascii=False, sort_keys=True)

    def rehash(self) -> str:
        return sha256_hex(self.chain_payload())


class AuditProof(BaseModel):
    """Signed envelope sealing a purge record (m3) — the 等保2.0 audit proof.

    ``signature`` is an ed25519 detached signature over the purge record hash;
    ``runtime_env_hash`` binds the proof to the on-prem box it was issued on.
    """

    model_config = ConfigDict(use_enum_values=True)

    purge_record_hash: str
    subject_id: str
    law_ref: LawRef
    signed_at: datetime
    signature: str = ""
    runtime_env_hash: str = ""
    schema_version: str = "1"
