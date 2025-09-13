#!/usr/bin/env python3
"""
Ensures the agent's *refinement* (self-fix) logic actually patches the parser
and achieves green after a deliberate schema break.

Strategy:
- Generate a valid parser (if missing).
- Corrupt the parser by reversing column order before returning the DataFrame.
- Run the agent with max-iters=2 and expect it to patch/reindex and pass.
"""

import sys
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agent import main  # type: ignore

PARSER_FILE = REPO_ROOT / "custom_parsers" / "icici_parser.py"
DATA_DIR = REPO_ROOT / "data" / "icici"


def _ensure_parser():
    # Run once to generate parser deterministically (quiet path)
    rc = main(["--target", "icici", "--max-iters", "1", "--quiet"])
    assert rc == 0 or PARSER_FILE.exists(), "Failed to create icici_parser.py"


def _corrupt_parser():
    code = PARSER_FILE.read_text(encoding="utf-8")
    # Force a schema mismatch by reversing columns right before reset_index/return.
    if "df = df.reset_index(drop=True)" in code:
        code = code.replace(
            "df = df.reset_index(drop=True)",
            "df = df[df.columns[::-1]]\n    df = df.reset_index(drop=True)",
            1,
        )
    else:
        # Fallback: if structure has changed, just append the reversal before the return.
        code = code.replace(
            "return df",
            "df = df[df.columns[::-1]]\n    return df",
            1,
        )
    PARSER_FILE.write_text(code, encoding="utf-8")


def test_agent_refines_after_schema_break():
    assert DATA_DIR.exists(), "Missing data/icici/"
    _ensure_parser()
    _corrupt_parser()

    # Now the agent should detect mismatch and patch the parser (reindex) to fix it.
    rc = main(["--target", "icici", "--max-iters", "2", "--quiet"])
    assert rc == 0, "Agent refinement failed to recover from schema mismatch"
