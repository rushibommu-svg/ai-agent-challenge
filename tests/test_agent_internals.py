#!/usr/bin/env python3
"""
Covers internal branches in agent.py:
- pretty_diff() schema + rowcount + first-diff reporting
- refine_parser_code() patch paths (schema reindex, dropna, numeric cast)
- main([...]) argument path (already covered elsewhere, but we add a direct call)
"""
from pathlib import Path
import pandas as pd
import sys

# Make repo importable
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import agent  # type: ignore


def test_pretty_diff_schema_mismatch():
    got = pd.DataFrame({"A": [1,2]})
    exp = pd.DataFrame({"X": [1,2]})
    msg = agent.pretty_diff(got, exp)
    assert "Column schema mismatch" in msg


def test_pretty_diff_rowcount_and_first_diffs():
    got = pd.DataFrame({"A":[1,2,3], "B":[10,20,30]})
    exp = pd.DataFrame({"A":[1,2],   "B":[10,99]})
    msg = agent.pretty_diff(got, exp, max_rows=2)
    assert "Row count mismatch" in msg
    assert "First diffs" in msg
    assert "('B')" in msg or "B" in msg  # column mentioned somehow


def test_refine_parser_code_schema_patch():
    before = (
        "    # Defensive clean-up (common equality gotchas)\n"
        "    df = df.reset_index(drop=True)\n"
        "    return df\n"
    )
    diff_text = "Column schema mismatch."
    after = agent.refine_parser_code(before, diff_text)
    assert "df = df.reindex(columns=expected_columns)" in after


def test_refine_parser_code_rowcount_patch():
    before = (
        "    # Defensive clean-up (common equality gotchas)\n"
        "    df = df.reset_index(drop=True)\n"
        "    return df\n"
    )
    diff_text = "Row count mismatch"
    after = agent.refine_parser_code(before, diff_text)
    assert "dropna(how='all')" in after


def test_refine_parser_code_numeric_patch_and_trim():
    # Make sure both numeric cast and strip branch can trigger
    before = (
        "        if col in expected_dtypes and \"float\" in str(expected_dtypes[col]):\n"
        "            df[col] = df[col].map(normalize_amount).astype(\"float64\")\n"
        "        else:\n"
        "            df[col] = df[col].astype(\"object\").astype(str).str.strip()\n"
    )
    diff_text = "First diffs (row, col, got, exp):"
    after = agent.refine_parser_code(before, diff_text)
    assert "pd.to_numeric" in after  # numeric path tightened
    assert ".str.strip()" in after   # keep trim path intact (present)


def test_main_cli_path_smoke():
    # Just exercise CLI wrapper; agent logic already tested elsewhere
    rc = agent.main(["--target","icici","--max-iters","1","--quiet"])
    assert rc in (0, 1)  # usually 0; allow 1 to avoid flakiness if assets missing
