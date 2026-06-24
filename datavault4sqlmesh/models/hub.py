from __future__ import annotations

from typing import Callable, Dict, List, Optional

from datavault4sqlmesh.schema.inference import infer_hub_columns


def hub_model(
    name: str,
    hashkey: str,
    business_keys: List[str],
    *,
    source_schema: Optional[str] = None,
    source_table: Optional[str] = None,
    sources: Optional[List] = None,
    rsrc_statics: Optional[List[str]] = None,
    kind: Optional[Dict[str, object]] = None,
    cron: Optional[str] = None,
    grain: Optional[List[str]] = None,
    tags: Optional[List[str]] = None,
    additional_columns: Optional[List[str]] = None,
    column_overrides: Optional[Dict[str, str]] = None,
    **model_kwargs,
) -> Callable:
    """
    Register a Data Vault Hub SQLMesh model.

    **Single-source auto-generate mode** (most common) — pass ``source_table``::

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

    **Multi-source auto-generate mode** — pass a list of ``SourceModel`` objects
    via ``sources``::

        from datavault4sqlmesh import hub_model, SourceModel

        hub_model(
            name="dv.customer_h",
            hashkey="hk_customer_h",
            business_keys=["customer_id"],
            sources=[
                SourceModel(schema_name="stage", table_name="stg_crm"),
                SourceModel(schema_name="stage", table_name="stg_erp"),
            ],
            rsrc_statics=["CRM/customers", "ERP/customers"],
        )

    **Decorator mode** (for custom execute bodies) — omit both ``source_table``
    and ``sources``::

        @hub_model(
            name="dv.customer_h",
            hashkey="hk_customer_h",
            business_keys=["customer_id"],
        )
        def execute(evaluator, **kwargs):
            return HubGenerator(...).generate_sql()

    Args:
        name: Qualified model name (e.g. ``"dv.customer_h"``).
        hashkey: Hub hash key column name.
        business_keys: Business key column names (at least one).
        source_schema: Schema of the staging source table (single-source shorthand).
        source_table: Table name of the staging source (single-source shorthand).
        sources: List of ``SourceModel`` objects for multi-source hubs.  Cannot
                 be combined with ``source_table``.
        rsrc_statics: LIKE-pattern strings for HWM scoping, applied to all sources.
        kind: SQLMesh model kind dict.  Defaults to ``INCREMENTAL_UNMANAGED``.
        cron: SQLMesh cron expression.
        grain: Unique-row columns.  Defaults to ``[hashkey]``.
        tags: Optional list of SQLMesh model tags.
        additional_columns: Extra columns to include in the inferred schema.
        column_overrides: Exact SQL type strings applied after inference.
        **model_kwargs: Extra keyword arguments forwarded to ``@model``.

    Returns:
        When ``source_table`` or ``sources`` is provided: the registered SQLMesh
        execute function.
        When both are ``None``: a decorator for a user-written ``execute``.

    Raises:
        ValueError: When ``business_keys`` is empty.
        ValueError: When both ``source_table`` and ``sources`` are provided.
    """
    from sqlmesh import model as sqlmesh_model
    from sqlmesh.core.model import ModelKindName

    if not business_keys:
        raise ValueError(f"hub_model '{name}' requires at least one business key.")
    if source_table is not None and sources is not None:
        raise ValueError(
            f"hub_model '{name}': pass either source_table (single-source) or "
            "sources (multi-source), not both."
        )

    columns = infer_hub_columns(hashkey, business_keys, additional_columns, column_overrides)
    effective_grain = grain or [hashkey]

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

    # --- Resolve sources list (single-source shorthand or explicit list) ---
    resolved_sources = sources
    if source_table is not None:
        from datavault4sqlglot.metadata import SourceModel
        resolved_sources = [SourceModel(schema_name=source_schema, table_name=source_table)]

    # --- Auto-generate mode ---
    if resolved_sources is not None:
        from datavault4sqlmesh.models._utils import parse_model_name

        target_table, target_schema, _ = parse_model_name(name)
        _sources_data = [sm.model_dump() for sm in resolved_sources]
        _hashkey = hashkey
        _business_keys = business_keys
        _rsrc_statics = rsrc_statics
        _target_table = target_table
        _target_schema = target_schema

        def _execute(evaluator, **kwargs):  # noqa: ANN001
            from datavault4sqlglot.generators.hub import HubGenerator
            from datavault4sqlglot.metadata import SourceBinding, SourceModel

            rebuilt = [
                SourceBinding(
                    source=SourceModel(**d),
                    bk_columns=_business_keys,
                    rsrc_statics=_rsrc_statics,
                )
                for d in _sources_data
            ]
            return HubGenerator(
                target_table=_target_table,
                target_schema=_target_schema,
                sources=rebuilt,
                hashkey=_hashkey,
                business_keys=_business_keys,
                is_incremental=True,
            ).generate_sql()

        from datavault4sqlmesh.models._utils import _bind_execute_to_caller
        _bind_execute_to_caller(_execute, name)
        return _make_decorator(_execute)

    # --- Decorator mode ---
    return _make_decorator
