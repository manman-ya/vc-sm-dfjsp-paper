from __future__ import annotations

import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from smdfjsp.data.mvc_io import load_mvc_instance_json


@pytest.fixture
def mvc_instance():
    return load_mvc_instance_json(
        ROOT
        / "data"
        / "mvc_mk01_15_2vc4sru_equalproc_vcpenalty"
        / "mk05_mvc_2vc_2type_4sru_equalproc_vcpenalty.json"
    )
