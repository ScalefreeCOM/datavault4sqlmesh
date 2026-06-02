"""
Tests for datavault4sqlmesh.models.stage — stage_model() factory.
"""

from __future__ import annotations

import pytest

from datavault4sqlglot.metadata import StageModel


def _make_stage_model() -> StageModel:
    return StageModel(
        schema_name="user_mszerencse",
        table_name="customers",
        hashed_columns={
            "hk_customer_h": ["customer_id"],
            "hd_customer_s": {
                "is_hashdiff": True,
                "columns": ["customer_name", "email", "phone", "address"],
            },
        },
    )


class TestStageModel:
    def test_returns_callable(self, sqlmesh):
        """stage_model(...) registers and returns a callable execute function."""
        from datavault4sqlmesh.models.stage import stage_model

        execute_fn = stage_model(
            name="stage.stg_customer",
            source_model=_make_stage_model(),
        )
        assert callable(execute_fn)

    def test_execute_returns_expression(self, sqlmesh):
        """Calling the returned function produces a SQL expression."""
        from sqlglot import exp
        from datavault4sqlmesh.models.stage import stage_model

        execute_fn = stage_model(
            name="stage.stg_customer",
            source_model=_make_stage_model(),
        )
        result = execute_fn(evaluator=None)
        assert isinstance(result, exp.Expression)

    def test_sql_contains_hashed_columns(self, sqlmesh):
        from datavault4sqlmesh.models.stage import stage_model

        execute_fn = stage_model(
            name="stage.stg_customer",
            source_model=_make_stage_model(),
        )
        sql = execute_fn(evaluator=None).sql(dialect="snowflake")
        assert "hk_customer_h" in sql
        assert "hd_customer_s" in sql

    def test_sql_references_source_table(self, sqlmesh):
        from datavault4sqlmesh.models.stage import stage_model

        execute_fn = stage_model(
            name="stage.stg_customer",
            source_model=_make_stage_model(),
        )
        sql = execute_fn(evaluator=None).sql(dialect="snowflake")
        assert "customers" in sql

    def test_cast_ldts_to_timestamp(self, sqlmesh):
        """cast_ldts_to_timestamp=True wraps SQL with an outer CAST for ldts."""
        from sqlglot import exp
        from datavault4sqlmesh.models.stage import stage_model

        execute_fn = stage_model(
            name="stage.stg_customer",
            source_model=_make_stage_model(),
            column_overrides={"customer_id": "VARCHAR"},
            cast_ldts_to_timestamp=True,
        )
        result = execute_fn(evaluator=None)
        assert isinstance(result, exp.Expression)
        sql = result.sql(dialect="duckdb")
        # The outer SELECT must contain a CAST of the ldts column
        assert "CAST" in sql.upper() or "cast" in sql.lower()
        assert "TIMESTAMP" in sql.upper()

    def test_column_overrides_forwarded_to_inferred_schema(self, sqlmesh):
        """column_overrides affect the columns dict passed to @model."""
        from datavault4sqlmesh.schema.inference import infer_stage_columns

        source = _make_stage_model()
        overrides = {"customer_id": "BIGINT"}
        cols = infer_stage_columns(source, column_overrides=overrides)
        assert cols["customer_id"] == "BIGINT"

    def test_derived_columns_included_in_schema(self, sqlmesh):
        from datavault4sqlmesh.schema.inference import infer_stage_columns

        source = StageModel(
            table_name="orders",
            derived_columns={"order_total": "quantity * unit_price"},
        )
        cols = infer_stage_columns(source)
        assert "order_total" in cols

    def test_minimal_source_model_produces_callable(self, sqlmesh):
        """Even a minimal StageModel produces a valid execute function."""
        from datavault4sqlmesh.models.stage import stage_model

        execute_fn = stage_model(
            name="stage.stg_customer",
            source_model=StageModel(table_name="raw_table"),
        )
        assert callable(execute_fn)
