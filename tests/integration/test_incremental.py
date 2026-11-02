"""
Integration tests for incremental Data Vault loading through datavault4sqlmesh.

Prerequisites:
    Postgres running on localhost:5432 (user=dev, password=dev, database=dev)

Run:
    pytest tests/integration/ -v -m integration
"""
from __future__ import annotations

import pytest

from tests.integration.helpers import (
    BATCH_C1,
    BATCH_C2,
    BATCH_C3,
    BATCH_O1,
    BATCH_O2,
    fetch_all,
    insert_customers,
    insert_orders,
    row_count,
    run_plan,
)

pytestmark = pytest.mark.integration


# ===========================================================================
# Hub tests
# ===========================================================================


class TestHubIncremental:
    def test_hub_initial_load(self, pg, sqlmesh_ctx):
        """First run: all batch-1 customers create hub records."""
        insert_customers(pg, BATCH_C1)
        run_plan(sqlmesh_ctx)

        assert row_count(pg, "dv.customer_h") == 2

    def test_hub_incremental_new_key(self, pg, sqlmesh_ctx):
        """Second run with a new customer adds exactly one new hub record."""
        insert_customers(pg, BATCH_C1)
        run_plan(sqlmesh_ctx)
        count_after_batch1 = row_count(pg, "dv.customer_h")

        insert_customers(pg, BATCH_C2)
        run_plan(sqlmesh_ctx)
        count_after_batch2 = row_count(pg, "dv.customer_h")

        assert count_after_batch1 == 2
        assert count_after_batch2 == 3

    def test_hub_no_duplicate_on_resend(self, pg, sqlmesh_ctx):
        """Re-sending an existing business key with a later ldts must not create a duplicate hub record."""
        insert_customers(pg, BATCH_C1 + BATCH_C3)  # X001 appears twice
        run_plan(sqlmesh_ctx)

        assert row_count(pg, "dv.customer_h") == 2  # X001 and X002, no dup

    def test_hub_idempotency(self, pg, sqlmesh_ctx):
        """Running the plan twice with no new source data must not change row counts."""
        insert_customers(pg, BATCH_C1)
        run_plan(sqlmesh_ctx)
        count_first = row_count(pg, "dv.customer_h")

        run_plan(sqlmesh_ctx)
        count_second = row_count(pg, "dv.customer_h")

        assert count_first == count_second == 2


# ===========================================================================
# Satellite v0 tests
# ===========================================================================


class TestSatelliteIncremental:
    def test_sat_initial_load(self, pg, sqlmesh_ctx):
        """First run populates customer_0_s with one record per customer."""
        insert_customers(pg, BATCH_C1)
        run_plan(sqlmesh_ctx)

        assert row_count(pg, "dv.customer_0_s") == 2

    def test_sat_change_detection(self, pg, sqlmesh_ctx):
        """Attribute change for X001 (new email) must create a second satellite record."""
        insert_customers(pg, BATCH_C1)
        run_plan(sqlmesh_ctx)
        count_after_batch1 = row_count(pg, "dv.customer_0_s")

        insert_customers(pg, BATCH_C3)  # X001 with new email, later ldts
        run_plan(sqlmesh_ctx)

        rows = fetch_all(
            pg,
            """
            SELECT s.email, s.hd_customer_s
            FROM dv.customer_0_s s
            JOIN dv.customer_h h USING (hk_customer_h)
            WHERE h.customer_id = 'X001'
            ORDER BY s.load_date
            """,
        )

        assert count_after_batch1 == 2
        assert row_count(pg, "dv.customer_0_s") == 3  # one new record for X001
        assert len(rows) == 2
        # Two records for X001 must have different hashdiffs
        assert rows[0]["hd_customer_s"] != rows[1]["hd_customer_s"]
        # Latest record has the updated email
        assert rows[-1]["email"] == "foo.new@example.com"

    def test_sat_no_duplicate_on_unchanged_resend(self, pg, sqlmesh_ctx):
        """Re-inserting the same source rows (same ldts, same payload) must not add satellite records."""
        insert_customers(pg, BATCH_C1)
        run_plan(sqlmesh_ctx)

        insert_customers(pg, BATCH_C1)  # exact duplicate of batch 1
        run_plan(sqlmesh_ctx)

        assert row_count(pg, "dv.customer_0_s") == 2

    def test_sat_idempotency(self, pg, sqlmesh_ctx):
        """Re-running the plan with no new source data must not add satellite records."""
        insert_customers(pg, BATCH_C1)
        run_plan(sqlmesh_ctx)
        count_first = row_count(pg, "dv.customer_0_s")

        run_plan(sqlmesh_ctx)

        assert count_first == row_count(pg, "dv.customer_0_s") == 2


# ===========================================================================
# Satellite v1 (EMBEDDED view) tests
# ===========================================================================


class TestSatelliteV1:
    def test_sat_v1_current_state_after_change(self, pg, sqlmesh_ctx):
        """customer_1_s must show exactly one is_current row per customer, reflecting the latest state."""
        insert_customers(pg, BATCH_C1)
        run_plan(sqlmesh_ctx)

        insert_customers(pg, BATCH_C3)  # X001 email change
        run_plan(sqlmesh_ctx)

        current_rows = fetch_all(
            pg,
            "SELECT customer_id, email, is_current FROM dv.customer_1_s WHERE is_current = TRUE",
        )
        all_rows = fetch_all(pg, "SELECT * FROM dv.customer_1_s ORDER BY load_date")

        # Three rows total: X001 (old), X001 (new), X002
        assert len(all_rows) == 3
        # Exactly 2 current rows (one per customer)
        assert len(current_rows) == 2

        x001_current = next(r for r in current_rows if r["customer_id"] == "X001")
        assert x001_current["email"] == "foo.new@example.com"

    def test_sat_v1_end_dates_old_record(self, pg, sqlmesh_ctx):
        """X001's superseded satellite record must have a ledts that is not '9999-12-31'."""
        insert_customers(pg, BATCH_C1)
        run_plan(sqlmesh_ctx)
        insert_customers(pg, BATCH_C3)
        run_plan(sqlmesh_ctx)

        rows = fetch_all(
            pg,
            """
            SELECT s.email, s.ledts, s.is_current
            FROM dv.customer_1_s s
            JOIN dv.customer_h h USING (hk_customer_h)
            WHERE h.customer_id = 'X001'
            ORDER BY s.load_date
            """,
        )

        assert len(rows) == 2
        old_record = rows[0]
        new_record = rows[1]
        assert old_record["is_current"] is False
        assert str(old_record["ledts"]) != "9999-12-31 00:00:00"
        assert new_record["is_current"] is True


# ===========================================================================
# Link tests
# ===========================================================================


class TestLinkIncremental:
    def test_link_initial_load(self, pg, sqlmesh_ctx):
        """First run creates one link record per order."""
        insert_customers(pg, BATCH_C1)
        insert_orders(pg, BATCH_O1)
        run_plan(sqlmesh_ctx)

        assert row_count(pg, "dv.order_customer_l") == 2

    def test_link_incremental_new_key(self, pg, sqlmesh_ctx):
        """Second run with a new order adds exactly one new link record."""
        insert_customers(pg, BATCH_C1)
        insert_orders(pg, BATCH_O1)
        run_plan(sqlmesh_ctx)
        count_after_batch1 = row_count(pg, "dv.order_customer_l")

        insert_customers(pg, BATCH_C2)
        insert_orders(pg, BATCH_O2)
        run_plan(sqlmesh_ctx)
        count_after_batch2 = row_count(pg, "dv.order_customer_l")

        assert count_after_batch1 == 2
        assert count_after_batch2 == 3

    def test_link_no_duplicate_on_resend(self, pg, sqlmesh_ctx):
        """Re-sending existing orders must not duplicate link records."""
        insert_customers(pg, BATCH_C1)
        insert_orders(pg, BATCH_O1)
        run_plan(sqlmesh_ctx)

        insert_orders(pg, BATCH_O1)  # exact duplicate
        run_plan(sqlmesh_ctx)

        assert row_count(pg, "dv.order_customer_l") == 2

    def test_link_idempotency(self, pg, sqlmesh_ctx):
        """Re-running the plan with no new source data must not change link counts."""
        insert_customers(pg, BATCH_C1)
        insert_orders(pg, BATCH_O1)
        run_plan(sqlmesh_ctx)
        count_first = row_count(pg, "dv.order_customer_l")

        run_plan(sqlmesh_ctx)

        assert count_first == row_count(pg, "dv.order_customer_l") == 2
