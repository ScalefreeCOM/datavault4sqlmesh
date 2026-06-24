"""
Tests for datavault4sqlmesh.models.satellite — satellite_model() decorator factory.
"""

from __future__ import annotations

import pytest


class TestSatelliteModel:
    def test_returns_decorator(self, sqlmesh):
        """satellite_model(...) must return a callable decorator."""
        from datavault4sqlmesh.models.satellite import satellite_model

        decorator = satellite_model(
            name="dv.customer_0_s",
            parent_hash_key="hk_customer_h",
            hash_diff="hd_customer_s",
            payload=["customer_name", "email"],
        )
        assert callable(decorator)

    def test_decorated_execute_returns_expression(self, sqlmesh):
        """Applying the decorator to a SatelliteGenerator execute body produces SQL."""
        from sqlglot import exp
        from datavault4sqlmesh.models.satellite import satellite_model
        from datavault4sqlglot.generators.satellite import SatelliteGenerator
        from datavault4sqlglot.metadata import SourceModel

        @satellite_model(
            name="dv.customer_0_s",
            parent_hash_key="hk_customer_h",
            hash_diff="hd_customer_s",
            payload=["customer_name", "email"],
        )
        def execute(evaluator, **kwargs):
            return SatelliteGenerator(
                target_table="customer_0_s",
                target_schema="dv",
                source_model=SourceModel(schema_name="stage", table_name="stg_customer"),
                parent_hash_key="hk_customer_h",
                hash_diff="hd_customer_s",
                payload=["customer_name", "email"],
                is_incremental=True,
            ).generate_sql()

        result = execute(evaluator=None)
        assert isinstance(result, exp.Expression)

    def test_sql_contains_payload_columns(self, sqlmesh):
        from datavault4sqlmesh.models.satellite import satellite_model
        from datavault4sqlglot.generators.satellite import SatelliteGenerator
        from datavault4sqlglot.metadata import SourceModel

        @satellite_model(
            name="dv.customer_0_s",
            parent_hash_key="hk_customer_h",
            hash_diff="hd_customer_s",
            payload=["customer_name", "email", "phone"],
        )
        def execute(evaluator, **kwargs):
            return SatelliteGenerator(
                target_table="customer_0_s",
                target_schema="dv",
                source_model=SourceModel(schema_name="stage", table_name="stg_customer"),
                parent_hash_key="hk_customer_h",
                hash_diff="hd_customer_s",
                payload=["customer_name", "email", "phone"],
                is_incremental=True,
            ).generate_sql()

        sql = execute(evaluator=None).sql(dialect="snowflake")
        assert "customer_name" in sql
        assert "email" in sql
        assert "phone" in sql

    def test_hash_diff_as_dict(self, sqlmesh):
        """hash_diff can be a dict with alias key."""
        from sqlglot import exp
        from datavault4sqlmesh.models.satellite import satellite_model
        from datavault4sqlglot.generators.satellite import SatelliteGenerator
        from datavault4sqlglot.metadata import SourceModel

        @satellite_model(
            name="dv.customer_0_s",
            parent_hash_key="hk_customer_h",
            hash_diff={"source_column": "hd_src_col", "alias": "hd_customer_s"},
            payload=["customer_name"],
        )
        def execute(evaluator, **kwargs):
            return SatelliteGenerator(
                target_table="customer_0_s",
                target_schema="dv",
                source_model=SourceModel(schema_name="stage", table_name="stg_customer"),
                parent_hash_key="hk_customer_h",
                hash_diff={"source_column": "hd_src_col", "alias": "hd_customer_s"},
                payload=["customer_name"],
                is_incremental=True,
            ).generate_sql()

        result = execute(evaluator=None)
        assert isinstance(result, exp.Expression)

    def test_incremental_includes_hwm_logic(self, sqlmesh):
        """Incremental mode adds a NOT EXISTS / HWM check referencing the target table."""
        from datavault4sqlmesh.models.satellite import satellite_model
        from datavault4sqlglot.generators.satellite import SatelliteGenerator
        from datavault4sqlglot.metadata import SourceModel

        @satellite_model(
            name="dv.customer_0_s",
            parent_hash_key="hk_customer_h",
            hash_diff="hd_customer_s",
            payload=["customer_name"],
        )
        def execute(evaluator, **kwargs):
            return SatelliteGenerator(
                target_table="customer_0_s",
                target_schema="dv",
                source_model=SourceModel(schema_name="stage", table_name="stg_customer"),
                parent_hash_key="hk_customer_h",
                hash_diff="hd_customer_s",
                payload=["customer_name"],
                is_incremental=True,
            ).generate_sql()

        sql = execute(evaluator=None).sql(dialect="snowflake")
        assert "customer_0_s" in sql

    def test_no_payload_produces_valid_sql(self, sqlmesh):
        """Omitting payload is valid — satellite has only hash key + hash diff."""
        from sqlglot import exp
        from datavault4sqlmesh.models.satellite import satellite_model
        from datavault4sqlglot.generators.satellite import SatelliteGenerator
        from datavault4sqlglot.metadata import SourceModel

        @satellite_model(
            name="dv.customer_0_s",
            parent_hash_key="hk_customer_h",
            hash_diff="hd_customer_s",
        )
        def execute(evaluator, **kwargs):
            return SatelliteGenerator(
                target_table="customer_0_s",
                target_schema="dv",
                source_model=SourceModel(schema_name="stage", table_name="stg_customer"),
                parent_hash_key="hk_customer_h",
                hash_diff="hd_customer_s",
                is_incremental=True,
            ).generate_sql()

        result = execute(evaluator=None)
        assert isinstance(result, exp.Expression)

    def test_auto_generate_with_source_table(self, sqlmesh):
        """source_schema + source_table auto-generates the execute closure."""
        from sqlglot import exp
        from datavault4sqlmesh.models.satellite import satellite_model

        execute = satellite_model(
            name="dv.customer_0_s",
            parent_hash_key="hk_customer_h",
            hash_diff="hd_customer_s",
            payload=["customer_name", "email"],
            source_schema="stage",
            source_table="stg_customer",
        )
        result = execute(evaluator=None)
        assert isinstance(result, exp.Expression)
        sql = result.sql(dialect="snowflake")
        assert "stg_customer" in sql
        assert "customer_name" in sql
