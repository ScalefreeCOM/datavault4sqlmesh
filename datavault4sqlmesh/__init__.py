"""
datavault4sqlmesh
=================

SQLMesh model decorator factories for Data Vault 2, built on top of
datavault4sqlglot.

Each factory function is a **decorator factory** — it returns a decorator that
applies the correct SQLMesh ``@model`` metadata (kind, columns, grain) to a
user-written ``execute`` function.  This keeps the ``execute`` body explicit
and visible to SQLMesh's source-code analysis, while eliminating the boilerplate
of manually maintaining ``columns={}`` dicts.

All classes and generators needed in model files are re-exported here so that
each model file only needs a single ``from datavault4sqlmesh import ...``
statement::

    from datavault4sqlmesh import hub_model, SourceModel

Typical usage in a SQLMesh project::

    # models/__init__.py  ← load config once for the whole models/ package
    from datavault4sqlmesh.config import load_dv_config
    load_dv_config()

    # models/customer_h.py
    from datavault4sqlmesh import hub_model, SourceModel

    hub_model(
        name="dv.customer_h",
        hashkey="hk_customer_h",
        business_keys=["customer_id"],
        sources=[SourceModel(schema_name="stage", table_name="stg_customer")],
        rsrc_statics=["ERP/customers"],
    )
"""

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
from datavault4sqlmesh.config import load_dv_config

# ---------------------------------------------------------------------------
# Model decorator factories
# ---------------------------------------------------------------------------
from datavault4sqlmesh.models.hub import hub_model
from datavault4sqlmesh.models.link import link_model
from datavault4sqlmesh.models.satellite import satellite_model
from datavault4sqlmesh.models.satellite_v1 import satellite_v1_model
from datavault4sqlmesh.models.stage import stage_model

# ---------------------------------------------------------------------------
# Schema inference helpers (useful for custom model wrappers)
# ---------------------------------------------------------------------------
from datavault4sqlmesh.schema.inference import (
    infer_hub_columns,
    infer_link_columns,
    infer_satellite_columns,
    infer_satellite_v1_columns,
    infer_stage_columns,
)

# ---------------------------------------------------------------------------
# datavault4sqlglot generators — re-exported for single-import convenience
# ---------------------------------------------------------------------------
from datavault4sqlglot.generators.hub import HubGenerator
from datavault4sqlglot.generators.link import LinkGenerator
from datavault4sqlglot.generators.satellite import SatelliteGenerator
from datavault4sqlglot.generators.satellite_v1 import SatelliteV1Generator
from datavault4sqlglot.generators.stage import StageGenerator

# ---------------------------------------------------------------------------
# datavault4sqlglot metadata — re-exported for single-import convenience
# ---------------------------------------------------------------------------
from datavault4sqlglot.metadata import SourceModel, StageModel

__all__ = [
    # Config
    "load_dv_config",
    # Model decorator factories
    "hub_model",
    "link_model",
    "satellite_model",
    "satellite_v1_model",
    "stage_model",
    # Schema inference
    "infer_hub_columns",
    "infer_link_columns",
    "infer_satellite_columns",
    "infer_satellite_v1_columns",
    "infer_stage_columns",
    # Generators
    "HubGenerator",
    "LinkGenerator",
    "SatelliteGenerator",
    "SatelliteV1Generator",
    "StageGenerator",
    # Metadata
    "SourceModel",
    "StageModel",
]
