from dataclasses import dataclass
from rapidfuzz.fuzz import ratio
from djcheck.db.models import AudioInfo, Candidate
from .normalize import normalize_text


def similarity(a: str | None, b: str | None) -> float:
    x, y = normalize_text(a), normalize_text(b)
    return ratio(x, y) / 100 if x and y else 0.0


def duration_score(a: float | None, b: float | None) -> float:
    if a is None or b is None:
        return 0.0
    difference = abs(a - b)
    if difference <= 3:
        return 1.0 - difference / 150
    return max(0.0, 1.0 - (difference - 3) / 45)


@dataclass(frozen=True)
class MetadataScore:
    artist: float
    title: float
    filename: float
    duration: float
    score: float


def score_metadata(query: AudioInfo, candidate: Candidate) -> MetadataScore:
    artist = similarity(query.artist, candidate.artist)
    title = similarity(query.title, candidate.title)
    filename = similarity(query.normalized_filename, candidate.normalized_filename)
    duration = duration_score(query.duration, candidate.duration)
    if query.artist and query.title and candidate.artist and candidate.title:
        score = 0.32 * artist + 0.38 * title + 0.15 * filename + 0.15 * duration
    else:
        score = 0.73 * filename + 0.27 * duration
    # Text alone is evidence of a possible match, never an automatic played verdict.
    return MetadataScore(artist, title, filename, duration, min(score, 0.89))
