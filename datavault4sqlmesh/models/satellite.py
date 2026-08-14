from __future__ import annotations

from typing import Callable, Dict, List, Optional, Union

from datavault4sqlmesh.schema.inference import infer_satellite_columns


def satellite_model(
    name: str,
    parent_hash_key: str,
    hash_diff: Union[str, Dict[str, str]],
    payload: Optional[List[str]] = None,
    *,
    source_schema: Optional[str] = None,
    source_table: Optional[str] = None,
    kind: Optional[Dict[str, object]] = None,
    cron: Optional[str] = None,
    grain: Optional[List[str]] = None,
    tags: Optional[List[str]] = None,
    additional_columns: Optional[List[str]] = None,
    column_overrides: Optional[Dict[str, str]] = None,
    **model_kwargs,
) -> Callable:
    """
    Register a Data Vault Satellite v0 (current-record) SQLMesh model.

    **Auto-generate mode** (recommended) — pass ``source_table`` and no
    ``execute`` body is needed::

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

    **Decorator mode** (for custom execute bodies) — omit ``source_table``::

        @satellite_model(
            name="dv.customer_0_s",
            parent_hash_key="hk_customer_h",
            hash_diff="hd_customer_s",
            payload=["customer_name", "email"],
        )
        def execute(evaluator, **kwargs):
            return SatelliteGenerator(...).generate_sql()

    Args:
        name: Qualified model name (e.g. ``"dv.customer_0_s"``).
        parent_hash_key: Hash key column of the parent Hub or Link.
        hash_diff: Hash diff column name (string) or config dict with ``alias`` key.
        payload: Satellite payload (attribute) column names.
        source_schema: Schema of the staging source table.
        source_table: Table name of the staging source.  When supplied the
                      function generates the ``execute`` closure automatically.
        kind: SQLMesh model kind dict.  Defaults to ``INCREMENTAL_UNMANAGED``.
        cron: SQLMesh cron expression.
        grain: Unique-row columns.  Defaults to ``[parent_hash_key, ldts_alias]``.
        tags: Optional list of SQLMesh model tags.
        additional_columns: Extra columns to include in the inferred schema.
        column_overrides: Exact SQL type strings applied after inference.
        **model_kwargs: Extra keyword arguments forwarded to ``@model``.

    Returns:
        When ``source_table`` is provided: the registered SQLMesh execute function.
        When ``source_table`` is ``None``: a decorator for a user-written ``execute``.
    """
    from sqlmesh import model as sqlmesh_model
    from sqlmesh.core.model import ModelKindName
    from datavault4sqlglot.config import config as _dv_config

    columns = infer_satellite_columns(
        parent_hash_key, hash_diff, payload, additional_columns, column_overrides
    )
    effective_grain = grain or [parent_hash_key, _dv_config.ldts_alias]

    _kind_name = kind.get("name") if kind is not None else None
    _resolved_name = ModelKindName(_kind_name) if isinstance(_kind_name, str) else (_kind_name or ModelKindName.INCREMENTAL_UNMANAGED)
    effective_kind: Dict[str, object] = {**(kind or {}), "name": _resolved_name}
    if _resolved_name == ModelKindName.INCREMENTAL_UNMANAGED and "disable_restatement" not in (kind or {}):
        effective_kind["disable_restatement"] = False
    decorator_kwargs: Dict[str, object] = {
        "kind": effective_kind,
        "is_sql": True,
        "columns": columns,
        "grain": effective_grain,
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
    if source_table is not None:
        from datavault4sqlmesh.models._utils import parse_model_name

        target_table, target_schema, _ = parse_model_name(name)
        _source_schema = source_schema
        _source_table = source_table
        _parent_hash_key = parent_hash_key
        _hash_diff = hash_diff
        _payload = list(payload or [])
        _target_table = target_table
        _target_schema = target_schema

        def _execute(evaluator, **kwargs):  # noqa: ANN001
            from datavault4sqlglot.generators.satellite import SatelliteGenerator
            from datavault4sqlglot.metadata import SourceModel

            return SatelliteGenerator(
                target_table=_target_table,
                target_schema=_target_schema,
                source_model=SourceModel(schema_name=_source_schema, table_name=_source_table),
                parent_hash_key=_parent_hash_key,
                hash_diff=_hash_diff,
                payload=_payload or None,
                is_incremental=True,
            ).generate_sql()

        from datavault4sqlmesh.models._utils import _bind_execute_to_caller
        _bind_execute_to_caller(_execute, name)
        return _make_decorator(_execute)

    # --- Decorator mode (backward-compat) ---
    return _make_decorator
