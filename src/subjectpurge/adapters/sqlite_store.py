"""SQLite adapter — locates a subject's PII in an agent-memory SQLite DB.

Target schema: the claude-mem style ``memories`` table, but the adapter is
schema-flexible — it scans every configured text column of the configured table
for the subject id and classifies each hit as ``direct_pii`` (the value lives in
a PII-named column and matches) or ``embedded`` (the id is embedded in a
free-text / summary column). Matching is deterministic (literal substring +
PII-pattern); no LLM is invoked.
"""

from __future__ import annotations

import os
import sqlite3
from typing import Any

from subjectpurge.adapters.base import Adapter
from subjectpurge.models import AdapterKind, ResidueHit, sha256_hex

# Column-name fragments that signal a *direct* PII field rather than free text.
_DIRECT_PII_COLUMN_HINTS = (
    "phone",
    "mobile",
    "tel",
    "email",
    "mail",
    "id_card",
    "idcard",
    "identity",
    "cert",
    "id_number",
    "ssn",
)

# Alias under which the implicit rowid is surfaced by the row select. `SELECT *`
# never returns it, so without the alias tables lacking an explicit rowid column
# would fall back to a non-unique first-column identity in their locators.
_ROWID_ALIAS = "__sp_rowid__"


def _is_direct_pii_column(column: str) -> bool:
    lc = column.lower()
    return any(hint in lc for hint in _DIRECT_PII_COLUMN_HINTS)


class SQLiteAdapter(Adapter):
    """Reverse-locate a subject's PII residue in a SQLite agent-memory table."""

    kind = "sqlite"
    required_fields = ("path",)

    def __init__(
        self,
        store_id: str,
        path: str,
        table: str = "memories",
        text_columns: list[str] | None = None,
        **_: object,
    ) -> None:
        super().__init__(store_id)
        self.path = path
        self.table = table
        self.text_columns = text_columns or ["content", "summary", "text"]
        self._conn: sqlite3.Connection | None = None

    def _connect(self) -> sqlite3.Connection:
        if self._conn is None:
            # Fail loudly on a typo'd path: sqlite3.connect would silently
            # create an empty database and the scan would report a false-clean
            # 0-hit store.
            if not os.path.exists(self.path):
                raise FileNotFoundError(
                    f"sqlite store {self.store_id!r}: no database file at {self.path!r}"
                )
            self._conn = sqlite3.connect(self.path)
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def _columns(self) -> list[str]:
        conn = self._connect()
        try:
            cur = conn.execute(f'SELECT * FROM "{self.table}" LIMIT 0')
            return [d[0] for d in cur.description or []]
        except sqlite3.Error:
            return []

    def _select_rows(self, conn: sqlite3.Connection) -> list[sqlite3.Row]:
        # The rowid alias makes every locator resolvable to a true rowid even
        # when the table has no explicit rowid column. WITHOUT-ROWID tables
        # reject the alias; for those, fall back to a plain SELECT * (the
        # first-column identity in _rowid_of).
        try:
            cur = conn.execute(f'SELECT *, rowid AS "{_ROWID_ALIAS}" FROM "{self.table}"')
        except sqlite3.OperationalError:
            cur = conn.execute(f'SELECT * FROM "{self.table}"')
        return cur.fetchall()

    def _rowid_of(self, row: sqlite3.Row) -> Any:
        keys = row.keys()
        if "rowid" in keys:
            return row["rowid"]
        if _ROWID_ALIAS in keys:
            return row[_ROWID_ALIAS]
        # fall back to the first column value as the row identity
        return row[0]

    def locate(self, subject_id: str) -> list[ResidueHit]:
        conn = self._connect()
        present = self._columns()
        if not present:
            # every sqlite table has >= 1 column, so this means the table is
            # missing or unreadable — never a legitimate "no residue" answer
            raise ValueError(
                f"sqlite store {self.store_id!r}: cannot read table "
                f"{self.table!r} from {self.path!r} — does the table exist?"
            )
        scan_cols = [c for c in self.text_columns if c in present] or present
        hits: list[ResidueHit] = []
        for row in self._select_rows(conn):
            rowid = self._rowid_of(row)
            for col in scan_cols:
                if col not in row.keys():
                    continue
                value = row[col]
                if value is None:
                    continue
                value_str = str(value)
                if subject_id not in value_str:
                    continue
                evidence = value_str.encode("utf-8")
                residue_kind = "direct_pii" if _is_direct_pii_column(col) else "embedded"
                hits.append(
                    ResidueHit(
                        store_id=self.store_id,
                        adapter=AdapterKind.sqlite,
                        locator=f"{self.table}:rowid={rowid}:{col}",
                        residue_kind=residue_kind,
                        confidence=1.0,
                        evidence_hash=sha256_hex(evidence),
                    )
                )
        return hits

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None
