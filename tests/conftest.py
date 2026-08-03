"""Shared fixtures — a seeded 3-store agent-memory fixture.

The fixture seeds one subject's PII into exactly **7 places across 3 stores**
(SQLite agent-memory table + Chroma vector collection + compressed trace logs),
so the m1 done-criterion — ``scan`` shows "subject X's PII leaked to 7 places
across 3 stores" — is directly assertable.

The Chroma half needs the optional ``chroma`` extra (``pip install
subjectpurge[chroma]``). To stay fully offline, documents are added with
**explicit dummy embeddings**, so no embedding model is ever downloaded — the
locate direction only inspects documents + metadata, never computes embeddings.
"""

from __future__ import annotations

import sqlite3
import textwrap
from pathlib import Path
from typing import Any

import pytest
import yaml

# The canonical fixture subject — a CN mobile, the kind a 信创 合规 officer pastes
# in from a 个保法 deletion request.
SUBJECT = "13800138000"
# A decoy subject that must NOT match — proves the adapter is selective.
DECOY = "13900139000"


def seed_sqlite(db_path: Path, subject: str = SUBJECT, decoy: str = DECOY) -> None:
    """Seed a claude-mem style ``memories`` table with the subject's PII in 3 places."""
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            CREATE TABLE memories (
                rowid INTEGER PRIMARY KEY AUTOINCREMENT,
                session TEXT,
                phone TEXT,
                content TEXT,
                summary TEXT
            )
            """
        )
        # hit 1 — direct PII (phone column matches the subject)
        # hit 2 — embedded (subject id embedded in a free-text content column)
        # hit 3 — embedded (subject id embedded in a summary column)
        # plus one decoy row that must NOT match
        conn.executemany(
            "INSERT INTO memories (session, phone, content, summary) VALUES (?, ?, ?, ?)",
            [
                ("sess-A", subject, "user asked about billing", "n/a"),
                ("sess-B", "n/a", f"transcript: {subject} opened a ticket #42", "session notes"),
                ("sess-C", "n/a", "general chat", f"compressed summary for {subject} (derived)"),
                ("sess-D", decoy, f"decoy row about {decoy}", f"summary {decoy}"),
            ],
        )
        conn.commit()
    finally:
        conn.close()


def seed_trace(trace_dir: Path, subject: str = SUBJECT, decoy: str = DECOY) -> None:
    """Seed two trace-log files each carrying the subject id once (2 hits)."""
    trace_dir.mkdir(parents=True, exist_ok=True)
    (trace_dir / "agent-001.log").write_text(
        textwrap.dedent(
            f"""
            2026-08-03T09:12:01Z agent.run user={subject} tool=lookup billing
            2026-08-03T09:12:02Z agent.reply token=ok
            """
        ).lstrip(),
        encoding="utf-8",
    )
    (trace_dir / "agent-002.log").write_text(
        f"2026-08-03T10:00:00Z tool.call from {subject} args={{q:'invoice'}}\n",
        encoding="utf-8",
    )
    # a decoy file mentioning the decoy subject only — must not match
    (trace_dir / "agent-003.log").write_text(
        f"2026-08-03T11:00:00Z decoy {decoy} unrelated\n", encoding="utf-8"
    )


def seed_chroma(chroma_dir: Path, subject: str = SUBJECT, decoy: str = DECOY) -> bool:
    """Seed a persisted Chroma collection with the subject's PII in 2 places.

    Returns False (and is a no-op) if ``chromadb`` is not installed so callers
    can skip the chroma half of the fixture. Documents are added with explicit
    dummy embeddings so no embedding model is ever loaded (fully offline).
    """
    try:
        import chromadb
    except ImportError:
        return False
    client = chromadb.PersistentClient(path=str(chroma_dir))
    # dimension 384 matches the default MiniLM so the store is query-compatible
    # later; the locate direction never computes embeddings, so this is cosmetic.
    dim = 384
    collection = client.get_or_create_collection("sessions")
    collection.add(
        ids=["vec-1", "vec-2", "vec-3"],
        documents=[
            f"{subject} interaction transcript turn-1",
            "a transcript with no subject id",
            "another clean document",
        ],
        metadatas=[
            {"session": "sess-A", "kind": "transcript"},
            # the subject id lives ONLY in a summary-ish metadata key here ->
            # the load-bearing "summarized" residue the lawyer gate must clear
            {"session": "sess-B", "summary": f"derived summary for {subject}"},
            {"session": "sess-D"},
        ],
        embeddings=[[0.0] * dim, [0.0] * dim, [0.0] * dim],
    )
    # decoy doc must not match
    collection.add(
        ids=["vec-decoy"],
        documents=[f"decoy content about {decoy}"],
        metadatas=[{"session": "sess-X"}],
        embeddings=[[0.0] * dim],
    )
    return True


def write_stores_yaml(
    path: Path,
    *,
    db_path: Path,
    chroma_dir: Path | None,
    trace_dir: Path,
    operator: str = "sre-alice",
) -> None:
    stores: list[dict[str, Any]] = [
        {
            "id": "claude_mem",
            "kind": "sqlite",
            "path": str(db_path),
            "table": "memories",
            "text_columns": ["session", "phone", "content", "summary"],
        },
        {"id": "trace_logs", "kind": "trace_text", "glob": str(trace_dir / "**" / "*.log")},
    ]
    if chroma_dir is not None:
        stores.append(
            {"id": "vec_index", "kind": "chroma", "path": str(chroma_dir), "collection": "sessions"}
        )
    payload = {"operator": operator, "law_ref": "PIPL-47", "stores": stores}
    path.write_text(yaml.safe_dump(payload, allow_unicode=True), encoding="utf-8")


@pytest.fixture()
def three_store_fixture(tmp_path: Path):
    """Seed all 3 stores + write stores.yaml; returns paths + whether chroma is live."""
    db_path = tmp_path / "claude-mem.db"
    trace_dir = tmp_path / "trace"
    chroma_dir = tmp_path / "chroma"
    seed_sqlite(db_path)
    seed_trace(trace_dir)
    chroma_live = seed_chroma(chroma_dir)
    if not chroma_live:
        chroma_dir = None
    stores_yaml = tmp_path / "stores.yaml"
    write_stores_yaml(stores_yaml, db_path=db_path, chroma_dir=chroma_dir, trace_dir=trace_dir)
    return {
        "root": tmp_path,
        "db_path": db_path,
        "trace_dir": trace_dir,
        "chroma_dir": chroma_dir,
        "chroma_live": chroma_live,
        "stores_yaml": stores_yaml,
        "residue_out": tmp_path / "residue_map.json",
    }
