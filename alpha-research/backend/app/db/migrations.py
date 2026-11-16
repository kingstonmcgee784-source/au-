"""Programmatic access to Alembic: upgrade the schema and inspect its revision."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Connection, Engine

from app.core.config import BACKEND_DIR


def alembic_config(database_url: str) -> Config:
    config = Config(str(Path(BACKEND_DIR) / "alembic.ini"))
    config.set_main_option("script_location", str(Path(BACKEND_DIR) / "alembic"))
    config.set_main_option("sqlalchemy.url", database_url)
    # Leave the application's logging configuration alone.
    config.attributes["configure_logger"] = False
    return config


def upgrade_to_head(database_url: str) -> None:
    command.upgrade(alembic_config(database_url), "head")


def head_revision(database_url: str) -> str | None:
    return ScriptDirectory.from_config(alembic_config(database_url)).get_current_head()


def current_revision(bind: Engine | Connection) -> str | None:
    if isinstance(bind, Connection):
        return MigrationContext.configure(bind).get_current_revision()
    with bind.connect() as connection:
        return MigrationContext.configure(connection).get_current_revision()
