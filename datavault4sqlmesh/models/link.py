from __future__ import annotations

from typing import Callable, Dict, List, Optional

from datavault4sqlglot.metadata import SourceBinding, SourceModel

from datavault4sqlmesh.schema.inference import infer_link_columns


def link_model(
    name: str,
    link_hash_key: str,
    foreign_hash_keys: List[str],
    *,
    sources: Optional[List[SourceBinding]] = None,
    kind: Optional[Dict[str, object]] = None,
    cron: Optional[str] = None,
    grain: Optional[List[str]] = None,
    tags: Optional[List[str]] = None,
    additional_columns: Optional[List[str]] = None,
    column_overrides: Optional[Dict[str, str]] = None,
    **model_kwargs,
) -> Callable:
    """
    Decorator factory for a Data Vault Link SQLMesh model.

    **Auto-generate mode** (recommended) — pass ``sources`` and no ``execute``
    body is needed::

        # models/order_customer_l.py
        from datavault4sqlmesh import link_model, SourceBinding, SourceModel

        link_model(
            name="dv.order_customer_l",
            link_hash_key="hk_order_customer_l",
            foreign_hash_keys=["hk_order_h", "hk_customer_h"],
            sources=[
                SourceBinding(
                    source=SourceModel(schema_name="stage", table_name="stg_orders"),
                    hash_key_col="hk_order_customer_l",
                    foreign_hash_keys=["hk_order_h", "hk_customer_h"],
                    rsrc_statics=["OMS/orders"],
                )
            ],
        )

    **Decorator mode** (backward-compatible) — omit ``sources``::

        @link_model(
            name="dv.order_customer_l",
            link_hash_key="hk_order_customer_l",
            foreign_hash_keys=["hk_order_h", "hk_customer_h"],
        )
        def execute(evaluator, **kwargs):
            return LinkGenerator(...).generate_sql()

    Args:
        name: Qualified model name (e.g. ``"dv.order_customer_l"``).
        link_hash_key: Target link hash key column name.
        foreign_hash_keys: All foreign hash key column names.  At least 2 required.
        sources: Full ``SourceBinding`` list.  When supplied the factory
                 generates the ``execute`` closure automatically.
        kind: SQLMesh model kind dict.  Defaults to ``INCREMENTAL_UNMANAGED``.
              Pass e.g. ``{"name": "FULL"}`` to override.
        cron: SQLMesh cron expression.
        grain: Unique-row columns.  Defaults to ``[link_hash_key]``.
        tags: Optional list of SQLMesh model tags.
        additional_columns: Extra columns appended after foreign hash keys.
        column_overrides: Exact type strings for individual columns.
        **model_kwargs: Extra keyword arguments forwarded to ``@model``.

    Returns:
        When ``sources`` is provided: the registered SQLMesh execute function.
        When ``sources`` is ``None``: a decorator for a user-written ``execute``.

    Raises:
        ValueError: When fewer than 2 ``foreign_hash_keys`` are supplied.
    """
    from sqlmesh import model as sqlmesh_model
    from sqlmesh.core.model import ModelKindName

    if len(foreign_hash_keys) < 2:
        raise ValueError(
            f"link_model '{name}' requires at least 2 foreign_hash_keys, "
            f"got {len(foreign_hash_keys)}."
        )

    # Column inference: use real sources when available, dummy otherwise.
    _infer_sources = sources or [
        SourceBinding(
            source=SourceModel(table_name="_"),
            foreign_hash_keys=foreign_hash_keys,
        )
    ]
    columns = infer_link_columns(link_hash_key, _infer_sources, additional_columns, column_overrides)
    effective_grain = grain or [link_hash_key]

    _kind_name = kind.get("name") if kind is not None else None
    effective_kind: Dict[str, object] = {
        **(kind or {}),
        "name": ModelKindName(_kind_name) if isinstance(_kind_name, str) else (_kind_name or ModelKindName.INCREMENTAL_UNMANAGED),
    }
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
    if sources is not None:
        from datavault4sqlmesh.models._utils import parse_model_name

        target_table, target_schema, _ = parse_model_name(name)
        _sources_data = [
            {
                "source": sb.source.model_dump(),
                "business_keys": list(sb.business_keys),
                "foreign_hash_keys": list(sb.foreign_hash_keys),
                "hash_key_col": sb.hash_key_col,
                "payload": list(sb.payload),
                "rsrc_statics": list(sb.rsrc_statics) if sb.rsrc_statics else None,
                "additional_columns": list(sb.additional_columns) if sb.additional_columns else None,
            }
            for sb in sources
        ]
        _link_hash_key = link_hash_key
        _target_table = target_table
        _target_schema = target_schema

        def _execute(evaluator, **kwargs):  # noqa: ANN001
            from datavault4sqlglot.generators.link import LinkGenerator
            from datavault4sqlglot.metadata import SourceBinding, SourceModel

            rebuilt = [
                SourceBinding(
                    source=SourceModel(**d["source"]),
                    business_keys=d["business_keys"],
                    foreign_hash_keys=d["foreign_hash_keys"],
                    hash_key_col=d["hash_key_col"],
                    payload=d["payload"],
                    rsrc_statics=d["rsrc_statics"],
                    additional_columns=d["additional_columns"],
                )
                for d in _sources_data
            ]
            return LinkGenerator(
                target_table=_target_table,
                target_schema=_target_schema,
                sources=rebuilt,
                link_hash_key=_link_hash_key,
                is_incremental=True,
            ).generate_sql()

        from datavault4sqlmesh.models._utils import _bind_execute_to_caller
        _bind_execute_to_caller(_execute, name)
        return _make_decorator(_execute)

    # --- Decorator mode (backward-compat) ---
    return _make_decorator
