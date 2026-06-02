from __future__ import annotations

from typing import Callable, Dict, List, Optional

from datavault4sqlglot.metadata import StageModel

from datavault4sqlmesh.schema.inference import infer_stage_columns


def stage_model(
    name: str,
    source_model: StageModel,
    *,
    kind: Optional[Dict[str, object]] = None,
    cast_ldts_to_timestamp: bool = False,
    cron: Optional[str] = None,
    tags: Optional[List[str]] = None,
    column_overrides: Optional[Dict[str, str]] = None,
    **model_kwargs,
) -> Callable:
    """
    Factory for a Data Vault Stage (hash) layer SQLMesh model.

    Registers a complete SQLMesh model — no ``execute`` function needs to be
    written.  Call this at module level in a model file::

        # models/stg_customer.py
        from datavault4sqlmesh import stage_model, StageModel

        stage_model(
            name="stage.stg_customer",
            source_model=StageModel(
                schema_name="user_mszerencse",
                table_name="customers",
                hashed_columns={
                    "hk_customer_h": ["customer_id"],
                    "hd_customer_s": {
                        "is_hashdiff": True,
                        "columns": ["customer_name", "email", "phone", "address"],
                    },
                },
            ),
        )

    ``target_table`` and ``target_schema`` are derived automatically from ``name``
    (e.g. ``"stage.stg_customer"`` → table ``"stg_customer"``, schema ``"stage"``).

    Args:
        name: Qualified model name (e.g. ``"stage.stg_customer"``).
        source_model: ``StageModel`` describing the raw source table, its
                      hashed columns, derived columns, and ghost records.
        kind: SQLMesh model kind dict.  Defaults to ``FULL``.  Pass e.g.
              ``{"name": "VIEW"}`` to override.
        cast_ldts_to_timestamp: When ``True``, wraps the generated SQL in an
                                outer SELECT that casts the ``ldts`` column to
                                TIMESTAMP.  Useful when the source is a Postgres
                                seed loaded from CSV (where dates arrive as TEXT).
        cron: SQLMesh cron expression.  Omit to inherit the project default.
        tags: Optional list of SQLMesh model tags.
        column_overrides: Exact SQL type strings applied after inference.  Also
                          used to declare source-table columns that cannot be
                          inferred automatically.
        **model_kwargs: Extra keyword arguments forwarded to the SQLMesh
                        ``@model`` decorator.

    Returns:
        The registered SQLMesh execute function (callable).
    """
    from sqlmesh import model as sqlmesh_model
    from sqlmesh.core.model import ModelKindName

    from datavault4sqlmesh.models._utils import parse_model_name

    target_table, target_schema, _ = parse_model_name(name)
    columns = infer_stage_columns(source_model, column_overrides)

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

    # Capture values for the closure.  We close over the StageModel instance
    # directly (Pydantic models are picklable) rather than re-serialising its
    # fields, which avoids needing to know every field name.
    _source_model_data = source_model.model_dump()
    _target_table = target_table
    _target_schema = target_schema
    _cast = cast_ldts_to_timestamp
    _columns = columns  # used by the cast path to enumerate all output columns

    def _execute(evaluator, **kwargs):  # noqa: ANN001
        from datavault4sqlglot.config import config as _cfg
        from datavault4sqlglot.generators.stage import StageGenerator
        from datavault4sqlglot.metadata import StageModel

        sql = StageGenerator(
            source_model=StageModel(**_source_model_data),
            target_table=_target_table,
            target_schema=_target_schema,
        ).generate_sql()

        if _cast:
            from sqlglot import exp as _exp

            ldts = _cfg.ldts_alias
            # Build the outer SELECT from the inferred columns dict so that
            # every declared column is enumerated explicitly (including source
            # columns arriving via SELECT *).  This avoids relying on
            # sql.named_selects, which only lists explicitly aliased columns
            # and does not include the implicit SELECT * expansion.
            selects = []
            for col in _columns:
                if col == ldts:
                    selects.append(
                        _exp.Cast(
                            this=_exp.column(col),
                            to=_exp.DataType.build("TIMESTAMP"),
                        ).as_(col)
                    )
                else:
                    selects.append(_exp.column(col))
            return _exp.select(*selects).from_(
                _exp.Subquery(
                    this=sql,
                    alias=_exp.TableAlias(this=_exp.Identifier(this="_stg")),
                )
            )

        return sql

    from datavault4sqlmesh.models._utils import _bind_execute_to_caller
    _bind_execute_to_caller(_execute, name)

    try:
        return sqlmesh_model(name, **decorator_kwargs)(_execute)
    except ValueError as exc:
        if "Duplicate" in str(exc):
            return _execute
        raise
