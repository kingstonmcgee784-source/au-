"""Command-line tasks.

Usage, from the backend directory:

    python -m app.cli sync-prices MSFT LIVN PLAB
"""

import argparse
import sys

from app.core.config import get_settings
from app.db.migrations import upgrade_to_head
from app.db.session import SessionLocal
from app.providers.registry import get_market_data_provider
from app.schemas.common import DataStatus, normalize_ticker
from app.services.ingestion import sync_prices


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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    sync = commands.add_parser("sync-prices", help="Load daily prices for tickers")
    sync.add_argument("tickers", nargs="+")
    args = parser.parse_args(argv)
    if args.command == "sync-prices":
        return _sync_prices(args.tickers)
    return 2


if __name__ == "__main__":
    sys.exit(main())
