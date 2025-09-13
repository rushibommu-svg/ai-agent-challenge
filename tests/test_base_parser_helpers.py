#!/usr/bin/env python3
"""
Unit tests that target helper paths in custom_parsers/base_parser.py
to improve coverage without touching real PDFs.
"""

from pathlib import Path
import pandas as pd
import numpy as np

from custom_parsers import base_parser as bp


def test_normalize_amount_various_forms():
    # plain number
    assert bp.normalize_amount("1,234.56") == 1234.56
    # negative with parentheses
    assert bp.normalize_amount("(987.65)") == -987.65
    # EU style
    assert bp.normalize_amount("1.234,56") == 1234.56
    # currency/CR/DR stripped
    assert bp.normalize_amount("₹ 2,500.00 CR") == 2500.0
    assert bp.normalize_amount(" $3,000.00 dr ") == 3000.0
    # blanks/None
    assert bp.normalize_amount("") is None
    assert bp.normalize_amount(None) is None


def test_clean_desc_strips_cr_dr_and_trailing_numbers():
    s = "UPI QR Grocery 1234.00 CR"
    assert bp.clean_desc(s) == "UPI QR Grocery"
    s2 = "Some Text 1,234.56 789.00"
    assert bp.clean_desc(s2) == "Some Text"


def test_guess_outfmt_from_sample_alpha_and_numeric():
    # alpha month
    fmt1 = bp._guess_outfmt_from_sample("01-Aug-2024")
    assert "%d" in fmt1 and "%b" in fmt1 and "%Y" in fmt1
    # numeric
    fmt2 = bp._guess_outfmt_from_sample("01/08/24")
    assert "%d" in fmt2 and "%m" in fmt2 and ("%y" in fmt2 or "%Y" in fmt2)


def test_coerce_to_expected_date_format_matches_sample_display():
    ser = pd.Series(["1/8/24", "02/08/2024", "03-08-2024"])
    exp = pd.Series(["01-08-2024", "02-08-2024", "03-08-2024"])
    out = bp.coerce_to_expected_date_format(ser, exp)
    assert list(out) == ["01-08-2024", "02-08-2024", "03-08-2024"]


def test_best_source_for_expected_synonyms_and_fallback():
    headers = ["Transaction Date", "Narration", "Withdrawal Amount", "Deposit Amount", "Closing Balance"]
    # exact/synonym matches
    assert bp.best_source_for_expected("Date", headers) in ("Transaction Date", "Date")
    assert bp.best_source_for_expected("Description", headers) in ("Narration", "Description")
    assert bp.best_source_for_expected("Debit", headers) in ("Withdrawal Amount", "Debit")
    assert bp.best_source_for_expected("Credit", headers) in ("Deposit Amount", "Credit")
    assert bp.best_source_for_expected("Balance", headers) in ("Closing Balance", "Balance")
    # fallback (no match)
    assert bp.best_source_for_expected("FooBar", headers) is None


def test_build_df_from_lines_infers_credit_debit_and_balance():
    # Two synthetic lines (mimic stitched line-mode)
    lines = [
        "01-08-2024 Salary Credit XYZ Pvt Ltd 1935.30 6864.58",  # credit then balance
        "03-08-2024 IMPS UPI Payment Amazon 3886.08 4631.11",   # debit then balance
    ]
    expected_columns = ["Date", "Description", "Debit Amt", "Credit Amt", "Balance"]
    df = bp.build_df_from_lines(lines, expected_columns)

    assert list(df.columns) == expected_columns
    assert len(df) == 2

    # Row 1 (credit)
    r0 = df.iloc[0]
    assert r0["Date"] == "01-08-2024"
    assert "Salary Credit" in r0["Description"]
    assert pd.isna(r0["Debit Amt"]) or r0["Debit Amt"] in (None, np.nan)
    assert float(r0["Credit Amt"]) == 1935.30
    assert float(r0["Balance"]) == 6864.58

    # Row 2 (debit)
    r1 = df.iloc[1]
    assert r1["Date"] == "03-08-2024"
    assert "IMPS UPI" in r1["Description"]
    assert float(r1["Debit Amt"]) == 3886.08
    assert pd.isna(r1["Credit Amt"]) or r1["Credit Amt"] in (None, np.nan)
    assert float(r1["Balance"]) == 4631.11


def test_build_df_from_tables_header_mapping_and_cast():
    # simulate a table extracted by pdfplumber
    t = pd.DataFrame(
        [
            ["01-08-2024", "Salary Credit XYZ Pvt Ltd", "1935.30", "6864.58"],
            ["03-08-2024", "IMPS UPI Payment Amazon", "3886.08", "4631.11"],
        ],
        columns=["Txn Date", "Narration", "Credit Amt", "Balance"]
    )
    expected_columns = ["Date", "Description", "Debit Amt", "Credit Amt", "Balance"]
    out = bp.build_df_from_tables([t], expected_columns)

    assert list(out.columns) == expected_columns
    assert len(out) == 2
    # Casting check: ensure numeric columns are floats or NaNs
    assert out["Credit Amt"].dtype.kind in ("f", "O")
    assert out["Balance"].dtype.kind in ("f", "O")
