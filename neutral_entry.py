"""Neutral Windows entry point for the portable GUI."""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication
import gui


class NeutralMainWindow(gui.MainWindow):
    def __init__(self):
        super().__init__()
        # Remove startup wording intended for temporary testing/demo packaging.
        self.console.clear()
        self.log(
            f"已应用任务：{self.task.sample_id}，槽深 {self.task.target_depth_mm:.4f} mm，"
            f"槽宽 {self.task.target_width_mm:.4f} mm，公差 ±{self.task.tolerance_mm:.4f} mm。"
        )
        self.log("软件已启动。可通过“选择原始图片目录”或“导入点云文件”载入测量数据。")


def main() -> int:
    app_root = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
    gui.ROOT = app_root
    gui.OUTPUT_ROOT = app_root / "outputs"
    gui.DATA_ROOT = app_root / "示例数据"
    gui.HISTORY_PATH = gui.OUTPUT_ROOT / "history" / "measurement_history.csv"

    app = QApplication(sys.argv)
    app.setApplicationName("槽型深度宽度测量软件")
    window = NeutralMainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
