from pathlib import Path
from mutagen import File
from djcheck.db.models import AudioInfo
from djcheck.matching.normalize import normalize_filename


def _tag(audio, *keys: str) -> str | None:
    for key in keys:
        value = audio.get(key)
        if value:
            item = value[0] if isinstance(value, (list, tuple)) else value
            text = str(item).strip()
            if text:
                return text
    return None


def read_metadata(path: Path) -> AudioInfo:
    audio = File(path, easy=True)
    if audio is None or audio.info is None:
        raise ValueError("unreadable audio metadata")
    duration = getattr(audio.info, "length", None)
    return AudioInfo(
        path=path,
        artist=_tag(audio, "artist", "albumartist"),
        title=_tag(audio, "title"),
        album=_tag(audio, "album"),
        duration=float(duration) if duration is not None else None,
        normalized_filename=normalize_filename(path.name),
    )
