from pathlib import Path
from djcheck.config import AUDIO_EXTENSIONS


def scan_audio(folder: Path) -> list[Path]:
    return sorted(
        (path for path in folder.rglob("*") if path.is_file() and path.suffix.lower() in AUDIO_EXTENSIONS),
        key=lambda path: str(path).casefold(),
    )
