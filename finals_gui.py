"""Finals launcher: no-console, self-check-first entry point for on-site demo."""
from __future__ import annotations

import logging
import shutil
import sys
import traceback
from datetime import datetime
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
from gui import MainWindow, OUTPUT_ROOT, DEMO_DIR, ROOT

LOG_DIR = ROOT / "logs"
LOG_FILE = LOG_DIR / "finals_app.log"
BACKUP_DIR = ROOT / "finals_assets" / "demo_backup"


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
            "软件遇到异常，详细信息已写入 logs/finals_app.log。\n\n"
            "请先点击“恢复演示数据”后重试；如仍无法运行，请切换到备用演示材料。",
        )


def check_system() -> list[tuple[str, bool, str]]:
    checks: list[tuple[str, bool, str]] = []

    try:
        OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
        probe = OUTPUT_ROOT / ".write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        checks.append(("输出目录可写", True, str(OUTPUT_ROOT)))
    except Exception as exc:
        checks.append(("输出目录可写", False, str(exc)))

    try:
        demo_dir = ensure_demo_frames(DEMO_DIR, frame_count=31)
        frame_count = len(list(demo_dir.glob("frame_*.*")))
        checks.append(("标准演示数据", frame_count == 31, f"{frame_count}/31 帧"))
    except Exception as exc:
        checks.append(("标准演示数据", False, str(exc)))

    try:
        import cv2  # noqa: F401
        import numpy  # noqa: F401
        import pandas  # noqa: F401
        checks.append(("图像与数据模块", True, "OpenCV / NumPy / Pandas"))
    except Exception as exc:
        checks.append(("图像与数据模块", False, str(exc)))

    try:
        import pyvista  # noqa: F401
        from pyvistaqt import QtInteractor  # noqa: F401
        checks.append(("三维点云模块", True, "PyVista / VTK"))
    except Exception as exc:
        checks.append(("三维点云模块", False, str(exc)))

    try:
        import reportlab  # noqa: F401
        import matplotlib  # noqa: F401
        checks.append(("报告模块", True, "ReportLab / Matplotlib"))
    except Exception as exc:
        checks.append(("报告模块", False, str(exc)))

    return checks


def restore_demo_data() -> tuple[bool, str]:
    try:
        if DEMO_DIR.exists():
            shutil.rmtree(DEMO_DIR)
        DEMO_DIR.mkdir(parents=True, exist_ok=True)
        ensure_demo_frames(DEMO_DIR, frame_count=31)
        return True, "标准演示数据已恢复。"
    except Exception as exc:
        logging.exception("Restore demo data failed")
        return False, str(exc)


class FinalsLauncher(QDialog):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("槽型深度宽度测量软件 · 决赛现场版")
        self.setMinimumSize(760, 560)
        self.main_window: MainWindow | None = None
        self.status_labels: list[QLabel] = []
        self._build_ui()
        self.refresh_checks()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)

        title = QLabel("槽型深度宽度测量软件")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignCenter)
        subtitle = QLabel("决赛现场冻结版 · Finals v1.0")
        subtitle.setObjectName("subtitle")
        subtitle.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        layout.addWidget(subtitle)

        card = QWidget()
        grid = QGridLayout(card)
        grid.setContentsMargins(18, 18, 18, 18)
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(12)
        self.status_grid = grid
        layout.addWidget(card)

        self.overall = QLabel("正在检查系统……")
        self.overall.setAlignment(Qt.AlignCenter)
        self.overall.setObjectName("overall")
        layout.addWidget(self.overall)

        self.start_button = QPushButton("开始现场演示")
        self.start_button.setObjectName("primary")
        self.start_button.setMinimumHeight(58)
        self.start_button.clicked.connect(self.start_demo)
        layout.addWidget(self.start_button)

        bottom = QGridLayout()
        refresh_button = QPushButton("重新自检")
        refresh_button.clicked.connect(self.refresh_checks)
        restore_button = QPushButton("恢复演示数据")
        restore_button.clicked.connect(self.restore_data)
        advanced_button = QPushButton("进入完整软件")
        advanced_button.clicked.connect(self.open_main_window)
        bottom.addWidget(refresh_button, 0, 0)
        bottom.addWidget(restore_button, 0, 1)
        bottom.addWidget(advanced_button, 0, 2)
        layout.addLayout(bottom)

        hint = QLabel("现场建议：优先点击“开始现场演示”。所有异常写入 logs/finals_app.log，不显示代码 traceback。")
        hint.setWordWrap(True)
        hint.setObjectName("hint")
        layout.addWidget(hint)

        self.setStyleSheet("""
        QDialog, QWidget { background:#182028; color:#eaf1f6; font-family:'Microsoft YaHei UI'; font-size:10.5pt; }
        QLabel#title { font-size:24pt; font-weight:700; color:white; }
        QLabel#subtitle { color:#8fa8ba; font-size:11pt; }
        QLabel#overall { font-size:13pt; font-weight:700; padding:10px; border-radius:6px; background:#11181e; }
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
            detail_label = QLabel(detail)
            detail_label.setStyleSheet("color:#93a7b5;")
            detail_label.setWordWrap(True)
            self.status_grid.addWidget(icon, row, 0)
            self.status_grid.addWidget(label, row, 1)
            self.status_grid.addWidget(detail_label, row, 2)

        if all_ok:
            self.overall.setText("系统状态：就绪")
            self.overall.setStyleSheet("color:#70e895;background:#102019;padding:10px;border-radius:6px;")
            self.start_button.setEnabled(True)
        else:
            self.overall.setText("系统状态：需要处理")
            self.overall.setStyleSheet("color:#ff8383;background:#261616;padding:10px;border-radius:6px;")
            self.start_button.setEnabled(False)

    def restore_data(self) -> None:
        ok, message = restore_demo_data()
        QMessageBox.information(self, "恢复演示数据" if ok else "恢复失败", message)
        self.refresh_checks()

    def open_main_window(self) -> None:
        if self.main_window is None:
            self.main_window = MainWindow()
        self.main_window.showMaximized()
        self.hide()

    def start_demo(self) -> None:
        logging.info("Finals demo started at %s", datetime.now().isoformat())
        self.open_main_window()
        QApplication.processEvents()
        try:
            self.main_window.run_demo()
        except Exception:
            logging.exception("Finals demo run failed")
            QMessageBox.critical(
                self.main_window,
                "现场演示未完成",
                "标准演示未能完成。请返回启动页，点击“恢复演示数据”后重试。",
            )


def main() -> int:
    configure_logging()
    sys.excepthook = exception_hook
    logging.info("Application start")
    app = QApplication(sys.argv)
    app.setApplicationName("槽型深度宽度测量软件")
    launcher = FinalsLauncher()
    launcher.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
