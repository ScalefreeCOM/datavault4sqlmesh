# datavault4sqlmesh

SQLMesh model factories for **Data Vault 2.0**, built on
[datavault4sqlglot](../datavault4sqlglot).

Each factory function replaces the full `@model` decorator + `execute` function
boilerplate in a SQLMesh model file with a single declarative call.

---

## What it does

Instead of writing this in every Hub model:

```python
# models/customer_h.py  (before)
import sys, os
sys.path.insert(0, ...)

from sqlmesh import model
from sqlmesh.core.model import ModelKindName
from datavault4sqlglot.config import config, load_config
from datavault4sqlglot.generators.hub import HubGenerator
from datavault4sqlglot.metadata import SourceBinding, SourceModel

load_config(config, os.path.join(os.path.dirname(__file__), "..", "config.json"))

@model(
    "dv.customer_h",
    kind={"name": ModelKindName.INCREMENTAL_UNMANAGED},
    is_sql=True,
    columns={
        "hk_customer_h": "VARCHAR",
        "customer_id":   "VARCHAR",
        "load_date":     "TIMESTAMP",
        "record_source": "VARCHAR",
    },
)
def execute(evaluator, **kwargs):
    return HubGenerator(
        target_table="customer_h",
        target_schema="dv",
        sources=[
            SourceBinding(
                source=SourceModel(schema_name="stage", table_name="stg_customer"),
                hash_key_col="hk_customer_h",
                business_keys=["customer_id"],
                rsrc_statics=["ERP/customers"],
            )
        ],
        hashkey="hk_customer_h",
        is_incremental=True,
    ).generate_sql()
```

You write this:

```python
# models/customer_h.py  (after)
from datavault4sqlmesh import hub_model
from datavault4sqlglot.metadata import SourceBinding, SourceModel

execute = hub_model(
    name="dv.customer_h",
    hashkey="hk_customer_h",
    sources=[
        SourceBinding(
            source=SourceModel(schema_name="stage", table_name="stg_customer"),
            hash_key_col="hk_customer_h",
            business_keys=["customer_id"],
            rsrc_statics=["ERP/customers"],
        )
    ],
)
```

---

## Installation

```bash
pip install -e datavault4sqlmesh/
```

Requires `datavault4sqlglot`, `sqlmesh`, and `sqlglot` to be installed.

---

## Configuration

Call `load_dv_config()` once in your SQLMesh models package so every model file
inherits the same settings:

```python
# models/__init__.py
from datavault4sqlmesh.config import load_dv_config
load_dv_config()              # reads config.json from the SQLMesh project root
# or:
load_dv_config("path/to/config.json")
```

---

## Factories

### `hub_model`

Creates an `INCREMENTAL_UNMANAGED` Hub model.

```python
from datavault4sqlmesh import hub_model
from datavault4sqlglot.metadata import SourceBinding, SourceModel

execute = hub_model(
    name="dv.customer_h",
    hashkey="hk_customer_h",
    sources=[
        SourceBinding(
            source=SourceModel(schema_name="stage", table_name="stg_customer"),
            hash_key_col="hk_customer_h",
            business_keys=["customer_id"],
            rsrc_statics=["ERP/customers"],
        )
    ],
    # Optional overrides
    cron="@daily",
    column_overrides={"customer_id": "BIGINT"},
)
```

### `link_model`

Creates an `INCREMENTAL_UNMANAGED` Link model.

```python
from datavault4sqlmesh import link_model
from datavault4sqlglot.metadata import SourceBinding, SourceModel

execute = link_model(
    name="dv.order_customer_l",
    link_hash_key="hk_order_customer_l",
    sources=[
        SourceBinding(
            source=SourceModel(schema_name="stage", table_name="stg_orders"),
            hash_key_col="hk_order_customer_l",
            foreign_hash_keys=["hk_order_h", "hk_customer_h"],
            rsrc_statics=["OMS/orders"],
        )
    ],
)
```

### `satellite_model`

Creates an `INCREMENTAL_UNMANAGED` Satellite v0 (current-record) model.

```python
from datavault4sqlmesh import satellite_model
from datavault4sqlglot.metadata import SourceModel

execute = satellite_model(
    name="dv.customer_0_s",
    source_model=SourceModel(schema_name="stage", table_name="stg_customer"),
    parent_hash_key="hk_customer_h",
    hash_diff="hd_customer_s",
    payload=["customer_name", "email", "phone", "address"],
)
```

### `satellite_v1_model`

Creates a `VIEW` Satellite v1 (end-dated) model from a sat_v0 source.

```python
from datavault4sqlmesh import satellite_v1_model

execute = satellite_v1_model(
    name="dv.customer_1_s",
    source_v0="dv.customer_0_s",
    parent_hash_key="hk_customer_h",
    hash_diff="hd_customer_s",
    payload=["customer_name", "email", "phone", "address"],
)
```

### `stage_model`

Creates a `FULL` (complete refresh) Stage model.

```python
from datavault4sqlmesh import stage_model
from datavault4sqlglot.metadata import StageModel

execute = stage_model(
    name="stage.stg_customer",
    source_model=StageModel(
        schema_name="user_mszerencse",
        table_name="customers",
        hashed_columns={
            "hk_customer_h": ["customer_id"],
            "hd_customer_s": {
                "is_hashdiff": True,
                "columns": ["customer_name", "email", "phone", "address"],
            },
        },
    ),
    # Source columns that cannot be inferred automatically:
    column_overrides={
        "customer_id":   "VARCHAR",
        "customer_name": "VARCHAR",
        "email":         "VARCHAR",
        "phone":         "VARCHAR",
        "address":       "VARCHAR",
    },
)
```

---

## Column type inference

All factories automatically build the `columns={}` dict required by SQLMesh.
Default types:

| Column category            | Inferred type |
|----------------------------|---------------|
| Hash key / hash diff       | `VARCHAR`     |
| Business keys / payload    | `VARCHAR`     |
| Foreign hash keys          | `VARCHAR`     |
| `ldts_alias` (load date)   | `TIMESTAMP`   |
| `rsrc_alias` (record src)  | `VARCHAR`     |
| `ledts_alias` (load end)   | `TIMESTAMP`   |
| `is_current` (sat v1)      | `BOOLEAN`     |

Override individual columns with the `column_overrides` parameter.

---

## SQLMesh model kind mapping

| DV entity       | SQLMesh kind            |
|-----------------|-------------------------|
| Stage           | `FULL`                  |
| Hub             | `INCREMENTAL_UNMANAGED` |
| Link            | `INCREMENTAL_UNMANAGED` |
| Satellite v0    | `INCREMENTAL_UNMANAGED` |
| Satellite v1    | `VIEW`                  |

Override the kind via `model_kwargs` if needed:

```python
from sqlmesh.core.model import ModelKindName
execute = satellite_v1_model(..., kind={"name": ModelKindName.FULL})
```

---

## Running tests

```bash
cd datavault4sqlmesh
pip install -e ".[test]"
pytest tests/
```

Tests that exercise model factories require SQLMesh; the others (schema
inference) run without it.
