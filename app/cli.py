from __future__ import annotations

from pathlib import Path

import typer
from dotenv import load_dotenv

from app.config import ALL_PROVIDERS, DEFAULT_KEYWORDS, DEFAULT_PROVIDERS, EXPERIMENTAL_PROVIDERS, RunConfig
from app.runner import EXIT_DEGRADED, EXIT_ERROR, EXIT_OK, read_status, run_sync

app = typer.Typer(add_completion=False, help="고윤정 이미지 수집 CLI")


def _parse_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


@app.command()
def run(
    providers: str = typer.Option(
        ",".join(DEFAULT_PROVIDERS),
        help='사용할 provider 목록. 기본: "naver,wikimedia,instagram_seed,google"',
    ),
    keywords: str = typer.Option(
        "",
        help="검색어 목록(쉼표 구분). 비우면 기본 추천 키워드 사용",
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="다운로드/저장을 건너뛰고 수집 후보만 점검"),
    once: bool = typer.Option(True, "--once/--no-once", help="단발 실행 여부. 현재는 단발 실행만 지원"),
) -> None:
    load_dotenv()

    selected_providers = _parse_csv(providers)
    unknown = [provider for provider in selected_providers if provider not in ALL_PROVIDERS]
    if unknown:
        typer.echo(f"Unknown provider(s): {','.join(unknown)}")
        raise typer.Exit(code=EXIT_ERROR)

    if not once:
        typer.echo("--no-once는 app.cli run에서 지원하지 않습니다. run_loop.py를 사용하세요.")
        raise typer.Exit(code=EXIT_ERROR)

    selected_keywords = _parse_csv(keywords) if keywords else list(DEFAULT_KEYWORDS)
    config = RunConfig(providers=selected_providers, keywords=selected_keywords, dry_run=dry_run)
    project_root = Path(__file__).resolve().parents[1]
    code = run_sync(config, project_root)
    raise typer.Exit(code=code)


@app.command()
def status() -> None:
    load_dotenv()
    current = read_status()
    if not current:
        typer.echo("No status found. Run collection first.")
        raise typer.Exit(code=EXIT_ERROR)

    last_run = current.get("last_run_kst", "unknown")
    last_ok = int(current.get("last_ok_count", 0) or 0)
    raw_exit = current.get("last_exit_code", EXIT_ERROR)
    last_exit = int(EXIT_ERROR if raw_exit is None else raw_exit)

    typer.echo(f"last_run_kst: {last_run}")
    typer.echo(f"last_ok_count: {last_ok}")
    typer.echo(f"last_exit_code: {last_exit}")

    failures = current.get("failures_by_reason") or {}
    if failures:
        typer.echo("failures_by_reason:")
        for reason in sorted(failures):
            typer.echo(f"  {reason}: {failures[reason]}")

    counts = current.get("counts") or {}
    unique_urls = int(current.get("unique_urls", 0) or 0)

    # Healthy when the last run completed successfully and produced any meaningful outcome
    # (new OKs or confirmed duplicates).
    if last_exit == EXIT_OK and (last_ok > 0 or unique_urls > 0 or int(counts.get("DUPLICATE", 0) or 0) > 0):
        raise typer.Exit(code=EXIT_OK)

    raise typer.Exit(code=EXIT_DEGRADED)


@app.command("providers")
def list_providers() -> None:
    typer.echo(f"recommended: {','.join(DEFAULT_PROVIDERS)}")
    typer.echo(f"experimental: {','.join(EXPERIMENTAL_PROVIDERS)}")


if __name__ == "__main__":
    app()
