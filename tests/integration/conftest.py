from __future__ import annotations

import pathlib
import pytest

try:
    import psycopg2
except ImportError:
    psycopg2 = None  # type: ignore[assignment]

try:
    from sqlmesh import Context as SQLMeshContext
except ImportError:
    SQLMeshContext = None  # type: ignore[assignment]


_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
PY_DV_PROJECT_PATH = _REPO_ROOT / "python_dv_project" / "sqlmesh"

# Only INCREMENTAL_UNMANAGED tables need manual clearing — SQLMesh does not
# truncate them between runs.  FULL / VIEW models (stage, sat-v1) are replaced
# entirely by SQLMesh on each plan and must NOT be truncated here.
_INCREMENTAL_TABLES = [
    "dv.customer_h",
    "dv.order_h",
    "dv.order_customer_l",
    "dv.customer_0_s",
    "dv.order_0_s",
]

_PG_DSN = dict(host="localhost", port=5432, user="dev", password="dev", dbname="dev")


def _drop_relation(cur, schema: str, name: str) -> None:
    """Drop a relation regardless of whether it is a table or a view."""
    cur.execute(
        """
        SELECT c.relkind
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = %s AND c.relname = %s
        """,
        (schema, name),
    )
    row = cur.fetchone()
    if row is None:
        return
    relkind = row[0]
    qualified = f"{schema}.{name}"
    if relkind == "r":
        cur.execute(f"DROP TABLE {qualified} CASCADE")  # noqa: S608
    elif relkind in ("v", "m"):
        cur.execute(f"DROP VIEW {qualified} CASCADE")  # noqa: S608


@pytest.fixture(scope="session")
def pg():
    if psycopg2 is None:
        pytest.skip("psycopg2 not installed — run: pip install psycopg2-binary")
    try:
        conn = psycopg2.connect(**_PG_DSN)
        conn.autocommit = False
    except Exception as exc:
        pytest.skip(f"Postgres unavailable ({exc})")
    yield conn
    conn.close()


@pytest.fixture(scope="session")
def sqlmesh_ctx():
    if SQLMeshContext is None:
        pytest.skip("sqlmesh not installed")
    if not PY_DV_PROJECT_PATH.exists():
        pytest.skip(f"python_dv_project not found at {PY_DV_PROJECT_PATH}")
    ctx = SQLMeshContext(paths=[str(PY_DV_PROJECT_PATH)], gateway="local")
    yield ctx


@pytest.fixture(autouse=True)
def clean_state(pg):
    """Reset source and DV tables to empty before every integration test."""
    # Roll back any failed transaction from the previous test.
    pg.rollback()
    cur = pg.cursor()

    # Source tables: drop whatever currently exists (may be a view from a SQLMesh
    # seed run) then create as plain tables that the tests control directly.
    cur.execute("CREATE SCHEMA IF NOT EXISTS user_mszerencse")
    _drop_relation(cur, "user_mszerencse", "customers")
    cur.execute(
        """
        CREATE TABLE user_mszerencse.customers (
            customer_id   VARCHAR,
            customer_name VARCHAR,
            email         VARCHAR,
            phone         VARCHAR,
            address       VARCHAR,
            load_date     TIMESTAMP,
            record_source VARCHAR
        )
        """
    )
    _drop_relation(cur, "user_mszerencse", "orders")
    cur.execute(
        """
        CREATE TABLE user_mszerencse.orders (
            order_id      VARCHAR,
            customer_id   VARCHAR,
            order_date    VARCHAR,
            status        VARCHAR,
            amount        VARCHAR,
            load_date     TIMESTAMP,
            record_source VARCHAR
        )
        """
    )
    pg.commit()

    # Incremental DV tables: drop whatever exists so SQLMesh recreates them as
    # proper tables on the first plan call.  Truncate would fail if a prior plan
    # left them as views; dropping ensures a clean slate regardless of prior state.
    # FULL models (stage, sat-v1) are omitted — SQLMesh replaces them on each plan.
    for qualified in _INCREMENTAL_TABLES:
        schema, _, name = qualified.partition(".")
        _drop_relation(cur, schema, name)
    pg.commit()
    cur.close()
    yield
