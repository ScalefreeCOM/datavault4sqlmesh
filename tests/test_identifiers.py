"""
Tests for datavault4sqlmesh.models._identifiers and its use in the factories.

Generated identifiers must follow the dialect's normalization so they match
the column names SQLMesh creates (lowercase on PostgreSQL, uppercase on
Snowflake). Source references in stage models must keep their exact case.
"""

from __future__ import annotations

import pytest
from datavault4sqlglot.config import config as _dv_config


def _set_dialect(dialect: str) -> None:
    # conftest.reset_config restores the original value after each test.
    object.__setattr__(_dv_config, "dialect", dialect)


class TestNormalizeName:
    @pytest.mark.parametrize(
        ("dialect", "expected"),
        [
            ("postgres", "hk_region_h"),
            ("duckdb", "hk_region_h"),
            ("snowflake", "HK_REGION_H"),
        ],
    )
    def test_follows_dialect_case(self, dialect, expected):
        from datavault4sqlmesh.models._identifiers import normalize_name

        assert normalize_name("HK_Region_H", dialect) == expected


class TestStageNormalization:
    def _stage_sql(self, dialect: str, **kwargs) -> str:
        from datavault4sqlmesh.models.stage import stage_model

        _set_dialect(dialect)
        execute_fn = stage_model(
            name="stage.stg_region",
            source_table="Region",
            source_schema="tpch_sf1",
            hashed_columns={"HK_REGION_H": ["R_Name"]},
            derived_columns={"REGION_NAME": "r_name", "ldts": "now()"},
            **kwargs,
        )
        return execute_fn(evaluator=None).sql(dialect=dialect)

    def test_postgres_lowercases_generated_columns(self, sqlmesh):
        sql = self._stage_sql("postgres")
        assert 'AS "hk_region_h"' in sql
        assert 'AS "region_name"' in sql
        assert '"HK_REGION_H"' not in sql
        assert '"REGION_NAME"' not in sql

    def test_postgres_keeps_source_references_as_written(self, sqlmesh):
        sql = self._stage_sql("postgres")
        assert '"tpch_sf1"."Region"' in sql
        assert '"R_Name"' in sql

    def test_snowflake_uppercases_generated_columns(self, sqlmesh):
        sql = self._stage_sql("snowflake")
        assert 'AS "HK_REGION_H"' in sql
        assert 'AS "LDTS"' in sql

    def test_postgres_cast_ldts_wrapper_uses_normalized_names(self, sqlmesh):
        sql = self._stage_sql("postgres", cast_ldts_to_timestamp=True)
        assert '"HK_REGION_H"' not in sql
        assert "AS _stg" in sql or 'AS "_stg"' in sql


class TestDataVaultModelNormalization:
    def test_postgres_hub_lowercases_tables_and_columns(self, sqlmesh):
        from datavault4sqlmesh.models.hub import hub_model

        _set_dialect("postgres")
        execute_fn = hub_model(
            name="rdv.CUSTOMER_H",
            hashkey="HK_CUSTOMER_H",
            business_keys=["C_CUSTKEY"],
            source_schema="stage",
            source_table="stg__tpch__customer",
        )
        sql = execute_fn(evaluator=None).sql(dialect="postgres")
        assert '"rdv"."customer_h"' in sql
        assert "CUSTOMER_H" not in sql
        assert "C_CUSTKEY" not in sql

    def test_postgres_satellite_v1_lowercases_v0_reference(self, sqlmesh):
        from datavault4sqlmesh.models.satellite_v1 import satellite_v1_model

        _set_dialect("postgres")
        execute_fn = satellite_v1_model(
            name="rdv.CUSTOMER_N_S_v1",
            sat_v0_table="CUSTOMER_N_S",
            sat_v0_schema="rdv",
            parent_hash_key="HK_CUSTOMER_H",
            hash_diff="HD_CUSTOMER_N_S",
        )
        sql = execute_fn(evaluator=None).sql(dialect="postgres")
        assert '"rdv"."customer_n_s"' in sql
        assert "HK_CUSTOMER_H" not in sql
