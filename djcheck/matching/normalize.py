import re
import unicodedata
from pathlib import Path

_NOISE = re.compile(r"[\[(]\s*(?:320(?:\s*kbps)?|flac|mp3|wav|aiff?|m4a)\s*[\])]", re.IGNORECASE)
_LEADING_NUMBER = re.compile(r"^\s*\d{1,3}\s*[-._ ]+\s*")


def normalize_text(value: str | None) -> str:
    if not value:
        return ""
    value = unicodedata.normalize("NFKC", value).casefold()
    value = _NOISE.sub(" ", value)
    value = value.replace("_", " ")
    value = re.sub(r"\s+-\s+", " ", value)
    value = re.sub(r"(?<=\w)-(?=\w)", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def normalize_filename(value: str) -> str:
    stem = Path(value).stem
    return normalize_text(_LEADING_NUMBER.sub("", stem))
