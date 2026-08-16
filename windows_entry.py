"""Windows/PyInstaller entry point.

Keeps writable outputs and bundled demo data next to the executable rather than
inside PyInstaller's internal runtime directory.
"""
from __future__ import annotations

import sys
from pathlib import Path

import gui


def main() -> int:
    app_root = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
    gui.ROOT = app_root
    gui.OUTPUT_ROOT = app_root / "outputs"
    gui.DEMO_DIR = app_root / "samples" / "raw_laser_demo"
    gui.HISTORY_PATH = gui.OUTPUT_ROOT / "history" / "measurement_history.csv"
    return gui.main()


if __name__ == "__main__":
    raise SystemExit(main())
