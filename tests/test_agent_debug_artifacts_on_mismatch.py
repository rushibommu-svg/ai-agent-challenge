#!/usr/bin/env python3
"""
Forces parser.parse() to return a wrong value so compare_with_expected() fails.
This exercises diff printing and debug CSV writing in agent.py.
"""
import importlib.util
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import agent  # type: ignore



def test_agent_debug_artifacts_on_mismatch(monkeypatch, tmp_path):
    target = "icici"

    # Point DEBUG_DIR to a temp folder so we can assert outputs safely
    monkeypatch.setattr(agent, "DEBUG_DIR", tmp_path / "debug")
    agent.DEBUG_DIR.mkdir(parents=True, exist_ok=True)

    # Prepare a fake parser that returns a trivially wrong DF (schema mismatch)
    parser_dir = tmp_path / "custom_parsers"
    parser_dir.mkdir(parents=True, exist_ok=True)
    bad = parser_dir / f"{target}_parser.py"
    bad.write_text(
        "import pandas as pd\n"
        "def parse(_):\n"
        "    return pd.DataFrame({'WRONG':[1,2,3]})\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(agent, "PARSERS_DIR", parser_dir)

    # Keep real data so expected CSV/PDF load correctly
    monkeypatch.setattr(agent, "DATA_DIR", ROOT / "data")

    ok, got, exp, diff = agent.compare_with_expected(target, verbose=False)
    assert not ok
    # Debug files should be present
    got_path = agent.DEBUG_DIR / f"{target}_got.csv"
    exp_path = agent.DEBUG_DIR / f"{target}_expected.csv"
    assert got_path.exists() and exp_path.exists()
    # Diff message should mention schema mismatch
    assert "Column schema mismatch" in diff
