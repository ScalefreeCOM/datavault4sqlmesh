---
sidebar_position: 1
sidebar_label: Documentation
title: Documentation
---

# DOCUMENTATION

---

The following documentation describes the model functions developed by Scalefree to integrate
Data Vault 2.0 patterns into [SQLMesh](https://sqlmesh.com/) projects. Each function replaces
the full `@model` decorator, `execute` function, and manually maintained `columns={}` schema
dict in a SQLMesh Python model file with a single declarative call.

The library is built on top of [datavault4sqlglot](../datavault4sqlglot), which remains the
SQL generation engine. datavault4sqlmesh adds only the SQLMesh integration layer on top.

## INCLUDED MODEL FUNCTIONS

- **stage_model** — Staging layer (hashing, derived columns, complete refresh)
- **hub_model** — Hub entity (incremental, HWM-based, single- and multi-source)
- **link_model** — Link entity (incremental, HWM-based, single- and multi-source)
- **satellite_model** — Satellite v0 / current-record satellite (incremental, single-source)
- **satellite_v1_model** — Satellite v1 / end-dated satellite (full refresh, derived from v0)

## FEATURES

- **Reduced boilerplate**: One factory call replaces 30–40 lines of repetitive model setup
- **Auto-derived schema**: Column types are inferred from DV metadata — no manual `columns={}` maintenance
- **Correct SQLMesh model kinds**: Each DV entity is mapped to the appropriate SQLMesh kind (`INCREMENTAL_UNMANAGED` or `FULL`)
- **High-water mark loading**: Hubs, links, and v0 satellites use HWM-based incremental loading out of the box
- **Multi-source support**: Hubs and links can be loaded from multiple staging sources with automatic union and deduplication
- **Two usage modes**: Auto-generate mode (pass a source table) or decorator mode (wrap a custom `execute` function)

## SQLMESH MODEL KIND MAPPING

| DV Entity | SQLMesh Kind | Notes |
|---|---|---|
| Stage | `FULL` | Complete refresh every run |
| Hub | `INCREMENTAL_UNMANAGED` | HWM-based incremental load |
| Link | `INCREMENTAL_UNMANAGED` | HWM-based incremental load |
| Satellite v0 | `INCREMENTAL_UNMANAGED` | HWM-based incremental load |
| Satellite v1 | `FULL` | Python model constraint — cannot use VIEW |

## REQUIREMENTS

- Python 3.9+
- SQLMesh
- datavault4sqlglot (installed as a dependency)
- A `config.json` in the SQLMesh project root defining at minimum `dialect`, `ldts_alias`, `rsrc_alias`, and `hash`

## GETTING STARTED

### 1. Install

```bash
pip install -e datavault4sqlglot/
pip install -e datavault4sqlmesh/
```

### 2. Create `config.json` in your SQLMesh project root

```json
{
  "dialect": "snowflake",
  "ldts_alias": "ldts",
  "rsrc_alias": "rsrc",
  "hash": "MD5"
}
```

### 3. Load configuration in `models/__init__.py`

```python
from datavault4sqlmesh.config import load_dv_config

load_dv_config()
```

### 4. Write model files

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
)
```

## RESOURCES

- [Scalefree Blog](https://www.scalefree.com/blog/)
- [SQLMesh Documentation](https://sqlmesh.readthedocs.io/)
- [Data Vault 2.0 — Dan Linstedt](https://datavaultalliance.com/)
