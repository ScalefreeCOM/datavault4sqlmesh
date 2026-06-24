"""Shared helpers for integration tests — not a pytest conftest."""
from __future__ import annotations

import psycopg2.extras
from sqlmesh.utils.errors import SQLMeshError


# ---------------------------------------------------------------------------
# Test data batches (synthetic — no realistic personal data)
# ---------------------------------------------------------------------------

# customers: (customer_id, customer_name, email, phone, address, load_date, record_source)
BATCH_C1 = [
    ("X001", "Foo Bar",    "foo@example.com",     "+0-000-0001", "1 Example St", "2024-01-15 08:00:00", "ERP/customers"),
    ("X002", "Baz Qux",    "baz@example.com",     "+0-000-0002", "2 Example St", "2024-01-15 08:00:00", "ERP/customers"),
]
BATCH_C2 = [
    ("X003", "Quux Corge", "quux@example.com",    "+0-000-0003", "3 Example St", "2024-01-16 09:00:00", "ERP/customers"),
]
# X001 reappears with a changed email — triggers a satellite change record
BATCH_C3 = [
    ("X001", "Foo Bar",    "foo.new@example.com", "+0-000-0001", "1 Example St", "2024-02-01 08:00:00", "ERP/customers"),
]

# orders: (order_id, customer_id, order_date, status, amount, load_date, record_source)
BATCH_O1 = [
    ("Y001", "X001", "2024-01-20", "OPEN",      "100.00", "2024-01-20 10:00:00", "OMS/orders"),
    ("Y002", "X002", "2024-01-21", "SHIPPED",   "200.00", "2024-01-21 11:00:00", "OMS/orders"),
]
BATCH_O2 = [
    ("Y003", "X003", "2024-01-22", "OPEN",      "300.00", "2024-01-22 09:00:00", "OMS/orders"),
]
BATCH_O3 = [
    ("Y004", "X001", "2024-02-05", "DELIVERED", "150.00", "2024-02-05 12:00:00", "OMS/orders"),
]

# ---------------------------------------------------------------------------
# SQLMesh model names used for restate
# ---------------------------------------------------------------------------

ALL_DV_MODELS = [
    "stage.stg_customer",
    "stage.stg_orders",
    "dv.customer_h",
    "dv.order_h",
    "dv.order_customer_l",
    "dv.customer_0_s",
    "dv.order_0_s",
    "dv.customer_1_s",
    "dv.order_1_s",
]


# ---------------------------------------------------------------------------
# Source-table helpers
# ---------------------------------------------------------------------------

def insert_customers(pg, rows: list) -> None:
    cur = pg.cursor()
    psycopg2.extras.execute_values(
        cur,
        """
        INSERT INTO user_mszerencse.customers
            (customer_id, customer_name, email, phone, address, load_date, record_source)
        VALUES %s
        """,
        rows,
    )
    pg.commit()
    cur.close()


def insert_orders(pg, rows: list) -> None:
    cur = pg.cursor()
    psycopg2.extras.execute_values(
        cur,
        """
        INSERT INTO user_mszerencse.orders
            (order_id, customer_id, order_date, status, amount, load_date, record_source)
        VALUES %s
        """,
        rows,
    )
    pg.commit()
    cur.close()


# ---------------------------------------------------------------------------
# Assertion helpers
# ---------------------------------------------------------------------------

def row_count(pg, table: str) -> int:
    cur = pg.cursor()
    cur.execute(f"SELECT COUNT(*) FROM {table}")  # noqa: S608
    (n,) = cur.fetchone()
    cur.close()
    return n


def fetch_all(pg, query: str, params=None) -> list:
    cur = pg.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(query, params)
    rows = cur.fetchall()
    cur.close()
    return rows


# ---------------------------------------------------------------------------
# SQLMesh plan helper
# ---------------------------------------------------------------------------

def run_plan(ctx) -> None:
    """Run all DV models against the prod (default) environment, forcing restate.

    On the first call against a fresh DB the 'prod' environment doesn't exist yet,
    so restate_models would raise.  Fall back to a plain plan in that case.
    """
    try:
        ctx.plan(
            auto_apply=True,
            no_prompts=True,
            restate_models=ALL_DV_MODELS,
        )
    except SQLMeshError as exc:
        if "must exist" in str(exc):
            ctx.plan(auto_apply=True, no_prompts=True)
        else:
            raise
