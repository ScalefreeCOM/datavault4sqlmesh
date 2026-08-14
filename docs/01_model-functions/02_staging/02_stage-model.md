---
sidebar_position: 2
sidebar_label: Stage Model
title: Stage Model
---

# STAGE MODEL

---

`stage_model` creates a `FULL` (complete refresh) staging model. The staging layer handles
hashing and optionally adds derived columns not present in the raw source. Always create one
stage per raw source table you want to feed into the Data Vault.

Features:

- Computes hashkeys and hashdiffs from raw business key columns
- Supports derived columns (e.g. static record source strings, SQL expressions)
- Complete refresh on every run — no incremental state
- Auto-derives the SQLMesh `columns={}` schema from DV metadata

---

## REQUIRED PARAMETERS

| Parameter | Data Type | Required | Default Value | Explanation |
|---|---|---|---|---|
| `name` | string | mandatory | – | Qualified model name, e.g. `"stage.stg_customer"`. Must include schema. |
| `source_table` | string | mandatory | – | Name of the raw source table to select from. |
| `source_schema` | string | mandatory | – | Schema of the raw source table. |

---

## OPTIONAL PARAMETERS

| Parameter | Data Type | Required | Default Value | Explanation |
|---|---|---|---|---|
| `hashed_columns` | dictionary | important | `{}` | Hash columns to generate. Keys are output column names. Values are either a list of input business key column names (for hashkeys) or a dict with `is_hashdiff: True` and `columns: [...]` (for hashdiffs). |
| `derived_columns` | dictionary | optional | `{}` | SQL expressions to add as new columns. Keys are output column names; values are SQL expression strings. Prefix a string literal with `!` to emit it as a quoted constant. |
| `column_overrides` | dictionary | optional | `{}` | Override inferred SQLMesh column types. Keys are column names; values are SQL type strings (e.g. `"BIGINT"`, `"VARCHAR(100)"`). |
| `cron` | string | optional | None | SQLMesh cron expression for scheduled runs, e.g. `"@daily"`. |

---

## EXAMPLE 1 — Hashkeys and hashdiff

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

### DESCRIPTION

- **name**: The model is registered in SQLMesh under the `stage` schema as `stg_customer`.
- **source_table / source_schema**: Reads from `raw.customers`.
- **hashed_columns**:
  - **hk_customer_h**: A hub hashkey computed from the single business key `customer_id`.
  - **hd_customer_s**: A hashdiff computed from the descriptive attributes `customer_name` and `email`.
- **column_overrides**: Explicitly types the three business key / payload columns as `VARCHAR` since `stage_model` cannot infer raw source column types automatically.

---

## EXAMPLE 2 — Derived record source

```python
from datavault4sqlmesh import stage_model

stage_model(
    name="stage.stg_orders",
    source_table="orders",
    source_schema="raw",
    derived_columns={"rsrc": "'OMS/orders'"},
    hashed_columns={"hk_order_h": ["order_id"]},
)
```

### DESCRIPTION

- **derived_columns**: Adds a constant `rsrc` column with the value `OMS/orders` to every row. Use this when the raw source does not carry a record source column and it must be injected at the staging layer.
- **hashed_columns**: A single hub hashkey `hk_order_h` is derived from `order_id`.

---

## COLUMN TYPE INFERENCE

Because `stage_model` emits a `SELECT *` from the raw source, raw source column types are
not known at model-definition time. Any column that must appear in the SQLMesh `columns={}`
schema — including all business key and payload columns — must be declared explicitly via
`column_overrides`.

Hash key and hash diff columns default to `VARCHAR`. The `ldts` and `rsrc` columns (as
configured in `config.json`) default to `TIMESTAMP` and `VARCHAR` respectively.
