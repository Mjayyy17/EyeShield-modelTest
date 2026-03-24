"""
Main entry point for EyeShield EMR with segmented modules.
Run this file to start the application with the segmented code structure.
"""

import sys
import traceback
from pathlib import Path

# Add parent directory to path to import auth module when running from project root
sys.path.insert(0, str(Path(__file__).parent.parent))


from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtGui import QIcon, QPixmap, QImage, QPainter, QFont, QFontDatabase
from PySide6.QtSvg import QSvgRenderer
from auth import UserManager
from login import LoginWindow
from safety_runtime import get_results_dir, write_activity, write_crash_log


def load_svg_icon(svg_path, size=256):
    """Render an SVG file to a QIcon."""
    renderer = QSvgRenderer(svg_path)
    if not renderer.isValid():
        return QIcon()
    image = QImage(size, size, QImage.Format_ARGB32_Premultiplied)
    image.fill(0)
    painter = QPainter(image)
    renderer.render(painter)
    painter.end()
    return QIcon(QPixmap.fromImage(image))


if __name__ == "__main__":
    app = QApplication(sys.argv)

    def _crash_hook(exc_type, exc_value, exc_tb):
        try:
            crash_file = write_crash_log(exc_type, exc_value, exc_tb, app_state="main")
            write_activity("ERROR", "APP_CRASH", f"Crash log: {crash_file}")
        except Exception:
            pass
        traceback.print_exception(exc_type, exc_value, exc_tb)

    sys.excepthook = _crash_hook

    # Modern font — Segoe UI Variable is available on Windows 11; falls back gracefully
    modern_font = QFont("Segoe UI Variable", 11)
    if not modern_font.exactMatch():
        modern_font = QFont("Segoe UI", 11)
    modern_font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    app.setFont(modern_font)

    # Enforce font family globally via stylesheet
    app.setStyleSheet("* { font-family: 'Segoe UI Variable', 'Segoe UI', 'Inter', 'Arial', sans-serif; font-size: 13px; text-decoration: none; }")

    # Set application-wide icon
    import os
    _icon_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons")
    _logo_path = os.path.join(_icon_dir, "Logo.png")
    _fallback_icon_path = os.path.join(_icon_dir, "eyeshield_icon.svg")
    if os.path.isfile(_logo_path):
        app.setWindowIcon(QIcon(_logo_path))
    else:
        app.setWindowIcon(load_svg_icon(_fallback_icon_path))

    # Initialize the database
    UserManager._init_db()

    # Validate write access to local results directory on launch.
    _results_dir_display = "unknown path"
    try:
        _results_dir = get_results_dir()
        _results_dir_display = str(_results_dir)
    except OSError as err:
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Icon.Critical)
        msg.setWindowTitle("Storage Error")
        msg.setText(f"Cannot access results directory at {_results_dir_display}. Check folder permissions.")
        msg.setInformativeText(str(err))
        msg.addButton("Exit", QMessageBox.ButtonRole.RejectRole)
        msg.exec()
        sys.exit(1)

    # Begin loading the DR model in the background so it is warm before the
    # user navigates to the Screening page (eliminates first-scan delay).
    from model_inference import preload_model_async, is_model_available, MODEL_PATH
    if not is_model_available():
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Icon.Critical)
        msg.setWindowTitle("Model Error")
        msg.setText("Model file not found or corrupted. Please reinstall the application.")
        msg.setInformativeText(f"Expected model path:\n{MODEL_PATH}")
        copy_btn = msg.addButton("Copy Error", QMessageBox.ButtonRole.ActionRole)
        exit_btn = msg.addButton("Exit", QMessageBox.ButtonRole.RejectRole)
        msg.exec()
        if msg.clickedButton() == copy_btn:
            app.clipboard().setText(f"Model file not found or corrupted: {MODEL_PATH}")
        if msg.clickedButton() in (copy_btn, exit_btn):
            sys.exit(1)

    preload_model_async()
    write_activity("INFO", "APP_OPENED", "EyeShield launched")
    app.aboutToQuit.connect(lambda: write_activity("INFO", "APP_CLOSED", "Application exit"))

    win = LoginWindow()
    win.show()

    sys.exit(app.exec())
