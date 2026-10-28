#!/usr/bin/env python3
"""Linux launcher for the authenticated remote MCP gateway."""

from __future__ import annotations

import glob
import os
from pathlib import Path
import sys


APP = Path(__file__).resolve().parent


def _load_env_file(path: Path) -> None:
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:]
        key, sep, value = line.partition("=")
        if sep and key.strip():
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def main() -> int:
    env_path = Path(os.environ.get(
        "CRONI_ENV_FILE",
        "~/.config/croni-call/remote.env",
    )).expanduser()
    _load_env_file(env_path)

    pjdir = Path(os.environ.get("PJPROJECT_DIR", "~/build/pjproject-2.17")).expanduser()
    swig_matches = sorted(glob.glob(str(
        pjdir / "pjsip-apps" / "src" / "swig" / "python" / "build" / "lib.*"
    )))
    swig_lib = swig_matches[0] if swig_matches else ""
    if not swig_lib or not (pjdir / "pjlib" / "lib").is_dir():
        sys.stderr.write(
            f"croni-call: pjsua2 build not found under PJPROJECT_DIR={pjdir}\n"
            "Run the repository's Linux installer first.\n"
        )
        return 1

    python_path = [swig_lib, str(APP)]
    if os.environ.get("PYTHONPATH"):
        python_path.append(os.environ["PYTHONPATH"])
    os.environ["PYTHONPATH"] = os.pathsep.join(python_path)

    lib_dirs = [
        str(pjdir / part / "lib")
        for part in ("pjlib", "pjlib-util", "pjnath", "pjmedia", "pjsip", "third_party")
    ]
    if os.environ.get("LD_LIBRARY_PATH"):
        lib_dirs.append(os.environ["LD_LIBRARY_PATH"])
    os.environ["LD_LIBRARY_PATH"] = os.pathsep.join(lib_dirs)

    os.execv(sys.executable, [sys.executable, "-m", "croni_remote.server"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
