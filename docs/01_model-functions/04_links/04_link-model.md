---
sidebar_position: 4
sidebar_label: Link Model
title: Link Model
---

# LINK MODEL

---

`link_model` creates an `INCREMENTAL_UNMANAGED` Link model. It loads distinct combinations
of the link hash key and its foreign hub hash keys from one or more staging sources using a
high-water mark on the load date timestamp column.

Features:

- Loadable from a single source table or multiple sources (union + deduplication)
- High-water mark (HWM) based incremental loading
- `rsrc_statics` attribute for scoping the HWM to a specific record source pattern
- Auto-derives the SQLMesh `columns={}` schema from DV metadata

---

## REQUIRED PARAMETERS

| Parameter | Data Type | Required | Default Value | Explanation |
|---|---|---|---|---|
| `name` | string | mandatory | – | Qualified model name, e.g. `"dv.order_customer_l"`. Must include schema. |
| `link_hash_key` | string | mandatory | – | Name of the link hash key column. Must exist in the staging source. |
| `foreign_hash_keys` | list of strings | mandatory | – | Names of the foreign hub hash key columns (at least two). Must exist in the staging source. |

---

## OPTIONAL PARAMETERS

| Parameter | Data Type | Required | Default Value | Explanation |
|---|---|---|---|---|
| `source_schema` | string | optional | None | Schema of the staging source table. Used together with `source_table` in auto-generate mode. |
| `source_table` | string | optional | None | Staging source table name. Providing this triggers auto-generate mode; an `execute` body is not required. Cannot be combined with `sources`. |
| `sources` | list of `SourceModel` | optional | None | List of source descriptors for multi-source links. Each source is unioned and deduplicated by earliest `ldts` per link hash key. Cannot be combined with `source_table`. |
| `rsrc_statics` | list of strings | optional | None | LIKE-pattern strings used to scope the HWM query to a specific record source. Required for multi-source links. |
| `cron` | string | optional | None | SQLMesh cron expression, e.g. `"@daily"`. |
| `column_overrides` | dictionary | optional | `{}` | Override inferred SQLMesh column types for specific columns. |

---

## EXAMPLE 1 — Single source

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

### DESCRIPTION

- **name**: The link model lives in the `dv` schema under the name `order_customer_l`.
- **link_hash_key**: `hk_order_customer_l` is the link's primary key, combining the business keys of both connected hubs.
- **foreign_hash_keys**: The link references `hk_order_h` (order hub) and `hk_customer_h` (customer hub). At least two foreign keys are required.
- **source_schema / source_table**: Auto-generate mode — the factory builds the `execute` body from `stage.stg_orders`.
- **rsrc_statics**: Scopes the HWM to rows whose `rsrc` column matches the pattern `OMS/orders`.

---

## MULTI-SOURCE LINKS

For links loaded from more than one staging table, pass a list of `SourceModel` objects via
`sources`. All sources are unioned and deduplicated: for each link hash key, the record with
the earliest `ldts` across all sources is kept.

Each source in a multi-source link must have an `rsrc_static` defined so the HWM can be
scoped correctly per source.

`source_table` and `sources` are mutually exclusive — do not combine them.
