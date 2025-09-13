from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import agent  # type: ignore


def _code_with_markers() -> str:
    return (
        "# --- [PATCHPOINT:NUMERIC_CAST] ---\n"
        "df[col] = df[col].map(normalize_amount).astype('float64')\n"
        "# --- [/PATCHPOINT:NUMERIC_CAST] ---\n"
        "# --- [PATCHPOINT:CLEANUP] ---\n"
        "df = df.reset_index(drop=True)\n"
        "return df\n"
        "# --- [/PATCHPOINT:CLEANUP] ---\n"
    )


def test_refine_applies_numeric_cast_then_cleanup():
    code = _code_with_markers()
    after = agent.refine_parser_code(code, "First diffs (row, col, got, exp):")
    assert "pd.to_numeric" in after

    after2 = agent.refine_parser_code(after, "Row count mismatch")
    assert "dropna(how='all')" in after2
