import json
import sqlite3
import tempfile
from pathlib import Path

from subjectpurge.config import SubjectPurgeConfig
from subjectpurge.scanner import Scanner

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    db = root / "memory.db"
    trace = root / "trace.log"
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE memories (content TEXT)")
        conn.executemany(
            "INSERT INTO memories VALUES (?)",
            [("Contact demo@example.com",), ("Unrelated note",)],
        )
    trace.write_text("Read contact demo@example.com\nUnrelated event\n")
    config = SubjectPurgeConfig.from_dict(
        {
            "operator": "demo",
            "stores": [
                {
                    "id": "notes",
                    "kind": "sqlite",
                    "path": str(db),
                    "table": "memories",
                    "text_columns": ["content"],
                },
                {"id": "traces", "kind": "trace_text", "glob": str(trace)},
            ],
        }
    )
    residue = Scanner(config).locate("demo@example.com")
    print(
        json.dumps(
            {
                "subject": residue.subject_id,
                "hits": [
                    {"store": h.store_id, "adapter": h.adapter, "kind": h.residue_kind}
                    for h in residue.hits
                ],
            },
            indent=2,
        )
    )
    with sqlite3.connect(db) as conn:
        count = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
        print("database rows after scan:", count)
