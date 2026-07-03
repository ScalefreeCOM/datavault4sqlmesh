---
sidebar_position: 6
sidebar_label: Satellite Model (v1)
title: Satellite Model (v1)
---

# SATELLITE MODEL (v1)

---

`satellite_v1_model` creates a `FULL` (complete refresh) Satellite v1 (end-dated) model
derived from a v0 satellite. It adds `ledts` (load end date timestamp) and optionally an
`is_current` flag to enable point-in-time and as-of queries without a separate PIT table.

Features:

- Adds `ledts` (load end date) to every row from the v0 satellite
- Optional `is_current` boolean column to flag the latest record per parent hash key
- Complete refresh on every run — full reconstruction from the v0 source
- Auto-derives the SQLMesh `columns={}` schema from DV metadata

---

## REQUIRED PARAMETERS

| Parameter | Data Type | Required | Default Value | Explanation |
|---|---|---|---|---|
| `name` | string | mandatory | – | Qualified model name, e.g. `"dv.customer_1_s"`. Must include schema. |
| `parent_hash_key` | string | mandatory | – | Hash key column of the parent Hub or Link. Must match the column in the v0 satellite. |
| `hash_diff` | string | mandatory | – | Hash diff column name. Must match the column in the v0 satellite. |

---

## OPTIONAL PARAMETERS

| Parameter | Data Type | Required | Default Value | Explanation |
|---|---|---|---|---|
| `payload` | list of strings | important | `[]` | Descriptive attribute column names carried over from the v0 satellite. |
| `sat_v0_table` | string | optional | None | Table name of the v0 source satellite. Providing this triggers auto-generate mode; omit to use decorator mode. |
| `sat_v0_schema` | string | optional | Same schema as `name` | Schema of the v0 source satellite. Defaults to the same schema as the v1 target. |
| `add_is_current` | boolean | optional | `True` | Append an `is_current` boolean column that is `True` for the most recent record per parent hash key. |
| `cron` | string | optional | None | SQLMesh cron expression, e.g. `"@daily"`. |
| `column_overrides` | dictionary | optional | `{}` | Override inferred SQLMesh column types for specific columns. |

---

## EXAMPLE 1

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

### DESCRIPTION

- **name**: The v1 satellite lives in the `dv` schema as `customer_1_s`. The `_1_s` suffix is a naming convention for v1 (end-dated) satellites.
- **parent_hash_key / hash_diff / payload**: Must match the corresponding columns in the v0 satellite `dv.customer_0_s`.
- **sat_v0_table / sat_v0_schema**: Auto-generate mode — the factory reads from `dv.customer_0_s` and computes `ledts` as the next row's `ldts` minus one microsecond (or a configured sentinel for the latest row).
- **add_is_current**: Defaults to `True`, so an `is_current` column is added. Set to `False` to omit it.

---

## LIMITATIONS

### Materializes as a table, not a view

Data Vault 2 specifies that a v1 satellite is a derived view over the v0 base satellite.
In SQLMesh, Python `execute` models can only produce **tables** — the `VIEW` kind is
available only for SQL models. For this reason, `satellite_v1_model` uses `FULL` (complete
refresh table).

The semantic result is equivalent: every run reconstructs the full end-dated history from
the v0 source. The cost is a full table rewrite on each run rather than a zero-cost view.

If you control the model type and want to bypass this, you can pass `kind={"name": "VIEW"}`
— but this requires a SQL model, not a Python factory.
