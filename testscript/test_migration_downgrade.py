import subprocess
import time
import uuid

import psycopg
import pytest
from alembic import command
from alembic.config import Config


@pytest.fixture
def disposable_pg():
    container_name = f"test_pg_alpha_brain_{uuid.uuid4().hex[:8]}"
    try:
        subprocess.run(
            [
                "docker",
                "run",
                "--name",
                container_name,
                "-e",
                "POSTGRES_PASSWORD=postgres",
                "-d",
                "-p",
                "0:5432",
                "postgres:17",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        pytest.fail(f"Docker run failed: {e.stderr}")
    except Exception as e:
        pytest.fail(f"Docker exception: {e}")

    try:
        port_res = subprocess.run(
            ["docker", "port", container_name, "5432/tcp"],
            capture_output=True,
            text=True,
            check=True,
        )
        # Output looks like 0.0.0.0:32768 or :::32768
        host_port = port_res.stdout.strip().split(":")[-1]

        # Use 127.0.0.1 to avoid resolving to IPv6 ::1 if docker mapped to IPv4
        db_url_psycopg = f"postgresql://postgres:postgres@127.0.0.1:{host_port}/postgres"
        db_url_sa = f"postgresql+psycopg://postgres:postgres@127.0.0.1:{host_port}/postgres"

        ready = False
        last_err = ""
        for _ in range(30):
            try:
                with psycopg.connect(db_url_psycopg):
                    ready = True
                    break
            except Exception as e:
                last_err = str(e)
                time.sleep(1)

        if not ready:
            pytest.fail(f"Disposable postgres did not become ready. Last error: {last_err}")

        yield {"sa_url": db_url_sa, "psycopg_url": db_url_psycopg}
    finally:
        subprocess.run(["docker", "rm", "-f", container_name], capture_output=True)


def test_base_to_head_to_base_migration(disposable_pg):
    # Construct Alembic Config pointing to real alembic.ini but override connection
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", disposable_pg["sa_url"])

    def get_alembic_version():
        try:
            with psycopg.connect(disposable_pg["psycopg_url"]) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT version_num FROM alembic_version")
                    row = cur.fetchone()
                    return row[0] if row else None
        except psycopg.errors.UndefinedTable:
            return None

    def get_public_tables():
        with psycopg.connect(disposable_pg["psycopg_url"]) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
                )
                return [row[0] for row in cur.fetchall()]

    def check_approvals_attempt_fk():
        with psycopg.connect(disposable_pg["psycopg_url"]) as conn:
            with conn.cursor() as cur:
                # Check for attempt_id column
                cur.execute(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name = 'approvals' AND column_name = 'attempt_id'"
                )
                if not cur.fetchone():
                    return False

                # Check for foreign key
                cur.execute(
                    "SELECT constraint_name FROM information_schema.table_constraints "
                    "WHERE table_name = 'approvals' AND constraint_type = 'FOREIGN KEY'"
                )
                fks = [row[0] for row in cur.fetchall()]
                return "fk_approvals_attempt_id" in fks

    # 1. Upgrade to head
    command.upgrade(config, "head")

    # Assert Head State
    version = get_alembic_version()
    assert version == "58b5b056d9e3", f"Expected head version 58b5b056d9e3, got {version}"
    assert check_approvals_attempt_fk(), (
        "Missing attempt_id or foreign key on approvals table at head"
    )

    # 2. Downgrade to base
    command.downgrade(config, "base")

    # Assert Base State
    version = get_alembic_version()
    assert version is None, f"Expected alembic_version to be absent or empty, got {version}"

    tables = get_public_tables()
    # At base, all D3 tables should be removed. alembic_version may remain.
    d3_tables = [t for t in tables if t != "alembic_version"]
    assert len(d3_tables) == 0, f"Expected no tables (or just alembic_version), got {d3_tables}"

    # 3. Upgrade to head again
    command.upgrade(config, "head")

    # Assert Second Head State
    version = get_alembic_version()
    assert version == "58b5b056d9e3", f"Expected head version 58b5b056d9e3, got {version}"
    assert check_approvals_attempt_fk(), (
        "Missing attempt_id or foreign key on approvals table at second head"
    )
