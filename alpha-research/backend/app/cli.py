"""Command-line tasks.

Usage, from the backend directory:

    python -m app.cli sync-prices MSFT LIVN PLAB
    python -m app.cli sync-financials MSFT LIVN PLAB
    python -m app.cli sync-insiders MSFT LIVN PLAB
    python -m app.cli sync-events MSFT LIVN PLAB
    python -m app.cli score MSFT LIVN PLAB
    python -m app.cli scan MSFT LIVN PLAB ...   (waits out rate limits; can take a while)
"""

import argparse
import sys

from app.core.config import get_settings
from app.db.migrations import upgrade_to_head
from app.db.session import SessionLocal
from app.providers.registry import get_fundamentals_client, get_market_data_provider
from app.schemas.common import DataStatus, normalize_ticker
from app.schemas.screener import ScanRequest
from app.services.catalysts import sync_events
from app.services.ingestion import sync_financials, sync_prices
from app.services.insiders import sync_insiders
from app.services.scoring_pipeline import score_stock
from app.services.screener import create_scan, get_scan, process_scan


def _sync_prices(tickers: list[str]) -> int:
    settings = get_settings()
    upgrade_to_head(settings.database_url)
    provider = get_market_data_provider(settings)
    failures = 0
    with SessionLocal() as db:
        for raw in tickers:
            try:
                ticker = normalize_ticker(raw)
            except ValueError as exc:
                print(f"{raw}: {exc}")
                failures += 1
                continue
            result = sync_prices(db, provider, ticker, history_years=settings.price_history_years)
            if result.status == DataStatus.OK and result.data:
                d = result.data
                print(
                    f"{ticker}: +{d.bars_added} new bars, {d.bars_stored} stored "
                    f"({d.first_date} to {d.last_date})"
                )
            else:
                print(f"{ticker}: not synced ({result.reason}): {result.message}")
                failures += 1
    return 1 if failures else 0


def _sync_financials(tickers: list[str]) -> int:
    settings = get_settings()
    upgrade_to_head(settings.database_url)
    source = get_fundamentals_client(settings)
    failures = 0
    with SessionLocal() as db:
        for raw in tickers:
            try:
                ticker = normalize_ticker(raw)
            except ValueError as exc:
                print(f"{raw}: {exc}")
                failures += 1
                continue
            result = sync_financials(db, source, ticker)
            if result.status == DataStatus.OK and result.data:
                d = result.data
                print(
                    f"{ticker}: {d.statements_stored} statements ({d.quarterly_periods} quarters, "
                    f"{d.annual_periods} years), latest period {d.latest_period_end}"
                )
            else:
                print(f"{ticker}: not synced ({result.reason}): {result.message}")
                failures += 1
    return 1 if failures else 0


def _sync_insiders(tickers: list[str]) -> int:
    settings = get_settings()
    upgrade_to_head(settings.database_url)
    source = get_fundamentals_client(settings)
    failures = 0
    with SessionLocal() as db:
        for raw in tickers:
            try:
                ticker = normalize_ticker(raw)
            except ValueError as exc:
                print(f"{raw}: {exc}")
                failures += 1
                continue
            result = sync_insiders(db, source, ticker)
            if result.status == DataStatus.OK and result.data:
                d = result.data
                print(
                    f"{ticker}: {d.filings_added} new Form 4 filings, {d.transactions_added} "
                    f"trades ({d.filings_remaining} more to load next time)"
                )
            else:
                print(f"{ticker}: not synced ({result.reason}): {result.message}")
                failures += 1
    return 1 if failures else 0


def _sync_events(tickers: list[str]) -> int:
    settings = get_settings()
    upgrade_to_head(settings.database_url)
    source = get_fundamentals_client(settings)
    failures = 0
    with SessionLocal() as db:
        for raw in tickers:
            try:
                ticker = normalize_ticker(raw)
            except ValueError as exc:
                print(f"{raw}: {exc}")
                failures += 1
                continue
            result = sync_events(db, source, ticker)
            if result.status == DataStatus.OK and result.data:
                d = result.data
                print(f"{ticker}: {d.events_added} new 8-K events ({d.events_stored} stored)")
            else:
                print(f"{ticker}: not synced ({result.reason}): {result.message}")
                failures += 1
    return 1 if failures else 0


def _score(tickers: list[str]) -> int:
    settings = get_settings()
    upgrade_to_head(settings.database_url)
    market = get_market_data_provider(settings)
    fundamentals = get_fundamentals_client(settings)
    failures = 0
    with SessionLocal() as db:
        for raw in tickers:
            try:
                ticker = normalize_ticker(raw)
            except ValueError as exc:
                print(f"{raw}: {exc}")
                failures += 1
                continue
            result = score_stock(
                db,
                ticker,
                market=market,
                fundamentals=fundamentals,
                refresh=True,
                history_years=settings.price_history_years,
            )
            if result.status == DataStatus.OK and result.data:
                d = result.data
                print(
                    f"{ticker}: {d.total_score:.1f}/100 ({d.interpretation}), "
                    f"coverage {d.coverage:.0%}, risk {d.risk_class or 'unknown'}"
                )
            else:
                print(f"{ticker}: not scored ({result.reason}): {result.message}")
                failures += 1
    return 1 if failures else 0


def _scan(tickers: list[str]) -> int:
    settings = get_settings()
    upgrade_to_head(settings.database_url)
    try:
        request = ScanRequest(tickers=tickers)
    except ValueError as exc:
        print(exc)
        return 1
    with SessionLocal() as db:
        scan = create_scan(db, request)
    print(f"Scanning {scan.total} tickers (scan #{scan.id})...")
    process_scan(
        scan.id,
        market=get_market_data_provider(settings),
        fundamentals=get_fundamentals_client(settings),
        history_years=settings.price_history_years,
    )
    with SessionLocal() as db:
        result = get_scan(db, scan.id)
    for item in result.items:
        detail = f"{item.score:.1f}/100" if item.score is not None else item.message or ""
        print(f"{item.ticker}: {item.status} {detail}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    sync = commands.add_parser("sync-prices", help="Load daily prices for tickers")
    sync.add_argument("tickers", nargs="+")
    fin = commands.add_parser("sync-financials", help="Load SEC financial statements for tickers")
    fin.add_argument("tickers", nargs="+")
    ins = commands.add_parser("sync-insiders", help="Load Form 4 insider filings for tickers")
    ins.add_argument("tickers", nargs="+")
    events = commands.add_parser("sync-events", help="Load SEC 8-K events for tickers")
    events.add_argument("tickers", nargs="+")
    score = commands.add_parser("score", help="Refresh data and score tickers")
    score.add_argument("tickers", nargs="+")
    scan = commands.add_parser("scan", help="Score many tickers, waiting out rate limits")
    scan.add_argument("tickers", nargs="+")
    args = parser.parse_args(argv)
    if args.command == "sync-prices":
        return _sync_prices(args.tickers)
    if args.command == "sync-financials":
        return _sync_financials(args.tickers)
    if args.command == "sync-insiders":
        return _sync_insiders(args.tickers)
    if args.command == "sync-events":
        return _sync_events(args.tickers)
    if args.command == "score":
        return _score(args.tickers)
    if args.command == "scan":
        return _scan(args.tickers)
    return 2


if __name__ == "__main__":
    sys.exit(main())
