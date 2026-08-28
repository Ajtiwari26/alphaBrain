import os
import subprocess

import psycopg
import pytest


@pytest.fixture
def disposable_pg():
    container_name = "test_pg_alpha_brain"
    try:
        subprocess.run(["docker", "rm", "-f", container_name], capture_output=True)
        res = subprocess.run(
            [
                "docker",
                "run",
                "--name",
                container_name,
                "-e",
                "POSTGRES_PASSWORD=postgres",
                "-d",
                "-p",
                "5433:5432",
                "postgres:17",
            ],
            capture_output=True,
            text=True,
        )
        if res.returncode != 0:
            pytest.skip(f"Docker run failed: {res.stderr}")
    except Exception as e:
        pytest.skip(f"Docker exception: {e}")

    import time

    db_url = "postgresql://postgres:postgres@localhost:5433/postgres"
    ready = False
    last_err = ""
    for _ in range(30):
        try:
            with psycopg.connect(db_url):
                ready = True
                break
        except Exception as e:
            last_err = str(e)
            time.sleep(1)

    if not ready:
        subprocess.run(["docker", "rm", "-f", container_name], capture_output=True)
        pytest.skip(f"Disposable postgres did not become ready. Last error: {last_err}")

    # Return SQLAlchemy dialect url for alembic
    yield "postgresql+psycopg://postgres:postgres@localhost:5433/postgres"

    subprocess.run(["docker", "rm", "-f", container_name], capture_output=True)


def test_base_to_head_to_base_migration(disposable_pg, monkeypatch):
    import configparser

    config = configparser.ConfigParser()
    config.read("alembic.ini")

    try:
        config.set("alembic", "sqlalchemy.url", disposable_pg)
        with open("alembic_test.ini", "w") as f:
            config.write(f)

        res = subprocess.run(
            ["alembic", "-c", "alembic_test.ini", "upgrade", "head"], capture_output=True, text=True
        )
        assert res.returncode == 0, f"Forward migration failed: {res.stderr}"

        res = subprocess.run(
            ["alembic", "-c", "alembic_test.ini", "downgrade", "base"],
            capture_output=True,
            text=True,
        )
        assert res.returncode == 0, f"Downgrade failed: {res.stderr}"

        res = subprocess.run(
            ["alembic", "-c", "alembic_test.ini", "upgrade", "head"], capture_output=True, text=True
        )
        assert res.returncode == 0, f"Second forward migration failed: {res.stderr}"

    finally:
        if os.path.exists("alembic_test.ini"):
            os.remove("alembic_test.ini")
