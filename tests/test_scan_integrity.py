"""v0.2.0 scan-integrity tests — unique/byte-true locators + fail-loud stores.

Regressions for the v0.2.0 fix milestones:

- m4: every locator in ``residue_map.json`` must uniquely identify its hit
  (true sqlite rowid) and trace offsets must be true byte offsets into the
  raw file, even when the content is not valid UTF-8.
- m5: a misregistered store must fail loudly (store id + field named) instead
  of crashing with a raw TypeError, silently reporting a false-clean 0-hit
  store, or leaving a stray empty database behind.
- m6: the ``audit`` subcommand must thread its documented options through.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from subjectpurge import audit as audit_mod
from subjectpurge.cli import app
from subjectpurge.config import StoreConfig
from subjectpurge.models import sha256_hex
from subjectpurge.scanner import build_adapter, scan

try:  # chromadb is an optional extra
    import chromadb  # noqa: F401

    _HAS_CHROMA = True
except ImportError:  # pragma: no cover
    _HAS_CHROMA = False

needs_chroma = pytest.mark.skipif(not _HAS_CHROMA, reason="chroma extra not installed")

runner = CliRunner()
SUBJECT = "13800138000"


def _write_stores_yaml(path: Path, stores: list[dict]) -> Path:
    path.write_text(
        yaml.safe_dump(
            {"operator": "sre-alice", "law_ref": "PIPL-47", "stores": stores},
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    return path


# --------------------------------------------------------------------------- #
# m4 — sqlite locators carry the true rowid
# --------------------------------------------------------------------------- #


def test_sqlite_locators_unique_without_explicit_rowid_column(tmp_path):
    """Two distinct rows sharing a first-column value must not collapse into
    one locator — v0.1.0 emitted ``notes:rowid=sess-A:content`` twice."""
    db = tmp_path / "agent.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE notes (session TEXT, content TEXT)")  # no rowid col
    conn.executemany(
        "INSERT INTO notes (session, content) VALUES (?, ?)",
        [
            ("sess-A", f"ticket opened by {SUBJECT}"),
            ("sess-A", f"follow-up from {SUBJECT}"),
        ],
    )
    conn.commit()
    conn.close()

    stores_yaml = _write_stores_yaml(
        tmp_path / "stores.yaml",
        [
            {
                "id": "notes_db",
                "kind": "sqlite",
                "path": str(db),
                "table": "notes",
                "text_columns": ["content"],
            }
        ],
    )
    residue = scan(SUBJECT, stores_yaml, tmp_path / "residue_map.json")
    assert residue.total == 2
    locators = [h.locator for h in residue.hits]
    # one unique locator per row, carrying the true implicit rowids 1 and 2
    assert len(set(locators)) == 2
    assert sorted(locators) == ["notes:rowid=1:content", "notes:rowid=2:content"]


# --------------------------------------------------------------------------- #
# m4 — trace offsets are true byte offsets
# --------------------------------------------------------------------------- #


def test_trace_offset_true_on_non_utf8_content(tmp_path):
    """A non-UTF-8 byte before the match must not skew the reported offset —
    v0.1.0 reported offset=13 for a subject actually sitting at byte 11."""
    trace_dir = tmp_path / "trace"
    trace_dir.mkdir()
    log = trace_dir / "agent.log"
    payload = b"\xff" + b"x" * 10 + SUBJECT.encode() + b" tail\n"
    log.write_bytes(payload)

    stores_yaml = _write_stores_yaml(
        tmp_path / "stores.yaml",
        [{"id": "trace_logs", "kind": "trace_text", "glob": str(trace_dir / "*.log")}],
    )
    residue = scan(SUBJECT, stores_yaml, tmp_path / "residue_map.json")
    assert residue.total == 1
    assert residue.hits[0].locator == f"{log}:offset={payload.find(SUBJECT.encode())}"


def test_trace_offsets_true_on_utf8_fixture(three_store_fixture):
    """Byte-level search reproduces the v0.1.0 behaviour on clean UTF-8 files:
    each reported offset is exactly where the subject sits in the raw bytes."""
    fx = three_store_fixture
    residue = scan(SUBJECT, fx["stores_yaml"], fx["residue_out"])
    trace_hits = [h for h in residue.hits if h.adapter == "trace_text"]
    assert len(trace_hits) == 2
    for hit in trace_hits:
        file_path, _, offset = hit.locator.rpartition(":offset=")
        raw = Path(file_path).read_bytes()
        assert int(offset) == raw.find(SUBJECT.encode())
        # evidence window is byte-exact around the match
        idx = int(offset)
        expected = raw[max(0, idx - 48) : idx + len(SUBJECT) + 48]
        assert hit.evidence_hash == sha256_hex(expected)


# --------------------------------------------------------------------------- #
# m5 — misregistered stores fail loudly
# --------------------------------------------------------------------------- #


def test_sqlite_store_missing_path_raises_value_error_naming_store(tmp_path):
    stores_yaml = _write_stores_yaml(
        tmp_path / "stores.yaml", [{"id": "broken", "kind": "sqlite", "table": "memories"}]
    )
    with pytest.raises(ValueError, match=r"store 'broken'.*missing required field.*path"):
        scan(SUBJECT, stores_yaml, tmp_path / "residue_map.json")


def test_trace_store_missing_glob_raises_value_error_naming_store(tmp_path):
    stores_yaml = _write_stores_yaml(
        tmp_path / "stores.yaml", [{"id": "broken", "kind": "trace_text"}]
    )
    with pytest.raises(ValueError, match=r"store 'broken'.*missing required field.*glob"):
        scan(SUBJECT, stores_yaml, tmp_path / "residue_map.json")


def test_build_adapter_missing_path_error_names_store_and_field():
    with pytest.raises(ValueError, match=r"'broken'.*path"):
        build_adapter(StoreConfig(id="broken", kind="sqlite", table="memories"))


def test_missing_sqlite_db_file_raises_and_creates_no_stray_file(tmp_path):
    """v0.1.0 silently created an empty db and reported a false-clean 0-hit
    store; scan must refuse instead."""
    missing_db = tmp_path / "typo.db"  # parent exists, file does not
    stores_yaml = _write_stores_yaml(
        tmp_path / "stores.yaml",
        [{"id": "claude_mem", "kind": "sqlite", "path": str(missing_db)}],
    )
    with pytest.raises(FileNotFoundError, match="claude_mem"):
        scan(SUBJECT, stores_yaml, tmp_path / "residue_map.json")
    assert not missing_db.exists()


def test_missing_sqlite_table_raises_instead_of_silent_clean(tmp_path):
    db = tmp_path / "agent.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE memories (session TEXT, content TEXT)")
    conn.execute("INSERT INTO memories VALUES ('sess-A', 'clean')")
    conn.commit()
    conn.close()
    stores_yaml = _write_stores_yaml(
        tmp_path / "stores.yaml",
        [
            {
                "id": "claude_mem",
                "kind": "sqlite",
                "path": str(db),
                "table": "typo_table",
            }
        ],
    )
    with pytest.raises(ValueError, match="typo_table"):
        scan(SUBJECT, stores_yaml, tmp_path / "residue_map.json")


@needs_chroma
def test_missing_chroma_dir_raises_and_creates_no_stray_dir(tmp_path):
    missing_dir = tmp_path / "no-chroma"
    stores_yaml = _write_stores_yaml(
        tmp_path / "stores.yaml",
        [{"id": "vec_index", "kind": "chroma", "path": str(missing_dir), "collection": "sessions"}],
    )
    with pytest.raises(FileNotFoundError, match="vec_index"):
        scan(SUBJECT, stores_yaml, tmp_path / "residue_map.json")
    assert not missing_dir.exists()


def test_cli_scan_missing_store_file_fails_loud(tmp_path):
    """The CLI surfaces the loud failure as a non-zero exit, not a 0-hit map."""
    stores_yaml = _write_stores_yaml(
        tmp_path / "stores.yaml",
        [{"id": "claude_mem", "kind": "sqlite", "path": str(tmp_path / "typo.db")}],
    )
    result = runner.invoke(app, ["scan", "--subject", SUBJECT, "--config", str(stores_yaml)])
    assert result.exit_code != 0
    assert isinstance(result.exception, FileNotFoundError)


# --------------------------------------------------------------------------- #
# m6 — audit CLI threads its documented options
# --------------------------------------------------------------------------- #


def test_audit_entrypoint_accepts_and_refuses_with_paths():
    """The stub still refuses (m3), but now accepts the CLI's paths."""
    with pytest.raises(NotImplementedError, match="m3"):
        audit_mod.audit(SUBJECT, residue="r.json", lineage="l.jsonl", out="proof.json")


def test_cli_audit_threads_options_into_entrypoint(monkeypatch):
    seen: dict[str, str] = {}

    def fake_audit(subject_id, residue="r", lineage="l", out="o"):
        seen.update(subject=subject_id, residue=residue, lineage=lineage, out=out)
        raise RuntimeError("stop-here")  # prove the CLI called through

    monkeypatch.setattr(audit_mod, "audit", fake_audit)
    result = runner.invoke(
        app,
        [
            "audit",
            "--subject",
            SUBJECT,
            "--residue",
            "custom-map.json",
            "--lineage",
            "custom-lineage.jsonl",
            "--out",
            "custom-proof.json",
        ],
    )
    assert isinstance(result.exception, RuntimeError)
    assert seen == {
        "subject": SUBJECT,
        "residue": "custom-map.json",
        "lineage": "custom-lineage.jsonl",
        "out": "custom-proof.json",
    }
