from pathlib import Path
import logging
from collections.abc import Callable
from djcheck.audio.scanner import scan_audio
from djcheck.audio.hashing import sha256_file
from djcheck.audio.metadata import read_metadata
from djcheck.audio.fingerprint import fingerprint_file
from djcheck.db.database import Database
from djcheck.matching.matcher import MatchResult, match_track

logger = logging.getLogger(__name__)


def check_folder(root: Path, db: Database, progress: Callable[[int, int, Path], None] | None = None) -> tuple[list[MatchResult], int]:
    files = scan_audio(root)
    results = []
    fingerprint_cache: dict[str, str | None] = {}
    for number, path in enumerate(files, 1):
        if progress:
            progress(number, len(files), path)
        try:
            digest = sha256_file(path)
            info = read_metadata(path)
            fingerprint = None
            if db.track_by_hash(digest) is None:
                if digest not in fingerprint_cache:
                    try:
                        fingerprint_cache[digest] = fingerprint_file(path)
                    except Exception as exc:
                        logger.warning("could not fingerprint file %s: %s", path, exc)
                        fingerprint_cache[digest] = None
                fingerprint = fingerprint_cache[digest]
            results.append(match_track(info, digest, fingerprint, db))
        except Exception as exc:
            logger.warning("could not read file %s: %s", path, exc)
    return results, len(files)
