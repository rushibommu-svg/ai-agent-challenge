import pandas as pd
from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "icici"
PARSERS = ROOT / "custom_parsers"

def _import(bank: str):
    mod_path = PARSERS / f"{bank}_parser.py"
    if not mod_path.exists():
        raise RuntimeError(f"Parser not found: {mod_path} (run `python agent.py --target {bank}` first)")
    spec = importlib.util.spec_from_file_location(mod_path.stem, mod_path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod

def test_icici_equals():
    pdf = next(iter(DATA.glob("*.pdf")), None)
    assert pdf and pdf.exists(), "ICICI sample PDF missing under data/icici/"
    csv = DATA / "result.csv"
    assert csv.exists(), "result.csv missing under data/icici/"
    exp = pd.read_csv(csv)

    mod = _import("icici")
    got = mod.parse(str(pdf))

    assert list(got.columns) == list(exp.columns), "Column schema mismatch"
    assert got.reset_index(drop=True).equals(exp.reset_index(drop=True)), "Data mismatch vs gold CSV"
