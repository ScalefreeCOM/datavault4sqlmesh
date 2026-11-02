"""
Align generated identifiers with SQLMesh's identifier normalization.

SQLMesh normalizes the column names a Python model declares (``columns=``)
to the dialect's default case before it creates the table and writes the
INSERT: lowercase on PostgreSQL, DuckDB, Trino, ...; uppercase on Snowflake.
datavault4sqlglot quotes the identifiers it generates (``quote_identifiers``
defaults to true), which pins their case. On a dialect where quoted names are
case-sensitive this breaks the insert, e.g. on PostgreSQL the query outputs
``"HK_REGION_H"`` while SQLMesh selects ``"hk_region_h"`` from it.

The helpers below rewrite identifiers to the dialect's normalized case and
keep their quoting, so both sides agree on every dialect.
"""

from __future__ import annotations

from sqlglot import exp
from sqlglot.dialects.dialect import Dialect


def normalize_name(name: str, dialect: str) -> str:
    """Return *name* the way *dialect* resolves it when it is unquoted."""
    identifier = exp.to_identifier(name, quoted=False)
    return Dialect.get_or_raise(dialect).normalize_identifier(identifier).name


def _normalize_identifier(identifier: exp.Identifier, dialect: str) -> None:
    identifier.set("this", normalize_name(identifier.name, dialect))


def normalize_generated_columns(query: exp.Expression, dialect: str) -> exp.Expression:
    """
    Normalize the column names a stage query defines, in place.

    Every column alias in *query* (hash keys, hash diffs, derived columns,
    ``ldts`` / ``rsrc``, ...) is normalized, as is every column reference to
    one of those names. Source table and source column references are left
    untouched, so quoted mixed-case source objects keep resolving.

    Returns *query* for chaining.
    """
    generated = {alias.alias for alias in query.find_all(exp.Alias) if alias.alias}
    for alias in query.find_all(exp.Alias):
        alias_identifier = alias.args.get("alias")
        if isinstance(alias_identifier, exp.Identifier):
            _normalize_identifier(alias_identifier, dialect)
    for column in query.find_all(exp.Column):
        column_identifier = column.this
        if isinstance(column_identifier, exp.Identifier) and column_identifier.name in generated:
            _normalize_identifier(column_identifier, dialect)
    return query


def normalize_all_identifiers(query: exp.Expression, dialect: str) -> exp.Expression:
    """
    Normalize every identifier in *query*, in place.

    For hub, link and satellite queries, whose inputs and targets are all
    SQLMesh-managed Data Vault tables: their schema, table and column names
    are normalized by SQLMesh as well, so every reference must follow suit.

    Returns *query* for chaining.
    """
    for identifier in query.find_all(exp.Identifier):
        _normalize_identifier(identifier, dialect)
    return query
