import socket
import subprocess
import time
import uuid

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text


def get_free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def test_checkpoint_migration():
    """Hermetic PostgreSQL 17 migration proof."""
    import pytest

    try:
        subprocess.run(["docker", "info"], check=True, capture_output=True, timeout=5.0)
    except Exception:
        pytest.skip("Docker is required for real PostgreSQL 17 migration proof")

    container_name = f"pg17-checkpoint-test-{uuid.uuid4().hex[:8]}"
    db_port = get_free_port()
    db_url = f"postgresql+psycopg://postgres:postgres@localhost:{db_port}/postgres"

    try:
        # Start PostgreSQL 17
        print(f"Starting PostgreSQL 17 container: {container_name} on port {db_port}")
        subprocess.run(
            [
                "docker",
                "run",
                "-d",
                "--name",
                container_name,
                "-p",
                f"{db_port}:5432",
                "-e",
                "POSTGRES_PASSWORD=postgres",
                "postgres:17-alpine",
            ],
            check=True,
            stdout=subprocess.DEVNULL,
        )

        # Wait for DB to be ready
        engine = create_engine(db_url)
        ready = False
        for _ in range(30):
            try:
                with engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
                ready = True
                break
            except Exception:
                time.sleep(1)

        assert ready, "PostgreSQL failed to start"

        # Run Alembic migrations
        alembic_cfg = Config("alembic.ini")
        alembic_cfg.set_main_option("sqlalchemy.url", db_url)
        command.upgrade(alembic_cfg, "head")

        # Verify task_checkpoints table exists and has correct columns
        with engine.connect() as conn:
            # PostgreSQL specific query to check table schema
            result = conn.execute(
                text("""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = 'task_checkpoints'
            """)
            ).fetchall()

            columns = {row[0]: row[1] for row in result}
            assert "id" in columns
            assert "task_id" in columns
            assert "attempt_id" in columns
            assert "lease_token_hash" in columns
            assert "scrubbed_payload" in columns
            assert "created_at" in columns
            print("task_checkpoints table verified.")

    finally:
        # Cleanup
        print(f"Cleaning up container: {container_name}")
        subprocess.run(
            ["docker", "rm", "-f", container_name], check=False, stdout=subprocess.DEVNULL
        )


if __name__ == "__main__":
    test_checkpoint_migration()
    print("Migration test passed!")
