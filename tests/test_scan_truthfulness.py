"""v0.4.0 scan-truthfulness tests — a scan must never lie about being clean.

Regressions for the v0.4.0 fix milestones: a broken or unavailable Chroma
backend, a misregistered trace path, an unreadable trace file, a blank subject,
an empty registry and a duplicate store id must fail loud instead of producing a
misleading residue map (or an all-match one).
"""

from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from subjectpurge.adapters.chroma_vector import ChromaAdapter
from subjectpurge.cli import app
from subjectpurge.config import SubjectPurgeConfig
from subjectpurge.scanner import scan

try:  # chromadb is an optional extra
    import chromadb

    _HAS_CHROMA = True
except ImportError:  # pragma: no cover
    _HAS_CHROMA = False

needs_chroma = pytest.mark.skipif(not _HAS_CHROMA, reason="chroma extra not installed")

runner = CliRunner()
SUBJECT = "13800138000"


def _stores_yaml(path: Path, stores: list[dict]) -> Path:
    path.write_text(
        yaml.safe_dump(
            {"operator": "sre-alice", "law_ref": "PIPL-47", "stores": stores},
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    return path


def _clean_memories_db(tmp_path: Path) -> Path:
    db = tmp_path / "agent.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE memories (content TEXT)")
    conn.executemany(
        "INSERT INTO memories VALUES (?)", [("unrelated note",), ("another clean row",)]
    )
    conn.commit()
    conn.close()
    return db


def _matching_memories_db(tmp_path: Path) -> Path:
    db = tmp_path / "agent.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE memories (content TEXT)")
    conn.execute("INSERT INTO memories VALUES (?)", (f"contact {SUBJECT}",))
    conn.commit()
    conn.close()
    return db


# --------------------------------------------------------------------------- #
# Chroma — a broken backend must not read as a clean store
# --------------------------------------------------------------------------- #


@needs_chroma
def test_chroma_backend_error_is_not_a_clean_scan(tmp_path, monkeypatch):
    class BrokenClient:
        def list_collections(self):
            raise RuntimeError("backend down")

    monkeypatch.setattr(chromadb, "PersistentClient", lambda path: BrokenClient())
    stores = _stores_yaml(
        tmp_path / "stores.yaml",
        [{"id": "vec", "kind": "chroma", "path": str(tmp_path), "collection": "sessions"}],
    )
    with pytest.raises(ValueError, match=r"vec.*backend down"):
        scan(SUBJECT, stores, tmp_path / "residue_map.json")


@needs_chroma
def test_chroma_absent_collection_is_a_legitimate_clean_store(tmp_path, monkeypatch):
    class EmptyClient:
        def list_collections(self):
            return []

        def get_collection(self, name):  # pragma: no cover - must not be reached
            raise AssertionError("an absent collection must not be opened")

    monkeypatch.setattr(chromadb, "PersistentClient", lambda path: EmptyClient())
    stores = _stores_yaml(
        tmp_path / "stores.yaml",
        [{"id": "vec", "kind": "chroma", "path": str(tmp_path), "collection": "sessions"}],
    )
    residue = scan(SUBJECT, stores, tmp_path / "residue_map.json")
    assert residue.total == 0


def test_chroma_missing_extra_names_the_install_command(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "chromadb", None)
    adapter = ChromaAdapter(store_id="vec", path=str(tmp_path), collection="sessions")
    with pytest.raises(ValueError, match=r"vec.*optional 'chroma' extra"):
        adapter.locate(SUBJECT)


def test_cli_scan_missing_chroma_extra_is_one_line(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "chromadb", None)
    stores = _stores_yaml(
        tmp_path / "stores.yaml",
        [{"id": "vec", "kind": "chroma", "path": str(tmp_path), "collection": "sessions"}],
    )
    result = runner.invoke(
        app,
        ["scan", "--subject", SUBJECT, "--config", str(stores), "--out", str(tmp_path / "r.json")],
    )
    assert result.exit_code == 1
    assert result.stderr.startswith("error:")
    assert "optional 'chroma' extra" in result.stderr
    assert "Traceback" not in result.output


# --------------------------------------------------------------------------- #
# Trace — a misregistered path or an unreadable file must fail loud
# --------------------------------------------------------------------------- #


def test_trace_glob_with_missing_root_fails_loud(tmp_path):
    stores = _stores_yaml(
        tmp_path / "stores.yaml",
        [
            {
                "id": "traces",
                "kind": "trace_text",
                "glob": str(tmp_path / "missing" / "**" / "*.log"),
            }
        ],
    )
    with pytest.raises(FileNotFoundError, match=r"traces.*no path"):
        scan(SUBJECT, stores, tmp_path / "residue_map.json")


def test_trace_existing_empty_root_is_a_clean_store(tmp_path):
    trace_dir = tmp_path / "trace"
    trace_dir.mkdir()
    stores = _stores_yaml(
        tmp_path / "stores.yaml",
        [{"id": "traces", "kind": "trace_text", "glob": str(trace_dir / "*.log")}],
    )
    residue = scan(SUBJECT, stores, tmp_path / "residue_map.json")
    assert residue.total == 0


@pytest.mark.skipif(
    hasattr(os, "geteuid") and os.geteuid() == 0,
    reason="root bypasses file permissions",
)
def test_trace_unreadable_matched_file_fails_loud(tmp_path):
    trace_dir = tmp_path / "trace"
    trace_dir.mkdir()
    log = trace_dir / "agent.log"
    log.write_text(f"user {SUBJECT} here\n", encoding="utf-8")
    log.chmod(0o000)
    try:
        stores = _stores_yaml(
            tmp_path / "stores.yaml",
            [{"id": "traces", "kind": "trace_text", "glob": str(trace_dir / "*.log")}],
        )
        with pytest.raises(OSError, match=r"traces.*cannot read"):
            scan(SUBJECT, stores, tmp_path / "residue_map.json")
    finally:
        log.chmod(0o644)


# --------------------------------------------------------------------------- #
# Meaningless subject / registry
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("subject", ["", "   "])
def test_blank_subject_is_refused(tmp_path, subject):
    db = _clean_memories_db(tmp_path)
    stores = _stores_yaml(
        tmp_path / "stores.yaml",
        [{"id": "notes", "kind": "sqlite", "path": str(db), "table": "memories"}],
    )
    with pytest.raises(ValueError, match="non-empty string"):
        scan(subject, stores, tmp_path / "residue_map.json")


def test_empty_store_registry_is_refused(tmp_path):
    stores = _stores_yaml(tmp_path / "stores.yaml", [])
    with pytest.raises(ValueError, match="no stores registered"):
        scan(SUBJECT, stores, tmp_path / "residue_map.json")


def test_duplicate_store_ids_are_rejected(tmp_path):
    stores = _stores_yaml(
        tmp_path / "stores.yaml",
        [
            {"id": "notes", "kind": "sqlite", "path": str(tmp_path / "a.db")},
            {"id": "notes", "kind": "sqlite", "path": str(tmp_path / "b.db")},
        ],
    )
    with pytest.raises(ValueError, match=r"duplicate store id.*notes"):
        SubjectPurgeConfig.from_yaml(stores)


def test_duplicate_text_columns_emit_one_locator(tmp_path):
    db = _matching_memories_db(tmp_path)
    stores = _stores_yaml(
        tmp_path / "stores.yaml",
        [
            {
                "id": "notes",
                "kind": "sqlite",
                "path": str(db),
                "table": "memories",
                "text_columns": ["content", "content"],
            }
        ],
    )
    residue = scan(SUBJECT, stores, tmp_path / "residue_map.json")
    assert residue.total == 1
    assert len({hit.locator for hit in residue.hits}) == 1


def test_cli_zero_hit_summary_does_not_claim_zero_stores_scanned(tmp_path):
    db = _clean_memories_db(tmp_path)
    stores = _stores_yaml(
        tmp_path / "stores.yaml",
        [{"id": "notes", "kind": "sqlite", "path": str(db), "table": "memories"}],
    )
    result = runner.invoke(
        app,
        ["scan", "--subject", SUBJECT, "--config", str(stores), "--out", str(tmp_path / "r.json")],
    )
    assert result.exit_code == 0, result.output
    assert "with residue in 0 store(s)" in result.output
    assert "across 0 store(s)" not in result.output
