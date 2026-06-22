"""
conftest.py — Pytest fixtures shared across the test suite.

No FEFLOW / IFM execution occurs here.  All tests are pure-Python
and work without a FEFLOW installation.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Make scripts/ importable without installing the package.
SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


@pytest.fixture(scope="session")
def cfg():
    """Load a real GeothermalConfig from the workbook (session-scoped)."""
    from config import load_config
    return load_config()
