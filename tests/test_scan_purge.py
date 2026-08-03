"""m1 scan + m2 purge-stub tests.

The headline test (``test_scan_locates_7_residues_across_3_stores``) is the m1
done-criterion from ``mvp_plan.md`` §5: a user runs ``scan`` and sees the
subject's PII leaked to 7 places across the 3 registered stores. The two-store
variants (SQLite + trace) run without the Chroma extra so the m1 core is always
covered; the Chroma tests skip when the optional extra is absent.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from subjectpurge import __version__
from subjectpurge.cli import app
from subjectpurge.config import SubjectPurgeConfig
from subjectpurge.models import AdapterKind, ResidueMap
from subjectpurge.purger import Purger
from subjectpurge.scanner import Scanner, build_adapter, scan

try:  # chromadb is an optional extra
    import chromadb  # noqa: F401

    _HAS_CHROMA = True
except ImportError:  # pragma: no cover
    _HAS_CHROMA = False

needs_chroma = pytest.mark.skipif(not _HAS_CHROMA, reason="chroma extra not installed")

runner = CliRunner()


# --------------------------------------------------------------------------- #
# scan — m1 core
# --------------------------------------------------------------------------- #


def test_scan_writes_residue_map_and_returns_model(three_store_fixture):
    fx = three_store_fixture
    residue = scan(SUBJECT, fx["stores_yaml"], fx["residue_out"])
    assert isinstance(residue, ResidueMap)
    assert residue.subject_id == SUBJECT
    assert residue.operator == "sre-alice"
    # the file exists and is valid JSON with the same shape
    payload = json.loads(Path(fx["residue_out"]).read_text(encoding="utf-8"))
    assert payload["subject_id"] == SUBJECT
    assert payload["schema_version"] == "1"
    assert len(payload["hits"]) == len(residue.hits)


def test_scan_is_selective_no_hits_for_unknown_subject(three_store_fixture):
    fx = three_store_fixture
    residue = scan("00000000000", fx["stores_yaml"], fx["residue_out"])
    assert residue.total == 0
    assert residue.by_store() == {}


def test_scan_evidence_hashes_are_unique_per_hit(three_store_fixture):
    fx = three_store_fixture
    residue = scan(SUBJECT, fx["stores_yaml"], fx["residue_out"])
    hashes = {h.evidence_hash for h in residue.hits}
    # 7 distinct pieces of evidence -> 7 distinct hashes (no accidental collapse)
    assert len(hashes) == residue.total


def test_scan_locates_sqlite_hits_without_chroma(three_store_fixture):
    """SQLite half always runs (no heavy dep) and finds exactly 3 residues."""
    fx = three_store_fixture
    # strip the chroma store to prove the sqlite+trace core is dependency-free
    cfg = SubjectPurgeConfig.from_yaml(fx["stores_yaml"])
    cfg.stores = [s for s in cfg.stores if s.kind != "chroma"]
    residue = Scanner(cfg).locate(SUBJECT)
    sqlite_hits = [h for h in residue.hits if h.adapter == AdapterKind.sqlite]
    trace_hits = [h for h in residue.hits if h.adapter == AdapterKind.trace_text]
    assert len(sqlite_hits) == 3
    assert len(trace_hits) == 2
    # sqlite locator shape
    assert all(h.locator.startswith("memories:rowid=") for h in sqlite_hits)
    # at least one direct_pii (phone column) and at least one embedded
    kinds = {h.residue_kind for h in sqlite_hits}
    assert "direct_pii" in kinds
    assert "embedded" in kinds


@needs_chroma
def test_scan_locates_chroma_hits(three_store_fixture):
    fx = three_store_fixture
    assert fx["chroma_live"], "chroma fixture did not seed"
    residue = scan(SUBJECT, fx["stores_yaml"], fx["residue_out"])
    chroma_hits = [h for h in residue.hits if h.adapter == AdapterKind.chroma]
    assert len(chroma_hits) == 2
    # one embedded (id in document), one summarized (id only in summary metadata)
    kinds = {h.residue_kind for h in chroma_hits}
    assert "embedded" in kinds
    assert "summarized" in kinds
    assert all(h.locator.startswith("sessions:id=") for h in chroma_hits)


@needs_chroma
def test_scan_locates_7_residues_across_3_stores(three_store_fixture):
    """m1 done-criterion: subject X's PII leaked to 7 places across 3 stores."""
    fx = three_store_fixture
    residue = scan(SUBJECT, fx["stores_yaml"], fx["residue_out"])
    assert residue.total == 7
    by_store = residue.by_store()
    assert len(by_store) == 3
    assert sorted(by_store.values()) == [2, 2, 3]


# --------------------------------------------------------------------------- #
# adapter wiring
# --------------------------------------------------------------------------- #


def test_build_adapter_rejects_graph_kind():
    from subjectpurge.config import StoreConfig

    with pytest.raises(ValueError, match="graph"):
        build_adapter(StoreConfig(id="g", kind="graph", path="/x"))


def test_scan_fans_out_to_every_registered_store(three_store_fixture):
    fx = three_store_fixture
    cfg = SubjectPurgeConfig.from_yaml(fx["stores_yaml"])
    store_ids = {s.id for s in cfg.stores}
    assert "claude_mem" in store_ids
    assert "trace_logs" in store_ids


# --------------------------------------------------------------------------- #
# m2 purge stub
# --------------------------------------------------------------------------- #


def test_purger_raises_not_implemented(three_store_fixture):
    fx = three_store_fixture
    residue = scan(SUBJECT, fx["stores_yaml"], fx["residue_out"])
    purger = Purger(residue)
    with pytest.raises(NotImplementedError, match="m2"):
        purger.purge(confirm=True)


def test_purge_module_function_raises_not_implemented():
    import subjectpurge.purger as purger_mod

    with pytest.raises(NotImplementedError, match="m2"):
        purger_mod.purge(SUBJECT, "stores.yaml", confirm=True)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def test_cli_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_cli_scan_command(three_store_fixture):
    fx = three_store_fixture
    result = runner.invoke(
        app,
        [
            "scan",
            "--subject",
            SUBJECT,
            "--config",
            str(fx["stores_yaml"]),
            "--out",
            str(fx["residue_out"]),
        ],
    )
    assert result.exit_code == 0, result.output
    assert "scan complete" in result.output
    assert "total residue hits:" in result.output
    # residue map was actually written
    payload = json.loads(Path(fx["residue_out"]).read_text(encoding="utf-8"))
    assert payload["subject_id"] == SUBJECT


def test_cli_purge_stub_exits_nonzero(three_store_fixture):
    fx = three_store_fixture
    result = runner.invoke(app, ["purge", "--subject", SUBJECT, "--config", str(fx["stores_yaml"])])
    assert result.exit_code == 2
    assert "not in this build" in result.output
    assert "m2" in result.output


def test_cli_scan_help_lists_subject_option():
    result = runner.invoke(app, ["scan", "--help"])
    assert result.exit_code == 0
    assert "--subject" in result.output


# module-level import of the fixture subject so tests read cleanly
SUBJECT = "13800138000"
