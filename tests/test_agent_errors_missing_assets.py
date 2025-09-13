#!/usr/bin/env python3
from pathlib import Path
import sys
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import agent  # type: ignore

def test_load_expected_csv_missing(tmp_path, monkeypatch):
    # Point data/<target> to an empty temp dir to trigger FileNotFoundError
    fake_data = tmp_path / "data" / "ghost"
    fake_data.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(agent, "DATA_DIR", tmp_path / "data")
    with pytest.raises(FileNotFoundError):
        agent.load_expected_csv("ghost")

def test_locate_pdf_missing(tmp_path, monkeypatch):
    fake_data = tmp_path / "data" / "ghost"
    fake_data.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(agent, "DATA_DIR", tmp_path / "data")
    with pytest.raises(FileNotFoundError):
        agent.locate_pdf("ghost")
