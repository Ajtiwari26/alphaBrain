from alpha_core.db.connection import async_database_url


def test_supabase_postgres_url_uses_async_psycopg_dialect():
    source = "postgresql://postgres.example:5432/postgres?sslmode=require"
    assert async_database_url(source) == (
        "postgresql+psycopg://postgres.example:5432/postgres?sslmode=require"
    )


def test_sqlite_url_remains_unchanged():
    source = "sqlite+aiosqlite:///alpha_brain.db"
    assert async_database_url(source) == source
