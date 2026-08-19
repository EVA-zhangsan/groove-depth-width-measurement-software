"""Windows/PyInstaller entry point for the one-click compatibility demo."""
from __future__ import annotations

import sys
from pathlib import Path

import gui
import compat_gui


def main() -> int:
    app_root = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
    gui.ROOT = app_root
    gui.OUTPUT_ROOT = app_root / "outputs"
    gui.DATA_ROOT = app_root / "示例数据"
    gui.HISTORY_PATH = gui.OUTPUT_ROOT / "history" / "measurement_history.csv"
    return compat_gui.main()


if __name__ == "__main__":
    raise SystemExit(main())
