"""
test_utils.py — Tests for pure-Python helpers in utils.py (no FEFLOW required).
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from utils import (
    node_to_slice,
    node_to_local,
    elem_to_layer,
    local_to_global,
)


# ---------------------------------------------------------------------------
# node_to_slice / node_to_local
# ---------------------------------------------------------------------------

NPS = 4706   # realistic value from Group 3 mesh

@pytest.mark.parametrize("node, expected_slice", [
    (0,          1),
    (NPS - 1,    1),
    (NPS,        2),
    (2 * NPS,    3),
    (5 * NPS,    6),
    (6 * NPS - 1, 6),
])
def test_node_to_slice(node, expected_slice):
    assert node_to_slice(node, NPS) == expected_slice


@pytest.mark.parametrize("node, expected_local", [
    (0,       0),
    (NPS - 1, NPS - 1),
    (NPS,     0),
    (NPS + 7, 7),
])
def test_node_to_local(node, expected_local):
    assert node_to_local(node, NPS) == expected_local


def test_node_slice_local_roundtrip():
    for node in [0, 1000, NPS, NPS + 100, 5 * NPS + 50]:
        s = node_to_slice(node, NPS)
        l = node_to_local(node, NPS)
        recovered = local_to_global(l, s, NPS)
        assert recovered == node, (
            f"Roundtrip failed for node {node}: got {recovered}"
        )


# ---------------------------------------------------------------------------
# elem_to_layer
# ---------------------------------------------------------------------------

EPL = 9406   # realistic value from Group 3 mesh

@pytest.mark.parametrize("elem, expected_layer", [
    (0,          1),
    (EPL - 1,    1),
    (EPL,        2),
    (4 * EPL,    5),
    (5 * EPL - 1, 5),
])
def test_elem_to_layer(elem, expected_layer):
    assert elem_to_layer(elem, EPL) == expected_layer


# ---------------------------------------------------------------------------
# local_to_global
# ---------------------------------------------------------------------------

def test_local_to_global_slice1():
    assert local_to_global(0, 1, NPS) == 0
    assert local_to_global(10, 1, NPS) == 10


def test_local_to_global_slice2():
    assert local_to_global(0, 2, NPS) == NPS
    assert local_to_global(5, 2, NPS) == NPS + 5


def test_local_to_global_slice6():
    assert local_to_global(0, 6, NPS) == 5 * NPS
    assert local_to_global(100, 6, NPS) == 5 * NPS + 100
