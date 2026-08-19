"""Windows/PyInstaller entry point for the no-OpenGL competition safe edition."""
from __future__ import annotations

import sys
from pathlib import Path

import safe_gui


def main() -> int:
    app_root = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
    safe_gui.ROOT = app_root
    safe_gui.OUTPUT_ROOT = app_root / "outputs"
    safe_gui.DATA_ROOT = app_root / "示例数据"
    safe_gui.HISTORY_PATH = safe_gui.OUTPUT_ROOT / "history" / "measurement_history.csv"
    return safe_gui.main()


if __name__ == "__main__":
    raise SystemExit(main())
