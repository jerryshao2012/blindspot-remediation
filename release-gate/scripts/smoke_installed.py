"""Build-artifact smoke test for the installed console command."""

from __future__ import annotations

import os
import site
import subprocess
import sys
import tempfile
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    wheels = sorted((root / "dist").glob("release_gate-*.whl"))
    if len(wheels) != 1:
        raise SystemExit(f"expected exactly one wheel, found {len(wheels)}")
    with tempfile.TemporaryDirectory(prefix="release-gate-wheel-") as temporary:
        environment = Path(temporary) / "venv"
        subprocess.run(
            [sys.executable, "-m", "venv", "--system-site-packages", str(environment)],
            check=True,
        )
        scripts = "Scripts" if os.name == "nt" else "bin"
        python = environment / scripts / ("python.exe" if os.name == "nt" else "python")
        command = (
            environment
            / scripts
            / ("release-gate.exe" if os.name == "nt" else "release-gate")
        )
        subprocess.run(
            [str(python), "-m", "pip", "install", "--no-deps", str(wheels[0])],
            check=True,
        )
        inherited_dependencies = os.pathsep.join(site.getsitepackages())
        process_environment = {**os.environ, "PYTHONPATH": inherited_dependencies}
        result = subprocess.run(
            [str(command), "--help"],
            capture_output=True,
            text=True,
            env=process_environment,
            check=False,
        )
        if result.returncode != 0:
            raise SystemExit(
                "installed command failed:\n"
                f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
            )
        if "{init,validate,run}" not in result.stdout:
            raise SystemExit("installed command did not expose the expected CLI")
        version = subprocess.run(
            [str(command), "--version"],
            capture_output=True,
            text=True,
            env=process_environment,
            check=False,
        )
        if version.returncode != 0 or version.stdout != "release-gate 0.2.3\n":
            raise SystemExit(
                "installed command reported the wrong version:\n"
                f"stdout:\n{version.stdout}stderr:\n{version.stderr}"
            )
        target = Path(temporary) / "target"
        target.mkdir()
        subprocess.run(
            [str(command), "init", "--repo", str(target)],
            env=process_environment,
            check=True,
        )
        subprocess.run(
            [str(command), "validate", "--repo", str(target)],
            env=process_environment,
            check=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
