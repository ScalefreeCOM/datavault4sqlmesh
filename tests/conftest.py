from __future__ import annotations

import pytest

from datavault4sqlglot.config import config as _dv_config


@pytest.fixture(autouse=True)
def reset_config():
    """
    Save and restore the global DataVaultConfig around every test.

    Because inference.py holds a direct reference to the config singleton,
    replacing the object (cfg_mod.config = DataVaultConfig(...)) would not
    be seen by inference functions.  We therefore save the field values and
    restore them in-place so that mutations made in individual tests are
    always cleaned up.
    """
    # Pydantic v2: model_dump() returns a plain dict of field values
    saved = _dv_config.model_dump()
    yield
    for field, value in saved.items():
        object.__setattr__(_dv_config, field, value)


@pytest.fixture(autouse=True)
def reset_sqlmesh_model_registry():
    """
    Clear the SQLMesh global model registry before and after every test.

    The SQLMesh ``@model`` decorator stores registered models in a module-level
    ``UniqueKeyDict``.  When multiple tests register a model with the same name
    the registry raises ``ValueError: Duplicate Name``.  Clearing it around
    each test keeps tests independent without requiring them to use unique names.

    This fixture is a no-op when SQLMesh is not installed.
    """
    try:
        from sqlmesh.core.model.decorator import model as _sm_model
        _sm_model.registry().clear()
        yield
        _sm_model.registry().clear()
    except ImportError:
        yield


@pytest.fixture
def sqlmesh():
    """
    Skip the test if SQLMesh is not installed.

    Use as a function-scoped fixture on any test that exercises a model factory::

        def test_hub_registers(sqlmesh):
            ...
    """
    sqlmesh_mod = pytest.importorskip("sqlmesh", reason="SQLMesh not installed")
    return sqlmesh_mod
