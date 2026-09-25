from dataclasses import dataclass
import logging
from djcheck.config import MAX_CANDIDATES, PLAYED_THRESHOLD, POSSIBLE_THRESHOLD
from djcheck.db.database import Database
from djcheck.db.models import AudioInfo, Candidate, Play
from .metadata_matcher import MetadataScore, score_metadata
from .fingerprint_matcher import combined_score, fingerprint_similarity

logger = logging.getLogger(__name__)


def classify(confidence: float) -> str:
    if confidence >= PLAYED_THRESHOLD:
        return "PLAYED_BEFORE"
    if confidence >= POSSIBLE_THRESHOLD:
        return "POSSIBLE_MATCH"
    return "NEW"


@dataclass(frozen=True)
class MatchResult:
    path: str
    status: str
    confidence: float
    method: str | None
    candidate: Candidate | None
    plays: list[Play]


def select_candidates(info: AudioInfo, db: Database) -> list[tuple[Candidate, MetadataScore]]:
    scored = [(candidate, score_metadata(info, candidate)) for candidate in db.candidates(info.duration)]
    text = sorted(scored, key=lambda pair: pair[1].score, reverse=True)[:MAX_CANDIDATES]
    # Preserve close-duration candidates even when all tags and filenames differ.
    nearby = sorted(
        (pair for pair in scored if info.duration is not None and pair[0].duration is not None),
        key=lambda pair: abs(info.duration - pair[0].duration),
    )[:MAX_CANDIDATES]
    selected = {candidate.id: (candidate, score) for candidate, score in text + nearby}
    return list(selected.values())


def match_track(info: AudioInfo, digest: str, fingerprint: str | None, db: Database) -> MatchResult:
    exact = db.track_by_hash(digest)
    if exact:
        candidate = Candidate(exact["id"], exact["artist"], exact["title"], exact["duration"], exact["normalized_filename"], exact["fingerprint"])
        logger.debug("Candidate #%s: SHA-256 exact; final score: 1.000; classification: PLAYED_BEFORE", candidate.id)
        return MatchResult(str(info.path), "PLAYED_BEFORE", 1.0, "EXACT_FILE", candidate, db.plays_for_track(candidate.id))

    best: tuple[Candidate, float, str] | None = None
    for candidate, meta in select_candidates(info, db):
        fp_score = None
        if fingerprint and candidate.fingerprint:
            try:
                fp_score = fingerprint_similarity(fingerprint, candidate.fingerprint)
            except (ValueError, TypeError, ModuleNotFoundError) as exc:
                logger.warning("Could not compare fingerprint for candidate #%s: %s", candidate.id, exc)
        final = combined_score(meta, fp_score) if fp_score is not None else meta.score
        method = "AUDIO_FINGERPRINT" if fp_score is not None and final > meta.score else "METADATA_MATCH"
        logger.debug(
            "Candidate #%s: title similarity: %.3f; artist similarity: %.3f; filename similarity: %.3f; "
            "duration score: %.3f; fingerprint: %s; final score: %.3f; classification: %s",
            candidate.id, meta.title, meta.artist, meta.filename, meta.duration,
            f"{fp_score:.3f}" if fp_score is not None else "unavailable", final, classify(final),
        )
        if best is None or final > best[1]:
            best = (candidate, final, method)
    if not best or classify(best[1]) == "NEW":
        if not best:
            logger.debug("No candidates within the duration prefilter; classification: NEW")
        return MatchResult(str(info.path), "NEW", best[1] if best else 0.0, best[2] if best else None, None, [])
    candidate, confidence, method = best
    return MatchResult(str(info.path), classify(confidence), confidence, method, candidate, db.plays_for_track(candidate.id))
