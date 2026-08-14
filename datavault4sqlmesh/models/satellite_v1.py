from __future__ import annotations

from typing import Callable, Dict, List, Optional

from datavault4sqlmesh.schema.inference import infer_satellite_v1_columns


def satellite_v1_model(
    name: str,
    parent_hash_key: str,
    hash_diff: str,
    payload: Optional[List[str]] = None,
    *,
    sat_v0_table: Optional[str] = None,
    sat_v0_schema: Optional[str] = None,
    add_is_current: bool = True,
    is_current_col: str = "is_current",
    ledts_alias: Optional[str] = None,
    kind: Optional[Dict[str, object]] = None,
    cron: Optional[str] = None,
    tags: Optional[List[str]] = None,
    column_overrides: Optional[Dict[str, str]] = None,
    **model_kwargs,
) -> Callable:
    """
    Decorator factory for a Data Vault Satellite v1 (end-dated) SQLMesh model.

    **Auto-generate mode** (recommended) — pass ``sat_v0_table`` (and optionally
    ``sat_v0_schema``) and no ``execute`` body is needed::

        # models/customer_1_s.py
        from datavault4sqlmesh import satellite_v1_model

        satellite_v1_model(
            name="dv.customer_1_s",
            parent_hash_key="hk_customer_h",
            hash_diff="hd_customer_s",
            payload=["customer_name", "email", "phone", "address"],
            sat_v0_table="customer_0_s",
            sat_v0_schema="dv",
        )

    **Decorator mode** (backward-compatible) — omit ``sat_v0_table``::

        @satellite_v1_model(
            name="dv.customer_1_s",
            parent_hash_key="hk_customer_h",
            hash_diff="hd_customer_s",
        )
        def execute(evaluator, **kwargs):
            return SatelliteV1Generator(...).generate_sql()

    Args:
        name: Qualified model name (e.g. ``"dv.customer_1_s"``).
        parent_hash_key: Hash key column of the parent Hub or Link.
        hash_diff: Hash diff column name — used for column inference.
        payload: Satellite payload column names.
        sat_v0_table: Table name of the source Satellite v0.  When supplied
                      (together with ``sat_v0_schema``) the factory generates
                      the ``execute`` closure automatically.
        sat_v0_schema: Schema of the source Satellite v0.  Defaults to the
                       same schema as the v1 target when ``sat_v0_table`` is given.
        add_is_current: Append an ``is_current`` boolean column (default ``True``).
        is_current_col: Column name for the is-current flag.
        ledts_alias: Load-end-timestamp column name.
        kind: SQLMesh model kind dict.  Defaults to ``FULL``.
              Pass e.g. ``{"name": "VIEW"}`` to override.
        cron: SQLMesh cron expression.
        tags: Optional list of SQLMesh model tags.
        column_overrides: Exact SQL type strings applied after inference.
        **model_kwargs: Extra keyword arguments forwarded to ``@model``.

    Returns:
        When ``sat_v0_table`` is provided: the registered SQLMesh execute function.
        When ``sat_v0_table`` is ``None``: a decorator for a user-written ``execute``.
    """
    from sqlmesh import model as sqlmesh_model
    from sqlmesh.core.model import ModelKindName

    columns = infer_satellite_v1_columns(
        parent_hash_key,
        hash_diff,
        payload,
        add_is_current,
        is_current_col,
        ledts_alias,
        column_overrides,
    )

    _kind_name = kind.get("name") if kind is not None else None
    effective_kind: Dict[str, object] = {
        **(kind or {}),
        "name": ModelKindName(_kind_name) if isinstance(_kind_name, str) else (_kind_name or ModelKindName.FULL),
    }
    decorator_kwargs: Dict[str, object] = {
        "kind": effective_kind,
        "is_sql": True,
        "columns": columns,
    }
    if cron is not None:
        decorator_kwargs["cron"] = cron
    if tags is not None:
        decorator_kwargs["tags"] = tags
    decorator_kwargs.update(model_kwargs)

    def _make_decorator(fn: Callable) -> Callable:
        try:
            return sqlmesh_model(name, **decorator_kwargs)(fn)
        except ValueError as exc:
            if "Duplicate" in str(exc):
                return fn
            raise

    # --- Auto-generate mode ---
    if sat_v0_table is not None:
        from datavault4sqlmesh.models._utils import parse_model_name

        target_table, target_schema, _ = parse_model_name(name)
        # Default sat_v0_schema to the same schema as the v1 target
        _sat_v0_schema = sat_v0_schema if sat_v0_schema is not None else target_schema
        _sat_v0_table = sat_v0_table
        _parent_hash_key = parent_hash_key
        _hash_diff = hash_diff
        _target_table = target_table
        _target_schema = target_schema

        def _execute(evaluator, **kwargs):  # noqa: ANN001
            from datavault4sqlglot.generators.satellite_v1 import SatelliteV1Generator

            return SatelliteV1Generator(
                target_table=_target_table,
                target_schema=_target_schema,
                sat_v0_table=_sat_v0_table,
                sat_v0_schema=_sat_v0_schema,
                parent_hash_key=_parent_hash_key,
                hash_diff=_hash_diff,
            ).generate_sql()

        from datavault4sqlmesh.models._utils import _bind_execute_to_caller
        _bind_execute_to_caller(_execute, name)
        return _make_decorator(_execute)

    # --- Decorator mode (backward-compat) ---
    return _make_decorator
