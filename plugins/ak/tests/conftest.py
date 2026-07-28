from __future__ import annotations

import sys
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
for path in (PACKAGE, PACKAGE / "contracts", PACKAGE / "scripts"):
    value = str(path)
    if value not in sys.path:
        sys.path.insert(0, value)