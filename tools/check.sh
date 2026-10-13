#!/usr/bin/env bash
set -euo pipefail
here="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$here"
bash -n install.sh uninstall.sh plugins/cyclops-keeper/scripts/integration.bash tools/check.sh
python3 -B -m unittest discover -s tests -p 'test_*.py' -v
