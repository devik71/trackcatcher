import shutil
import subprocess
from pathlib import Path
import acoustid
from djcheck.config import FINGERPRINT_LENGTH


class FingerprintUnavailable(RuntimeError):
    pass


def require_fpcalc() -> None:
    if shutil.which("fpcalc") is None:
        raise FingerprintUnavailable("fpcalc is unavailable. Install Chromaprint and put fpcalc on PATH. See README.md.")


def fingerprint_file(path: Path) -> str:
    process = subprocess.run(
        ["fpcalc", "-raw", "-length", str(FINGERPRINT_LENGTH), str(path)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180, check=True,
    )
    for line in process.stdout.splitlines():
        if line.startswith("FINGERPRINT="):
            value = line.partition("=")[2].strip()
            if value:
                return value
    raise ValueError("fpcalc returned no fingerprint")


def fingerprint_similarity(a: str, b: str) -> float:
    left = [int(value) & 0xFFFFFFFF for value in a.split(",")]
    right = [int(value) & 0xFFFFFFFF for value in b.split(",")]
    if not left or not right:
        raise ValueError("empty fingerprint")
    return float(acoustid._match_fingerprints(left, right))
