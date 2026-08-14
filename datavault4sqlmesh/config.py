from __future__ import annotations

import os
from typing import Optional

from datavault4sqlglot.config import config, load_config


def load_dv_config(config_path: Optional[str] = None) -> None:
    """
    Load the Data Vault configuration for a SQLMesh project.

    Convenience wrapper around ``datavault4sqlglot.config.load_config`` that
    resolves a sensible default path when none is provided.  When called
    without arguments inside a SQLMesh project, it looks for ``config.json``
    in the current working directory, which SQLMesh sets to the project root.

    Call this once from a shared location (e.g. ``models/__init__.py``) so
    every model file inherits the same settings without repeating the call.

    Args:
        config_path: Absolute or relative path to a ``config.json`` file.
                     When omitted, defaults to ``<cwd>/config.json``.

    Example::

        # models/__init__.py
        from datavault4sqlmesh.config import load_dv_config
        load_dv_config()

        # models/customer_h.py
        from datavault4sqlmesh import hub_model
        ...
    """
    resolved = config_path or os.path.join(os.getcwd(), "config.json")
    load_config(config, resolved)
