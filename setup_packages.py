"""Install the backend dependencies offline from the vendored wheels.

Extracting the wheels from inside the workspace (instead of pointing pip at a
directory created outside the sandbox) keeps every provisioned file readable by
later confined runs.

Usage:
    python setup_packages.py            # extract .wheels/*.whl into .packages/
    python setup_packages.py --clean    # wipe .packages/ first
"""

from __future__ import annotations

import argparse
import shutil
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
WHEELS = HERE / ".wheels"
TARGET = HERE / ".site"


def extract_all(clean: bool) -> int:
    if not WHEELS.is_dir():
        print(f"No wheel directory at {WHEELS}", file=sys.stderr)
        print("Run: pip download --dest .wheels --only-binary=:all: -r requirements.txt")
        return 1

    wheels = sorted(WHEELS.glob("*.whl"))
    if not wheels:
        print(f"No wheels found in {WHEELS}", file=sys.stderr)
        return 1

    if clean and TARGET.exists():
        shutil.rmtree(TARGET, ignore_errors=True)
    TARGET.mkdir(parents=True, exist_ok=True)

    for wheel in wheels:
        with zipfile.ZipFile(wheel) as archive:
            archive.extractall(TARGET)
        print(f"extracted {wheel.name}")

    print(f"\n{len(wheels)} wheels -> {TARGET}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--clean",
        action="store_true",
        help="remove the target directory before extracting",
    )
    args = parser.parse_args()
    return extract_all(clean=args.clean)


if __name__ == "__main__":
    raise SystemExit(main())
