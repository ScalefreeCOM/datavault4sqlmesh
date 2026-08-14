"""
Tests for datavault4sqlmesh.schema.inference

These tests do NOT require SQLMesh to be installed — they exercise pure
column-inference logic only.
"""

from __future__ import annotations

import pytest

from datavault4sqlglot.config import DataVaultConfig
from datavault4sqlglot.metadata import StageModel
from datavault4sqlmesh.schema.inference import (
    infer_hub_columns,
    infer_link_columns,
    infer_satellite_columns,
    infer_satellite_v1_columns,
    infer_stage_columns,
)


# ---------------------------------------------------------------------------
# Hub inference
# ---------------------------------------------------------------------------

class TestInferHubColumns:
    def test_single_source_produces_expected_keys(self):
        cols = infer_hub_columns("hk_customer_h", ["customer_id"])

        assert "hk_customer_h" in cols
        assert "customer_id" in cols
        assert "ldts" in cols
        assert "rsrc" in cols

    def test_hash_key_is_first(self):
        cols = infer_hub_columns("hk_customer_h", ["customer_id"])
        keys = list(cols.keys())
        assert keys[0] == "hk_customer_h"

    def test_ldts_is_timestamp(self):
        cols = infer_hub_columns("hk_customer_h", ["customer_id"])
        assert cols["ldts"] == "TIMESTAMP"

    def test_hash_key_is_varchar(self):
        cols = infer_hub_columns("hk_customer_h", ["customer_id"])
        assert cols["hk_customer_h"] == "VARCHAR"

    def test_multiple_business_keys_deduplicates(self):
        cols = infer_hub_columns("hk_customer_h", ["customer_id", "region", "customer_id"])

        bk_keys = [k for k in cols if k not in ("hk_customer_h", "ldts", "rsrc")]
        assert bk_keys.count("customer_id") == 1
        assert "region" in cols

    def test_additional_columns_appear(self):
        cols = infer_hub_columns("hk_customer_h", ["customer_id"], additional_columns=["extra_col"])
        assert "extra_col" in cols

    def test_column_overrides_applied(self):
        cols = infer_hub_columns(
            "hk_customer_h",
            ["customer_id"],
            column_overrides={"customer_id": "BIGINT", "ldts": "TIMESTAMPTZ"},
        )
        assert cols["customer_id"] == "BIGINT"
        assert cols["ldts"] == "TIMESTAMPTZ"

    def test_empty_business_keys_raises(self):
        with pytest.raises(ValueError, match="at least one business key"):
            infer_hub_columns("hk_customer_h", [])

    def test_config_aliases_used(self, reset_config):
        # Mutate the singleton in-place; replacing it would not be seen by
        # inference.py which holds a direct reference to the same object.
        from datavault4sqlglot.config import config as dv_config
        dv_config.ldts_alias = "load_date"
        dv_config.rsrc_alias = "record_source"

        cols = infer_hub_columns("hk_customer_h", ["customer_id"])

        assert "load_date" in cols
        assert "record_source" in cols
        assert "ldts" not in cols


# ---------------------------------------------------------------------------
# Link inference
# ---------------------------------------------------------------------------

class TestInferLinkColumns:
    def test_produces_all_expected_keys(self):
        cols = infer_link_columns("hk_order_customer_l", ["hk_order_h", "hk_customer_h"])

        assert "hk_order_customer_l" in cols
        assert "hk_order_h" in cols
        assert "hk_customer_h" in cols
        assert "ldts" in cols
        assert "rsrc" in cols

    def test_link_hash_key_is_first(self):
        cols = infer_link_columns("hk_order_customer_l", ["hk_order_h", "hk_customer_h"])
        assert list(cols.keys())[0] == "hk_order_customer_l"

    def test_foreign_keys_are_varchar(self):
        cols = infer_link_columns("hk_order_customer_l", ["hk_order_h", "hk_customer_h"])
        assert cols["hk_order_h"] == "VARCHAR"
        assert cols["hk_customer_h"] == "VARCHAR"

    def test_too_few_foreign_keys_raises(self):
        with pytest.raises(ValueError, match="at least 2 foreign_hash_keys"):
            infer_link_columns("hk_order_customer_l", ["hk_order_h"])

    def test_empty_foreign_keys_raises(self):
        with pytest.raises(ValueError, match="at least 2 foreign_hash_keys"):
            infer_link_columns("hk_l", [])

    def test_deduplicates_foreign_keys(self):
        cols = infer_link_columns("hk_l", ["hk_order_h", "hk_customer_h", "hk_order_h"])
        fhk_keys = [k for k in cols if k not in ("hk_l", "ldts", "rsrc")]
        assert fhk_keys.count("hk_order_h") == 1
        assert "hk_customer_h" in cols


# ---------------------------------------------------------------------------
# Satellite v0 inference
# ---------------------------------------------------------------------------

class TestInferSatelliteColumns:
    def test_produces_all_expected_keys(self):
        cols = infer_satellite_columns(
            "hk_customer_h",
            "hd_customer_s",
            payload=["customer_name", "email"],
        )
        assert "hk_customer_h" in cols
        assert "hd_customer_s" in cols
        assert "customer_name" in cols
        assert "email" in cols
        assert "ldts" in cols
        assert "rsrc" in cols

    def test_hash_diff_as_dict(self):
        cols = infer_satellite_columns(
            "hk_customer_h",
            {"source_column": "hd_src", "alias": "hd_customer_s"},
        )
        assert "hd_customer_s" in cols
        assert "hd_src" not in cols

    def test_parent_hash_key_is_first(self):
        cols = infer_satellite_columns("hk_customer_h", "hd_customer_s")
        assert list(cols.keys())[0] == "hk_customer_h"

    def test_ldts_timestamp(self):
        cols = infer_satellite_columns("hk_customer_h", "hd_customer_s")
        assert cols["ldts"] == "TIMESTAMP"

    def test_column_overrides(self):
        cols = infer_satellite_columns(
            "hk_customer_h",
            "hd_customer_s",
            payload=["amount"],
            column_overrides={"amount": "DECIMAL(18,2)"},
        )
        assert cols["amount"] == "DECIMAL(18,2)"


# ---------------------------------------------------------------------------
# Satellite v1 inference
# ---------------------------------------------------------------------------

class TestInferSatelliteV1Columns:
    def test_includes_ledts_and_is_current(self):
        cols = infer_satellite_v1_columns(
            "hk_customer_h",
            "hd_customer_s",
            payload=["customer_name"],
        )
        assert "ledts" in cols
        assert "is_current" in cols
        assert cols["ledts"] == "TIMESTAMP"
        assert cols["is_current"] == "BOOLEAN"

    def test_no_is_current_when_disabled(self):
        cols = infer_satellite_v1_columns(
            "hk_customer_h",
            "hd_customer_s",
            add_is_current=False,
        )
        assert "is_current" not in cols

    def test_custom_is_current_col_name(self):
        cols = infer_satellite_v1_columns(
            "hk_customer_h",
            "hd_customer_s",
            add_is_current=True,
            is_current_col="active",
        )
        assert "active" in cols
        assert "is_current" not in cols

    def test_config_ledts_alias_used(self, reset_config):
        # Mutate the singleton in-place — see note in test_config_aliases_used.
        from datavault4sqlglot.config import config as dv_config
        dv_config.ledts_alias = "load_end_date"

        cols = infer_satellite_v1_columns("hk_customer_h", "hd_customer_s")
        assert "load_end_date" in cols
        assert "ledts" not in cols


# ---------------------------------------------------------------------------
# Stage inference
# ---------------------------------------------------------------------------

class TestInferStageColumns:
    def test_hashed_columns_included(self):
        source = StageModel(
            table_name="customers",
            hashed_columns={
                "hk_customer_h": ["customer_id"],
                "hd_customer_s": {
                    "is_hashdiff": True,
                    "columns": ["customer_name", "email"],
                },
            },
        )
        cols = infer_stage_columns(source)
        assert "hk_customer_h" in cols
        assert "hd_customer_s" in cols

    def test_hashed_columns_are_varchar(self):
        source = StageModel(
            table_name="customers",
            hashed_columns={"hk_customer_h": ["customer_id"]},
        )
        cols = infer_stage_columns(source)
        assert cols["hk_customer_h"] == "VARCHAR"

    def test_derived_columns_included(self):
        source = StageModel(
            table_name="customers",
            derived_columns={"full_name": "first_name || ' ' || last_name"},
        )
        cols = infer_stage_columns(source)
        assert "full_name" in cols

    def test_ldts_rsrc_always_present(self):
        source = StageModel(table_name="customers")
        cols = infer_stage_columns(source)
        assert "ldts" in cols
        assert "rsrc" in cols

    def test_column_overrides_add_source_columns(self):
        source = StageModel(
            table_name="customers",
            hashed_columns={"hk_customer_h": ["customer_id"]},
        )
        cols = infer_stage_columns(
            source,
            column_overrides={
                "customer_id": "VARCHAR",
                "customer_name": "VARCHAR",
                "amount": "DECIMAL(18,2)",
            },
        )
        assert "customer_id" in cols
        assert "customer_name" in cols
        assert cols["amount"] == "DECIMAL(18,2)"

    def test_missing_columns_included(self):
        source = StageModel(
            table_name="customers",
            missing_columns={"deprecated_col": "VARCHAR"},
        )
        cols = infer_stage_columns(source)
        assert "deprecated_col" in cols

    def test_empty_stage_model_still_valid(self):
        source = StageModel(table_name="raw_table")
        cols = infer_stage_columns(source)
        assert "ldts" in cols
        assert "rsrc" in cols
