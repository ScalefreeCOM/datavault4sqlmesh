# datavault4sqlmesh

SQLMesh model functions for **Data Vault**, built on
[datavault4sqlglot](../datavault4sqlglot).

Each function replaces the full `@model` decorator, `execute` function, and
manually maintained `columns={}` dict in a SQLMesh Python model file with a
single declarative call.

---

## Installation

```bash
pip install -e datavault4sqlglot/
pip install -e datavault4sqlmesh/ -- dependency to sqlglot
```

Requires Python 3.9+, `sqlmesh`, and `sqlglot`.

---

## Getting Started

### 1. Create `config.json` in your SQLMesh project root

```json
{
  "dialect": "snowflake",
  "ldts_alias": "ldts",
  "rsrc_alias": "rsrc",
  "hash": "MD5"
}
```

See [datavault4sqlglot configuration](../datavault4sqlglot/README.md#configuration) --> link auf github md
for all available keys and their defaults.

### 2. Load configuration once in `models/__init__.py`

```python
# models/__init__.py
from datavault4sqlmesh.config import load_dv_config

load_dv_config()  # reads config.json from the SQLMesh project root
```

All model files in the package automatically inherit these settings.

### 3. Write model files

```python
# models/stg_customer.py
from datavault4sqlmesh import stage_model

stage_model(
    name="stage.stg_customer",
    source_table="customers",
    source_schema="raw",
    hashed_columns={
        "hk_customer_h": ["customer_id"],
        "hd_customer_s": {
            "is_hashdiff": True,
            "columns": ["customer_name", "email"],
        },
    },
    column_overrides={
        "customer_id":   "VARCHAR",
        "customer_name": "VARCHAR",
        "email":         "VARCHAR",
    },
)
```

```python
# models/customer_h.py
from datavault4sqlmesh import hub_model

hub_model(
    name="dv.customer_h",
    hashkey="hk_customer_h",
    business_keys=["customer_id"],
    source_schema="stage",
    source_table="stg_customer",
    rsrc_statics=["ERP/customers"],
)
```

```python
# models/customer_0_s.py
from datavault4sqlmesh import satellite_model

satellite_model(
    name="dv.customer_0_s",
    parent_hash_key="hk_customer_h",
    hash_diff="hd_customer_s",
    payload=["customer_name", "email"],
    source_schema="stage",
    source_table="stg_customer",
)
```

```python
# models/customer_1_s.py
from datavault4sqlmesh import satellite_v1_model

satellite_v1_model(
    name="dv.customer_1_s",
    parent_hash_key="hk_customer_h",
    hash_diff="hd_customer_s",
    payload=["customer_name", "email"],
    sat_v0_table="customer_0_s",
    sat_v0_schema="dv",
)
```

---

## Model functions

### `hub_model`

Creates an `INCREMENTAL_UNMANAGED` Hub model.

```python
from datavault4sqlmesh import hub_model

hub_model(
    name="dv.customer_h",
    hashkey="hk_customer_h",
    business_keys=["customer_id"],
    source_schema="stage",
    source_table="stg_customer",
    rsrc_statics=["ERP/customers"],
    # Optional
    cron="@daily",
    column_overrides={"customer_id": "BIGINT"},
)
```

| Parameter | Required | Description |
|---|---|---|
| `name` | yes | Qualified model name, e.g. `"dv.customer_h"` |
| `hashkey` | yes | Hub hash key column name |
| `business_keys` | yes | Business key column names (at least one) |
| `source_schema` | no | Schema of the staging source table |
| `source_table` | no | Staging source table name; triggers auto-generate mode |
| `sources` | no | List of `SourceModel` objects for multi-source hubs |
| `rsrc_statics` | no | LIKE-pattern strings for HWM scoping |
| `cron` | no | SQLMesh cron expression |
| `grain` | no | Unique-row columns; defaults to `[hashkey]` |
| `column_overrides` | no | Override inferred column types |

**Multi-source** hubs pass a list of `SourceModel` objects via `sources`. Each
source is unioned and deduplicated by earliest `ldts` per hash key. `source_table`
and `sources` cannot be combined.

---

### `link_model`

Creates an `INCREMENTAL_UNMANAGED` Link model.

```python
from datavault4sqlmesh import link_model

link_model(
    name="dv.order_customer_l",
    link_hash_key="hk_order_customer_l",
    foreign_hash_keys=["hk_order_h", "hk_customer_h"],
    source_schema="stage",
    source_table="stg_orders",
    rsrc_statics=["OMS/orders"],
)
```

| Parameter | Required | Description |
|---|---|---|
| `name` | yes | Qualified model name |
| `link_hash_key` | yes | Link hash key column name |
| `foreign_hash_keys` | yes | Foreign hash key columns (at least two) |
| `source_schema` | no | Schema of the staging source table |
| `source_table` | no | Staging source table name; triggers auto-generate mode |
| `sources` | no | List of `SourceModel` objects for multi-source links |
| `rsrc_statics` | no | LIKE-pattern strings for HWM scoping |

---

### `satellite_model`

Creates an `INCREMENTAL_UNMANAGED` Satellite v0 (current-record) model.

**Single source only** — pass one `SourceModel` to `source_model`.

```python
from datavault4sqlmesh import satellite_model

satellite_model(
    name="dv.customer_0_s",
    parent_hash_key="hk_customer_h",
    hash_diff="hd_customer_s",
    payload=["customer_name", "email"],
    source_schema="stage",
    source_table="stg_customer",
)
```

| Parameter | Required | Description |
|---|---|---|
| `name` | yes | Qualified model name |
| `parent_hash_key` | yes | Hash key of the parent Hub or Link |
| `hash_diff` | yes | Hash diff column name |
| `payload` | no | Attribute column names |
| `source_schema` | no | Schema of the staging source table |
| `source_table` | no | Staging source table name; triggers auto-generate mode |

---

### `satellite_v1_model`

Creates a `FULL` Satellite v1 (end-dated) model derived from a v0 satellite.

```python
from datavault4sqlmesh import satellite_v1_model

satellite_v1_model(
    name="dv.customer_1_s",
    parent_hash_key="hk_customer_h",
    hash_diff="hd_customer_s",
    payload=["customer_name", "email"],
    sat_v0_table="customer_0_s",
    sat_v0_schema="dv",
)
```

| Parameter | Required | Description |
|---|---|---|
| `name` | yes | Qualified model name |
| `parent_hash_key` | yes | Hash key of the parent Hub or Link |
| `hash_diff` | yes | Hash diff column name |
| `payload` | no | Attribute column names |
| `sat_v0_table` | no | Table name of the v0 source satellite; omit to use decorator mode |
| `sat_v0_schema` | no | Schema of the v0 source; defaults to the same schema as the v1 target |
| `add_is_current` | no | Append an `is_current` boolean column (default `True`) |

---

### `stage_model`

Creates a `FULL` (complete refresh) Stage model.

```python
from datavault4sqlmesh import stage_model

stage_model(
    name="stage.stg_customer",
    source_table="customers",
    source_schema="raw",
    hashed_columns={
        "hk_customer_h": ["customer_id"],
        "hd_customer_s": {
            "is_hashdiff": True,
            "columns": ["customer_name", "email"],
        },
    },
    column_overrides={
        "customer_id":   "VARCHAR",
        "customer_name": "VARCHAR",
        "email":         "VARCHAR",
    },
)
```

Use `derived_columns` for expressions not present in the raw source (e.g. a
constant record source):

```python
stage_model(
    name="stage.stg_orders",
    source_table="orders",
    source_schema="raw",
    derived_columns={"rsrc": "'OMS/orders'"},
    hashed_columns={"hk_order_h": ["order_id"]},
)
```

---

## Column type inference

All model functions automatically build the `columns={}` dict required by SQLMesh.
Default types:

| Column category | Inferred type |
|---|---|
| Hash key / hash diff | `VARCHAR` |
| Business keys / payload | `VARCHAR` |
| Foreign hash keys | `VARCHAR` |
| `ldts_alias` (load date) | `TIMESTAMP` |
| `rsrc_alias` (record source) | `VARCHAR` |
| `ledts_alias` (load end date, sat v1 only) | `TIMESTAMP` |
| `is_current` (sat v1 only) | `BOOLEAN` |

Override specific columns with `column_overrides`:

```python
hub_model(..., column_overrides={"customer_id": "BIGINT"})
```

---

## SQLMesh model kind mapping

| DV entity | SQLMesh kind | Notes |
|---|---|---|
| Stage | `FULL` | Complete refresh every run |
| Hub | `INCREMENTAL_UNMANAGED` | HWM-based incremental load |
| Link | `INCREMENTAL_UNMANAGED` | HWM-based incremental load |
| Satellite v0 | `INCREMENTAL_UNMANAGED` | HWM-based incremental load |
| Satellite v1 | `FULL` | Complete refresh; see Limitations |

Override the kind via `kind={"name": "FULL"}` if needed.

---

## Limitations

### Satellite v1 materializes as a table, not a view

Data Vault 2.0 specifies that a v1 (end-dated) satellite is a derived view over
the v0 base satellite. In SQLMesh, Python `execute` models can only produce
**tables** — the `VIEW` model kind is only available for SQL models. For this
reason, `satellite_v1_model` uses `FULL` (complete refresh table).

The semantic result is the same: every run reconstructs the full end-dated
history from the v0 source. The cost is a full table rewrite on each run rather
than a no-op view.

### Satellite v0 is single-source only

`satellite_model` accepts a single `SourceModel`. Multi-source satellites are
not supported. If your source data comes from multiple staging tables, load
them into a single staging model first.

### Stage source columns are not inferred automatically

`StageGenerator` produces a `SELECT *` from the raw source, so the source table
columns are not known at model-definition time. Any column that needs to appear
in the SQLMesh `columns={}` schema — including all business key and payload
columns — must be declared explicitly via `column_overrides`.

---

## Running tests

```bash
cd datavault4sqlmesh
pip install -e ".[test]"
pytest tests/
```
