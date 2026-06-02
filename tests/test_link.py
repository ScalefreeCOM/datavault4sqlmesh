"""
Tests for datavault4sqlmesh.models.link — link_model() decorator factory.
"""

from __future__ import annotations

import pytest


class TestLinkModel:
    def test_returns_decorator(self, sqlmesh):
        """link_model(...) must return a callable decorator."""
        from datavault4sqlmesh.models.link import link_model

        decorator = link_model(
            name="dv.order_customer_l",
            link_hash_key="hk_order_customer_l",
            foreign_hash_keys=["hk_order_h", "hk_customer_h"],
        )
        assert callable(decorator)

    def test_decorated_execute_returns_expression(self, sqlmesh):
        """Applying the decorator to a LinkGenerator execute body produces SQL."""
        from sqlglot import exp
        from datavault4sqlmesh.models.link import link_model
        from datavault4sqlglot.generators.link import LinkGenerator
        from datavault4sqlglot.metadata import SourceBinding, SourceModel

        @link_model(
            name="dv.order_customer_l",
            link_hash_key="hk_order_customer_l",
            foreign_hash_keys=["hk_order_h", "hk_customer_h"],
        )
        def execute(evaluator, **kwargs):
            return LinkGenerator(
                target_table="order_customer_l",
                target_schema="dv",
                sources=[
                    SourceBinding(
                        source=SourceModel(schema_name="stage", table_name="stg_orders"),
                        hash_key_col="hk_order_customer_l",
                        foreign_hash_keys=["hk_order_h", "hk_customer_h"],
                        rsrc_statics=["OMS/orders"],
                    )
                ],
                link_hash_key="hk_order_customer_l",
                is_incremental=True,
            ).generate_sql()

        result = execute(evaluator=None)
        assert isinstance(result, exp.Expression)

    def test_sql_contains_foreign_keys(self, sqlmesh):
        from datavault4sqlmesh.models.link import link_model
        from datavault4sqlglot.generators.link import LinkGenerator
        from datavault4sqlglot.metadata import SourceBinding, SourceModel

        @link_model(
            name="dv.order_customer_l",
            link_hash_key="hk_order_customer_l",
            foreign_hash_keys=["hk_order_h", "hk_customer_h"],
        )
        def execute(evaluator, **kwargs):
            return LinkGenerator(
                target_table="order_customer_l",
                target_schema="dv",
                sources=[
                    SourceBinding(
                        source=SourceModel(schema_name="stage", table_name="stg_orders"),
                        hash_key_col="hk_order_customer_l",
                        foreign_hash_keys=["hk_order_h", "hk_customer_h"],
                        rsrc_statics=["OMS/orders"],
                    )
                ],
                link_hash_key="hk_order_customer_l",
                is_incremental=True,
            ).generate_sql()

        sql = execute(evaluator=None).sql(dialect="snowflake")
        assert "hk_order_h" in sql
        assert "hk_customer_h" in sql

    def test_too_few_foreign_keys_raises(self, sqlmesh):
        from datavault4sqlmesh.models.link import link_model

        with pytest.raises(ValueError, match="at least 2 foreign_hash_keys"):
            link_model(
                name="dv.order_l",
                link_hash_key="hk_l",
                foreign_hash_keys=["hk_order_h"],  # only 1
            )

    def test_incremental_sql_contains_target_reference(self, sqlmesh):
        from datavault4sqlmesh.models.link import link_model
        from datavault4sqlglot.generators.link import LinkGenerator
        from datavault4sqlglot.metadata import SourceBinding, SourceModel

        @link_model(
            name="dv.order_customer_l",
            link_hash_key="hk_order_customer_l",
            foreign_hash_keys=["hk_order_h", "hk_customer_h"],
        )
        def execute(evaluator, **kwargs):
            return LinkGenerator(
                target_table="order_customer_l",
                target_schema="dv",
                sources=[
                    SourceBinding(
                        source=SourceModel(schema_name="stage", table_name="stg_orders"),
                        hash_key_col="hk_order_customer_l",
                        foreign_hash_keys=["hk_order_h", "hk_customer_h"],
                        rsrc_statics=["OMS/orders"],
                    )
                ],
                link_hash_key="hk_order_customer_l",
                is_incremental=True,
            ).generate_sql()

        sql = execute(evaluator=None).sql(dialect="snowflake")
        # Incremental mode anti-joins against the target table
        assert "order_customer_l" in sql
