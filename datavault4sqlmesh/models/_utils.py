from __future__ import annotations

from typing import Callable, Dict

_EXECUTE_REGISTRY: Dict[str, Callable] = {}


def _bind_execute_to_caller(fn: Callable, model_name: str) -> None:
    """
    Make a factory-generated execute closure importable so SQLMesh can re-import it.

    SQLMesh validates that every Python model's execute function is importable by
    __module__ + __name__.  Closures defined inside a factory cannot satisfy this
    because they have no module-level name.

    This helper creates a thin shim defined inside this module, registers it in
    this module's globals, and wires it so that:

    - ``build_env`` follows ``fn.__wrapped__`` → shim, sees its file is not
      project-relative, and emits an IMPORT executable
      (``from datavault4sqlmesh.models._utils import <safe_key>``).
    - ``MacroEvaluator`` imports the shim, sees ``__sqlmesh__macro__``, and
      registers it as a callable macro.
    - ``call_macro`` calls the shim, which delegates to ``fn``.

    The shim deliberately has **no** ``__wrapped__`` attribute.  Python 3.13's
    ``typing.get_type_hints`` follows ``__wrapped__`` chains without cycle
    detection; a self-referential ``fn.__wrapped__ = fn`` (previous approach)
    caused an infinite loop inside ``call_macro``.
    """
    _EXECUTE_REGISTRY[model_name] = fn
    safe_key = "_execute_" + model_name.replace(".", "_")

    # fn.__module__ / __name__ must match this module so build_env serializes the
    # function as an IMPORT from here (not as an inline DEFINITION from the factory).
    fn.__module__ = __name__
    fn.__name__ = safe_key
    fn.__qualname__ = safe_key

    # The shim is defined here (in _utils.py) so inspect.getfile returns a
    # non-project path, and it captures fn by closure to delegate the call.
    def _shim(evaluator, **kwargs):  # noqa: ANN001
        return fn(evaluator, **kwargs)

    _shim.__module__ = __name__
    _shim.__name__ = safe_key
    _shim.__qualname__ = safe_key
    # __sqlmesh__macro__ causes MacroEvaluator to register the IMPORT-serialized
    # function as a callable macro (otherwise IMPORT functions are skipped).
    setattr(_shim, "__sqlmesh__macro__", True)

    # build_env does `obj = obj.__wrapped__` when it sees __sqlmesh__macro__;
    # point it at the shim so serialize_env picks up the right name/module.
    fn.__wrapped__ = _shim

    globals()[safe_key] = _shim


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
