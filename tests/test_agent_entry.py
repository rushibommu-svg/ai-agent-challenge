# Ensures we import agent.py from the repo root, then runs main([...])
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:  # make repo importable
    sys.path.insert(0, str(REPO_ROOT))

from agent import main  # now import works


def test_agent_runs_icici_once():
    """
    Executes the agent loop once in quiet mode.
    This imports agent.py (so coverage tracks it) and ensures rc == 0.
    """
    rc = main(["--target", "icici", "--max-iters", "1", "--quiet"])
    assert rc == 0
