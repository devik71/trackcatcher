from pathlib import Path
import os

AUDIO_EXTENSIONS = frozenset({".mp3", ".wav", ".flac", ".aiff", ".aif", ".m4a"})
PLAYED_THRESHOLD = 0.90
POSSIBLE_THRESHOLD = 0.65
FINGERPRINT_LENGTH = 120
MAX_DURATION_DIFFERENCE = 45.0
MAX_CANDIDATES = 30


def database_path() -> Path:
    override = os.environ.get("DJCHECK_DB")
    return Path(override).expanduser() if override else Path.home() / ".djcheck" / "djcheck.sqlite3"
