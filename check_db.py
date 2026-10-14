"""One-off connectivity probe for the Railway PostgreSQL instance."""

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# Importing the package adds the vendored .site directory to sys.path.
import app  # noqa: E402,F401

from dotenv import load_dotenv  # noqa: E402

load_dotenv(Path(__file__).resolve().parent / ".env")

import asyncpg  # noqa: E402


async def main() -> int:
    dsn = os.environ["DATABASE_URL"]
    print("Connecting to Railway PostgreSQL...")
    conn = await asyncpg.connect(dsn=dsn, ssl="prefer", timeout=30)
    try:
        print("server:", await conn.fetchval("SELECT version()"))
        print("database:", await conn.fetchval("SELECT current_database()"))
        print("search path:", await conn.fetchval("SHOW search_path"))

        tables = await conn.fetch(
            """
            SELECT table_schema, table_name
            FROM information_schema.tables
            WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
            ORDER BY table_schema, table_name
            """
        )
        print("\ntables:")
        for row in tables:
            print(f"  {row['table_schema']}.{row['table_name']}")

        for row in tables:
            if row["table_name"] != "shopping_items":
                continue
            print(f"\ncolumns of {row['table_schema']}.{row['table_name']}:")
            cols = await conn.fetch(
                """
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns
                WHERE table_schema = $1 AND table_name = $2
                ORDER BY ordinal_position
                """,
                row["table_schema"],
                row["table_name"],
            )
            for col in cols:
                print(
                    f"  {col['column_name']:<13} {col['data_type']:<28} "
                    f"null={col['is_nullable']:<3} default={col['column_default']}"
                )
            count = await conn.fetchval(f'SELECT count(*) FROM "{row["table_name"]}"')
            print(f"  rows: {count}")
    finally:
        await conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
