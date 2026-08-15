"""Product entry point for the groove depth and width measurement software."""
from __future__ import annotations

import logging
import os
import sys
import traceback
from datetime import datetime
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from history_manager import append_history, read_recent_history
from measurement_analysis import analyze_groove
from offline_reconstruction import reconstruct_directory
from report_generator import generate_measurement_report
import gui as base_gui

APP_ROOT = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
OUTPUT_ROOT = APP_ROOT / "outputs"
DATA_ROOT = APP_ROOT / "data"
LOG_DIR = APP_ROOT / "logs"
LOG_FILE = LOG_DIR / "app.log"
HISTORY_PATH = OUTPUT_ROOT / "history" / "measurement_history.csv"

base_gui.ROOT = APP_ROOT
base_gui.OUTPUT_ROOT = OUTPUT_ROOT
base_gui.HISTORY_PATH = HISTORY_PATH
MainWindow = base_gui.MainWindow


def configure_logging() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=str(LOG_FILE), level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s", encoding="utf-8")


def exception_hook(exc_type, exc_value, exc_tb) -> None:
    logging.critical("Unhandled exception\n%s", "".join(traceback.format_exception(exc_type, exc_value, exc_tb)))
    if QApplication.instance() is not None:
        QMessageBox.critical(None, "软件运行异常", "软件运行过程中出现异常。请重新启动软件；如问题出现在数据导入阶段，请检查数据格式。")


def process_image_directory(window: MainWindow, directory: Path) -> None:
    session = OUTPUT_ROOT / "reconstruction" / f"{window.task.sample_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    window.log("开始读取图像序列并进行三维重建……")
    window.reconstruction = reconstruct_directory(directory, session)
    window.points = window.reconstruction["points"]
    window.result = analyze_groove(window.points)
    window.render_points()
    window.update_images()
    window.update_results()
    window.log(f"处理完成：{window.reconstruction['valid_frames']}/{window.reconstruction['original_frames']} 帧有效，点云 {window.reconstruction['point_count']} 点。")


def import_image_sequence(window: MainWindow) -> None:
    start_dir = DATA_ROOT if DATA_ROOT.exists() else APP_ROOT
    directory = QFileDialog.getExistingDirectory(window, "导入图像序列", str(start_dir))
    if not directory:
        return
    try:
        window.apply_task()
        window.data_nature.setCurrentText("图像序列数据")
        process_image_directory(window, Path(directory))
    except Exception:
        logging.exception("Image sequence import failed")
        QMessageBox.critical(window, "图像序列处理失败", "所选图像序列未能完成处理，请检查图像格式与数据完整性。")


def import_point_cloud(window: MainWindow) -> None:
    start_dir = DATA_ROOT if DATA_ROOT.exists() else APP_ROOT
    filename, _ = QFileDialog.getOpenFileName(window, "导入点云文件", str(start_dir), "Point Cloud (*.csv *.ply *.pcd *.xyz)")
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
        QMessageBox.critical(window, "点云导入失败", "点云文件无法读取，请检查文件格式。")


def analyze_current(window: MainWindow) -> None:
    if window.points is None:
        QMessageBox.information(window, "提示", "请先导入图像序列或点云数据。")
        return
    try:
        window.result = analyze_groove(window.points)
        window.update_results()
        window.render_points()
        window.log("当前点云重新分析完成。")
    except Exception:
        logging.exception("Re-analysis failed")
        QMessageBox.critical(window, "分析失败", "当前点云未能完成分析，请检查数据质量。")


def generate_report(window: MainWindow) -> None:
    if not window.task or not window.reconstruction or not window.result:
        QMessageBox.information(window, "提示", "请先完成一次测量分析。")
        return

    report_dir = OUTPUT_ROOT / "reports" / datetime.now().strftime("%Y-%m-%d")
    report_path = report_dir / f"{window.task.sample_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_measurement_report.pdf"
    try:
        window.last_report, report_seconds = generate_measurement_report(window.task, window.reconstruction, window.result, report_path)
        depth_status = "合格" if abs(window.result.depth_mean - window.task.target_depth_mm) <= window.task.tolerance_mm else "超差"
        width_status = "合格" if abs(window.result.width_mean - window.task.target_width_mm) <= window.task.tolerance_mm else "超差"
        append_history(HISTORY_PATH, {
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
        QMessageBox.information(window, "报告生成成功", "测量报告已保存至输出结果目录。")
    except Exception:
        logging.exception("Report generation failed")
        QMessageBox.critical(window, "报告生成失败", "报告生成未完成，请稍后重试。")


def show_history(window: MainWindow) -> None:
    rows = read_recent_history(HISTORY_PATH, limit=20)
    dialog = QDialog(window)
    dialog.setWindowTitle("最近测量历史")
    dialog.resize(900, 500)
    layout = QVBoxLayout(dialog)
    text = QTextEdit()
    text.setReadOnly(True)
    if rows:
        text.setPlainText("\n".join(
            f"{row.get('timestamp')} | {row.get('sample_id')} | 槽深均值 {row.get('measured_depth_mm')} mm（{row.get('depth_status')}） | 槽宽均值 {row.get('measured_width_mm')} mm（{row.get('width_status')}）"
            for row in reversed(rows)
        ))
    else:
        text.setPlainText("暂无历史记录。完成测量并生成报告后自动写入。")
    layout.addWidget(text)
    dialog.exec()


def open_output_folder(window: MainWindow) -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    try:
        if hasattr(os, "startfile"):
            os.startfile(str(OUTPUT_ROOT))
        else:
            QMessageBox.information(window, "输出结果", "输出文件保存在软件目录下的 outputs 文件夹。")
    except Exception:
        logging.exception("Open output folder failed")
        QMessageBox.information(window, "输出结果", "输出文件保存在软件目录下的 outputs 文件夹。")


def configure_main_window(window: MainWindow) -> None:
    window.setWindowTitle("槽型深度宽度测量软件")
    window.sample_id.setText("SAMPLE-001")
    window.notes.clear()

    window.data_nature.clear()
    window.data_nature.addItems(["图像序列数据", "外部点云"])
    window.data_nature.setCurrentIndex(0)
    window._run_image_directory = lambda directory: process_image_directory(window, Path(directory))

    for button in window.findChildren(QPushButton):
        text = button.text()
        if text == "运行内置演示":
            button.hide()
            continue
        if text == "选择原始图片目录":
            button.setText("导入图像序列")
            try:
                button.clicked.disconnect()
            except (TypeError, RuntimeError):
                pass
            button.clicked.connect(lambda checked=False: import_image_sequence(window))
        elif text == "导入点云文件":
            try:
                button.clicked.disconnect()
            except (TypeError, RuntimeError):
                pass
            button.clicked.connect(lambda checked=False: import_point_cloud(window))
        elif text == "重新分析当前点云":
            try:
                button.clicked.disconnect()
            except (TypeError, RuntimeError):
                pass
            button.clicked.connect(lambda checked=False: analyze_current(window))
        elif text == "生成 PDF 报告":
            try:
                button.clicked.disconnect()
            except (TypeError, RuntimeError):
                pass
            button.clicked.connect(lambda checked=False: generate_report(window))
        elif text == "查看历史记录":
            try:
                button.clicked.disconnect()
            except (TypeError, RuntimeError):
                pass
            button.clicked.connect(lambda checked=False: show_history(window))
        elif text == "显示输出目录":
            button.setText("打开输出结果")
            try:
                button.clicked.disconnect()
            except (TypeError, RuntimeError):
                pass
            button.clicked.connect(lambda checked=False: open_output_folder(window))

    for label in window.findChildren(QLabel):
        text = label.text()
        if text == "运行演示或导入图片后显示":
            label.setText("导入图像序列后显示")
        elif text == "槽深判定":
            label.setText("槽深均值判定")
        elif text == "槽宽判定":
            label.setText("槽宽均值判定")

    window.console.clear()
    window.apply_task()
    window.log("系统已启动，测量模块就绪。")


def main() -> int:
    configure_logging()
    sys.excepthook = exception_hook
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    app = QApplication(sys.argv)
    app.setApplicationName("槽型深度宽度测量软件")
    window = MainWindow()
    configure_main_window(window)
    window.showMaximized()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
