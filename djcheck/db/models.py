from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AudioInfo:
    path: Path
    artist: str | None
    title: str | None
    album: str | None
    duration: float | None
    normalized_filename: str


@dataclass(frozen=True)
class Candidate:
    id: int
    artist: str | None
    title: str | None
    duration: float | None
    normalized_filename: str
    fingerprint: str | None


@dataclass(frozen=True)
class Play:
    performance: str
    date: str | None
    source_path: str
