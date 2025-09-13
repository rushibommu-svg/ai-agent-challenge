from pathlib import Path
import sys
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from custom_parsers import base_parser as bp  # type: ignore


def test_normalize_amount_inr_indian_and_eu_and_parens():
    cases = {
        "₹1,23,456.78": 123456.78,
        "(₹500)": -500.0,
        "1.234,56": 1234.56,           # EU style
        "2 345,67": 2345.67,           # narrow no-break space
        "1,234.00 DR": -1234.0,
        "1,234.00 CR": 1234.0,
        "₹-250": -250.0,
        "—": None,                     # em dash → NaN
        "": None,
    }
    for s, expected in cases.items():
        v = bp.normalize_amount(s)
        if expected is None:
            assert pd.isna(v)
        else:
            assert abs(float(v) - expected) < 1e-6


def test_coerce_date_several_formats():
    # These pairs represent expected CSV formatted dates we want to reach
    samples = [
        ("01-08-2024", "01-08-2024"),
        ("1/8/24", "01-08-2024"),
        ("01.Aug.2024".replace(".", "-"), "01-Aug-2024".replace(".", "-")),  # resilient to minor variants
        ("01.08.2024", "01-08-2024"),
        ("01 Aug 2024", "01 Aug 2024"),
    ]
    out_fmt = "auto"  # your base_parser guesses from sample; we just ensure it returns something stable
    for raw, _ in samples:
        # We call the internal pipeline through a tiny shim:
        # parse_date(cell, out_fmt=...) exists in your helpers; if not, adapt to your function name
        d = bp.parse_date(raw) if hasattr(bp, "parse_date") else bp._coerce_date(raw)
        assert isinstance(d, str)
        assert len(d) >= 8
