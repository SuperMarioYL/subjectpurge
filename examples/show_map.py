#!/usr/bin/env python
"""Print a one-hit summary of a residue_map.json (demo helper)."""

from __future__ import annotations

import json
import sys


def main() -> None:
    path = sys.argv[1] if len(sys.argv) > 1 else "/tmp/sp-demo/residue_map.json"
    with open(path, encoding="utf-8") as fh:
        h = json.load(fh)
    summary = {
        "subject_id": h["subject_id"],
        "total": len(h["hits"]),
        "first_hit": h["hits"][0],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
