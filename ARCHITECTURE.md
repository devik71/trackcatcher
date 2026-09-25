# DJCheck MVP architecture

## Modules

- `audio`: supported-file discovery, Mutagen tags and duration, streaming SHA-256, local `fpcalc` extraction.
- `db`: SQLite schema and queries. The database boundary is independent of CLI output, so a future UI can call services directly.
- `matching`: conservative text normalization, metadata scoring, Chromaprint comparison, classification and candidate selection.
- `services`: index and check workflows; callbacks report progress without coupling services to Typer.
- `output` and `cli`: human-readable results and command error handling.

## Data model

`tracks` has one row per distinct SHA-256. `performances` has one row per resolved first-level history directory. `plays` links a track and a performance and records the audio path; unique `(performance_id, source_path)` makes reindexing idempotent. Foreign keys are enabled per connection. Indices cover SHA, duration, normalized filename, and relation lookups. The path is retained as provenance; moving a history folder and reindexing it creates a new performance.

## Pipeline and scoring

`index`: discover first-level directories, scan recursively within each, hash first, reuse an existing track when SHA matches, otherwise read tags and calculate a compressed Chromaprint with `pyacoustid` forced through local `fpcalc`. Individual unreadable files produce warnings and do not stop the batch. `check`: hash first; exact SHA gives 1.0. Otherwise read tags and prefilter rows by a generous duration range plus metadata/filename similarity. Fingerprints are calculated once per query and compared only for prefiltered candidates.

Metadata combines artist/title/filename and duration. A complete artist/title pair gets a higher weight; an absent tag never counts as agreement. Metadata alone is capped below 0.90 to avoid declaring a played recording from text alone. Fingerprint results are combined with metadata and duration; a strong acoustic result can reach `PLAYED_BEFORE` even if names differ. The winning candidate supplies prior plays. Thresholds: 0.90 played, 0.65 possible. Debug logs expose every component.

`fpcalc -raw` returns integer fingerprints. Comparison uses pyacoustid's local integer alignment algorithm, which avoids requiring its optional `libchromaprint` Python binding. This uses a private pyacoustid function pinned to the supported major version; a future dependency upgrade should verify its behavior. It does not call AcoustID's network API. `fpcalc` is checked at command startup, including `check` when an exact match might otherwise avoid it, to expose a missing required dependency clearly.

## Dependencies and risks

Python 3.12+, Typer/Rich, Mutagen, RapidFuzz, pyacoustid, pytest; native Chromaprint `fpcalc` on PATH. Metadata can be absent or wrong, and duration may differ for edits. Chromaprint compares a bounded initial segment and may miss vinyl rips or edits with changed intros. Different songs with similar names can produce possible matches; a strong fingerprint and close duration are required for an automatic played verdict. Candidate prefiltering by duration can miss a substantially edited version; that is an explicit MVP limitation.

## Future partial matching

Persist fingerprints of overlapping windows such as 00:30–01:30, 01:30–02:30, 02:30–03:30 and 03:30–04:30, with offsets and algorithm version. Prefilter on metadata/coarse duration, compare aligned window pairs, require multiple consistent matches, and return matched spans as evidence. This can match a changed intro/outro without weakening whole-track classification. Import adapters (Rekordbox, Serato, Traktor), UI and report export can consume the same service results and provenance tables.
