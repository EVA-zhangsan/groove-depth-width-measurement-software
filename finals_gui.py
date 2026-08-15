"""Product launcher for the groove depth and width measurement software."""
from __future__ import annotations

import logging
import os
import shutil
import sys
import traceback
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QGridLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from demo_data import ensure_demo_frames
from measurement_analysis import analyze_groove
from offline_reconstruction import reconstruct_directory
import gui as base_gui

APP_ROOT = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
OUTPUT_ROOT = APP_ROOT / "outputs"
SAMPLE_DIR = APP_ROOT / "samples" / "raw_laser_demo"
LOG_DIR = APP_ROOT / "logs"
LOG_FILE = LOG_DIR / "app.log"
BACKUP_DIR = APP_ROOT / "assets" / "standard_sample_backup"

base_gui.ROOT = APP_ROOT
base_gui.OUTPUT_ROOT = OUTPUT_ROOT
base_gui.DEMO_DIR = SAMPLE_DIR
base_gui.HISTORY_PATH = OUTPUT_ROOT / "history" / "measurement_history.csv"
MainWindow = base_gui.MainWindow


def configure_logging() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=str(LOG_FILE),
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        encoding="utf-8",
    )


def exception_hook(exc_type, exc_value, exc_tb) -> None:
    text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    logging.critical("Unhandled exception\n%s", text)
    app = QApplication.instance()
    if app is not None:
        QMessageBox.critical(
            None,
            "软件运行异常",
            "软件运行过程中出现异常。详细信息已记录到 logs/app.log。\n\n"
            "可先执行“系统检测”或“恢复标准样例”后重试；如使用自定义数据，请检查数据格式。",
        )


def check_system() -> list[tuple[str, bool, str]]:
    checks: list[tuple[str, bool, str]] = []

    try:
        OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
        probe = OUTPUT_ROOT / ".write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        checks.append(("数据存储", True, "正常"))
    except Exception:
        checks.append(("数据存储", False, "不可用"))

    try:
        if len(list(SAMPLE_DIR.glob("frame_*.*"))) != 31 and BACKUP_DIR.exists():
            SAMPLE_DIR.mkdir(parents=True, exist_ok=True)
            for file in BACKUP_DIR.glob("frame_*.*"):
                shutil.copy2(file, SAMPLE_DIR / file.name)
        sample_dir = ensure_demo_frames(SAMPLE_DIR, frame_count=31)
        frame_count = len(list(sample_dir.glob("frame_*.*")))
        checks.append(("标准样例", frame_count == 31, f"{frame_count} 帧已就绪" if frame_count == 31 else "数据不完整"))
    except Exception:
        checks.append(("标准样例", False, "数据不可用"))

    try:
        import cv2  # noqa: F401
        import numpy  # noqa: F401
        import pandas  # noqa: F401
        checks.append(("图像处理", True, "正常"))
    except Exception:
        checks.append(("图像处理", False, "不可用"))

    try:
        import pyvista  # noqa: F401
        from pyvistaqt import QtInteractor  # noqa: F401
        checks.append(("三维重建", True, "正常"))
    except Exception:
        checks.append(("三维重建", False, "不可用"))

    try:
        import reportlab  # noqa: F401
        import matplotlib  # noqa: F401
        checks.append(("报告输出", True, "正常"))
    except Exception:
        checks.append(("报告输出", False, "不可用"))

    return checks


def restore_standard_sample() -> tuple[bool, str]:
    try:
        if SAMPLE_DIR.exists():
            shutil.rmtree(SAMPLE_DIR)
        SAMPLE_DIR.mkdir(parents=True, exist_ok=True)
        copied = 0
        if BACKUP_DIR.exists():
            for file in BACKUP_DIR.glob("frame_*.*"):
                shutil.copy2(file, SAMPLE_DIR / file.name)
                copied += 1
        if copied != 31:
            ensure_demo_frames(SAMPLE_DIR, frame_count=31)
        return True, "标准样例已恢复。"
    except Exception as exc:
        logging.exception("Restore standard sample failed")
        return False, str(exc)


def process_image_directory(window: MainWindow, directory: Path, label: str = "图像数据") -> None:
    session = OUTPUT_ROOT / "offline_reconstruction" / f"{window.task.sample_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    window.log(f"开始处理{label}……")
    window.reconstruction = reconstruct_directory(directory, session)
    window.points = window.reconstruction["points"]
    window.result = analyze_groove(window.points)
    window.render_points()
    window.update_images()
    window.update_results()
    window.log(
        f"处理完成：{window.reconstruction['valid_frames']}/{window.reconstruction['original_frames']} 帧有效，"
        f"点云 {window.reconstruction['point_count']} 点。"
    )


def run_standard_sample(window: MainWindow) -> None:
    try:
        if window.data_nature.count() > 0:
            window.data_nature.setCurrentIndex(0)
        window.apply_task()
        sample_dir = ensure_demo_frames(SAMPLE_DIR, frame_count=31)
        process_image_directory(window, sample_dir, "标准样例")
    except Exception:
        logging.exception("Standard sample measurement failed")
        QMessageBox.critical(
            window,
            "样例测量未完成",
            "标准样例测量未能完成。请执行“系统检测”或“恢复标准样例”后重试。",
        )


def import_point_cloud_product(window: MainWindow) -> None:
    filename, _ = QFileDialog.getOpenFileName(window, "导入点云文件", str(APP_ROOT), "Point Cloud (*.csv *.ply *.pcd *.xyz)")
    if not filename:
        return
    try:
        window.apply_task()
        window.data_nature.setCurrentText("外部点云")
        window.points = base_gui.load_point_cloud(Path(filename))
        window.reconstruction = {
            "points": window.points,
            "source_dir": str(Path(filename).parent),
            "point_cloud_csv": filename,
            "original_frames": 0,
            "valid_frames": 0,
            "point_count": int(window.points.shape[0]),
            "read_seconds": 0.0,
            "calibration_applied": False,
            "preview_original": "",
            "preview_overlay": "",
            "preview_mask": "",
        }
        window.result = analyze_groove(window.points)
        window.render_points()
        window.update_results()
        window.log(f"点云导入完成，共 {window.points.shape[0]} 点。")
    except Exception:
        logging.exception("Point cloud import failed")
        QMessageBox.critical(window, "导入失败", "点云文件无法读取，请检查文件格式。")


def analyze_current_product(window: MainWindow) -> None:
    if window.points is None:
        QMessageBox.information(window, "提示", "请先加载标准样例、原始图像或外部点云。")
        return
    window.analyze_current()


def generate_report_product(window: MainWindow) -> None:
    if not window.task or not window.reconstruction or not window.result:
        QMessageBox.information(window, "提示", "请先完成一次测量分析。")
        return
    report_dir = OUTPUT_ROOT / "reports" / datetime.now().strftime("%Y-%m-%d")
    report_path = report_dir / f"{window.task.sample_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_measurement_report.pdf"
    try:
        window.last_report, report_seconds = base_gui.generate_measurement_report(
            window.task, window.reconstruction, window.result, report_path
        )
        depth_status = "合格" if abs(window.result.depth_mean - window.task.target_depth_mm) <= window.task.tolerance_mm else "超差"
        width_status = "合格" if abs(window.result.width_mean - window.task.target_width_mm) <= window.task.tolerance_mm else "超差"
        base_gui.append_history(base_gui.HISTORY_PATH, {
            "sample_id": window.task.sample_id,
            "groove_type": window.task.groove_type,
            "data_nature": window.task.data_nature,
            "target_depth_mm": window.task.target_depth_mm,
            "measured_depth_mm": window.result.depth_mean,
            "target_width_mm": window.task.target_width_mm,
            "measured_width_mm": window.result.width_mean,
            "tolerance_mm": window.task.tolerance_mm,
            "depth_status": depth_status,
            "width_status": width_status,
            "point_count": window.reconstruction.get("point_count", 0),
            "valid_sections": len(window.result.sections),
            "read_seconds": window.reconstruction.get("read_seconds", 0),
            "analysis_seconds": window.result.analysis_seconds,
            "report_seconds": report_seconds,
            "report_path": str(window.last_report),
        })
        window.log("PDF 测量报告已生成。")
        QMessageBox.information(window, "报告生成成功", "测量报告已生成并保存至输出结果目录。")
    except Exception:
        logging.exception("Report generation failed")
        QMessageBox.critical(window, "报告生成失败", "报告生成未完成，请稍后重试。")


def show_history_product(window: MainWindow) -> None:
    rows = base_gui.read_recent_history(base_gui.HISTORY_PATH, limit=20)
    dialog = QDialog(window)
    dialog.setWindowTitle("最近测量历史")
    dialog.resize(900, 500)
    layout = QVBoxLayout(dialog)
    text = QTextEdit()
    text.setReadOnly(True)
    if rows:
        lines = []
        for row in reversed(rows):
            lines.append(
                f"{row.get('timestamp')} | {row.get('sample_id')} | "
                f"槽深 {row.get('measured_depth_mm')} mm（{row.get('depth_status')}） | "
                f"槽宽 {row.get('measured_width_mm')} mm（{row.get('width_status')}）"
            )
        text.setPlainText("\n".join(lines))
    else:
        text.setPlainText("暂无历史记录。完成测量并生成报告后自动写入。")
    layout.addWidget(text)
    dialog.exec()


def open_output_folder_product(window: MainWindow) -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    try:
        if hasattr(os, "startfile"):
            os.startfile(str(OUTPUT_ROOT))
        else:
            QMessageBox.information(window, "输出结果", "输出文件保存在软件目录下的 outputs 文件夹。")
    except Exception:
        logging.exception("Open output folder failed")
        QMessageBox.information(window, "输出结果", "输出文件保存在软件目录下的 outputs 文件夹。")


def configure_product_main_window(window: MainWindow) -> None:
    window.setWindowTitle("槽型深度宽度测量软件")
    window.sample_id.setText("SAMPLE-V-001")
    if window.data_nature.count() > 0:
        window.data_nature.setItemText(0, "标准样例数据")
        window.data_nature.setCurrentIndex(0)
    window.notes.setText("标准样例测量")

    # Replace the original image-processing method so logs remain concise and product-facing.
    window._run_image_directory = lambda directory: process_image_directory(window, Path(directory), "图像数据")

    button_actions = {
        "运行内置演示": ("标准样例测量", lambda: run_standard_sample(window)),
        "导入点云文件": ("导入点云文件", lambda: import_point_cloud_product(window)),
        "重新分析当前点云": ("重新分析当前点云", lambda: analyze_current_product(window)),
        "生成 PDF 报告": ("生成 PDF 报告", lambda: generate_report_product(window)),
        "查看历史记录": ("查看历史记录", lambda: show_history_product(window)),
        "显示输出目录": ("打开输出结果", lambda: open_output_folder_product(window)),
    }
    for button in window.findChildren(QPushButton):
        if button.text() in button_actions:
            new_text, action = button_actions[button.text()]
            button.setText(new_text)
            try:
                button.clicked.disconnect()
            except (TypeError, RuntimeError):
                pass
            button.clicked.connect(lambda checked=False, fn=action: fn())

    for label in window.findChildren(QLabel):
        if label.text() == "运行演示或导入图片后显示":
            label.setText("完成样例测量或导入图片后显示")

    window.console.clear()
    window.apply_task()
    window.log("系统已启动，测量模块就绪。")


class ProductLauncher(QDialog):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("槽型深度宽度测量软件")
        self.setMinimumSize(760, 540)
        self.main_window: MainWindow | None = None
        self._build_ui()
        self.refresh_checks()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(34, 28, 34, 28)
        layout.setSpacing(16)

        title = QLabel("槽型深度宽度测量软件")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignCenter)
        subtitle = QLabel("结构光图像处理 · 三维点云重建 · 槽型尺寸分析")
        subtitle.setObjectName("subtitle")
        subtitle.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        layout.addWidget(subtitle)

        card = QWidget()
        card.setObjectName("statusCard")
        grid = QGridLayout(card)
        grid.setContentsMargins(24, 20, 24, 20)
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(14)
        self.status_grid = grid
        layout.addWidget(card)

        self.overall = QLabel("正在检查系统……")
        self.overall.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.overall)

        self.start_button = QPushButton("标准样例测量")
        self.start_button.setObjectName("primary")
        self.start_button.setMinimumHeight(58)
        self.start_button.clicked.connect(self.start_standard_sample)
        layout.addWidget(self.start_button)

        bottom = QGridLayout()
        refresh_button = QPushButton("系统检测")
        refresh_button.clicked.connect(self.refresh_checks)
        restore_button = QPushButton("恢复标准样例")
        restore_button.clicked.connect(self.restore_data)
        system_button = QPushButton("进入测量系统")
        system_button.clicked.connect(self.open_main_window)
        bottom.addWidget(refresh_button, 0, 0)
        bottom.addWidget(restore_button, 0, 1)
        bottom.addWidget(system_button, 0, 2)
        layout.addLayout(bottom)

        hint = QLabel("支持标准样例、原始激光图像与外部点云三类数据输入。测量结果可生成 PDF 报告并保存历史记录。")
        hint.setWordWrap(True)
        hint.setAlignment(Qt.AlignCenter)
        hint.setObjectName("hint")
        layout.addWidget(hint)

        self.setStyleSheet("""
        QDialog, QWidget { background:#182028; color:#eaf1f6; font-family:'Microsoft YaHei UI'; font-size:10.5pt; }
        QLabel#title { font-size:24pt; font-weight:700; color:white; }
        QLabel#subtitle { color:#8fa8ba; font-size:11pt; padding-bottom:4px; }
        QWidget#statusCard { background:#141b22; border:1px solid #2f3d48; border-radius:10px; }
        QLabel#hint { color:#9eb0bd; padding-top:6px; }
        QPushButton { background:#2a3640; border:1px solid #4a5a66; border-radius:6px; padding:10px; }
        QPushButton:hover { background:#34434e; }
        QPushButton#primary { background:#087f76; border-color:#16b5a8; font-size:14pt; font-weight:700; }
        QPushButton#primary:hover { background:#0a978c; }
        """)

    def refresh_checks(self) -> None:
        while self.status_grid.count():
            item = self.status_grid.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        checks = check_system()
        all_ok = True
        for row, (name, ok, detail) in enumerate(checks):
            all_ok &= ok
            icon = QLabel("●")
            icon.setStyleSheet("color:#65e58a;font-size:14pt;" if ok else "color:#ff7474;font-size:14pt;")
            label = QLabel(name)
            label.setStyleSheet("font-weight:600;")
            detail_label = QLabel(detail)
            detail_label.setStyleSheet("color:#93a7b5;")
            self.status_grid.addWidget(icon, row, 0)
            self.status_grid.addWidget(label, row, 1)
            self.status_grid.addWidget(detail_label, row, 2)

        if all_ok:
            self.overall.setText("系统状态：就绪")
            self.overall.setStyleSheet("color:#70e895;background:#102019;padding:10px;border-radius:6px;font-size:13pt;font-weight:700;")
            self.start_button.setEnabled(True)
        else:
            self.overall.setText("系统状态：需要检查")
            self.overall.setStyleSheet("color:#ff8383;background:#261616;padding:10px;border-radius:6px;font-size:13pt;font-weight:700;")
            self.start_button.setEnabled(False)

    def restore_data(self) -> None:
        ok, message = restore_standard_sample()
        QMessageBox.information(self, "恢复标准样例" if ok else "恢复失败", message)
        self.refresh_checks()

    def open_main_window(self) -> None:
        if self.main_window is None:
            self.main_window = MainWindow()
            configure_product_main_window(self.main_window)
        self.main_window.showMaximized()
        self.hide()

    def start_standard_sample(self) -> None:
        self.open_main_window()
        QApplication.processEvents()
        run_standard_sample(self.main_window)


def main() -> int:
    configure_logging()
    sys.excepthook = exception_hook
    logging.info("Application start")
    app = QApplication(sys.argv)
    app.setApplicationName("槽型深度宽度测量软件")
    launcher = ProductLauncher()
    launcher.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
