"""
Tests for datavault4sqlmesh.models.satellite_v1 — satellite_v1_model() decorator factory.
"""

from __future__ import annotations

import pytest


def _make_sat_v1_execute(
    sat_v0_table: str = "customer_0_s",
    sat_v0_schema: str = "dv",
    parent_hash_key: str = "hk_customer_h",
    hash_diff: str = "hd_customer_s",
    add_is_current: bool = True,
    is_current_col: str = "is_current",
    ledts_alias: "str | None" = None,
):
    """Return an execute function body for testing — avoids closure variables."""
    from datavault4sqlglot.generators.satellite_v1 import SatelliteV1Generator

    def execute(evaluator, **kwargs):
        return SatelliteV1Generator(
            target_table="customer_1_s",
            target_schema="dv",
            sat_v0_table=sat_v0_table,
            sat_v0_schema=sat_v0_schema,
            parent_hash_key=parent_hash_key,
            hash_diff=hash_diff,
            add_is_current=add_is_current,
            is_current_col=is_current_col,
            ledts_alias=ledts_alias,
        ).generate_sql()

    return execute


class TestSatelliteV1Model:
    def test_returns_decorator(self, sqlmesh):
        """satellite_v1_model(...) must return a callable decorator."""
        from datavault4sqlmesh.models.satellite_v1 import satellite_v1_model

        decorator = satellite_v1_model(
            name="dv.customer_1_s",
            parent_hash_key="hk_customer_h",
            hash_diff="hd_customer_s",
            payload=["customer_name", "email"],
        )
        assert callable(decorator)

    def test_decorated_execute_returns_expression(self, sqlmesh):
        """Applying the decorator to a SatelliteV1Generator execute body produces SQL."""
        from sqlglot import exp
        from datavault4sqlmesh.models.satellite_v1 import satellite_v1_model
        from datavault4sqlglot.generators.satellite_v1 import SatelliteV1Generator

        @satellite_v1_model(
            name="dv.customer_1_s",
            parent_hash_key="hk_customer_h",
            hash_diff="hd_customer_s",
            payload=["customer_name", "email"],
        )
        def execute(evaluator, **kwargs):
            return SatelliteV1Generator(
                target_table="customer_1_s",
                target_schema="dv",
                sat_v0_table="customer_0_s",
                sat_v0_schema="dv",
                parent_hash_key="hk_customer_h",
                hash_diff="hd_customer_s",
            ).generate_sql()

        result = execute(evaluator=None)
        assert isinstance(result, exp.Expression)

    def test_sql_contains_lead_window(self, sqlmesh):
        """SatelliteV1Generator uses a LEAD() window for ledts computation."""
        from datavault4sqlmesh.models.satellite_v1 import satellite_v1_model
        from datavault4sqlglot.generators.satellite_v1 import SatelliteV1Generator

        @satellite_v1_model(
            name="dv.customer_1_s",
            parent_hash_key="hk_customer_h",
            hash_diff="hd_customer_s",
        )
        def execute(evaluator, **kwargs):
            return SatelliteV1Generator(
                target_table="customer_1_s",
                target_schema="dv",
                sat_v0_table="customer_0_s",
                sat_v0_schema="dv",
                parent_hash_key="hk_customer_h",
                hash_diff="hd_customer_s",
            ).generate_sql()

        sql = execute(evaluator=None).sql(dialect="snowflake")
        assert "LEAD" in sql.upper()

    def test_sql_references_source_v0_table(self, sqlmesh):
        """The execute body references the sat_v0 table via SatelliteV1Generator."""
        from datavault4sqlmesh.models.satellite_v1 import satellite_v1_model
        from datavault4sqlglot.generators.satellite_v1 import SatelliteV1Generator

        @satellite_v1_model(
            name="dv.customer_1_s",
            parent_hash_key="hk_customer_h",
            hash_diff="hd_customer_s",
        )
        def execute(evaluator, **kwargs):
            return SatelliteV1Generator(
                target_table="customer_1_s",
                target_schema="dv",
                sat_v0_table="customer_0_s",
                sat_v0_schema="dv",
                parent_hash_key="hk_customer_h",
                hash_diff="hd_customer_s",
            ).generate_sql()

        sql = execute(evaluator=None).sql(dialect="snowflake")
        assert "customer_0_s" in sql

    def test_is_current_column_present_by_default(self, sqlmesh):
        from datavault4sqlmesh.models.satellite_v1 import satellite_v1_model
        from datavault4sqlglot.generators.satellite_v1 import SatelliteV1Generator

        @satellite_v1_model(
            name="dv.customer_1_s",
            parent_hash_key="hk_customer_h",
            hash_diff="hd_customer_s",
        )
        def execute(evaluator, **kwargs):
            return SatelliteV1Generator(
                target_table="customer_1_s",
                target_schema="dv",
                sat_v0_table="customer_0_s",
                sat_v0_schema="dv",
                parent_hash_key="hk_customer_h",
                hash_diff="hd_customer_s",
                add_is_current=True,
            ).generate_sql()

        sql = execute(evaluator=None).sql(dialect="snowflake")
        assert "is_current" in sql.lower()

    def test_is_current_disabled(self, sqlmesh):
        from datavault4sqlmesh.models.satellite_v1 import satellite_v1_model
        from datavault4sqlglot.generators.satellite_v1 import SatelliteV1Generator

        @satellite_v1_model(
            name="dv.customer_1_s",
            parent_hash_key="hk_customer_h",
            hash_diff="hd_customer_s",
            add_is_current=False,
        )
        def execute(evaluator, **kwargs):
            return SatelliteV1Generator(
                target_table="customer_1_s",
                target_schema="dv",
                sat_v0_table="customer_0_s",
                sat_v0_schema="dv",
                parent_hash_key="hk_customer_h",
                hash_diff="hd_customer_s",
                add_is_current=False,
            ).generate_sql()

        sql = execute(evaluator=None).sql(dialect="snowflake")
        assert "is_current" not in sql.lower()

    def test_source_v0_schema_parsed_correctly(self, sqlmesh):
        """A non-default sat_v0 schema appears in the generated SQL."""
        from datavault4sqlmesh.models.satellite_v1 import satellite_v1_model
        from datavault4sqlglot.generators.satellite_v1 import SatelliteV1Generator

        @satellite_v1_model(
            name="dv.customer_1_s",
            parent_hash_key="hk_customer_h",
            hash_diff="hd_customer_s",
        )
        def execute(evaluator, **kwargs):
            return SatelliteV1Generator(
                target_table="customer_1_s",
                target_schema="dv",
                sat_v0_table="customer_0_s",
                sat_v0_schema="archive",
                parent_hash_key="hk_customer_h",
                hash_diff="hd_customer_s",
            ).generate_sql()

        sql = execute(evaluator=None).sql(dialect="snowflake")
        assert "archive" in sql.lower()
