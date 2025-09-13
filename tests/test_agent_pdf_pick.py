from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import agent  # type: ignore


def test_locate_pdf_prefers_target_named_file(tmp_path, monkeypatch):
    target = "demo"
    tdir = tmp_path / "data" / target
    tdir.mkdir(parents=True, exist_ok=True)

    # Two PDFs: generic and preferred
    (tdir / "statement.pdf").write_bytes(b"%PDF-1.4\n%stub")
    (tdir / f"{target}_sample.pdf").write_bytes(b"%PDF-1.4\n%stub")

    # Minimal CSV so downstream bits are happy if called
    (tdir / "result.csv").write_text("A,B\n1,2\n", encoding="utf-8")

    monkeypatch.setattr(agent, "DATA_DIR", tmp_path / "data")

    picked = agent.locate_pdf(target)
    assert picked.name == f"{target}_sample.pdf"
