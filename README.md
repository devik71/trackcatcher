# DJCheck

Local CLI for DJ Sominaryst: index folders of past sets, then check a folder for a future set and see which recordings were played before, where and when.

## Installation

Python 3.12 or newer is required. From this project directory:

```bash
python -m venv .venv
# macOS/Linux: source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -e .
```

For tests: `python -m pip install -e '.[dev]'` and `python -m pytest -q`.

## Chromaprint installation

`fpcalc` must be executable from your `PATH`. Check with `fpcalc -version` (or `fpcalc -help` if your build does not support `-version`).

- **macOS:** `brew install chromaprint`.
- **Linux:** install your distribution's Chromaprint tools package, for example `sudo apt install libchromaprint-tools` on Debian/Ubuntu.
- **Windows:** download the `fpcalc` binary from the [Chromaprint download page](https://acoustid.org/chromaprint), extract it, and add the directory containing `fpcalc.exe` to `PATH`. Open a new terminal after changing `PATH`.

The program checks `fpcalc` before `index` or `check` and reports a setup error if it is missing. Fingerprint generation and comparison are local; no AcoustID account, API key or network access is used.

## Usage

```bash
djcheck init
djcheck index ~/DJ/history
djcheck check ~/DJ/next-set
djcheck check ~/DJ/next-set --debug
```

On Windows, use Windows paths. If the virtual environment is not activated, use `.venv\Scripts\djcheck.exe` from this directory.

The history folder should contain one first-level folder per performance, for example `2025-11-22_BRUKXT/`. Audio files may be nested inside a performance folder. The date prefix is optional; an invalid or missing date becomes `NULL`. Supported extensions: MP3, WAV, FLAC, AIFF/AIF, M4A. Other files are ignored. Reindexing a folder is safe: existing SHA-256 tracks and play paths are reused.

`--debug` prints candidate scores (artist, title, filename, duration, fingerprint, final score and classification) for tuning.

## Database location

By default: `~/.djcheck/djcheck.sqlite3` (on Windows, inside your user home directory). Set `DJCHECK_DB` to an explicit SQLite path to use a different database, useful for tests or separate archives.

## Matching logic

1. **SHA-256:** identical file bytes give `EXACT_FILE`, confidence `1.0`.
2. **Metadata:** RapidFuzz compares normalized artist, title and filename plus duration. Text-only matches are capped below the `PLAYED_BEFORE` threshold.
3. **Audio fingerprint:** `fpcalc` computes a Chromaprint of the first 120 seconds. A bounded set of candidates is selected using duration and text, then raw fingerprints are aligned locally with pyacoustid's algorithm. Fingerprint and duration scores can lift a result to `PLAYED_BEFORE`.

Classification is `PLAYED_BEFORE` at 0.90 or above, `POSSIBLE_MATCH` from 0.65 through 0.89, and `NEW` below 0.65. The scores are heuristic evidence, not calibrated probabilities. Results show the winning candidate and every indexed performance linked to that exact historical file.

## Limitations

- Mutagen may not read every corrupt or unusual audio file; these files are warned about and skipped.
- Different encodes can fingerprint well; vinyl rips, heavy EQ, tempo changes and DJ edits may not. A changed intro can defeat the first-120-second fingerprint.
- Candidate selection uses a 45-second duration window and the closest duration/text candidates. Long edits can be missed, and dense archives with many equal-duration tracks may push a renamed match outside the shortlist.
- Similar names or near-identical recordings can yield possible matches. A metadata match alone does not establish that the recording is the same.
- Dates come from directory names, not audio tags or event records. Play counts and last-played ranking are not yet scored.

See [ARCHITECTURE.md](ARCHITECTURE.md) for scoring details, risks and a design note for future windowed fingerprint matching of edits.
