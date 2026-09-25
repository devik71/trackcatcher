from pathlib import Path
import typer
from djcheck.matching.matcher import MatchResult


def show_result(result: MatchResult) -> None:
    marker = {"NEW": "✓", "PLAYED_BEFORE": "⚠", "POSSIBLE_MATCH": "?"}[result.status]
    color = {"NEW": typer.colors.GREEN, "PLAYED_BEFORE": typer.colors.YELLOW, "POSSIBLE_MATCH": typer.colors.CYAN}[result.status]
    typer.secho(f"{marker} {Path(result.path).name}", fg=color)
    typer.secho(f"  {result.status.replace('_', ' ')}", fg=color)
    if result.candidate:
        label = result.candidate.title or result.candidate.normalized_filename
        typer.echo(f"  candidate: {label}")
    typer.echo(f"  match: {result.method or 'NONE'}")
    typer.echo(f"  confidence: {result.confidence:.3f}")
    if result.plays:
        typer.echo("  Previous plays:")
        for play in result.plays:
            typer.echo(f"    {play.date or 'unknown date'} — {play.performance}")
    typer.echo()


def show_summary(results: list[MatchResult], scanned: int) -> None:
    counts = {status: sum(r.status == status for r in results) for status in ("NEW", "PLAYED_BEFORE", "POSSIBLE_MATCH")}
    typer.echo("SUMMARY")
    typer.echo(f"Tracks scanned:       {scanned}")
    typer.echo(f"New:                  {counts['NEW']}")
    typer.echo(f"Played before:        {counts['PLAYED_BEFORE']}")
    typer.echo(f"Possible matches:     {counts['POSSIBLE_MATCH']}")
    if scanned != len(results):
        typer.echo(f"Could not read:       {scanned - len(results)}")
