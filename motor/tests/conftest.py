import os
import uuid
from pathlib import Path

import psycopg
import pytest
from psycopg.conninfo import make_conninfo

ROOT = Path(__file__).resolve().parents[2]
STUB = Path(__file__).with_name("supabase_stub.sql")


@pytest.fixture
def db_url():
    """En tom testdatabas med Klubbhusets schema. Kräver KH_TEST_DATABASE_URL."""
    admin = os.environ.get("KH_TEST_DATABASE_URL")
    if not admin:
        pytest.skip("KH_TEST_DATABASE_URL saknas – databastesterna hoppas över")
    name = f"kh_test_{uuid.uuid4().hex[:8]}"
    with psycopg.connect(admin, autocommit=True) as conn:
        conn.execute(f'create database "{name}"')
    url = make_conninfo(admin, dbname=name)
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute(STUB.read_text(encoding="utf-8"))
        conn.execute((ROOT / "supabase" / "schema.sql").read_text(encoding="utf-8"))
    yield url
    with psycopg.connect(admin, autocommit=True) as conn:
        conn.execute(f'drop database "{name}" with (force)')
