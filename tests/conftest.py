"""Pytest configuration: point liboqs-python at the local liboqs install before `oqs` loads."""

import os
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
os.environ.setdefault("OQS_INSTALL_PATH", str(_REPO / "third_party" / "install" / "liboqs"))
