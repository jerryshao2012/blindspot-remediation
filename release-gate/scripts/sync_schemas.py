"""Keep packaged schemas byte-identical to the canonical contracts."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--write", action="store_true", help="copy canonical schemas into the package"
    )
    arguments = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    canonical = root / "schemas"
    packaged = root / "src" / "release_gate" / "schemas"
    mismatches: list[str] = []
    for source in sorted(canonical.glob("*.schema.json")):
        destination = packaged / source.name
        if not destination.exists() or destination.read_bytes() != source.read_bytes():
            if arguments.write:
                shutil.copyfile(source, destination)
            else:
                mismatches.append(source.name)
    if mismatches:
        parser.error(
            "packaged schemas differ; run scripts/sync_schemas.py --write: "
            + ", ".join(mismatches)
        )
    print("SCHEMAS IN SYNC")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
