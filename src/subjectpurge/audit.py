"""Audit — m3 milestone (ed25519 signed 等保2.0 proof + verify).

**Not implemented in this m1 build.** The m3 milestone seals the purge record in
an ``AuditProof`` envelope: an ed25519 detached signature over the purge-record
hash, a 等保2.0-style report rendered from a jinja2 template (CN-primary), and
a ``runtime_env_hash`` binding the proof to the on-prem box it was issued on.
``verify`` round-trips green offline (no network) — the artefact a 合规 officer
hands an auditor.

Scaffolded here as a clearly-marked ``NotImplementedError`` so the CLI,
``AuditProof`` model and tests already reference the contract. ``cryptography``
+ ``jinja2`` are declared as the optional ``[audit]`` extra so they land with m3
without burdening the m1 core install.
"""

from __future__ import annotations

from subjectpurge.models import AuditProof


class AuditSigner:
    """m3: ed25519 detached signer + 等保2.0 jinja2 report."""

    NOT_IMPLEMENTED_MSG = (
        "audit is the m3 milestone (ed25519 detached signature + 等保2.0 jinja2 "
        "report + runtime_env_hash binding + offline verify round-trip). "
        "Not implemented in this m1 build."
    )

    def __init__(
        self,
        residue_map_path: str = "residue_map.json",
        lineage_path: str = "lineage.jsonl",
        operator: str = "operator",
    ) -> None:
        self.residue_map_path = residue_map_path
        self.lineage_path = lineage_path
        self.operator = operator

    def sign(self, subject_id: str) -> AuditProof:
        raise NotImplementedError(self.NOT_IMPLEMENTED_MSG)


def audit(subject_id: str) -> AuditProof:
    """``subjectpurge audit`` entrypoint — m3, not in this build."""
    raise NotImplementedError(AuditSigner.NOT_IMPLEMENTED_MSG)


def verify(proof_path: str = "audit_proof.json") -> bool:
    """``subjectpurge verify`` entrypoint — m3, not in this build."""
    raise NotImplementedError(
        "verify is the m3 milestone (ed25519 signature check + 等保2.0 report "
        "consistency, offline round-trip). Not implemented in this m1 build."
    )
