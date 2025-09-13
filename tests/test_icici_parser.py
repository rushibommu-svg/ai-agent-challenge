import importlib
import importlib.util
import subprocess
import sys
from pathlib import Path
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
PARSER_DIR = REPO_ROOT / "custom_parsers"
PARSER_FILE = PARSER_DIR / "icici_parser.py"
INIT_FILE = PARSER_DIR / "__init__.py"
PDF_PATH = REPO_ROOT / "data" / "icici" / "icici sample.pdf"
CSV_PATH = REPO_ROOT / "data" / "icici" / "result.csv"

# Ensure repo root is importable (so "custom_parsers" package can be found)
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _ensure_assets():
    assert PDF_PATH.exists(), "ICICI sample PDF missing under data/icici/"
    assert CSV_PATH.exists(), "result.csv missing under data/icici/"


def _ensure_parser_generated():
    """
    Generate the parser if it doesn't exist (clean checkout / CI).
    Also ensure custom_parsers is a package.
    """
    INIT_FILE.parent.mkdir(parents=True, exist_ok=True)
    INIT_FILE.touch(exist_ok=True)

    if PARSER_FILE.exists():
        return

    # Run the agent once to generate the parser deterministically (offline path)
    cmd = [sys.executable, str(REPO_ROOT / "agent.py"), "--target", "icici", "--max-iters", "1", "--quiet"]
    res = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True)
    if res.returncode != 0:
        raise AssertionError(
            "agent.py failed to generate the parser.\n"
            f"stdout:\n{res.stdout}\n\nstderr:\n{res.stderr}"
        )
    assert PARSER_FILE.exists(), "custom_parsers/icici_parser.py was not created by agent.py"


def _import_icici_parser():
    """
    Try normal package import first; if that fails for any reason,
    fall back to loading directly from file path.
    """
    try:
        return importlib.import_module("custom_parsers.icici_parser")
    except ModuleNotFoundError:
        spec = importlib.util.spec_from_file_location("custom_parsers.icici_parser", PARSER_FILE)
        if not spec or not spec.loader:
            raise
        mod = importlib.util.module_from_spec(spec)
        sys.modules["custom_parsers.icici_parser"] = mod
        spec.loader.exec_module(mod)  # type: ignore
        return mod


def test_icici_parser_has_parse_and_returns_df():
    """
    Smoke test:
    - Parser is generated (if needed)
    - custom_parsers.icici_parser exposes parse(pdf_path)
    - parse() returns a non-empty DataFrame
    """
    _ensure_assets()
    _ensure_parser_generated()

    mod = _import_icici_parser()
    assert hasattr(mod, "parse"), "icici_parser.parse(...) not found"

    df = mod.parse(str(PDF_PATH))
    assert isinstance(df, pd.DataFrame), "parse() must return a pandas DataFrame"
    assert not df.empty, "Parsed DataFrame should not be empty"


def test_line_mode_fallback(monkeypatch):
    """
    Forces table extraction to fail so we exercise the line-mode parser.
    Ensures we still get a valid, non-empty DataFrame.
    """
    _ensure_assets()
    _ensure_parser_generated()

    mod = _import_icici_parser()

    # Monkey-patch table extractor to return no tables
    monkeypatch.setattr(mod, "_extract_tables_pdfplumber", lambda _: [])

    df = mod.parse(str(PDF_PATH))
    assert isinstance(df, pd.DataFrame)
    assert not df.empty
