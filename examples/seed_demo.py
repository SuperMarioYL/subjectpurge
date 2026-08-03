#!/usr/bin/env python
"""Seed a 3-store agent-memory fixture for the SubjectPurge demo.

Creates a temp dir holding a claude-mem-style SQLite DB (3 residues), a
persisted Chroma collection (2 residues) and two trace-log files (2 residues) —
exactly 7 places where the subject's PII leaked — plus a ``stores.yaml`` ready
for ``subjectpurge scan``.

Usage::

    python examples/seed_demo.py /tmp/subjectpurge-demo
    subjectpurge scan --subject 13800138000 --config /tmp/subjectpurge-demo/stores.yaml \
        --out /tmp/subjectpurge-demo/residue_map.json

The fixture is fully offline (Chroma documents carry explicit dummy embeddings
so no embedding model is ever downloaded).
"""

from __future__ import annotations

import sqlite3
import sys
import textwrap
from pathlib import Path

import yaml

SUBJECT = "13800138000"
DECOY = "13900139000"


def seed_sqlite(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "CREATE TABLE memories ("
            "rowid INTEGER PRIMARY KEY AUTOINCREMENT, session TEXT, phone TEXT,"
            " content TEXT, summary TEXT)"
        )
        conn.executemany(
            "INSERT INTO memories (session, phone, content, summary) VALUES (?, ?, ?, ?)",
            [
                ("sess-A", SUBJECT, "user asked about billing", "n/a"),
                ("sess-B", "n/a", f"transcript: {SUBJECT} opened a ticket #42", "session notes"),
                ("sess-C", "n/a", "general chat", f"compressed summary for {SUBJECT} (derived)"),
                ("sess-D", DECOY, f"decoy row about {DECOY}", f"summary {DECOY}"),
            ],
        )
        conn.commit()
    finally:
        conn.close()


def seed_trace(trace_dir: Path) -> None:
    trace_dir.mkdir(parents=True, exist_ok=True)
    (trace_dir / "agent-001.log").write_text(
        textwrap.dedent(
            f"""
            2026-08-03T09:12:01Z agent.run user={SUBJECT} tool=lookup billing
            2026-08-03T09:12:02Z agent.reply token=ok
            """
        ).lstrip(),
        encoding="utf-8",
    )
    (trace_dir / "agent-002.log").write_text(
        f"2026-08-03T10:00:00Z tool.call from {SUBJECT} args={{q:'invoice'}}\n",
        encoding="utf-8",
    )


def seed_chroma(chroma_dir: Path) -> bool:
    try:
        import chromadb
    except ImportError:
        print(
            "  [warn] chromadb not installed — seeding only SQLite + trace (5 residues). "
            "Install the chroma extra for the full 7-place demo: pip install subjectpurge[chroma]",
            file=sys.stderr,
        )
        return False
    client = chromadb.PersistentClient(path=str(chroma_dir))
    dim = 384
    collection = client.get_or_create_collection("sessions")
    collection.add(
        ids=["vec-1", "vec-2", "vec-3"],
        documents=[
            f"{SUBJECT} interaction transcript turn-1",
            "a transcript with no subject id",
            "another clean document",
        ],
        metadatas=[
            {"session": "sess-A", "kind": "transcript"},
            {"session": "sess-B", "summary": f"derived summary for {SUBJECT}"},
            {"session": "sess-D"},
        ],
        embeddings=[[0.0] * dim, [0.0] * dim, [0.0] * dim],
    )
    collection.add(
        ids=["vec-decoy"],
        documents=[f"decoy content about {DECOY}"],
        metadatas=[{"session": "sess-X"}],
        embeddings=[[0.0] * dim],
    )
    return True


def main(root: str) -> None:
    root_path = Path(root)
    root_path.mkdir(parents=True, exist_ok=True)
    db_path = root_path / "claude-mem.db"
    trace_dir = root_path / "trace"
    chroma_dir = root_path / "chroma"
    seed_sqlite(db_path)
    seed_trace(trace_dir)
    chroma_live = seed_chroma(chroma_dir)
    stores = [
        {
            "id": "claude_mem",
            "kind": "sqlite",
            "path": str(db_path),
            "table": "memories",
            "text_columns": ["session", "phone", "content", "summary"],
        },
        {"id": "trace_logs", "kind": "trace_text", "glob": str(trace_dir / "**" / "*.log")},
    ]
    if chroma_live:
        stores.append(
            {"id": "vec_index", "kind": "chroma", "path": str(chroma_dir), "collection": "sessions"}
        )
    (root_path / "stores.yaml").write_text(
        yaml.safe_dump(
            {"operator": "sre-alice", "law_ref": "PIPL-47", "stores": stores}, allow_unicode=True
        ),
        encoding="utf-8",
    )
    print(f"seeded fixture at {root_path}")
    print(f"  sqlite : {db_path}  (3 residues)")
    print(f"  trace  : {trace_dir}  (2 residues)")
    if chroma_live:
        print(f"  chroma : {chroma_dir}  (2 residues)")
    print(
        f"  total  : {7 if chroma_live else 5} residues across {3 if chroma_live else 2} store(s)"
    )
    print(f"  config : {root_path / 'stores.yaml'}")


if __name__ == "__main__":
    root = sys.argv[1] if len(sys.argv) > 1 else "/tmp/subjectpurge-demo"
    main(root)
