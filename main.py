"""
Main entry point for EyeShield EMR with segmented modules.
Run this file to start the application with the segmented code structure.
"""

import sys
from pathlib import Path

# Add parent directory to path to import auth module when running from project root
sys.path.insert(0, str(Path(__file__).parent.parent))


from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon, QPixmap, QImage, QPainter, QFont, QFontDatabase
from PySide6.QtSvg import QSvgRenderer
from auth import UserManager
from login import LoginWindow


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

    # Begin loading the DR model in the background so it is warm before the
    # user navigates to the Screening page (eliminates first-scan delay).
    from model_inference import preload_model_async
    preload_model_async()

    win = LoginWindow()
    win.show()

    sys.exit(app.exec())
