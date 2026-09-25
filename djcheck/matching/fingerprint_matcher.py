from djcheck.audio.fingerprint import fingerprint_similarity
from .metadata_matcher import MetadataScore


def combined_score(metadata: MetadataScore, fingerprint: float) -> float:
    # Very close audio plus close duration can outweigh renamed or missing tags.
    audio_evidence = 0.78 * fingerprint + 0.17 * metadata.duration + 0.05 * metadata.score
    return max(metadata.score, min(1.0, audio_evidence))


__all__ = ["fingerprint_similarity", "combined_score"]
