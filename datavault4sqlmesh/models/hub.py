from __future__ import annotations

from typing import Callable, Dict, List, Optional

from datavault4sqlglot.metadata import SourceBinding, SourceModel

from datavault4sqlmesh.schema.inference import infer_hub_columns


def hub_model(
    name: str,
    hashkey: str,
    business_keys: List[str],
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
    Decorator factory for a Data Vault Hub SQLMesh model.

    **Auto-generate mode** (recommended) — pass ``sources`` and no ``execute``
    body is needed::

        # models/customer_h.py
        from datavault4sqlmesh import hub_model, SourceBinding, SourceModel

        hub_model(
            name="dv.customer_h",
            hashkey="hk_customer_h",
            business_keys=["customer_id"],
            sources=[
                SourceBinding(
                    source=SourceModel(schema_name="stage", table_name="stg_customer"),
                    hash_key_col="hk_customer_h",
                    business_keys=["customer_id"],
                    rsrc_statics=["ERP/customers"],
                )
            ],
        )

    **Decorator mode** (backward-compatible) — omit ``sources`` and supply an
    ``execute`` body that calls ``HubGenerator`` directly::

        @hub_model(
            name="dv.customer_h",
            hashkey="hk_customer_h",
            business_keys=["customer_id"],
        )
        def execute(evaluator, **kwargs):
            return HubGenerator(...).generate_sql()

    Args:
        name: Qualified model name (e.g. ``"dv.customer_h"``).
        hashkey: Target hash key column name — used as the model grain and
                 first column in the inferred schema.
        business_keys: Business key column names — added to the inferred schema
                       as VARCHAR.
        sources: Full ``SourceBinding`` list.  When supplied the factory
                 generates the ``execute`` closure automatically.  Omit to use
                 the classic decorator pattern instead.
        kind: SQLMesh model kind dict.  Defaults to ``INCREMENTAL_UNMANAGED``.
              Pass e.g. ``{"name": "FULL"}`` to override.
        cron: SQLMesh cron expression.  Omit to inherit the project default.
        grain: Unique-row columns.  Defaults to ``[hashkey]``.
        tags: Optional list of SQLMesh model tags.
        additional_columns: Extra columns to include in the inferred schema.
        column_overrides: Exact SQL type strings for individual columns, applied
                          after inference.
        **model_kwargs: Extra keyword arguments forwarded to the SQLMesh
                        ``@model`` decorator.

    Returns:
        When ``sources`` is provided: the registered SQLMesh execute function.
        When ``sources`` is ``None``: a decorator to apply to a user-written
        ``execute`` function.

    Raises:
        ValueError: When ``business_keys`` is empty.
    """
    from sqlmesh import model as sqlmesh_model
    from sqlmesh.core.model import ModelKindName

    if not business_keys:
        raise ValueError(f"hub_model '{name}' requires at least one business key.")

    # Column inference: use real sources when available, dummy otherwise.
    _infer_sources = sources or [
        SourceBinding(source=SourceModel(table_name="_"), business_keys=business_keys)
    ]
    columns = infer_hub_columns(hashkey, _infer_sources, additional_columns, column_overrides)
    effective_grain = grain or [hashkey]

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
        _hashkey = hashkey
        _target_table = target_table
        _target_schema = target_schema

        def _execute(evaluator, **kwargs):  # noqa: ANN001
            from datavault4sqlglot.generators.hub import HubGenerator
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
            return HubGenerator(
                target_table=_target_table,
                target_schema=_target_schema,
                sources=rebuilt,
                hashkey=_hashkey,
                is_incremental=True,
            ).generate_sql()

        from datavault4sqlmesh.models._utils import _bind_execute_to_caller
        _bind_execute_to_caller(_execute, name)
        return _make_decorator(_execute)

    # --- Decorator mode (backward-compat) ---
    return _make_decorator
