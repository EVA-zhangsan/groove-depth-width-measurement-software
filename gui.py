"""Desktop GUI for groove depth and width measurement."""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
import pyvista as pv
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QApplication, QComboBox, QDialog, QDoubleSpinBox, QFileDialog, QFormLayout,
    QGridLayout, QGroupBox, QLabel, QLineEdit, QMainWindow,
    QMessageBox, QPushButton, QSplitter, QTabWidget, QTextEdit, QVBoxLayout, QWidget,
)
from pyvistaqt import QtInteractor

from history_manager import append_history, read_recent_history
from measurement_analysis import analyze_groove
from measurement_task import MeasurementTask
from offline_reconstruction import imread_unicode, reconstruct_directory
from report_generator import generate_measurement_report

ROOT = Path(__file__).resolve().parent
OUTPUT_ROOT = ROOT / "outputs"
HISTORY_PATH = OUTPUT_ROOT / "history" / "measurement_history.csv"


def load_point_cloud(path: Path) -> np.ndarray:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        frame = pd.read_csv(path)
        if {"x", "y", "z"}.issubset(frame.columns):
            return frame[["x", "y", "z"]].to_numpy(float)
        if frame.shape[1] >= 3:
            return frame.iloc[:, :3].to_numpy(float)
        raise ValueError("CSV 至少需要三列或 x、y、z 三列")
    mesh = pv.read(path)
    return np.asarray(mesh.points, dtype=float)


def array_to_pixmap(image: np.ndarray, target: QLabel) -> QPixmap:
    if image.ndim == 2:
        image = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
    else:
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    image = np.ascontiguousarray(image)
    height, width, channels = image.shape
    qimage = QImage(image.data, width, height, width * channels, QImage.Format_RGB888).copy()
    return QPixmap.fromImage(qimage).scaled(target.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("槽型深度宽度测量软件")
        self.resize(1680, 980)
        self.task: MeasurementTask | None = None
        self.reconstruction: dict | None = None
        self.result = None
        self.points: np.ndarray | None = None
        self.last_report: Path | None = None
        self._build_ui()
        self._apply_style()
        self.apply_task()
        self.log("软件已启动。请从外部选择原始图片目录，或导入点云文件。")

    def _build_ui(self) -> None:
        root = QWidget(self)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(8, 8, 8, 8)

        title = QLabel("槽型深度宽度测量软件")
        title.setObjectName("title")
        subtitle = QLabel("任务设置 · 激光中心提取 · 离线点云重建 · 槽深槽宽分析 · PDF报告")
        subtitle.setObjectName("subtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self._build_task_panel())
        splitter.addWidget(self._build_viewer_panel())
        splitter.addWidget(self._build_result_panel())
        splitter.setSizes([310, 970, 390])
        layout.addWidget(splitter, 1)

        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setMaximumHeight(145)
        layout.addWidget(self.console)
        self.setCentralWidget(root)

    def _build_task_panel(self) -> QWidget:
        panel = QWidget()
        panel.setMinimumWidth(285)
        outer = QVBoxLayout(panel)

        group = QGroupBox("测量任务设置")
        form = QFormLayout(group)
        self.sample_id = QLineEdit("SAMPLE-001")
        self.groove_type = QComboBox()
        self.groove_type.addItems(["直线 V 型槽", "环形槽", "十字槽", "球弧面槽"])
        self.data_nature = QComboBox()
        self.data_nature.addItems(["原始激光图像", "外部点云"])
        self.target_depth = QDoubleSpinBox(); self.target_depth.setRange(0.0001, 1000); self.target_depth.setDecimals(4); self.target_depth.setValue(0.6000)
        self.target_width = QDoubleSpinBox(); self.target_width.setRange(0.0001, 1000); self.target_width.setDecimals(4); self.target_width.setValue(0.8500)
        self.tolerance = QDoubleSpinBox(); self.tolerance.setRange(0.0001, 100); self.tolerance.setDecimals(4); self.tolerance.setValue(0.0200)
        self.operator = QLineEdit("")
        self.notes = QLineEdit("")
        form.addRow("样本编号", self.sample_id)
        form.addRow("槽型", self.groove_type)
        form.addRow("数据性质", self.data_nature)
        form.addRow("标准槽深/mm", self.target_depth)
        form.addRow("标准槽宽/mm", self.target_width)
        form.addRow("允许误差/mm", self.tolerance)
        form.addRow("操作人员", self.operator)
        form.addRow("备注", self.notes)
        outer.addWidget(group)

        apply_button = QPushButton("应用任务参数")
        apply_button.clicked.connect(self.apply_task)
        image_button = QPushButton("选择原始图片目录")
        image_button.setObjectName("primary")
        image_button.clicked.connect(self.select_image_directory)
        cloud_button = QPushButton("导入点云文件")
        cloud_button.clicked.connect(self.import_point_cloud)
        analyze_button = QPushButton("重新分析当前点云")
        analyze_button.clicked.connect(self.analyze_current)
        reset_button = QPushButton("回到推荐视角")
        reset_button.clicked.connect(self.reset_camera)
        for button in [apply_button, image_button, cloud_button, analyze_button, reset_button]:
            outer.addWidget(button)
        outer.addStretch(1)
        return panel

    def _build_viewer_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        group = QGroupBox("三维点云与槽型结果")
        group_layout = QVBoxLayout(group)
        self.viewer = QtInteractor(group)
        self.viewer.set_background("#12171d", top="#26313a")
        self.viewer.add_axes()
        group_layout.addWidget(self.viewer)
        layout.addWidget(group)
        return panel

    def _build_result_panel(self) -> QWidget:
        panel = QWidget()
        panel.setMinimumWidth(360)
        outer = QVBoxLayout(panel)

        result_group = QGroupBox("测量结果")
        form = QFormLayout(result_group)
        keys = [
            "槽深均值", "槽宽均值", "槽深判定", "槽宽判定",
            "槽深最小值及位置", "槽深最大值及位置",
            "槽宽最小值及位置", "槽宽最大值及位置",
            "有效截面", "点云点数", "读取/重建耗时", "分析耗时",
        ]
        self.result_labels: dict[str, QLabel] = {}
        for key in keys:
            label = QLabel("—")
            label.setWordWrap(True)
            self.result_labels[key] = label
            form.addRow(key, label)
        outer.addWidget(result_group)

        self.tabs = QTabWidget()
        self.image_labels: dict[str, QLabel] = {}
        for name in ["原始图像", "中心提取", "二值掩膜"]:
            label = QLabel("导入原始图片目录后显示")
            label.setAlignment(Qt.AlignCenter)
            label.setMinimumHeight(190)
            label.setStyleSheet("background:#10151a;border:1px solid #3a4650;")
            self.image_labels[name] = label
            self.tabs.addTab(label, name)
        outer.addWidget(self.tabs)

        button_row = QGridLayout()
        report_button = QPushButton("生成 PDF 报告")
        report_button.setObjectName("primary")
        report_button.clicked.connect(self.generate_report)
        history_button = QPushButton("查看历史记录")
        history_button.clicked.connect(self.show_history)
        open_output_button = QPushButton("打开输出结果")
        open_output_button.clicked.connect(self.show_output_path)
        button_row.addWidget(report_button, 0, 0, 1, 2)
        button_row.addWidget(history_button, 1, 0)
        button_row.addWidget(open_output_button, 1, 1)
        outer.addLayout(button_row)
        return panel

    def _apply_style(self) -> None:
        self.setStyleSheet("""
        QMainWindow, QWidget { background:#1b2229; color:#e7eef5; font-family:'Microsoft YaHei UI'; font-size:10pt; }
        QLabel#title { font-size:22pt; font-weight:700; color:#ffffff; padding:3px; }
        QLabel#subtitle { color:#9fb1bf; padding:0 3px 6px 3px; }
        QGroupBox { border:1px solid #3a4650; border-radius:7px; margin-top:12px; padding-top:10px; font-weight:600; }
        QGroupBox::title { subcontrol-origin:margin; left:12px; padding:0 5px; color:#78e3d7; }
        QLineEdit, QComboBox, QDoubleSpinBox, QTextEdit, QTabWidget::pane { background:#11171c; border:1px solid #3a4650; border-radius:4px; padding:5px; }
        QPushButton { background:#2b3640; border:1px solid #4b5b67; border-radius:5px; padding:8px; }
        QPushButton:hover { background:#374550; }
        QPushButton#primary { background:#007f78; border-color:#00b7aa; font-weight:700; }
        QPushButton#primary:hover { background:#00978d; }
        QTabBar::tab { background:#242e37; padding:7px; }
        QTabBar::tab:selected { background:#007f78; }
        """)

    def log(self, message: str) -> None:
        self.console.append(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")

    def apply_task(self) -> None:
        try:
            self.task = MeasurementTask(
                sample_id=self.sample_id.text().strip() or "UNNAMED",
                groove_type=self.groove_type.currentText(),
                data_nature=self.data_nature.currentText(),
                target_depth_mm=self.target_depth.value(),
                target_width_mm=self.target_width.value(),
                tolerance_mm=self.tolerance.value(),
                operator=self.operator.text().strip(),
                notes=self.notes.text().strip(),
            )
            self.log(f"已应用任务：{self.task.sample_id}，槽深 {self.task.target_depth_mm:.4f} mm，槽宽 {self.task.target_width_mm:.4f} mm，公差 ±{self.task.tolerance_mm:.4f} mm。")
        except Exception as exc:
            QMessageBox.critical(self, "任务参数错误", str(exc))

    def select_image_directory(self) -> None:
        default_dir = ROOT / "示例数据"
        directory = QFileDialog.getExistingDirectory(self, "选择原始激光图片目录", str(default_dir if default_dir.exists() else ROOT))
        if not directory:
            return
        self.data_nature.setCurrentText("原始激光图像")
        self.apply_task()
        try:
            self._run_image_directory(Path(directory))
        except Exception as exc:
            QMessageBox.critical(self, "重建失败", str(exc))
            self.log(f"重建失败：{exc}")

    def _run_image_directory(self, directory: Path) -> None:
        session = OUTPUT_ROOT / "offline_reconstruction" / f"{self.task.sample_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.log(f"开始读取原始图片：{directory}")
        self.reconstruction = reconstruct_directory(directory, session)
        self.points = self.reconstruction["points"]
        self.result = analyze_groove(self.points)
        self.render_points()
        self.update_images()
        self.update_results()
        self.log(f"完成：{self.reconstruction['valid_frames']}/{self.reconstruction['original_frames']} 帧有效，点云 {self.reconstruction['point_count']} 点。")

    def import_point_cloud(self) -> None:
        default_dir = ROOT / "示例数据"
        filename, _ = QFileDialog.getOpenFileName(self, "导入点云文件", str(default_dir if default_dir.exists() else ROOT), "Point Cloud (*.csv *.ply *.pcd *.xyz)")
        if not filename:
            return
        try:
            self.data_nature.setCurrentText("外部点云")
            self.apply_task()
            self.points = load_point_cloud(Path(filename))
            self.reconstruction = {
                "points": self.points, "source_dir": str(Path(filename).parent), "point_cloud_csv": filename,
                "original_frames": 0, "valid_frames": 0, "point_count": int(self.points.shape[0]),
                "read_seconds": 0.0, "calibration_applied": False,
                "preview_original": "", "preview_overlay": "", "preview_mask": "",
            }
            self.result = analyze_groove(self.points)
            self.render_points(); self.update_results()
            self.log(f"已导入点云：{filename}，共 {self.points.shape[0]} 点。")
        except Exception as exc:
            QMessageBox.critical(self, "导入失败", str(exc))

    def analyze_current(self) -> None:
        if self.points is None:
            QMessageBox.information(self, "提示", "请先导入原始图片目录或点云文件。")
            return
        try:
            self.result = analyze_groove(self.points)
            self.update_results(); self.render_points()
            self.log("已重新分析当前点云。")
        except Exception as exc:
            QMessageBox.critical(self, "分析失败", str(exc))

    def render_points(self) -> None:
        if self.points is None:
            return
        self.viewer.clear()
        cloud = pv.PolyData(self.points)
        cloud["height"] = self.points[:, 2]
        self.viewer.add_mesh(cloud, scalars="height", point_size=3.0, render_points_as_spheres=True, cmap="turbo", scalar_bar_args={"title": "Z / mm"})
        self.viewer.add_axes()
        self.viewer.show_grid(color="#82909b")
        self.viewer.view_isometric()
        self.viewer.reset_camera()

    def reset_camera(self) -> None:
        self.viewer.view_isometric(); self.viewer.reset_camera()

    def update_images(self) -> None:
        if not self.reconstruction:
            return
        mapping = {
            "原始图像": self.reconstruction.get("preview_original"),
            "中心提取": self.reconstruction.get("preview_overlay"),
            "二值掩膜": self.reconstruction.get("preview_mask"),
        }
        for name, path in mapping.items():
            if path and Path(path).exists():
                image = imread_unicode(path, cv2.IMREAD_UNCHANGED)
                if image is not None:
                    self.image_labels[name].setPixmap(array_to_pixmap(image, self.image_labels[name]))

    def update_results(self) -> None:
        if not self.result or not self.reconstruction or not self.task:
            return
        depth_ok = abs(self.result.depth_mean - self.task.target_depth_mm) <= self.task.tolerance_mm
        width_ok = abs(self.result.width_mean - self.task.target_width_mm) <= self.task.tolerance_mm
        values = {
            "槽深均值": f"{self.result.depth_mean:.4f} mm",
            "槽宽均值": f"{self.result.width_mean:.4f} mm",
            "槽深判定": "合格" if depth_ok else "超差",
            "槽宽判定": "合格" if width_ok else "超差",
            "槽深最小值及位置": f"{self.result.depth_min:.4f} mm @ Y={self.result.depth_min_y:.3f}",
            "槽深最大值及位置": f"{self.result.depth_max:.4f} mm @ Y={self.result.depth_max_y:.3f}",
            "槽宽最小值及位置": f"{self.result.width_min:.4f} mm @ Y={self.result.width_min_y:.3f}",
            "槽宽最大值及位置": f"{self.result.width_max:.4f} mm @ Y={self.result.width_max_y:.3f}",
            "有效截面": str(len(self.result.sections)),
            "点云点数": str(self.reconstruction.get("point_count", 0)),
            "读取/重建耗时": f"{self.reconstruction.get('read_seconds', 0):.3f} s",
            "分析耗时": f"{self.result.analysis_seconds:.3f} s",
        }
        for key, value in values.items():
            self.result_labels[key].setText(value)
        for key in ["槽深判定", "槽宽判定"]:
            self.result_labels[key].setStyleSheet("color:#65e58a;font-weight:700;" if self.result_labels[key].text() == "合格" else "color:#ff7373;font-weight:700;")

    def generate_report(self) -> None:
        if not self.task or not self.reconstruction or not self.result:
            QMessageBox.information(self, "提示", "请先完成一次测量分析。")
            return
        report_dir = OUTPUT_ROOT / "reports" / datetime.now().strftime("%Y-%m-%d")
        report_path = report_dir / f"{self.task.sample_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_measurement_report.pdf"
        try:
            self.last_report, report_seconds = generate_measurement_report(self.task, self.reconstruction, self.result, report_path)
            depth_status = "合格" if abs(self.result.depth_mean - self.task.target_depth_mm) <= self.task.tolerance_mm else "超差"
            width_status = "合格" if abs(self.result.width_mean - self.task.target_width_mm) <= self.task.tolerance_mm else "超差"
            append_history(HISTORY_PATH, {
                "sample_id": self.task.sample_id, "groove_type": self.task.groove_type, "data_nature": self.task.data_nature,
                "target_depth_mm": self.task.target_depth_mm, "measured_depth_mm": self.result.depth_mean,
                "target_width_mm": self.task.target_width_mm, "measured_width_mm": self.result.width_mean,
                "tolerance_mm": self.task.tolerance_mm, "depth_status": depth_status, "width_status": width_status,
                "point_count": self.reconstruction.get("point_count", 0), "valid_sections": len(self.result.sections),
                "read_seconds": self.reconstruction.get("read_seconds", 0), "analysis_seconds": self.result.analysis_seconds,
                "report_seconds": report_seconds, "report_path": str(self.last_report),
            })
            self.log(f"PDF报告已生成：{self.last_report}")
            QMessageBox.information(self, "报告生成成功", "测量报告已保存至输出结果目录。")
        except Exception as exc:
            QMessageBox.critical(self, "报告生成失败", str(exc))

    def show_history(self) -> None:
        rows = read_recent_history(HISTORY_PATH, limit=20)
        dialog = QDialog(self); dialog.setWindowTitle("最近测量历史"); dialog.resize(1000, 520)
        layout = QVBoxLayout(dialog); text = QTextEdit(); text.setReadOnly(True)
        if rows:
            lines = []
            for row in reversed(rows):
                lines.append(f"{row.get('timestamp')} | {row.get('sample_id')} | 槽深均值 {row.get('measured_depth_mm')} mm ({row.get('depth_status')}) | 槽宽均值 {row.get('measured_width_mm')} mm ({row.get('width_status')})")
            text.setPlainText("\n".join(lines))
        else:
            text.setPlainText("暂无历史记录。完成测量并生成报告后自动写入。")
        layout.addWidget(text); dialog.exec()

    def show_output_path(self) -> None:
        OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
        try:
            import os
            os.startfile(str(OUTPUT_ROOT))
        except Exception:
            self.log(f"输出目录：{OUTPUT_ROOT}")
            QMessageBox.information(self, "输出目录", str(OUTPUT_ROOT))


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("槽型深度宽度测量软件")
    window = MainWindow(); window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
