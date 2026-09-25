import logging
from pathlib import Path
import typer
from djcheck.config import database_path
from djcheck.db.database import Database
from djcheck.audio.fingerprint import FingerprintUnavailable, require_fpcalc
from djcheck.services.indexer import index_history
from djcheck.services.checker import check_folder
from djcheck.output.console import show_result, show_summary

app = typer.Typer(help="Check a future DJ set against locally indexed performances.")


def _validate_folder(path: Path) -> Path:
    path = path.expanduser()
    if not path.is_dir():
        typer.echo(f"Folder does not exist: {path}", err=True)
        raise typer.Exit(2)
    return path


def _require_fpcalc() -> None:
    try:
        require_fpcalc()
    except FingerprintUnavailable as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(2) from exc


@app.command()
def init() -> None:
    """Create the local SQLite database."""
    with Database(database_path()):
        pass
    typer.echo(f"Database ready: {database_path()}")


@app.command()
def index(path: Path = typer.Argument(..., help="History directory with one folder per performance"), debug: bool = False) -> None:
    """Index past sets."""
    logging.basicConfig(level=logging.DEBUG if debug else logging.WARNING, format="%(levelname)s: %(message)s")
    path = _validate_folder(path)
    _require_fpcalc()
    with Database(database_path()) as db:
        def progress(number: int, total: int, file: Path) -> None:
            if number == 1:
                typer.echo(f"Scanning {total} files...")
            typer.echo(f"[{number}/{total}] {file.name}")
        done, total = index_history(path, db, progress)
    typer.echo(f"Indexed {done}/{total} files.")


@app.command()
def check(path: Path = typer.Argument(..., help="Folder for the next set"), debug: bool = False) -> None:
    """Compare a future set against the local history."""
    logging.basicConfig(level=logging.DEBUG if debug else logging.WARNING, format="%(levelname)s: %(message)s")
    path = _validate_folder(path)
    _require_fpcalc()
    if not database_path().exists():
        typer.echo("Database is missing. Run djcheck init or djcheck index first.", err=True)
        raise typer.Exit(2)
    with Database(database_path()) as db:
        results, scanned = check_folder(path, db)
    for result in results:
        show_result(result)
    show_summary(results, scanned)


if __name__ == "__main__":
    app()
