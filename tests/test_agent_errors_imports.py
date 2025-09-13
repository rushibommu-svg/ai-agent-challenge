#!/usr/bin/env python3
from pathlib import Path
import sys
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import agent  # type: ignore


def test_dynamic_import_failure(tmp_path):
    """
    _dynamic_import may fail in different ways depending on platform/loader:
    - FileNotFoundError if the path doesn't exist
    - SyntaxError if the file exists but has invalid code
    - ImportError if spec/loader is bad
    Make the test robust to all of these.
    """
    bad = tmp_path / "nope.py"
    # Optionally: uncomment next line to force a SyntaxError path instead
    # bad.write_text("this is not python", encoding="utf-8")

    with pytest.raises((ImportError, FileNotFoundError, SyntaxError)):
        agent._dynamic_import(bad, "custom_parsers.nope")


def test_compare_with_expected_no_parse(tmp_path, monkeypatch):
    target = "icici"

    # Point PARSERS_DIR to a temp and write a parser without parse()
    monkeypatch.setattr(agent, "PARSERS_DIR", tmp_path / "custom_parsers")
    agent.PARSERS_DIR.mkdir(parents=True, exist_ok=True)
    (agent.PARSERS_DIR / f"{target}_parser.py").write_text("X=1\n", encoding="utf-8")

    # Keep real data so CSV/PDF load works
    monkeypatch.setattr(agent, "DATA_DIR", ROOT / "data")

    with pytest.raises(AttributeError):
        agent.compare_with_expected(target, verbose=False)
