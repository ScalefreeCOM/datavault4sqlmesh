from __future__ import annotations

import inspect
from typing import Callable, Dict

_EXECUTE_REGISTRY: Dict[str, Callable] = {}

# Pre-built signature for all execute closures: (evaluator, **kwargs)
_EXECUTE_SIGNATURE = inspect.signature(lambda evaluator, **kwargs: None)


def _bind_execute_to_caller(fn: Callable, model_name: str) -> None:
    """
    Make a factory-generated execute closure importable so SQLMesh can re-import it.

    SQLMesh validates that every Python model's execute function is importable by
    __module__ + __name__.  Closures defined inside a factory cannot satisfy this
    because they have no module-level name.

    This helper registers the function in this module's own namespace under a
    unique key derived from the model name, then points __module__ and __name__
    here so SQLMesh's import resolves correctly without touching the model file's
    globals (which would collide with SQLMesh's own macro scanner).
    """
    _EXECUTE_REGISTRY[model_name] = fn
    safe_key = "_execute_" + model_name.replace(".", "_")
    fn.__module__ = __name__  # datavault4sqlmesh.models._utils
    fn.__name__ = safe_key
    fn.__qualname__ = safe_key
    # SQLMesh only promotes IMPORT-serialized functions to macros when this
    # attribute is set (same flag used by @macro() decorator).  build_env also
    # reads __wrapped__ immediately after finding the flag (expecting the
    # functools.wraps pattern), so we point it back at fn itself.
    setattr(fn, "__sqlmesh__macro__", True)
    # build_env accesses __wrapped__ to get the object to serialize;
    # pointing back at fn serializes the closure via IMPORT (module is external).
    fn.__wrapped__ = fn
    # inspect.signature calls unwrap(stop=lambda f: hasattr(f, "__signature__")),
    # so setting this prevents the self-referential __wrapped__ from causing a
    # wrapper loop when call_macro introspects the function.
    fn.__signature__ = _EXECUTE_SIGNATURE
    globals()[safe_key] = fn


def parse_model_name(name: str) -> tuple[str, str | None, str | None]:
    """
    Parse a qualified SQLMesh model name into generator-ready components.

    Splits on ``.`` (dot) only — quoted identifiers with embedded dots are
    not supported.  The full ``name`` string is still passed unchanged to the
    SQLMesh ``@model`` decorator; this function is only used to derive the
    target table, schema, and database arguments for the underlying generator.

    Examples::

        parse_model_name("customer_h")          # ("customer_h", None, None)
        parse_model_name("dv.customer_h")        # ("customer_h", "dv", None)
        parse_model_name("mydb.dv.customer_h")   # ("customer_h", "dv", "mydb")

    Args:
        name: Qualified model name with 1–3 dot-separated parts.

    Returns:
        Tuple of ``(table_name, schema_name, database_name)``.

    Raises:
        ValueError: When the name has more than 3 dot-separated parts.
    """
    parts = name.split(".")
    if len(parts) > 3:
        raise ValueError(
            f"Model name '{name}' has {len(parts)} parts; expected at most 3 "
            f"(database.schema.table)."
        )
    if len(parts) == 3:
        return parts[2], parts[1], parts[0]
    if len(parts) == 2:
        return parts[1], parts[0], None
    return parts[0], None, None
