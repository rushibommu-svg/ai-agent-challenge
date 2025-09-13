import sys, types
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from custom_parsers import base_parser as bp  # type: ignore


class _FakePage:
    def extract_text(self): return "01-08-2024 Salary Credit 100.00 200.00\n"


class _FakeReader:
    def __init__(self, *_a, **_k):
        self.pages = [_FakePage()]


def test_extract_lines_uses_pypdf_on_pdfplumber_error(monkeypatch, tmp_path):
    # Force pdfplumber.open to raise → triggers fallback
    fake_pdfplumber = types.SimpleNamespace(open=lambda *_: (_ for _ in ()).throw(RuntimeError("boom")))
    monkeypatch.setitem(sys.modules, "pdfplumber", fake_pdfplumber)

    # Provide a fake pypdf reader
    fake_pypdf = types.SimpleNamespace(PdfReader=_FakeReader)
    monkeypatch.setitem(sys.modules, "pypdf", fake_pypdf)

    pdf = tmp_path / "x.pdf"
    pdf.write_bytes(b"%PDF-1.4\n%stub")

    lines = bp.extract_lines_pdf(pdf)
    assert any("01-08-2024" in ln for ln in lines)
