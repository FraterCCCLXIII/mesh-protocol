"""
Pytest configuration for app/server tests.

Account-flow tests expect to be run with this directory on sys.path, e.g.:

    cd app/server && python -m pytest test_account_flows.py -v
"""

import importlib
import os
import sys
from pathlib import Path

import pytest

# Ensure sibling modules (main, mesh_views, discovery) resolve
_SERVER_DIR = Path(__file__).resolve().parent
if str(_SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(_SERVER_DIR))


@pytest.fixture
def mesh_test_env(tmp_path, monkeypatch):
    """
    Isolated DB file + reload main so globals (DB_PATH, app) use it.
    Yields (main_module, db_path: Path).
    """
    db = tmp_path / "mesh_test.db"
    monkeypatch.setenv("MESH_DB_PATH", str(db))
    monkeypatch.setenv("MESH_NODE_ID", f"pytest_{os.getpid()}")
    # Avoid colliding with a dev node URL if any code reads it
    monkeypatch.setenv("MESH_NODE_URL", "http://127.0.0.1:9")

    import main

    importlib.reload(main)
    return main, db
