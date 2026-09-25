from pathlib import Path
import logging
import re
from collections.abc import Callable
from djcheck.audio.scanner import scan_audio
from djcheck.audio.hashing import sha256_file
from djcheck.audio.metadata import read_metadata
from djcheck.audio.fingerprint import fingerprint_file
from djcheck.db.database import Database

logger = logging.getLogger(__name__)
_FOLDER_DATE = re.compile(r"^(\d{4}-\d{2}-\d{2})(?:[_\s-]+(.+))?$")


def parse_performance_name(folder: Path) -> tuple[str | None, str]:
    from datetime import date
    match = _FOLDER_DATE.match(folder.name)
    if not match:
        return None, folder.name
    try:
        date.fromisoformat(match.group(1))
    except ValueError:
        return None, folder.name
    return match.group(1), (match.group(2) or folder.name).strip()


def index_history(root: Path, db: Database, progress: Callable[[int, int, Path], None] | None = None) -> tuple[int, int]:
    folders = sorted((p for p in root.iterdir() if p.is_dir()), key=lambda p: p.name.casefold())
    items = [(folder, path) for folder in folders for path in scan_audio(folder)]
    indexed = 0
    for number, (folder, path) in enumerate(items, 1):
        if progress:
            progress(number, len(items), path)
        try:
            digest = sha256_file(path)
            existing = db.track_by_hash(digest)
            if existing:
                track_id = existing["id"]
            else:
                info = read_metadata(path)
                try:
                    fingerprint = fingerprint_file(path)
                except Exception as exc:
                    logger.warning("could not fingerprint file %s: %s", path, exc)
                    fingerprint = None
                track_id = db.add_track(info, digest, fingerprint)
            date, name = parse_performance_name(folder)
            performance_id = db.add_performance(name, date, folder)
            db.add_play(track_id, performance_id, path)
            indexed += 1
        except Exception as exc:
            logger.warning("could not read file %s: %s", path, exc)
    return indexed, len(items)
