---
sidebar_position: 5
sidebar_label: Satellite Model (v0)
title: Satellite Model (v0)
---

# SATELLITE MODEL (v0)

---

`satellite_model` creates an `INCREMENTAL_UNMANAGED` Satellite v0 (current-record) model.
It tracks the full change history of descriptive attributes for a hub or link, storing one
row per unique hash diff value per parent hash key.

Features:

- Stores all historical versions of descriptive attributes (no end-dating)
- High-water mark (HWM) based incremental loading
- Single source only — multi-source satellites are not supported
- Auto-derives the SQLMesh `columns={}` schema from DV metadata

---

## REQUIRED PARAMETERS

| Parameter | Data Type | Required | Default Value | Explanation |
|---|---|---|---|---|
| `name` | string | mandatory | – | Qualified model name, e.g. `"dv.customer_0_s"`. Must include schema. |
| `parent_hash_key` | string | mandatory | – | Hash key column of the parent Hub or Link. Must exist in the staging source. |
| `hash_diff` | string | mandatory | – | Name of the hash diff column. Must exist in the staging source. |

---

## OPTIONAL PARAMETERS

| Parameter | Data Type | Required | Default Value | Explanation |
|---|---|---|---|---|
| `payload` | list of strings | important | `[]` | Descriptive attribute column names to load into the satellite. Must exist in the staging source. |
| `source_schema` | string | optional | None | Schema of the staging source table. Used together with `source_table` in auto-generate mode. |
| `source_table` | string | optional | None | Staging source table name. Providing this triggers auto-generate mode; an `execute` body is not required. |
| `cron` | string | optional | None | SQLMesh cron expression, e.g. `"@daily"`. |
| `column_overrides` | dictionary | optional | `{}` | Override inferred SQLMesh column types for specific columns. |

---

## EXAMPLE 1

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

### DESCRIPTION

- **name**: The satellite model lives in the `dv` schema under the name `customer_0_s`. The `_0_s` suffix is a naming convention for v0 (non-end-dated) satellites.
- **parent_hash_key**: `hk_customer_h` links this satellite to its parent hub `customer_h`.
- **hash_diff**: `hd_customer_s` tracks changes — a new row is inserted only when this value changes.
- **payload**: The two descriptive attributes `customer_name` and `email` are stored alongside the hash key and hash diff.
- **source_schema / source_table**: Auto-generate mode — the factory builds the `execute` body from `stage.stg_customer`.

---

## LIMITATIONS

### Single source only

`satellite_model` accepts one staging source. Multi-source satellites are not supported. If
descriptive attributes for the same hub arrive from multiple staging tables, consolidate them
into a single staging model first.

### Use `satellite_v1_model` for end-dated history

The v0 satellite stores all versions without end-dating. To query the currently valid record
per hash key or to retrieve point-in-time snapshots, use `satellite_v1_model` on top of this
v0 satellite.
