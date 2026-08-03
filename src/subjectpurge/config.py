"""``stores.yaml`` configuration — the registry of agent-memory stores.

A 信创/政企 合规 officer authors one ``stores.yaml`` pointing at their
on-prem agent-memory runtime (claude-mem SQLite path, persisted Chroma dir,
trace-text glob) and SubjectPurge never leaves that box (数据不出境).

Example::

    operator: sre-alice
    law_ref: PIPL-47
    stores:
      - id: claude_mem
        kind: sqlite
        path: /var/agent/claude-mem.db
        table: memories
        text_columns: [content, summary]
      - id: vec_index
        kind: chroma
        path: /var/agent/chroma
        collection: sessions
      - id: trace_logs
        kind: trace_text
        glob: "/var/agent/trace/**/*.log"
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field

StoreKind = Literal["sqlite", "chroma", "trace_text", "graph"]


class StoreConfig(BaseModel):
    """One registered store the scanner fans out to."""

    id: str = Field(description="short id used in residue_map.json + lineage")
    kind: StoreKind = Field(description="adapter kind: sqlite | chroma | trace_text | graph")
    path: str | None = Field(default=None, description="file/dir path (sqlite, chroma)")
    collection: str | None = Field(default=None, description="chroma collection name")
    glob: str | None = Field(
        default=None, description="trace-text glob (supports ** for recursion)"
    )
    table: str = Field(default="memories", description="sqlite table holding agent-memory rows")
    text_columns: list[str] = Field(
        default_factory=lambda: ["content", "summary", "text"],
        description="sqlite text columns scanned for the subject id",
    )


class SubjectPurgeConfig(BaseModel):
    """Top-level ``stores.yaml`` model."""

    operator: str = Field(default="operator", description="合规/SRE account on the on-prem box")
    law_ref: str = Field(default="PIPL-47", description="regulation the audit proof cites")
    stores: list[StoreConfig] = Field(default_factory=list)

    @classmethod
    def from_yaml(cls, path: str | Path) -> SubjectPurgeConfig:
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        return cls.model_validate(data)

    @classmethod
    def from_dict(cls, data: dict) -> SubjectPurgeConfig:
        return cls.model_validate(data)
