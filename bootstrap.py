"""Run the API with the vendored dependencies available.

`python -m uvicorn app.main:app` cannot work when the dependencies live in
`backend/.site`, because `-m` resolves the module before `app/__init__.py` runs.
This entry point adds the vendored directory to sys.path first, then starts
uvicorn programmatically - so `--reload` keeps working too.

Usage (from shopping-list/backend):
    python bootstrap.py
    python bootstrap.py --reload --port 8000
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
VENDORED = HERE / ".site"
if VENDORED.is_dir():
    sys.path.insert(0, str(VENDORED))

try:
    import uvicorn
except ModuleNotFoundError:  # pragma: no cover - developer guidance path
    print(
        "uvicorn is not installed.\n"
        "  - create a venv:  python -m venv .venv && .venv\\Scripts\\pip install -r requirements.txt\n"
        "  - or vendor:      python setup_packages.py  (needs the wheels in backend/.wheels)",
        file=sys.stderr,
    )
    raise SystemExit(1) from None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument(
        "--reload",
        action="store_true",
        help="restart the server when source files change",
    )
    args = parser.parse_args()

    uvicorn.run(
        "app.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        # Pin the reloader to this directory so it picks up app/ changes only.
        reload_dirs=[str(HERE / "app")] if args.reload else None,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
