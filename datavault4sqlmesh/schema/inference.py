from __future__ import annotations

from typing import Dict, List, Optional, Union

# Import the config singleton directly from its own module so that
# `datavault4sqlglot/__init__.py` shadowing the `config` package attribute
# with a DataVaultConfig instance does not affect us.
# (Using `import datavault4sqlglot.config as X` would hit IMPORT_FROM which
# resolves via `getattr(datavault4sqlglot, 'config')` and returns the
# DataVaultConfig instance, not the module.)
from datavault4sqlglot.config import config as _dv_config
from datavault4sqlglot.metadata import SourceBinding, StageModel

# Default SQL type constants — override via column_overrides where needed.
_HASH_TYPE = "VARCHAR"
_VARCHAR_TYPE = "VARCHAR"
_TIMESTAMP_TYPE = "TIMESTAMP"
_BOOLEAN_TYPE = "BOOLEAN"


def _resolve_hash_diff_alias(hash_diff: Union[str, Dict[str, str]]) -> str:
    """
    Return the output column name for a hash_diff parameter.

    Mirrors the resolution logic in ``BaseGenerator._resolve_column_config``:
    - string → the string itself is both source column and alias
    - dict   → ``alias`` key; falls back to ``source_column``

    Args:
        hash_diff: A plain column name or a config dict with ``alias`` / ``source_column``.

    Returns:
        The alias (output column name) for the hash diff.
    """
    if isinstance(hash_diff, str):
        return hash_diff
    return hash_diff.get("alias", hash_diff.get("source_column", "hash_diff"))


def infer_hub_columns(
    hashkey: str,
    sources: List[SourceBinding],
    additional_columns: Optional[List[str]] = None,
    column_overrides: Optional[Dict[str, str]] = None,
) -> Dict[str, str]:
    """
    Infer the SQLMesh ``columns`` schema dict for a Hub model.

    Column order matches the Hub generator output:
    1. Hash key (VARCHAR)
    2. Business keys from all sources, de-duplicated in declaration order (VARCHAR)
    3. Additional columns (VARCHAR)
    4. ldts (TIMESTAMP)
    5. rsrc (VARCHAR)

    Args:
        hashkey: Target hash key column name in the Hub table.
        sources: SourceBinding list; business_keys are collected from every binding.
        additional_columns: Extra columns appended after business keys.
        column_overrides: Exact type strings applied last, overriding inferred types.

    Returns:
        Ordered dict mapping column name → SQL type string.

    Raises:
        ValueError: When ``sources`` is empty.
    """
    if not sources:
        raise ValueError("hub_model requires at least one SourceBinding in sources.")

    ldts_col = _dv_config.ldts_alias
    rsrc_col = _dv_config.rsrc_alias

    columns: Dict[str, str] = {}
    columns[hashkey] = _HASH_TYPE

    seen: set[str] = {hashkey}
    for binding in sources:
        for bk in binding.business_keys:
            if bk not in seen:
                columns[bk] = _VARCHAR_TYPE
                seen.add(bk)

    for col in additional_columns or []:
        if col not in seen:
            columns[col] = _VARCHAR_TYPE
            seen.add(col)

    columns[ldts_col] = _TIMESTAMP_TYPE
    columns[rsrc_col] = _VARCHAR_TYPE

    if column_overrides:
        columns.update(column_overrides)

    return columns


def infer_link_columns(
    link_hash_key: str,
    sources: List[SourceBinding],
    additional_columns: Optional[List[str]] = None,
    column_overrides: Optional[Dict[str, str]] = None,
) -> Dict[str, str]:
    """
    Infer the SQLMesh ``columns`` schema dict for a Link model.

    Column order matches the Link generator output:
    1. Link hash key (VARCHAR)
    2. Foreign hash keys from all sources, de-duplicated in declaration order (VARCHAR)
    3. Additional columns (VARCHAR)
    4. ldts (TIMESTAMP)
    5. rsrc (VARCHAR)

    Args:
        link_hash_key: Target link hash key column name.
        sources: SourceBinding list; foreign_hash_keys are collected from every binding.
        additional_columns: Extra columns appended after foreign hash keys.
        column_overrides: Exact type strings applied last, overriding inferred types.

    Returns:
        Ordered dict mapping column name → SQL type string.

    Raises:
        ValueError: When ``sources`` is empty or any binding has fewer than 2 foreign keys.
    """
    if not sources:
        raise ValueError("link_model requires at least one SourceBinding in sources.")

    for binding in sources:
        if len(binding.foreign_hash_keys) < 2:
            raise ValueError(
                f"Link source '{binding.source.table_name}' must declare at least "
                f"2 foreign_hash_keys, got {len(binding.foreign_hash_keys)}."
            )

    ldts_col = _dv_config.ldts_alias
    rsrc_col = _dv_config.rsrc_alias

    columns: Dict[str, str] = {}
    columns[link_hash_key] = _HASH_TYPE

    seen: set[str] = {link_hash_key}
    for binding in sources:
        for fhk in binding.foreign_hash_keys:
            if fhk not in seen:
                columns[fhk] = _HASH_TYPE
                seen.add(fhk)

    for col in additional_columns or []:
        if col not in seen:
            columns[col] = _VARCHAR_TYPE
            seen.add(col)

    columns[ldts_col] = _TIMESTAMP_TYPE
    columns[rsrc_col] = _VARCHAR_TYPE

    if column_overrides:
        columns.update(column_overrides)

    return columns


def infer_satellite_columns(
    parent_hash_key: str,
    hash_diff: Union[str, Dict[str, str]],
    payload: Optional[List[str]] = None,
    additional_columns: Optional[List[str]] = None,
    column_overrides: Optional[Dict[str, str]] = None,
) -> Dict[str, str]:
    """
    Infer the SQLMesh ``columns`` schema dict for a Satellite v0 model.

    Column order matches the Satellite generator output:
    1. Parent hash key (VARCHAR)
    2. Hash diff (VARCHAR)
    3. Payload columns (VARCHAR)
    4. Additional columns (VARCHAR)
    5. ldts (TIMESTAMP)
    6. rsrc (VARCHAR)

    Args:
        parent_hash_key: The parent entity's hash key column name.
        hash_diff: Hash diff column name (string) or config dict with ``alias`` key.
        payload: Satellite payload (attribute) column names.
        additional_columns: Extra columns appended after payload.
        column_overrides: Exact type strings applied last, overriding inferred types.

    Returns:
        Ordered dict mapping column name → SQL type string.
    """
    ldts_col = _dv_config.ldts_alias
    rsrc_col = _dv_config.rsrc_alias
    hash_diff_col = _resolve_hash_diff_alias(hash_diff)

    columns: Dict[str, str] = {}
    columns[parent_hash_key] = _HASH_TYPE
    columns[hash_diff_col] = _HASH_TYPE

    seen: set[str] = {parent_hash_key, hash_diff_col}
    for col in payload or []:
        if col not in seen:
            columns[col] = _VARCHAR_TYPE
            seen.add(col)

    for col in additional_columns or []:
        if col not in seen:
            columns[col] = _VARCHAR_TYPE
            seen.add(col)

    columns[ldts_col] = _TIMESTAMP_TYPE
    columns[rsrc_col] = _VARCHAR_TYPE

    if column_overrides:
        columns.update(column_overrides)

    return columns


def infer_satellite_v1_columns(
    parent_hash_key: str,
    hash_diff: str,
    payload: Optional[List[str]] = None,
    add_is_current: bool = True,
    is_current_col: str = "is_current",
    ledts_alias: Optional[str] = None,
    column_overrides: Optional[Dict[str, str]] = None,
) -> Dict[str, str]:
    """
    Infer the SQLMesh ``columns`` schema dict for a Satellite v1 (end-dated) model.

    Extends the v0 schema with ``ledts`` (TIMESTAMP) and an optional ``is_current``
    (BOOLEAN) flag, matching the columns produced by ``SatelliteV1Generator``.

    Column order:
    1. Parent hash key (VARCHAR)
    2. Hash diff (VARCHAR)
    3. Payload columns (VARCHAR)
    4. ldts (TIMESTAMP)
    5. rsrc (VARCHAR)
    6. ledts (TIMESTAMP)
    7. is_current (BOOLEAN) — when add_is_current=True

    Args:
        parent_hash_key: The parent entity's hash key column name.
        hash_diff: Hash diff column name.
        payload: Satellite payload (attribute) column names.
        add_is_current: Whether an ``is_current`` boolean column is appended.
        is_current_col: Column name for the is-current flag.
        ledts_alias: Override for the load-end-timestamp column name.
                     Defaults to ``config.ledts_alias``.
        column_overrides: Exact type strings applied last, overriding inferred types.

    Returns:
        Ordered dict mapping column name → SQL type string.
    """
    ldts_col = _dv_config.ldts_alias
    rsrc_col = _dv_config.rsrc_alias
    ledts_col = ledts_alias or _dv_config.ledts_alias

    columns: Dict[str, str] = {}
    columns[parent_hash_key] = _HASH_TYPE
    columns[hash_diff] = _HASH_TYPE

    seen: set[str] = {parent_hash_key, hash_diff}
    for col in payload or []:
        if col not in seen:
            columns[col] = _VARCHAR_TYPE
            seen.add(col)

    columns[ldts_col] = _TIMESTAMP_TYPE
    columns[rsrc_col] = _VARCHAR_TYPE
    columns[ledts_col] = _TIMESTAMP_TYPE

    if add_is_current:
        columns[is_current_col] = _BOOLEAN_TYPE

    if column_overrides:
        columns.update(column_overrides)

    return columns


def infer_stage_columns(
    source_model: StageModel,
    column_overrides: Optional[Dict[str, str]] = None,
) -> Dict[str, str]:
    """
    Infer the SQLMesh ``columns`` schema dict for a Stage model.

    Infers only the columns that are derivable from the ``StageModel`` metadata:
    hashed columns, derived columns, schema-evolution placeholders, ldts, and rsrc.

    Source columns produced by ``include_source_columns=True`` cannot be inferred
    without querying the source database.  Specify them explicitly via
    ``column_overrides``::

        execute = stage_model(
            name="stage.stg_customer",
            source_model=source,
            column_overrides={
                "customer_id": "VARCHAR",
                "customer_name": "VARCHAR",
            },
        )

    Column order:
    1. Hashed columns (VARCHAR)
    2. Derived columns (VARCHAR)
    3. Missing-column placeholders (VARCHAR)
    4. ldts (TIMESTAMP)
    5. rsrc (VARCHAR)
    6. Anything added via column_overrides

    Args:
        source_model: StageModel describing the raw source table.
        column_overrides: Exact type strings applied last, overriding inferred types
                          and adding any unknown source columns.

    Returns:
        Ordered dict mapping column name → SQL type string.
    """
    ldts_col = _dv_config.ldts_alias
    rsrc_col = _dv_config.rsrc_alias

    columns: Dict[str, str] = {}

    for alias in source_model.hashed_columns or {}:
        columns[alias] = _HASH_TYPE

    for alias in source_model.derived_columns or {}:
        if alias not in columns:
            columns[alias] = _VARCHAR_TYPE

    for col_name in source_model.missing_columns or {}:
        if col_name not in columns:
            columns[col_name] = _VARCHAR_TYPE

    columns[ldts_col] = _TIMESTAMP_TYPE
    columns[rsrc_col] = _VARCHAR_TYPE

    if column_overrides:
        columns.update(column_overrides)

    return columns
