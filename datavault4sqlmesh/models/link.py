from __future__ import annotations

from typing import Callable, Dict, List, Optional

from datavault4sqlmesh.schema.inference import infer_link_columns


def link_model(
    name: str,
    link_hash_key: str,
    foreign_hash_keys: List[str],
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
    Register a Data Vault Link SQLMesh model.

    **Single-source auto-generate mode** (most common) — pass ``source_table``::

        # models/order_customer_l.py
        from datavault4sqlmesh import link_model

        link_model(
            name="dv.order_customer_l",
            link_hash_key="hk_order_customer_l",
            foreign_hash_keys=["hk_order_h", "hk_customer_h"],
            source_schema="stage",
            source_table="stg_orders",
            rsrc_statics=["OMS/orders"],
        )

    **Multi-source auto-generate mode** — pass a list of ``SourceModel`` objects
    via ``sources``::

        from datavault4sqlmesh import link_model, SourceModel

        link_model(
            name="dv.order_customer_l",
            link_hash_key="hk_order_customer_l",
            foreign_hash_keys=["hk_order_h", "hk_customer_h"],
            sources=[
                SourceModel(schema_name="stage", table_name="stg_orders"),
                SourceModel(schema_name="stage", table_name="stg_legacy_orders"),
            ],
        )

    **Decorator mode** (for custom execute bodies) — omit both ``source_table``
    and ``sources``::

        @link_model(
            name="dv.order_customer_l",
            link_hash_key="hk_order_customer_l",
            foreign_hash_keys=["hk_order_h", "hk_customer_h"],
        )
        def execute(evaluator, **kwargs):
            return LinkGenerator(...).generate_sql()

    Args:
        name: Qualified model name (e.g. ``"dv.order_customer_l"``).
        link_hash_key: Link hash key column name.
        foreign_hash_keys: Foreign hash key columns (at least two).
        source_schema: Schema of the staging source table (single-source shorthand).
        source_table: Table name of the staging source (single-source shorthand).
        sources: List of ``SourceModel`` objects for multi-source links.  Cannot
                 be combined with ``source_table``.
        rsrc_statics: LIKE-pattern strings for HWM scoping, applied to all sources.
        kind: SQLMesh model kind dict.  Defaults to ``INCREMENTAL_UNMANAGED``.
        cron: SQLMesh cron expression.
        grain: Unique-row columns.  Defaults to ``[link_hash_key]``.
        tags: Optional list of SQLMesh model tags.
        additional_columns: Extra columns appended after foreign hash keys.
        column_overrides: Exact type strings for individual columns.
        **model_kwargs: Extra keyword arguments forwarded to ``@model``.

    Returns:
        When ``source_table`` or ``sources`` is provided: the registered SQLMesh
        execute function.
        When both are ``None``: a decorator for a user-written ``execute``.

    Raises:
        ValueError: When fewer than 2 ``foreign_hash_keys`` are supplied.
        ValueError: When both ``source_table`` and ``sources`` are provided.
    """
    from sqlmesh import model as sqlmesh_model
    from sqlmesh.core.model import ModelKindName

    if len(foreign_hash_keys) < 2:
        raise ValueError(
            f"link_model '{name}' requires at least 2 foreign_hash_keys, "
            f"got {len(foreign_hash_keys)}."
        )
    if source_table is not None and sources is not None:
        raise ValueError(
            f"link_model '{name}': pass either source_table (single-source) or "
            "sources (multi-source), not both."
        )

    columns = infer_link_columns(link_hash_key, foreign_hash_keys, additional_columns, column_overrides)
    effective_grain = grain or [link_hash_key]

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
        _link_hash_key = link_hash_key
        _foreign_hash_keys = foreign_hash_keys
        _rsrc_statics = rsrc_statics
        _target_table = target_table
        _target_schema = target_schema

        def _execute(evaluator, **kwargs):  # noqa: ANN001
            from datavault4sqlglot.generators.link import LinkGenerator
            from datavault4sqlglot.metadata import SourceBinding, SourceModel

            rebuilt = [
                SourceBinding(
                    source=SourceModel(**d),
                    fk_columns=_foreign_hash_keys,
                    rsrc_statics=_rsrc_statics,
                )
                for d in _sources_data
            ]
            return LinkGenerator(
                target_table=_target_table,
                target_schema=_target_schema,
                sources=rebuilt,
                link_hash_key=_link_hash_key,
                foreign_hash_keys=_foreign_hash_keys,
                is_incremental=True,
            ).generate_sql()

        from datavault4sqlmesh.models._utils import _bind_execute_to_caller
        _bind_execute_to_caller(_execute, name)
        return _make_decorator(_execute)

    # --- Decorator mode ---
    return _make_decorator
