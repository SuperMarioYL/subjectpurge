"""m3 audit/verify stub tests + core data-model round-trip tests.

The audit *signer* is the m3 milestone (ed25519 + 等保2.0 report + offline
verify) and is stubbed here, so this file asserts the stub raises clearly. The
**data models** (``AuditProof``, ``PurgeRecord``, ``ResidueHit``) are real and
shared across m1/m2/m3, so their serialisation + hash-chain payload are tested
for real — the contract m3 will build on.
"""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from subjectpurge import audit as audit_mod
from subjectpurge.cli import app
from subjectpurge.models import (
    GENESIS_HASH,
    AdapterKind,
    AuditProof,
    PurgeRecord,
    ResidueHit,
    sha256_hex,
    utcnow,
)

runner = CliRunner()


# --------------------------------------------------------------------------- #
# m3 audit / verify stubs
# --------------------------------------------------------------------------- #


def test_audit_module_raises_not_implemented():
    with pytest.raises(NotImplementedError, match="m3"):
        audit_mod.audit(SUBJECT)


def test_verify_module_raises_not_implemented():
    with pytest.raises(NotImplementedError, match="m3"):
        audit_mod.verify("audit_proof.json")


def test_audit_signer_class_raises_not_implemented():
    signer = audit_mod.AuditSigner()
    with pytest.raises(NotImplementedError, match="m3"):
        signer.sign(SUBJECT)


def test_cli_audit_stub_exits_nonzero():
    result = runner.invoke(app, ["audit", "--subject", SUBJECT])
    assert result.exit_code == 2
    assert "not in this build" in result.output
    assert "m3" in result.output


def test_cli_verify_stub_exits_nonzero():
    result = runner.invoke(app, ["verify", "audit_proof.json"])
    assert result.exit_code == 2
    assert "not in this build" in result.output


# --------------------------------------------------------------------------- #
# core data models (real, shared across milestones)
# --------------------------------------------------------------------------- #


def _sample_hit(store_id: str = "claude_mem", residue_kind: str = "direct_pii") -> ResidueHit:
    return ResidueHit(
        store_id=store_id,
        adapter=AdapterKind.sqlite,
        locator="memories:rowid=1:phone",
        residue_kind=residue_kind,
        confidence=1.0,
        evidence_hash=sha256_hex(b"evidence-bytes"),
    )


def test_residue_hit_roundtrip_json():
    hit = _sample_hit()
    dumped = hit.model_dump(mode="json")
    assert dumped["adapter"] == "sqlite"
    assert dumped["residue_kind"] == "direct_pii"
    # round-trip via model_validate
    rebuilt = ResidueHit.model_validate(dumped)
    assert rebuilt == hit


def test_audit_proof_roundtrip_json():
    proof = AuditProof(
        purge_record_hash=sha256_hex("purge-record"),
        subject_id=SUBJECT,
        law_ref="PIPL-47",
        signed_at=utcnow(),
        signature="ed25519:deadbeef",
        runtime_env_hash=sha256_hex("on-prem-box"),
    )
    dumped = proof.model_dump(mode="json")
    assert dumped["law_ref"] == "PIPL-47"
    assert dumped["schema_version"] == "1"
    rebuilt = AuditProof.model_validate(dumped)
    assert rebuilt == proof


def test_purge_record_chain_payload_excludes_self_hash():
    record = PurgeRecord(
        subject_id=SUBJECT,
        hits=[_sample_hit()],
        purged_at=utcnow(),
        operator="sre-alice",
        prior_hash=GENESIS_HASH,
    )
    payload = record.chain_payload()
    # the hash payload must NOT contain the (uninitialised) self_hash field
    assert "self_hash" not in payload
    assert record.prior_hash == GENESIS_HASH


def test_purge_record_rehash_is_deterministic_and_sensitive():
    record = PurgeRecord(
        subject_id=SUBJECT,
        hits=[_sample_hit()],
        purged_at=utcnow(),
        operator="sre-alice",
    )
    h1 = record.rehash()
    h2 = record.rehash()
    assert h1 == h2  # deterministic
    assert h1 != GENESIS_HASH  # not the genesis sentinel
    # tampering with the subject changes the hash (tamper-evidence)
    record.subject_id = "tampered"
    assert record.rehash() != h1


def test_chained_records_link_prior_to_self_hash():
    """Genesis record -> follow-on record: prior_hash == previous self_hash."""
    r1 = PurgeRecord(
        subject_id=SUBJECT,
        hits=[_sample_hit()],
        purged_at=utcnow(),
        operator="sre-alice",
        prior_hash=GENESIS_HASH,
    )
    r1.self_hash = r1.rehash()
    r2 = PurgeRecord(
        subject_id=SUBJECT,
        hits=[_sample_hit(store_id="vec_index", residue_kind="embedded")],
        purged_at=utcnow(),
        operator="sre-alice",
        prior_hash=r1.self_hash,
    )
    r2.self_hash = r2.rehash()
    assert r2.prior_hash == r1.self_hash
    assert r2.self_hash != r1.self_hash


# module-level subject id used by the tests above
SUBJECT = "13800138000"
