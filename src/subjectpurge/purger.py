"""Purger — m2 milestone (per-hit deletion + hash-chained lineage).

**Not implemented in this m1 build.** The m1 milestone ships the *locate*
direction (``scanner``). The reverse *delete* direction + the append-only,
hash-chained ``lineage.jsonl`` ledger (``prior_hash`` / ``self_hash`` + before/
after counts per store) is the m2 milestone — scaffolded here as a clearly-marked
``NotImplementedError`` so the CLI, models and tests can already reference the
contract.

When m2 lands, ``Purger.purge`` will:

1. read ``residue_map.json`` (from m1 ``scan``);
2. for each ``ResidueHit``, call the matching adapter's ``purge(hit)``;
3. append one ``PurgeRecord`` per subject to ``lineage.jsonl``, chaining
   ``prior_hash`` = previous record's ``self_hash`` (genesis = ``GENESIS_HASH``)
   and recomputing ``self_hash`` over the canonical payload;
4. print before/after counts per store and stay idempotent on re-run.
"""

from __future__ import annotations

from subjectpurge.models import ResidueMap


class Purger:
    """m2: per-hit deletion + append-only hash-chained lineage.

    Constructed from a ``ResidueMap`` (the m1 scan output) so it knows exactly
    what to delete. ``purge`` raises in m1; m2 fills it in without changing the
    scanner or the models.
    """

    NOT_IMPLEMENTED_MSG = (
        "purge is the m2 milestone (per-hit deletion + append-only hash-chained "
        "lineage.jsonl with prior_hash/self_hash + before/after counts). "
        "Not implemented in this m1 build."
    )

    def __init__(self, residue_map: ResidueMap, operator: str = "operator") -> None:
        self.residue_map = residue_map
        self.operator = operator

    def purge(self, confirm: bool = False) -> None:
        raise NotImplementedError(self.NOT_IMPLEMENTED_MSG)


def purge(
    subject_id: str,
    config_path: str = "stores.yaml",
    *,
    confirm: bool = False,
    residue_path: str = "residue_map.json",
    out: str = "lineage.jsonl",
) -> None:
    """``subjectpurge purge`` entrypoint — m2, not in this build."""
    raise NotImplementedError(Purger.NOT_IMPLEMENTED_MSG)
