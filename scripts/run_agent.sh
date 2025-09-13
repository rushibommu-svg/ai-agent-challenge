#!/usr/bin/env bash
set -euo pipefail

TARGET="${1:-icici}"
HERE="$(cd "$(dirname "$0")/.." && pwd)"

echo "[run_agent] target: $TARGET"
python "$HERE/agent.py" --target "$TARGET" --log-level INFO
