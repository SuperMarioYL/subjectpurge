# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow
[SemVer](https://semver.org/).

## [0.4.0] — 2026-11-12

### Fixed

- **scan: a broken Chroma backend no longer reads as a clean store.** The
  adapter caught every exception from `get_collection` and returned no hits, so
  a corrupt or unreadable persisted store reported `total residue hits: 0` with
  a zero exit code. The collection is now listed first (which surfaces backend
  errors) and only a genuinely absent collection means "no residue"; any other
  read failure raises a `ValueError` naming the store and path.
- **scan: a misregistered trace path fails loud.** A trace glob whose literal
  path prefix does not exist now raises `FileNotFoundError` naming the store
  instead of reporting a false-clean 0-hit store — the same rule the SQLite and
  Chroma adapters already followed. A directory that exists with no matching
  files remains a legitimately clean store. `~` in a trace glob is expanded.
- **scan: an unreadable trace file fails loud.** A matched file that cannot be
  opened is now an `OSError` naming the store and file instead of being silently
  skipped, so the map never claims to have examined bytes it could not read.
- **scan: an unavailable Chroma extra prints one error line.** A missing
  `chromadb` dependency is translated into the same named `ValueError` the CLI
  already renders as `error: <cause>` with exit 1, instead of a raw traceback.
- **scan: blank subjects and empty or duplicate registries are refused.** An
  empty subject (contained in every value) previously matched every row; a
  `stores: []` registry previously produced a "clean" scan of nothing; a
  duplicated store id double-counted one residue under identical locators. All
  three now fail with a named error.
- **scan: duplicate `text_columns` no longer emit duplicate locators**, and the
  CLI summary reports residue-bearing stores (`with residue in N store(s)`)
  rather than printing `across 0 store(s)` after a successful clean scan.

### Changed

- Scans that previously "succeeded" with a blank subject, an empty registry or
  duplicate store ids now exit non-zero. A wrong Chroma collection name still
  returns 0 hits — an accepted residual, now documented in both READMEs.

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
