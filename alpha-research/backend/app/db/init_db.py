"""Initialize (or upgrade) the database schema.

Usage, from the backend directory:

    python -m app.db.init_db

Safe to run repeatedly: Alembic only applies migrations that are missing.
No sample or placeholder financial data is inserted.
"""

import logging

from sqlalchemy import inspect

from app.core.config import get_settings
from app.db.migrations import current_revision, head_revision, upgrade_to_head
from app.db.session import engine

logger = logging.getLogger(__name__)


def init_db() -> str | None:
    settings = get_settings()
    upgrade_to_head(settings.database_url)
    return current_revision(engine)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    settings = get_settings()
    revision = init_db()
    tables = sorted(inspect(engine).get_table_names())
    logger.info("Database: %s", settings.database_url)
    logger.info("Schema revision: %s (head: %s)", revision, head_revision(settings.database_url))
    logger.info("Tables (%d): %s", len(tables), ", ".join(tables))


if __name__ == "__main__":
    main()
