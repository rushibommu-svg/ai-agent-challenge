
from __future__ import annotations
from pathlib import Path
from typing import List, Optional, Dict
import re
import unicodedata 
import numpy as np
import pandas as pd
import pdfplumber
from pypdf import PdfReader

# Date regex patterns for filtering transaction rows
DATE_PATTERNS = [
    r"^\d{1,2}[/-]\d{1,2}[/-]\d{2,4}$",   # 01-08-2024, 1/8/24
    r"^\d{1,2}-[A-Za-z]{3}-\d{2,4}$",     # 01-Aug-2024
    r"^\d{1,2}\.\d{1,2}\.\d{2,4}$",       # 01.08.2024
]

def maybe_date(tok: str) -> bool:
    return any(re.match(p, tok) for p in DATE_PATTERNS)

# Parse amounts and clean up descriptions
def normalize_amount(x: str) -> Optional[float]:
    """
    Convert currency-like strings to float.

    Handles:
      - Indian/US: 1,23,456.78 / 1,234.56 / 1234.56
      - EU: 1.234,56 or 2 345,67
      - Currency symbols: ₹, $, £, €, apostrophes
      - DR/CR suffixes (CASE-SENSITIVE):
            'DR' → negative
            'CR' → positive
            lowercase 'dr'/'cr' → neutral
      - Parentheses negatives: (123.45) → -123.45
      - Unicode spaces/minus signs
      - Returns None for blanks/dashes/unparseable
    """
    if x is None:
        return None

    s = unicodedata.normalize("NFKC", str(x)).strip()
    if not s or s.lower() == "nan" or s in {"—", "–", "-"}:
        return None

    # Detect DR/CR with case sensitivity
    has_dr = bool(re.search(r"(?:^|[^A-Za-z])DR(?:[^A-Za-z]|$)", s))
    has_cr = bool(re.search(r"(?:^|[^A-Za-z])CR(?:[^A-Za-z]|$)", s))

    # Normalize minus and whitespace, drop all spaces
    s = (s.replace("\u2212", "-")  # unicode minus
           .replace("\u00A0", "")  # NBSP
           .replace("\u202F", "")  # narrow NBSP
           .replace("\u2009", "")  # thin space
           .replace(" ", ""))

    # Strip currency symbols & apostrophes
    for sym in ("₹", "$", "£", "€", "'"):
        s = s.replace(sym, "")

    # Remove CR/DR tokens regardless of case (clean string for parsing)
    s = re.sub(r"(?:^|[^A-Za-z])(CR|DR)(?=[^A-Za-z]|$)", "", s, flags=re.IGNORECASE).strip()

    # Parentheses negative
    neg = False
    if s.startswith("(") and s.endswith(")"):
        neg = True
        s = s[1:-1].strip()

    if not s:
        return None

    # EU vs US/Indian format handling
    try:
        if "," in s and "." in s:
            last_comma, last_dot = s.rfind(","), s.rfind(".")
            if last_comma > last_dot:  # EU: ',' decimal, '.' thousands
                s = s.replace(".", "").replace(",", ".")
            else:  # US/IN: ',' thousands, '.' decimal
                s = s.replace(",", "")
        elif "," in s:
            if re.search(r",\d{2}$", s):  # comma as decimal
                s = s.replace(",", ".")
            else:  # comma as thousands
                s = s.replace(",", "")
        # else: plain digits or dot decimal
        v = float(s)
    except ValueError:
        return None

    # Apply DR/CR semantics (only uppercase)
    if has_dr:
        neg = True

    return -v if neg else v


def parse_date(x: str) -> Optional[str]:
    """
    Best-effort normalization for common bank statement date formats.
    Returns a stable 'DD-MM-YYYY' string when possible, else None.
    """
    if x is None:
        return None
    s = unicodedata.normalize("NFKC", str(x)).strip()
    if not s:
        return None

    # Try a small set of formats commonly seen in statements.
    from datetime import datetime
    fmts = [
        "%d-%m-%Y", "%d-%m-%y",
        "%d/%m/%Y", "%d/%m/%y",
        "%d.%m.%Y", "%d.%m.%y",
        "%d-%b-%Y", "%d-%b-%y",
        "%d %b %Y",
    ]
    for fmt in fmts:
        try:
            dt = datetime.strptime(s, fmt)
            return dt.strftime("%d-%m-%Y")
        except ValueError:
            continue
    # Last resort: compact number-like dates (e.g., 01082024 -> 01-08-2024)
    if re.fullmatch(r"\d{8}", s):
        try:
            dt = datetime.strptime(s, "%d%m%Y")
            return dt.strftime("%d-%m-%Y")
        except ValueError:
            pass
    return None


def clean_desc(s: str) -> str:
    if s is None:
        return ""
    t = str(s)
    # Remove trailing CR/DR
    t = re.sub(r"\s*(CR|DR)\s*$", "", t, flags=re.IGNORECASE)
    # Remove trailing numbers that got mixed in
    t = re.sub(r"\s*(?:[\(\-\u2212]?\d[\d,\u00A0\u202F\u2009']*\.?\d*\)?\s*)+$", "", t)
    return t.strip()

# Try to match the date format from the expected CSV
_DATE_INPUT_FORMATS = [
    "%d-%m-%Y", "%d/%m/%Y", "%d.%m.%Y",
    "%d-%m-%y", "%d/%m/%y", "%d.%m.%y",
    "%d-%b-%Y", "%d-%b-%y",
    "%Y-%m-%d",
    "%d %b %Y",
    "%d %B %Y",
]

def _guess_outfmt_from_sample(sample: str) -> str:
    s = sample.strip()
    sep = "-" if "-" in s else ("/" if "/" in s else ".")
    # If there are letters, probably has month name
    if any(c.isalpha() for c in s):
        return f"%d{sep}%b{sep}%y" if re.search(r"\D\d{2}$", s) else f"%d{sep}%b{sep}%Y"
    # All numbers
    return f"%d{sep}%m{sep}%y" if re.search(r"\D\d{2}$", s) else f"%d{sep}%m{sep}%Y"

def coerce_to_expected_date_format(series: pd.Series, exp_series: pd.Series) -> pd.Series:
    exp_sample = next((str(x) for x in exp_series.dropna().head(10).tolist() if str(x).strip()), None)
    if not exp_sample:
        return series

    outfmt = _guess_outfmt_from_sample(exp_sample)

    def _parse_one(x: str):
        s = str(x).strip()
        for fmt in _DATE_INPUT_FORMATS:
            try:
                return pd.to_datetime(s, format=fmt)
            except Exception:
                continue
        # Last try with flexible parsing
        return pd.to_datetime(s, dayfirst=True, errors="coerce")

    dt = series.astype(str).map(_parse_one)
    return dt.dt.strftime(outfmt)

# Column name matching - banks use different names for the same thing
_HEADER_SYNONYMS: Dict[str, List[str]] = {
    "date": ["date","txn date","transaction date","value date","posting date"],
    "description": ["description","narration","details","particulars","remarks","narr"],
    "debit": ["debit","debit amt","withdrawal","withdrawal amount","dr","amount debit","paid"],
    "credit": ["credit","credit amt","deposit","deposit amount","cr","amount credit","received"],
    "balance": ["balance","closing balance","available balance","avail bal","bal","ledger bal"],
}

def _norm(s: str) -> str:
    return re.sub(r"[^a-z]", "", str(s).lower())

def best_source_for_expected(expected_name: str, source_headers: List[str]) -> Optional[str]:
    exp_norm = _norm(expected_name)
    syns: List[str] = []
    for canon, names in _HEADER_SYNONYMS.items():
        if canon in exp_norm:
            syns.extend(names)
    syns = list(dict.fromkeys(syns))
    src_norms = {h: _norm(h) for h in source_headers}
    if syns:
        for syn in syns:
            sn = _norm(syn)
            for h, hn in src_norms.items():
                if sn and (sn == hn or sn in hn or hn in sn):
                    return h
    for h, hn in src_norms.items():
        if exp_norm and (exp_norm == hn or exp_norm in hn or hn in exp_norm):
            return h
    return None

# PDF extraction methods
def extract_tables_pdfplumber(pdf_path: Path):
    tables = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            try:
                tbl = page.extract_table()
                if tbl and len(tbl) > 1:
                    df = pd.DataFrame(tbl[1:], columns=tbl[0])
                    tables.append(df)
            except Exception:
                continue
    return tables

import unicodedata  # make sure this is at the top of the file

def extract_lines_pdf(pdf_path: Path) -> list[str]:
    """
    Get text lines from PDF - try pdfplumber first, fall back to pypdf if needed.
    Clean up unicode weirdness and rejoin wrapped lines.
    """
    raw: list[str] = []

    try:
        import pdfplumber
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                raw.extend(text.splitlines())
    except Exception:
        from pypdf import PdfReader
        reader = PdfReader(str(pdf_path))
        for page in reader.pages:
            text = page.extract_text() or ""
            raw.extend(text.splitlines())

    # Fix unicode normalization issues
    raw = [unicodedata.normalize("NFKC", ln) for ln in raw]

    # Join lines that don't start with dates (probably wrapped text)
    stitched: list[str] = []
    for ln in raw:
        parts = ln.split()
        if parts and maybe_date(parts[0]):
            stitched.append(ln)
        elif stitched:
            stitched[-1] = stitched[-1] + " " + ln
    return stitched

# Convert extracted data to DataFrames
def build_df_from_tables(tables, expected_columns: List[str]):
    if not tables:
        return None
    outs = []

    def norm(h): return re.sub(r"[^a-z]", "", str(h).lower())
    target_norms = [norm(c) for c in expected_columns]

    for t in tables:
        headers = [str(c) for c in t.columns]
        header_norms = [norm(h) for h in headers]
        score = sum(1 for n in target_norms if any(n in h for h in header_norms))
        if score < max(2, len(target_norms)//2):
            continue

        mapping = {}
        for ec in expected_columns:
            try:
                src = best_source_for_expected(ec, headers)
            except Exception:
                ec_n = norm(ec); src = None
                for h in headers:
                    if ec_n and ec_n in norm(h):
                        src = h; break
            mapping[ec] = src

        if sum(1 for v in mapping.values() if v) < 2:
            continue

        df = t.copy()
        for ec, src in mapping.items():
            if not src:
                continue
            el = ec.lower()
            if any(k in el for k in ("debit","credit","amount","balance")):
                df[src] = df[src].map(normalize_amount)
            elif any(k in el for k in ("desc","narrat","details","particular")):
                df[src] = df[src].astype(str).map(clean_desc)

        out = pd.DataFrame()
        for ec in expected_columns:
            src = mapping.get(ec)
            out[ec] = df[src] if (src in df.columns) else np.nan
        if not out.empty:
            outs.append(out)

    if not outs:
        return None
    return pd.concat(outs, ignore_index=True)

def build_df_from_lines(lines: List[str], expected_columns: List[str]) -> pd.DataFrame:
    CREDIT_KEYS = ("salary credit","interest credit","cheque deposit","cash deposit","neft transfer from","neft from","deposit","credited")
    DEBIT_KEYS  = ("imps","upi","qr payment","fuel","dining","restaurant","emi","utility bill","service charge","electricity bill","online card purchase","card swipe","atm cash withdrawal","credit card payment","mobile recharge","insurance premium")
    rows = []
    prev_balance = None
    for ln in lines:
        toks = ln.split()
        if not toks or not maybe_date(toks[0]):
            continue
        date = toks[0]
        tail = " ".join(toks[1:])
        tail_lower = tail.lower()
        nums = re.findall(r"[\(\-\u2212]?\d[\d,\u00A0\u202F\u2009']*\.?\d*\)?", tail)
        desc = tail
        debit = credit = balance = None
        if nums:
            balance = normalize_amount(nums[-1])
            amt = normalize_amount(nums[-2]) if len(nums) >= 2 else None
            is_cr = (" cr" in tail_lower) or tail_lower.endswith("cr")
            is_dr = (" dr" in tail_lower) or tail_lower.endswith("dr")
            has_credit_kw = any(k in tail_lower for k in CREDIT_KEYS)
            has_debit_kw  = any(k in tail_lower for k in DEBIT_KEYS)
            decided = False
            if amt is not None:
                if is_cr and not is_dr:
                    credit = amt; decided = True
                elif is_dr and not is_cr:
                    debit  = amt; decided = True
                elif has_credit_kw and not has_debit_kw:
                    credit = amt; decided = True
                elif has_debit_kw and not has_credit_kw:
                    debit  = amt; decided = True
                elif prev_balance is not None and balance is not None:
                    if balance > prev_balance:
                        credit = amt; decided = True
                    elif balance < prev_balance:
                        debit  = amt; decided = True
                if not decided:
                    credit = amt
        desc_clean = clean_desc(desc)
        row = {ec: pd.NA for ec in expected_columns}
        for ec in expected_columns:
            l = ec.lower()
            if "date" in l:
                row[ec] = date
            elif "debit" in l:
                row[ec] = debit
            elif "credit" in l:
                row[ec] = credit
            elif "balance" in l:
                row[ec] = balance
            elif any(k in l for k in ("desc","narrat","details","particular")):
                row[ec] = desc_clean
        rows.append(row)
        prev_balance = balance if balance is not None else prev_balance
    return pd.DataFrame(rows, columns=expected_columns)