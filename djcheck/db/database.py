import sqlite3
from pathlib import Path
from .models import AudioInfo, Candidate, Play

SCHEMA = """
CREATE TABLE IF NOT EXISTS tracks (
 id INTEGER PRIMARY KEY, artist TEXT, title TEXT, album TEXT,
 duration REAL, sha256 TEXT NOT NULL UNIQUE, fingerprint TEXT,
 normalized_filename TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_tracks_duration ON tracks(duration);
CREATE INDEX IF NOT EXISTS idx_tracks_filename ON tracks(normalized_filename);
CREATE TABLE IF NOT EXISTS performances (
 id INTEGER PRIMARY KEY, name TEXT NOT NULL, date TEXT, source_path TEXT NOT NULL UNIQUE,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS plays (
 id INTEGER PRIMARY KEY, track_id INTEGER NOT NULL REFERENCES tracks(id),
 performance_id INTEGER NOT NULL REFERENCES performances(id),
 source_path TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 UNIQUE(performance_id, source_path)
);
CREATE INDEX IF NOT EXISTS idx_plays_track ON plays(track_id);
CREATE INDEX IF NOT EXISTS idx_plays_performance ON plays(performance_id);
"""


class Database:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.executescript(SCHEMA)

    def close(self):
        self.connection.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def track_by_hash(self, digest: str):
        return self.connection.execute("SELECT * FROM tracks WHERE sha256 = ?", (digest,)).fetchone()

    def add_track(self, info: AudioInfo, digest: str, fingerprint: str | None) -> int:
        cursor = self.connection.execute(
            "INSERT INTO tracks (artist,title,album,duration,sha256,fingerprint,normalized_filename) VALUES (?,?,?,?,?,?,?)",
            (info.artist, info.title, info.album, info.duration, digest, fingerprint, info.normalized_filename),
        )
        self.connection.commit()
        return cursor.lastrowid

    def add_performance(self, name: str, date: str | None, source_path: Path) -> int:
        source = str(source_path.resolve())
        self.connection.execute("INSERT OR IGNORE INTO performances (name,date,source_path) VALUES (?,?,?)", (name, date, source))
        row = self.connection.execute("SELECT id FROM performances WHERE source_path = ?", (source,)).fetchone()
        self.connection.commit()
        return row["id"]

    def add_play(self, track_id: int, performance_id: int, source_path: Path) -> None:
        self.connection.execute(
            "INSERT OR IGNORE INTO plays (track_id,performance_id,source_path) VALUES (?,?,?)",
            (track_id, performance_id, str(source_path.resolve())),
        )
        self.connection.commit()

    def candidates(self, duration: float | None) -> list[Candidate]:
        from djcheck.config import MAX_DURATION_DIFFERENCE
        if duration is None:
            rows = self.connection.execute("SELECT * FROM tracks").fetchall()
        else:
            rows = self.connection.execute(
                "SELECT * FROM tracks WHERE duration IS NULL OR duration BETWEEN ? AND ?",
                (duration - MAX_DURATION_DIFFERENCE, duration + MAX_DURATION_DIFFERENCE),
            ).fetchall()
        return [Candidate(r["id"], r["artist"], r["title"], r["duration"], r["normalized_filename"], r["fingerprint"]) for r in rows]

    def plays_for_track(self, track_id: int) -> list[Play]:
        rows = self.connection.execute(
            "SELECT p.name, p.date, pl.source_path FROM plays pl JOIN performances p ON p.id=pl.performance_id WHERE pl.track_id=? ORDER BY p.date, p.name",
            (track_id,),
        ).fetchall()
        return [Play(r["name"], r["date"], r["source_path"]) for r in rows]
