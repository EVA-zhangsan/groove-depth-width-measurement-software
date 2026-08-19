"""Competition compatibility GUI.

Adds a one-click bundled demo and a conservative VTK rendering path for PCs
where point-sphere rendering may disappear even though the data and analysis
have completed successfully.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pyvista as pv
from PySide6.QtWidgets import QApplication, QMessageBox, QPushButton

import gui


class CompatibilityMainWindow(gui.MainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("槽型深度宽度测量软件 | 比赛兼容演示版")
        self.log("兼容模式已启用：可直接点击“一键运行内置案例”。三维显示同时绘制点云与截面线。")

    def _build_task_panel(self):
        panel = super()._build_task_panel()
        layout = panel.layout()
        demo_button = QPushButton("一键运行内置案例")
        demo_button.setObjectName("primary")
        demo_button.setToolTip("无需选择文件，直接载入软件目录内的 181 帧比赛案例")
        demo_button.clicked.connect(self.run_builtin_demo)
        # group=0, 应用任务参数=1；把一键案例放在其后。
        layout.insertWidget(2, demo_button)
        return panel

    def run_builtin_demo(self):
        candidates = [
            gui.DATA_ROOT / "01_原始图像_181帧_紧凑曲面V槽",
            gui.DATA_ROOT / "02_原始图像_301帧_高密度紧凑曲面V槽",
        ]
        directory = next((path for path in candidates if path.exists()), None)
        if directory is None:
            QMessageBox.critical(
                self,
                "内置案例缺失",
                f"未找到内置案例目录：\n{gui.DATA_ROOT}\n\n请确认软件已完整解压，不要只复制 EXE。",
            )
            return
        try:
            self.sample_id.setText("DEMO-V-001")
            self.data_nature.setCurrentText("图像序列数据")
            self.notes.setText("比赛兼容模式内置案例")
            self.apply_task()
            self.log(f"一键载入内置案例：{directory.name}")
            self._run_image_directory(Path(directory))
        except Exception as exc:
            self.log(f"内置案例运行失败：{exc}")
            QMessageBox.critical(self, "内置案例运行失败", str(exc))

    def render_points(self):
        """Use a robust rendering path: ordinary points + representative profile lines.

        Some integrated-GPU/driver combinations can render VTK point sprites poorly.  The
        profile-line overlay provides a second independent actor, so the groove remains
        visible even if the colored point actor has a driver-specific issue.
        """
        if self.points is None:
            return

        points = np.asarray(self.points, dtype=float)
        self.viewer.clear()

        cloud = pv.PolyData(points)
        cloud["height"] = points[:, 2]
        point_size = 3.8 if points.shape[0] > 150000 else 4.8
        self.viewer.add_mesh(
            cloud,
            scalars="height",
            style="points",
            point_size=point_size,
            render_points_as_spheres=False,
            cmap="turbo",
            opacity=1.0,
            scalar_bar_args={"title": "Z / mm"},
        )

        # Draw a manageable number of connected cross-section profiles.  This makes the
        # groove shape visible on machines where OpenGL point-sprite rendering is flaky.
        rounded_y = np.round(points[:, 1], 6)
        unique_y = np.unique(rounded_y)
        stride = max(1, len(unique_y) // 42)
        for y_value in unique_y[::stride]:
            section = points[rounded_y == y_value]
            if section.shape[0] < 2:
                continue
            section = section[np.argsort(section[:, 0])]
            line_mesh = pv.lines_from_points(section, close=False)
            self.viewer.add_mesh(
                line_mesh,
                color="#ff5b3a",
                line_width=1.6,
                lighting=False,
            )

        self.viewer.add_axes()
        self.viewer.show_grid(color="#82909b")
        self.viewer.view_isometric()
        self.viewer.reset_camera()
        self.viewer.render()


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("槽型深度宽度测量软件")
    window = CompatibilityMainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
