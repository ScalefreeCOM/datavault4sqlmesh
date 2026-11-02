from __future__ import annotations

from typing import Dict, List, Optional, Union

# Import the config singleton directly from its own module so that
# `datavault4sqlglot/__init__.py` shadowing the `config` package attribute
# with a DataVaultConfig instance does not affect us.
# (Using `import datavault4sqlglot.config as X` would hit IMPORT_FROM which
# resolves via `getattr(datavault4sqlglot, 'config')` and returns the
# DataVaultConfig instance, not the module.)
from datavault4sqlglot.config import config as _dv_config
from datavault4sqlglot.metadata import StageModel

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
    business_keys: List[str],
    additional_columns: Optional[List[str]] = None,
    column_overrides: Optional[Dict[str, str]] = None,
) -> Dict[str, str]:
    """
    Infer the SQLMesh ``columns`` schema dict for a Hub model.

    Column order matches the Hub generator output:
    1. Hash key (VARCHAR)
    2. Business keys, de-duplicated in declaration order (VARCHAR)
    3. Additional columns (VARCHAR)
    4. ldts (TIMESTAMP)
    5. rsrc (VARCHAR)

    Args:
        hashkey: Target hash key column name in the Hub table.
        business_keys: Business key column names.
        additional_columns: Extra columns appended after business keys.
        column_overrides: Exact type strings applied last, overriding inferred types.

    Returns:
        Ordered dict mapping column name → SQL type string.

    Raises:
        ValueError: When ``business_keys`` is empty.
    """
    if not business_keys:
        raise ValueError("infer_hub_columns requires at least one business key.")

    ldts_col = _dv_config.ldts_alias
    rsrc_col = _dv_config.rsrc_alias

    columns: Dict[str, str] = {}
    columns[hashkey] = _HASH_TYPE

    seen: set[str] = {hashkey}
    for bk in business_keys:
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
    foreign_hash_keys: List[str],
    additional_columns: Optional[List[str]] = None,
    column_overrides: Optional[Dict[str, str]] = None,
) -> Dict[str, str]:
    """
    Infer the SQLMesh ``columns`` schema dict for a Link model.

    Column order matches the Link generator output:
    1. Link hash key (VARCHAR)
    2. Foreign hash keys, de-duplicated in declaration order (VARCHAR)
    3. Additional columns (VARCHAR)
    4. ldts (TIMESTAMP)
    5. rsrc (VARCHAR)

    Args:
        link_hash_key: Target link hash key column name.
        foreign_hash_keys: All foreign hash key column names.
        additional_columns: Extra columns appended after foreign hash keys.
        column_overrides: Exact type strings applied last, overriding inferred types.

    Returns:
        Ordered dict mapping column name → SQL type string.

    Raises:
        ValueError: When fewer than 2 ``foreign_hash_keys`` are supplied.
    """
    if len(foreign_hash_keys) < 2:
        raise ValueError(
            f"infer_link_columns requires at least 2 foreign_hash_keys, "
            f"got {len(foreign_hash_keys)}."
        )

    ldts_col = _dv_config.ldts_alias
    rsrc_col = _dv_config.rsrc_alias

    columns: Dict[str, str] = {}
    columns[link_hash_key] = _HASH_TYPE

    seen: set[str] = {link_hash_key}
    for fhk in foreign_hash_keys:
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

    Derives the full stage output schema from the ``StageModel`` metadata without
    requiring a live database connection:

    - **Hash alias columns** — the output column names for every hashkey and hashdiff
      (e.g. ``hk_customer_h``, ``hd_customer_s``).
    - **Hash source columns** — the source columns consumed by each hashkey list and
      each hashdiff ``columns`` list (e.g. business keys, payload columns). These are
      the columns that hub and satellite models read from the stage; they are inferred
      directly from ``hashed_columns`` so ``column_overrides`` is no longer required
      just to make downstream DV models resolve.
    - **Derived columns** — targets of any rename or expression in ``derived_columns``.
    - **Missing-column placeholders** — entries in ``missing_columns``.
    - ``ldts`` (TIMESTAMP) and ``rsrc`` (VARCHAR) from the global DV config.

    ``column_overrides`` is still accepted and applied last, so callers can refine the
    inferred VARCHAR default to a more precise type (e.g. ``"amount": "DECIMAL(18,2)"``).

    Column order:
    1. Hashed column aliases (VARCHAR)
    2. Hash source columns — business keys and hashdiff payload columns (VARCHAR)
    3. Derived columns (VARCHAR)
    4. Missing-column placeholders (VARCHAR)
    5. ldts (TIMESTAMP)
    6. rsrc (VARCHAR)
    7. column_overrides (applied last — overrides any inferred type above)

    Args:
        source_model: StageModel describing the raw source table.
        column_overrides: Exact type strings applied last, overriding inferred types.

    Returns:
        Ordered dict mapping column name → SQL type string.
    """
    ldts_col = _dv_config.ldts_alias
    rsrc_col = _dv_config.rsrc_alias

    columns: Dict[str, str] = {}

    # 1. Hash aliases (hk_*, hd_*) — the computed output columns.
    for alias in source_model.hashed_columns or {}:
        columns[alias] = _HASH_TYPE

    # 2. Hash source columns — the raw columns consumed by each hash definition.
    #    Hashkey value is a list of source column names; hashdiff value is a dict
    #    with an "is_hashdiff" flag and a "columns" list. Both are added as VARCHAR
    #    so downstream hub/satellite models can resolve them without column_overrides.
    for definition in (source_model.hashed_columns or {}).values():
        if isinstance(definition, list):
            for src_col in definition:
                if src_col not in columns:
                    columns[src_col] = _VARCHAR_TYPE
        elif isinstance(definition, dict) and definition.get("is_hashdiff"):
            for src_col in definition.get("columns") or []:
                if src_col not in columns:
                    columns[src_col] = _VARCHAR_TYPE

    # 3. Derived columns (renames / expressions).
    for alias in source_model.derived_columns or {}:
        if alias not in columns:
            columns[alias] = _VARCHAR_TYPE

    # 4. Missing-column placeholders (schema evolution).
    for col_name in source_model.missing_columns or {}:
        if col_name not in columns:
            columns[col_name] = _VARCHAR_TYPE

    columns[ldts_col] = _TIMESTAMP_TYPE
    columns[rsrc_col] = _VARCHAR_TYPE

    if column_overrides:
        columns.update(column_overrides)

    return columns
