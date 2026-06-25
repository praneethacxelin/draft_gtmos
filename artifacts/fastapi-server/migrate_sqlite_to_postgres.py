from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Iterable

from sqlalchemy import MetaData, create_engine, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from app.db import Base

DEFAULT_SQLITE_PATH = Path(__file__).with_name("gtmdb.db")
DEFAULT_BATCH_SIZE = 1000


def build_engine(url: str) -> Engine:
    return create_engine(url, future=True)


def table_row_count(engine: Engine, table_name: str) -> int:
    with engine.connect() as conn:
        result = conn.execute(text(f'SELECT COUNT(*) FROM "{table_name}"'))
        return int(result.scalar_one())


def target_has_data(engine: Engine) -> bool:
    for table in Base.metadata.sorted_tables:
        if table_row_count(engine, table.name) > 0:
            return True
    return False


def copy_table(source_engine: Engine, target_engine: Engine, table_name: str, batch_size: int) -> int:
    table = Base.metadata.tables[table_name]
    copied = 0

    with source_engine.connect() as source_conn, target_engine.begin() as target_conn:
        result = source_conn.execution_options(stream_results=True).execute(select(table))
        while True:
            batch = result.mappings().fetchmany(batch_size)
            if not batch:
                break
            payload = [dict(row) for row in batch]
            if payload:
                target_conn.execute(table.insert(), payload)
                copied += len(payload)

    return copied


def migrate(sqlite_path: Path, postgres_url: str, batch_size: int, force: bool) -> None:
    if not sqlite_path.exists():
        raise FileNotFoundError(f"SQLite database not found: {sqlite_path}")

    source_engine = build_engine(f"sqlite:///{sqlite_path.as_posix()}")
    target_engine = build_engine(postgres_url)

    Base.metadata.create_all(bind=target_engine)

    if not force and target_has_data(target_engine):
        raise RuntimeError(
            "Target Postgres database already contains data. "
            "Use a fresh database or clear it manually before running the migration."
        )

    copied_tables: list[tuple[str, int]] = []
    for table in Base.metadata.sorted_tables:
        copied = copy_table(source_engine, target_engine, table.name, batch_size)
        copied_tables.append((table.name, copied))

    print("Migration complete.")
    for table_name, copied in copied_tables:
        print(f"  {table_name}: {copied} rows copied")


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Copy the existing SQLite data into a Postgres database without dropping source data."
    )
    parser.add_argument(
        "--sqlite-path",
        default=str(DEFAULT_SQLITE_PATH),
        help=f"Path to the source SQLite database file (default: {DEFAULT_SQLITE_PATH})",
    )
    parser.add_argument(
        "--postgres-url",
        default=os.getenv("POSTGRES_URL") or os.getenv("DATABASE_URL"),
        help="Target Postgres SQLAlchemy URL. Falls back to POSTGRES_URL or DATABASE_URL.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help=f"Number of rows to copy per batch (default: {DEFAULT_BATCH_SIZE})",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Allow running even if the target database already has rows.",
    )
    return parser.parse_args(list(argv))


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    if not args.postgres_url:
        raise SystemExit("Missing --postgres-url, POSTGRES_URL, or DATABASE_URL")

    try:
        migrate(Path(args.sqlite_path), args.postgres_url, args.batch_size, args.force)
    except (FileNotFoundError, RuntimeError, SQLAlchemyError) as exc:
        print(f"Migration failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
