from pathlib import Path

from alembic import command
from sqlalchemy import create_engine, inspect

from app.db.migrations import alembic_config, current_revision, head_revision, upgrade_to_head
from app.models import Base

EXPECTED_TABLES = {
    "stocks",
    "historical_prices",
    "financial_statements",
    "financial_metrics",
    "technical_indicators",
    "stock_scores",
    "research_reports",
    "news_articles",
    "watchlists",
    "watchlist_items",
    "recommendations",
    "backtest_results",
}


def test_fresh_database_upgrades_to_head_and_back(scratch_dir: Path) -> None:
    url = f"sqlite:///{(scratch_dir / 'fresh.db').as_posix()}"
    upgrade_to_head(url)
    engine = create_engine(url)
    tables = set(inspect(engine).get_table_names())
    assert EXPECTED_TABLES <= tables
    assert current_revision(engine) == head_revision(url)

    # Running again is a no-op.
    upgrade_to_head(url)

    command.downgrade(alembic_config(url), "base")
    assert set(inspect(engine).get_table_names()) <= {"alembic_version"}
    engine.dispose()


def test_models_match_migrations(scratch_dir: Path) -> None:
    """Fail if a model changed without a matching migration."""
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext

    url = f"sqlite:///{(scratch_dir / 'diff.db').as_posix()}"
    upgrade_to_head(url)
    engine = create_engine(url)
    with engine.connect() as connection:
        diff = compare_metadata(MigrationContext.configure(connection), Base.metadata)
    engine.dispose()
    assert diff == []
