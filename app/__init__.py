"""Shopping list API package.

Runtime dependencies may be vendored into ``backend/.site`` (see
``setup_packages.py``) instead of a virtualenv. Adding it here - in the package
``__init__`` - makes them importable before any submodule loads, so
``python -m uvicorn app.main:app`` works with no PYTHONPATH set.
"""

from __future__ import annotations

import sys
from pathlib import Path

_VENDORED = Path(__file__).resolve().parent.parent / ".site"
if _VENDORED.is_dir() and str(_VENDORED) not in sys.path:
    # Append rather than prepend: a real virtualenv or site-packages should win
    # when the developer installed requirements normally.
    sys.path.append(str(_VENDORED))
