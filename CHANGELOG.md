# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow
[SemVer](https://semver.org/).

## [0.3.0] — 2026-10-13

### Fixed

- **release: the GitHub Release now carries the built wheel/sdist.** The
  release workflow stored `dist/` as a CI artifact only, so the v0.2.0 release
  shipped with zero downloadable assets even though its release run completed
  green. A `publish` job now attaches the wheel, sdist and checksums to every
  tag's GitHub Release.
- **cli: `scan` errors print one named error line and exit 1.** A missing or
  malformed `stores.yaml`, a schema-invalid entry, a missing store file, a
  corrupt database or a path that is not a database previously escaped as a
  full Python traceback (and the not-a-database case named no store at all).
  The fail-loud behaviour is unchanged — non-zero exit, cause named — only the
  traceback presentation is gone.

## [0.2.0] — 2026-09-09

### Fixed

- **scan: unique, byte-true residue locators.** SQLite hits now carry the true
  table `rowid` in their locator (`<table>:rowid=<n>:<col>`); tables without an
  explicit `rowid` column previously emitted duplicate locators built from the
  first column value, so `residue_map.json` could not tell two hits apart.
  Trace-text locators (`<file>:offset=<n>`) are now true byte offsets into the
  raw file; non-UTF-8 bytes before a match previously inflated the reported
  offset, so a purge at the reported offset would have hit the wrong bytes.
- **scan: misregistered stores fail loudly.** A `stores.yaml` entry missing its
  required field (`path` for sqlite/chroma, `glob` for trace_text) now raises a
  `ValueError` naming the store and the field instead of a raw `TypeError`.
  A missing sqlite database file or chroma directory raises `FileNotFoundError`
  instead of silently reporting a 0-hit "clean" store (and creating a stray
  empty file). A missing sqlite table raises instead of silently scanning
  nothing. These were false "store is clean" answers — the worst failure mode
  for a deletion-request tool.
- **cli: `audit` threads its documented options.** The `audit` subcommand now
  passes `--residue` / `--lineage` / `--out` into the audit entrypoint instead
  of silently dropping them. The audit signer itself remains the m3 milestone
  (still a clearly-marked stub).

### Added

- `CHANGELOG.md` (this file) and a scan-integrity regression suite
  (`tests/test_scan_integrity.py`).

## [0.1.0] — 2026-08-03

### Added

- m1 `scan` core: scanner + SQLite / Chroma / trace-text adapters emitting
  `residue_map.json` for a subject across the registered stores; `subjectpurge`
  CLI with `scan` end-to-end and clearly-marked `purge` / `audit` / `verify`
  stubs (m2 / m3 milestones).
