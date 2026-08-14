---
sidebar_position: 3
sidebar_label: Hub Model
title: Hub Model
---

# HUB MODEL

---

`hub_model` creates an `INCREMENTAL_UNMANAGED` Hub model. It loads distinct hash key /
business key combinations from one or more staging sources using a high-water mark on the
load date timestamp column to skip already-processed records.

Features:

- Loadable from a single source table or multiple sources (union + deduplication)
- High-water mark (HWM) based incremental loading
- `rsrc_statics` attribute for scoping the HWM to a specific record source pattern
- Auto-derives the SQLMesh `columns={}` schema from DV metadata

---

## REQUIRED PARAMETERS

| Parameter | Data Type | Required | Default Value | Explanation |
|---|---|---|---|---|
| `name` | string | mandatory | – | Qualified model name, e.g. `"dv.customer_h"`. Must include schema. |
| `hashkey` | string | mandatory | – | Name of the hub hash key column. Must exist in the staging source. |
| `business_keys` | list of strings | mandatory | – | Business key column names to load into the hub. Must exist in the staging source. |

---

## OPTIONAL PARAMETERS

| Parameter | Data Type | Required | Default Value | Explanation |
|---|---|---|---|---|
| `source_schema` | string | optional | None | Schema of the staging source table. Used together with `source_table` in auto-generate mode. |
| `source_table` | string | optional | None | Staging source table name. Providing this triggers auto-generate mode; an `execute` body is not required. Cannot be combined with `sources`. |
| `sources` | list of `SourceModel` | optional | None | List of source descriptors for multi-source hubs. Each source is unioned and deduplicated by earliest `ldts` per hash key. Cannot be combined with `source_table`. |
| `rsrc_statics` | list of strings | optional | None | LIKE-pattern strings used to scope the HWM query to a specific record source. Required for multi-source hubs. |
| `cron` | string | optional | None | SQLMesh cron expression, e.g. `"@daily"`. |
| `grain` | list of strings | optional | `[hashkey]` | Columns that define a unique row in the model. Defaults to the hash key only. |
| `column_overrides` | dictionary | optional | `{}` | Override inferred SQLMesh column types for specific columns. |

---

## EXAMPLE 1 — Single source

```python
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

### DESCRIPTION

- **name**: The hub model lives in the `dv` schema under the name `customer_h`.
- **hashkey**: `hk_customer_h` is the hub's primary key, computed upstream in staging.
- **business_keys**: A single business key `customer_id` is loaded alongside the hash key.
- **source_schema / source_table**: Auto-generate mode — the factory builds the `execute` body from `stage.stg_customer`.
- **rsrc_statics**: Scopes the HWM to rows whose `rsrc` column matches the pattern `ERP/customers`.

---

## EXAMPLE 2 — Column type override

```python
from datavault4sqlmesh import hub_model

hub_model(
    name="dv.customer_h",
    hashkey="hk_customer_h",
    business_keys=["customer_id"],
    source_schema="stage",
    source_table="stg_customer",
    rsrc_statics=["ERP/customers"],
    cron="@daily",
    column_overrides={"customer_id": "BIGINT"},
)
```

### DESCRIPTION

- **cron**: The model is scheduled to run daily.
- **column_overrides**: The `customer_id` column is stored as `BIGINT` instead of the default `VARCHAR`.

---

## MULTI-SOURCE HUBS

For hubs loaded from more than one staging table, pass a list of `SourceModel` objects via
`sources`. All sources are unioned and deduplicated: for each hash key, the record with the
earliest `ldts` across all sources is kept.

Each source in a multi-source hub must have an `rsrc_static` defined so the HWM can be
scoped correctly per source.

`source_table` and `sources` are mutually exclusive — do not combine them.
