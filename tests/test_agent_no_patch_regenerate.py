#!/usr/bin/env python3
"""
Triggers the path where refine_parser_code finds no applicable patch and the agent
falls back to regenerating the parser.
"""
import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import agent  # type: ignore


def test_agent_regenerates_when_no_patch_applicable(tmp_path, monkeypatch):
    target = "icici"

    # Force PARSERS_DIR to temp and write a parser whose code won't match any refine replace hooks
    pdir = tmp_path / "custom_parsers"
    pdir.mkdir(parents=True, exist_ok=True)
    parser_file = pdir / f"{target}_parser.py"
    parser_file.write_text(
        "import pandas as pd\n"
        "def parse(path):\n"
        "    # Return same schema but wrong values so equality fails,\n"
        "    # and also omit any lines that refine_parser_code looks to replace.\n"
        "    return pd.DataFrame({'Date': ['01-01-2025'], 'Description':['X'], 'Debit Amt':[0.0], 'Credit Amt':[0.0], 'Balance':[0.0]})\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(agent, "PARSERS_DIR", pdir)

    # Real data for expected CSV/PDF
    monkeypatch.setattr(agent, "DATA_DIR", ROOT / "data")

    # Make write_parser_file deterministic in temp dir
    def _local_write(_target: str) -> Path:
        # Write a trivial but valid parser so that regeneration can succeed
        code = (
            "import pandas as pd\n"
            "def parse(path):\n"
            "    # minimal pass-through using expected CSV next to the PDF\n"
            "    import pathlib\n"
            "    p = pathlib.Path(path)\n"
            "    csv = p.parent / 'result.csv'\n"
            "    return pd.read_csv(csv)\n"
        )
        out = pdir / f"{_target}_parser.py"
        out.write_text(code, encoding='utf-8')
        return out

    monkeypatch.setattr(agent, "write_parser_file", _local_write)

    # Now run agent: first compare should fail; refine finds no applicable patch; agent regenerates; second compare passes
    rc = agent.run_agent(agent.AgentConfig(target=target, max_iters=2, verbose=False))
    assert rc == 0
