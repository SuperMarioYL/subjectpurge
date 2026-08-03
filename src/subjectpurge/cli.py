"""``subjectpurge`` CLI — typer app with scan / purge / audit / verify subcommands.

m1 ships ``scan`` end-to-end (locate every PII residue of a subject across the
registered stores, write ``residue_map.json``). ``purge`` (m2) and
``audit`` / ``verify`` (m3) are scaffolded and print a clear "not in this
build" message + exit non-zero so automation cannot mistake them for success.
"""

from __future__ import annotations

import json
from pathlib import Path

import typer

from subjectpurge import __version__
from subjectpurge import audit as audit_mod
from subjectpurge import purger as purger_mod
from subjectpurge.scanner import scan as scan_fn

app = typer.Typer(
    name="subjectpurge",
    help="清痕 — per-subject deletion-lineage mapper across agent-memory stores.",
    no_args_is_help=True,
    add_completion=False,
    rich_markup_mode="rich",
)


def _print_summary(subject_id: str, out: str) -> None:
    payload = json.loads(Path(out).read_text(encoding="utf-8"))
    hits = payload.get("hits", [])
    by_store: dict[str, int] = {}
    by_kind: dict[str, int] = {}
    for hit in hits:
        by_store[hit["store_id"]] = by_store.get(hit["store_id"], 0) + 1
        by_kind[hit["residue_kind"]] = by_kind.get(hit["residue_kind"], 0) + 1
    typer.echo(f"scan complete: subject={subject_id}")
    typer.echo(f"  total residue hits: {len(hits)}")
    for sid, count in sorted(by_store.items()):
        typer.echo(f"  {sid}: {count} hit(s)")
    for kind, count in sorted(by_kind.items()):
        typer.echo(f"  residue_kind={kind}: {count}")
    typer.echo(f"  residue map -> {out}")


@app.command()
def scan(
    subject: str = typer.Option(
        ..., "--subject", "-s", help="subject id (phone / id-card / email)"
    ),
    config: str = typer.Option("stores.yaml", "--config", "-c", help="path to stores.yaml"),
    out: str = typer.Option("residue_map.json", "--out", "-o", help="output residue map path"),
) -> None:
    """Locate every PII residue of <subject> across the registered stores."""
    residue = scan_fn(subject, config, out)
    typer.echo(
        f"scanned subject={residue.subject_id} across "
        f"{len(residue.by_store())} store(s), operator={residue.operator}"
    )
    _print_summary(subject, out)


def _not_in_build(label: str, exc: NotImplementedError) -> None:
    typer.echo(f"[{label}] not in this build")
    typer.echo(f"  {exc}")
    raise typer.Exit(code=2)


@app.command()
def purge(
    subject: str = typer.Option(..., "--subject", "-s", help="subject id to purge"),
    config: str = typer.Option("stores.yaml", "--config", "-c"),
    confirm: bool = typer.Option(False, "--confirm", help="confirm the destructive delete"),
    residue_path: str = typer.Option(
        "residue_map.json", "--residue", help="residue map produced by scan"
    ),
    out: str = typer.Option("lineage.jsonl", "--out", "-o", help="lineage ledger path"),
) -> None:
    """m2: per-hit deletion + hash-chained lineage (not in this m1 build)."""
    try:
        purger_mod.purge(subject, config, confirm=confirm, residue_path=residue_path, out=out)
    except NotImplementedError as exc:
        _not_in_build("purge", exc)


@app.command()
def audit(
    subject: str = typer.Option(
        ..., "--subject", "-s", help="subject id to issue an audit proof for"
    ),
    residue: str = typer.Option("residue_map.json", "--residue", help="residue map from scan"),
    lineage: str = typer.Option("lineage.jsonl", "--lineage", help="lineage ledger from purge"),
    out: str = typer.Option("audit_proof.json", "--out", "-o", help="audit proof path"),
) -> None:
    """m3: ed25519 signed 等保2.0 audit proof (not in this m1 build)."""
    try:
        audit_mod.audit(subject)
    except NotImplementedError as exc:
        _not_in_build("audit", exc)


@app.command()
def verify(
    proof: str = typer.Argument("audit_proof.json", help="audit proof json path"),
) -> None:
    """m3: verify an audit proof offline (not in this m1 build)."""
    try:
        audit_mod.verify(proof)
    except NotImplementedError as exc:
        _not_in_build("verify", exc)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"subjectpurge {__version__}")
        raise typer.Exit(code=0)


@app.callback()
def main(
    version: bool = typer.Option(
        None,
        "--version",
        "-V",
        help="show version and exit",
        callback=_version_callback,
        is_eager=True,
    ),
) -> None:
    """清痕 — per-subject deletion-lineage mapper. 数据不出境."""
    return None


if __name__ == "__main__":  # pragma: no cover
    app()
