"""Product launcher for the groove depth and width measurement software."""
from __future__ import annotations

import logging
import shutil
import sys
import traceback
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QGridLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from demo_data import ensure_demo_frames
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


def run_standard_sample(window: MainWindow) -> None:
    try:
        if window.data_nature.count() > 0:
            window.data_nature.setCurrentIndex(0)
        window.apply_task()
        sample_dir = ensure_demo_frames(SAMPLE_DIR, frame_count=31)
        window._run_image_directory(sample_dir)
    except Exception:
        logging.exception("Standard sample measurement failed")
        QMessageBox.critical(
            window,
            "样例测量未完成",
            "标准样例测量未能完成。请执行“系统检测”或“恢复标准样例”后重试。",
        )


def configure_product_main_window(window: MainWindow) -> None:
    window.setWindowTitle("槽型深度宽度测量软件")
    window.sample_id.setText("SAMPLE-V-001")
    if window.data_nature.count() > 0:
        window.data_nature.setItemText(0, "标准样例数据")
        window.data_nature.setCurrentIndex(0)
    window.notes.setText("标准样例测量")

    for button in window.findChildren(QPushButton):
        if button.text() == "运行内置演示":
            button.setText("标准样例测量")
            try:
                button.clicked.disconnect()
            except (TypeError, RuntimeError):
                pass
            button.clicked.connect(lambda checked=False: run_standard_sample(window))

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
