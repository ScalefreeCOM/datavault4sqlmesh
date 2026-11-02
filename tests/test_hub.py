"""
Tests for datavault4sqlmesh.models.hub — hub_model() decorator factory.

Tests that require SQLMesh use the ``sqlmesh`` fixture (from conftest) which
skips the test automatically when SQLMesh is not installed.
"""

from __future__ import annotations

import pytest

from datavault4sqlmesh.models._utils import parse_model_name


# ---------------------------------------------------------------------------
# parse_model_name (shared utility tested in isolation)
# ---------------------------------------------------------------------------

class TestParseModelName:
    def test_table_only(self):
        assert parse_model_name("customer_h") == ("customer_h", None, None)

    def test_schema_and_table(self):
        assert parse_model_name("dv.customer_h") == ("customer_h", "dv", None)

    def test_db_schema_table(self):
        assert parse_model_name("mydb.dv.customer_h") == ("customer_h", "dv", "mydb")

    def test_too_many_parts_raises(self):
        with pytest.raises(ValueError, match="at most 3"):
            parse_model_name("a.b.c.d")


# ---------------------------------------------------------------------------
# hub_model decorator factory
# ---------------------------------------------------------------------------

class TestHubModel:
    def test_returns_decorator(self, sqlmesh):
        """hub_model(...) must return a callable decorator."""
        from datavault4sqlmesh.models.hub import hub_model

        decorator = hub_model(
            name="dv.customer_h",
            hashkey="hk_customer_h",
            business_keys=["customer_id"],
        )
        assert callable(decorator)

    def test_decorated_execute_returns_expression(self, sqlmesh):
        """Applying the decorator to a HubGenerator execute body produces SQL."""
        from sqlglot import exp
        from datavault4sqlmesh.models.hub import hub_model
        from datavault4sqlglot.generators.hub import HubGenerator
        from datavault4sqlglot.metadata import SourceBinding, SourceModel

        @hub_model(
            name="dv.customer_h",
            hashkey="hk_customer_h",
            business_keys=["customer_id"],
        )
        def execute(evaluator, **kwargs):
            return HubGenerator(
                target_table="customer_h",
                target_schema="dv",
                sources=[
                    SourceBinding(
                        source=SourceModel(schema_name="stage", table_name="stg_customer"),
                        hash_key_col="hk_customer_h",
                        bk_columns=["customer_id"],
                        rsrc_statics=["ERP/customers"],
                    )
                ],
                hashkey="hk_customer_h",
                business_keys=["customer_id"],
                is_incremental=True,
            ).generate_sql()

        result = execute(evaluator=None)
        assert isinstance(result, exp.Expression)

    def test_sql_contains_hash_key(self, sqlmesh):
        from datavault4sqlmesh.models.hub import hub_model
        from datavault4sqlglot.generators.hub import HubGenerator
        from datavault4sqlglot.metadata import SourceBinding, SourceModel

        @hub_model(
            name="dv.customer_h",
            hashkey="hk_customer_h",
            business_keys=["customer_id"],
        )
        def execute(evaluator, **kwargs):
            return HubGenerator(
                target_table="customer_h",
                target_schema="dv",
                sources=[
                    SourceBinding(
                        source=SourceModel(schema_name="stage", table_name="stg_customer"),
                        hash_key_col="hk_customer_h",
                        bk_columns=["customer_id"],
                        rsrc_statics=["ERP/customers"],
                    )
                ],
                hashkey="hk_customer_h",
                business_keys=["customer_id"],
                is_incremental=True,
            ).generate_sql()

        sql = execute(evaluator=None).sql(dialect="snowflake")
        assert "hk_customer_h" in sql

    def test_empty_business_keys_raises(self, sqlmesh):
        from datavault4sqlmesh.models.hub import hub_model

        with pytest.raises(ValueError, match="at least one business key"):
            hub_model(name="dv.customer_h", hashkey="hk_customer_h", business_keys=[])

    def test_multi_source_hub(self, sqlmesh):
        """Multi-source hub UNION ALL — both staging tables referenced in SQL."""
        from sqlglot import exp
        from datavault4sqlmesh.models.hub import hub_model
        from datavault4sqlglot.generators.hub import HubGenerator
        from datavault4sqlglot.metadata import SourceBinding, SourceModel

        @hub_model(
            name="dv.customer_h",
            hashkey="hk_customer_h",
            business_keys=["customer_id"],
        )
        def execute(evaluator, **kwargs):
            return HubGenerator(
                target_table="customer_h",
                target_schema="dv",
                sources=[
                    SourceBinding(
                        source=SourceModel(schema_name="stage", table_name="stg_crm"),
                        hash_key_col="hk_customer_h",
                        bk_columns=["customer_id"],
                        rsrc_statics=["CRM/customers"],
                    ),
                    SourceBinding(
                        source=SourceModel(schema_name="stage", table_name="stg_erp"),
                        hash_key_col="hk_customer_h",
                        bk_columns=["customer_id"],
                        rsrc_statics=["ERP/customers"],
                    ),
                ],
                hashkey="hk_customer_h",
                business_keys=["customer_id"],
                is_incremental=True,
            ).generate_sql()

        result = execute(evaluator=None)
        assert isinstance(result, exp.Expression)
        sql = result.sql(dialect="snowflake")
        assert "stg_crm" in sql
        assert "stg_erp" in sql

    def test_custom_grain(self, sqlmesh):
        """grain parameter is forwarded to @model."""
        from datavault4sqlmesh.models.hub import hub_model

        decorator = hub_model(
            name="dv.customer_h",
            hashkey="hk_customer_h",
            business_keys=["customer_id"],
            grain=["hk_customer_h", "ldts"],
        )
        assert callable(decorator)

    def test_additional_columns_in_schema(self, sqlmesh):
        """additional_columns appear in the inferred schema."""
        from datavault4sqlmesh.schema.inference import infer_hub_columns

        cols = infer_hub_columns(
            "hk_customer_h", ["customer_id"], additional_columns=["tenant_id"]
        )
        assert "tenant_id" in cols
