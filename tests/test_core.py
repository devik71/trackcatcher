from pathlib import Path
import wave

from typer.testing import CliRunner

from djcheck.audio.hashing import sha256_file
from djcheck.audio.fingerprint import fingerprint_similarity, fingerprint_file
from djcheck.audio.scanner import scan_audio
from djcheck.db.database import Database
from djcheck.db.models import AudioInfo, Candidate
from djcheck.matching.normalize import normalize_filename
from djcheck.matching.metadata_matcher import score_metadata, similarity
from djcheck.matching.matcher import classify
from djcheck.matching.fingerprint_matcher import combined_score
from djcheck.matching.metadata_matcher import MetadataScore
from djcheck.services.indexer import index_history, parse_performance_name
from djcheck.services.checker import check_folder


def test_normalization():
    a = normalize_filename("01 Objekt - Theme From Q.wav")
    b = normalize_filename("Objekt - Theme from Q [320].mp3")
    assert a == b
    assert similarity(a, b) == 1.0
    assert normalize_filename("01 日本語_曲.flac") == "日本語 曲"
    assert normalize_filename("Objekt-Theme_From_Q.wav") == a


def test_hash(tmp_path):
    a, b = tmp_path / "a.mp3", tmp_path / "b.wav"
    a.write_bytes(b"identical bytes")
    b.write_bytes(b"identical bytes")
    assert sha256_file(a) == sha256_file(b)


def test_metadata_matcher():
    info = AudioInfo(Path("Objekt - Theme From Q.wav"), "Objekt", "Theme From Q", None, 312, "objekt theme from q")
    candidate = Candidate(1, "objekt", "Theme from Q", 313, "objekt theme from q", None)
    score = score_metadata(info, candidate)
    assert score.artist == 1.0
    assert score.title == 1.0
    assert score.duration > 0.98
    assert 0.85 < score.score < 0.90


def test_classifier():
    assert classify(0.90) == "PLAYED_BEFORE"
    assert classify(0.65) == "POSSIBLE_MATCH"
    assert classify(0.649) == "NEW"


def test_fingerprint_alignment():
    values = ",".join(str(100000 + i * 7919) for i in range(40))
    assert fingerprint_similarity(values, values) == 1.0


def test_fpcalc_raw_output(monkeypatch, tmp_path):
    from subprocess import CompletedProcess
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        return CompletedProcess(command, 0, "DURATION=120\nFINGERPRINT=1,2,3\n", "")

    monkeypatch.setattr("djcheck.audio.fingerprint.subprocess.run", fake_run)
    assert fingerprint_file(tmp_path / "日本語.wav") == "1,2,3"
    assert calls[0][:2] == ["fpcalc", "-raw"]


def test_audio_can_identify_renamed_track():
    metadata = MetadataScore(0, 0, 0, 1, 0.27)
    assert classify(combined_score(metadata, 1.0)) == "PLAYED_BEFORE"
    assert classify(combined_score(metadata, 0.4)) == "NEW"


def test_database_relationship(tmp_path):
    with Database(tmp_path / "db.sqlite3") as db:
        info = AudioInfo(tmp_path / "a.wav", "Artist", "Title", None, 60, "artist title")
        track = db.add_track(info, "abc", "fingerprint")
        p1 = db.add_performance("BRUKXT", "2025-11-22", tmp_path / "2025-11-22_BRUKXT")
        p2 = db.add_performance("K41", "2026-01-18", tmp_path / "2026-01-18_K41")
        db.add_play(track, p1, tmp_path / "one.wav")
        db.add_play(track, p2, tmp_path / "two.wav")
        db.add_play(track, p1, tmp_path / "one.wav")
        assert db.track_by_hash("abc")["id"] == track
        assert [(p.date, p.performance) for p in db.plays_for_track(track)] == [
            ("2025-11-22", "BRUKXT"), ("2026-01-18", "K41")
        ]


def _wav(path: Path):
    with wave.open(str(path), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(8000)
        out.writeframes(b"\0\0" * 8000)


def test_scanner_and_corrupt_file(tmp_path, caplog, monkeypatch):
    history = tmp_path / "history"
    performance = history / "2026-01-18_K41"
    performance.mkdir(parents=True)
    _wav(performance / "good.wav")
    (performance / "bad.mp3").write_bytes(b"not audio")
    (performance / "notes.txt").write_text("ignore")
    monkeypatch.setattr("djcheck.services.indexer.fingerprint_file", lambda _: "test-fingerprint")
    with Database(tmp_path / "db.sqlite3") as db:
        indexed, total = index_history(history, db)
        assert (indexed, total) == (1, 2)
        assert db.connection.execute("SELECT COUNT(*) FROM plays").fetchone()[0] == 1
    assert "could not read file" in caplog.text
    assert len(scan_audio(performance)) == 2


def test_end_to_end_exact_and_new(tmp_path, monkeypatch):
    history = tmp_path / "history"
    performance = history / "2025-11-22_BRUKXT"
    performance.mkdir(parents=True)
    _wav(performance / "played.wav")
    future = tmp_path / "future"
    future.mkdir()
    (future / "same.wav").write_bytes((performance / "played.wav").read_bytes())
    _wav(future / "new.wav")
    # Change a byte in sample data without breaking the WAV container.
    data = bytearray((future / "new.wav").read_bytes())
    data[-1] = 1
    (future / "new.wav").write_bytes(data)
    monkeypatch.setattr("djcheck.services.indexer.fingerprint_file", lambda _: "x")
    monkeypatch.setattr("djcheck.services.checker.fingerprint_file", lambda _: "y")
    monkeypatch.setattr("djcheck.matching.matcher.fingerprint_similarity", lambda *_: 0.0)
    with Database(tmp_path / "db.sqlite3") as db:
        index_history(history, db)
        results, scanned = check_folder(future, db)
    assert scanned == 2
    assert {Path(r.path).name: r.status for r in results} == {"new.wav": "NEW", "same.wav": "PLAYED_BEFORE"}
    assert next(r for r in results if r.status == "PLAYED_BEFORE").plays[0].performance == "BRUKXT"


def test_all_three_statuses(tmp_path, monkeypatch):
    history = tmp_path / "history" / "2026-01-18_K41"
    history.mkdir(parents=True)
    _wav(history / "played.wav")
    future = tmp_path / "future"
    future.mkdir()
    (future / "exact.wav").write_bytes((history / "played.wav").read_bytes())
    for name, last_byte in (("played.wav", 1), ("renamed.wav", 2), ("other.wav", 3)):
        data = bytearray((history / "played.wav").read_bytes())
        data[-1] = last_byte
        (future / name).write_bytes(data)
    monkeypatch.setattr("djcheck.services.indexer.fingerprint_file", lambda _: "same")
    monkeypatch.setattr(
        "djcheck.services.checker.fingerprint_file",
        lambda path: "same" if path.name == "renamed.wav" else "different",
    )
    monkeypatch.setattr("djcheck.matching.matcher.fingerprint_similarity", lambda a, b: float(a == b))
    with Database(tmp_path / "db.sqlite3") as db:
        index_history(tmp_path / "history", db)
        results, _ = check_folder(future, db)
    statuses = {Path(result.path).name: result.status for result in results}
    assert statuses == {
        "exact.wav": "PLAYED_BEFORE",
        "played.wav": "POSSIBLE_MATCH",
        "renamed.wav": "PLAYED_BEFORE",
        "other.wav": "NEW",
    }


def test_performance_parse():
    assert parse_performance_name(Path("2026-01-18_K41")) == ("2026-01-18", "K41")
    assert parse_performance_name(Path("no-date_日本語")) == (None, "no-date_日本語")
    assert parse_performance_name(Path("2026-99-99_Club")) == (None, "2026-99-99_Club")


def test_cli_missing_fpcalc(tmp_path, monkeypatch):
    from djcheck.cli import app
    monkeypatch.setattr("djcheck.audio.fingerprint.shutil.which", lambda _: None)
    runner = CliRunner()
    result = runner.invoke(app, ["index", str(tmp_path)])
    assert result.exit_code == 2
    assert "Install Chromaprint" in result.output


def test_cli_index_check_output(tmp_path, monkeypatch):
    from djcheck.cli import app
    source = tmp_path / "history" / "2025-11-22_BRUKXT"
    source.mkdir(parents=True)
    _wav(source / "played.wav")
    future = tmp_path / "future"
    future.mkdir()
    (future / "played.wav").write_bytes((source / "played.wav").read_bytes())
    monkeypatch.setenv("DJCHECK_DB", str(tmp_path / "db.sqlite3"))
    monkeypatch.setattr("djcheck.cli.require_fpcalc", lambda: None)
    monkeypatch.setattr("djcheck.services.indexer.fingerprint_file", lambda _: "same")
    runner = CliRunner()
    assert runner.invoke(app, ["init"]).exit_code == 0
    indexed = runner.invoke(app, ["index", str(tmp_path / "history")])
    assert indexed.exit_code == 0
    assert "Indexed 1/1 files" in indexed.output
    checked = runner.invoke(app, ["check", str(future), "--debug"])
    assert checked.exit_code == 0
    assert "PLAYED BEFORE" in checked.output
    assert "BRUKXT" in checked.output
    assert "EXACT_FILE" in checked.output
    assert "1.000" in checked.output
