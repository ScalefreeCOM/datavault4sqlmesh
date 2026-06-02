# datavault4sqlmesh — Claude Code Instructions

---

## 1. Project Context

### What is `datavault4sqlmesh`?

`datavault4sqlmesh` is a Python library that wraps `datavault4sqlglot` with SQLMesh-native model
factories, eliminating the boilerplate in every SQLMesh model file.

Instead of writing a full `@model` decorator, a typed `execute` function, and manually
maintaining the `columns={}` schema dict in each model, users call a single factory function
(e.g. `hub_model`, `satellite_model`) that handles all of this automatically.

### Goal & Vision

**Key Objectives:**
- **Reduce boilerplate**: One factory call replaces 30–40 lines of repetitive model setup.
- **Auto-derive schema**: Column types are inferred from DV metadata so users never manually
  maintain `columns={}` dicts.
- **SQLMesh parity**: Every SQLMesh model kind (`INCREMENTAL_UNMANAGED`, `FULL`, `VIEW`) is
  handled correctly for the corresponding DV entity type.
- **Extend, not replace**: datavault4sqlglot generators remain the SQL engine; this package
  only adds the SQLMesh integration layer.

### Architecture

**Package layout:**
```
datavault4sqlmesh/
├── datavault4sqlmesh/
│   ├── __init__.py          # top-level re-exports
│   ├── config.py            # load_dv_config() convenience wrapper
│   ├── schema/
│   │   ├── __init__.py
│   │   └── inference.py     # infer_*_columns() functions
│   └── models/
│       ├── __init__.py
│       ├── _utils.py        # internal helpers (parse_model_name)
│       ├── hub.py           # hub_model()
│       ├── link.py          # link_model()
│       ├── satellite.py     # satellite_model()
│       ├── satellite_v1.py  # satellite_v1_model()
│       └── stage.py         # stage_model()
└── tests/
    ├── conftest.py
    ├── test_schema_inference.py
    ├── test_hub.py
    ├── test_link.py
    ├── test_satellite.py
    ├── test_satellite_v1.py
    └── test_stage.py
```

**Data flow:**
1. User calls a factory function (e.g. `hub_model(name, hashkey, sources, ...)`)
2. Factory infers `columns` dict from DV metadata via `schema/inference.py`
3. Factory applies the SQLMesh `@model(...)` decorator with correct kind/columns/grain
4. Factory instantiates the corresponding `datavault4sqlglot` generator in the `execute`
   closure and calls `.generate_sql()` at runtime
5. The decorated `execute` function is returned and discovered by SQLMesh at import time

---

## 2. Coding Standards

Follow the **exact same standards** as `datavault4sqlglot/CLAUDE.md`:

- Python 3.9+, full type annotations, `from __future__ import annotations`
- Black + ruff + mypy compatible
- Absolute imports only
- PascalCase for classes, snake_case for functions/variables, `_prefix` for private helpers
- Short, clear docstrings on all public functions and classes
- `logging` module, not `print()`
- Fail early with specific exceptions

### Additional rules specific to this package

- **Never import SQLMesh at module top-level in model factory files.**
  Import inside the factory function (`from sqlmesh import model as sqlmesh_model`) so that
  `datavault4sqlmesh.schema` and other non-SQLMesh sub-packages can be imported without
  SQLMesh being installed.
- **Column inference is pure and stateless.** The `infer_*_columns` functions must have no
  side effects and must not call external services or read files.
- **Factories must not execute SQL.** They build and return decorated functions; actual SQL
  generation happens inside `execute()` at SQLMesh runtime.

---

## 3. SQLMesh Model Kind Mapping

| DV Entity       | SQLMesh Kind            | Notes                                   |
|-----------------|-------------------------|-----------------------------------------|
| Stage           | `FULL`                  | Complete refresh every run              |
| Hub             | `INCREMENTAL_UNMANAGED` | HWM-based incremental load              |
| Link            | `INCREMENTAL_UNMANAGED` | HWM-based incremental load              |
| Satellite v0    | `INCREMENTAL_UNMANAGED` | HWM-based incremental load              |
| Satellite v1    | `VIEW`                  | Always derived from v0; no state needed |

---

## 4. Column Type Defaults

All inferred columns default to:
- Hash key / hash diff columns → `VARCHAR`
- Business keys / payload / foreign keys → `VARCHAR`
- `ldts_alias` column → `TIMESTAMP`
- `rsrc_alias` column → `VARCHAR`
- `ledts_alias` column (sat v1 only) → `TIMESTAMP`
- `is_current` column (sat v1 only) → `BOOLEAN`

Users override individual column types via the `column_overrides` parameter.

---

## 5. Self-Review Checklist

When writing or refactoring code in this package:

1. Does the factory correctly parse the dotted `name` into table/schema/database?
2. Does the `execute` closure capture all required variables by reference — not by value?
3. Are SQLMesh imports inside the factory function body (not at module top-level)?
4. Does column inference handle edge cases: empty sources, dict-form hash_diff, etc.?
5. Are validation errors raised with descriptive messages (fail early)?
6. Do tests cover the column inference independently of SQLMesh installation?
