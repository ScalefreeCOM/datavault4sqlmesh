from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Union

from datavault4sqlmesh.schema.inference import infer_stage_columns


def stage_model(
    name: str,
    source_table: str,
    *,
    source_schema: Optional[str] = None,
    source_database: Optional[str] = None,
    hashed_columns: Optional[Dict[str, Union[List[str], Dict[str, Any]]]] = None,
    derived_columns: Optional[Dict[str, str]] = None,
    include_source_columns: bool = True,
    missing_columns: Optional[Dict[str, str]] = None,
    ghost_record_types: Optional[Dict[str, str]] = None,
    case_sensitivity: Optional[bool] = None,
    use_rtrim: Optional[bool] = None,
    load_date_col: Optional[str] = None,
    record_source_col: Optional[str] = None,
    sequence: Optional[str] = None,
    kind: Optional[Dict[str, object]] = None,
    cast_ldts_to_timestamp: bool = False,
    cron: Optional[str] = None,
    tags: Optional[List[str]] = None,
    column_overrides: Optional[Dict[str, str]] = None,
    **model_kwargs,
) -> Callable:
    """
    Register a Data Vault Stage (hash) layer SQLMesh model.

    Call this at module level in a model file::

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
            column_overrides={
                "customer_id":   "VARCHAR",
                "customer_name": "VARCHAR",
                "email":         "VARCHAR",
            },
        )

    ``target_table`` and ``target_schema`` are derived automatically from ``name``
    (e.g. ``"stage.stg_customer"`` → table ``"stg_customer"``, schema ``"stage"``).

    Args:
        name: Qualified model name (e.g. ``"stage.stg_customer"``).
        source_table: Raw source table name.
        source_schema: Schema of the raw source table.
        source_database: Database of the raw source table.
        hashed_columns: Hash key and hash diff definitions.  Each key is a
                        column alias; the value is either a list of source
                        columns (hash key) or a dict with ``is_hashdiff: True``
                        and ``columns`` (hash diff).
        derived_columns: Alias → SQL expression string for columns that do not
                         exist in the raw source (e.g. a constant record source).
        include_source_columns: When ``True`` (default), ``SELECT *`` from
                                the raw source is included.
        missing_columns: Column name → SQL type string for schema-evolution
                         placeholder columns.
        ghost_record_types: Column name → SQL type for ghost/zero record union.
        case_sensitivity: Override ``config.hashkey_input_case_sensitive``.
        use_rtrim: Override ``config.use_trim``.
        load_date_col: Source column carrying the load timestamp.  Defaults to
                       ``config.ldts_alias``.
        record_source_col: Source column carrying the record source.  Defaults
                           to ``config.rsrc_alias``.
        sequence: Column name for a ``ROW_NUMBER() OVER ()`` expression.
        kind: SQLMesh model kind dict.  Defaults to ``FULL``.
        cast_ldts_to_timestamp: When ``True``, wraps the generated SQL in an
                                outer SELECT that casts ``ldts`` to TIMESTAMP.
                                Useful when the source is a seed loaded from CSV.
        cron: SQLMesh cron expression.
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
    from datavault4sqlglot.metadata import StageModel

    source_model = StageModel(
        table_name=source_table,
        schema_name=source_schema,
        database=source_database,
        hashed_columns=hashed_columns,
        derived_columns=derived_columns,
        include_source_columns=include_source_columns,
        missing_columns=missing_columns,
        ghost_record_types=ghost_record_types,
        case_sensitivity=case_sensitivity,
        use_rtrim=use_rtrim,
        load_date_col=load_date_col,
        record_source_col=record_source_col,
        sequence=sequence,
    )

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

    _source_model_data = source_model.model_dump()
    _target_table = target_table
    _target_schema = target_schema
    _cast = cast_ldts_to_timestamp
    _columns = columns

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
