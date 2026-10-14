"""Print the columns of every table this app uses."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import app  # noqa: E402,F401  (adds the vendored .site directory)

from dotenv import load_dotenv  # noqa: E402

load_dotenv(Path(__file__).resolve().parent / ".env")

import asyncpg  # noqa: E402

COLUMNS_SQL = """
    SELECT column_name, data_type, is_nullable, column_default
    FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = $1
    ORDER BY ordinal_position
"""


async def main() -> int:
    conn = await asyncpg.connect(dsn=os.environ["DATABASE_URL"], ssl="prefer", timeout=30)
    try:
        tables = await conn.fetch(
            """
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public' ORDER BY table_name
            """
        )
        for row in tables:
            table = row["table_name"]
            count = await conn.fetchval(f'SELECT count(*) FROM public."{table}"')
            print(f"\n=== {table}  ({count} filas) ===")
            for col in await conn.fetch(COLUMNS_SQL, table):
                print(
                    f"  {col['column_name']:<14} {col['data_type']:<26} "
                    f"null={col['is_nullable']:<3} default={col['column_default']}"
                )
    finally:
        await conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
