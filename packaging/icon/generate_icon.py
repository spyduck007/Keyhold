"""Render AppIcon.png (1024x1024) — the source master for AppIcon.icns.

Run this, then rebuild the .icns with:

    sips -z <n> <n> AppIcon.png --out AppIcon.iconset/icon_<n>x<n>.png   # for each required size
    iconutil -c icns AppIcon.iconset -o AppIcon.icns

See scripts/build_macos_app.sh for the full pipeline.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QGuiApplication,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPixmap,
    QPolygonF,
)

SIZE = 1024
OUTPUT_PATH = Path(__file__).with_name("AppIcon.png")


def main() -> None:
    app = QGuiApplication(sys.argv)
    del app

    pixmap = QPixmap(SIZE, SIZE)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    _draw_background(painter)
    _draw_shield_glyph(painter)

    painter.end()
    pixmap.save(str(OUTPUT_PATH))
    print(f"saved {OUTPUT_PATH}")


def _draw_background(painter: QPainter) -> None:
    # Rounded square in the app's dark navy, matching SURFACE_0/SURFACE_2
    # from theme.py, with a subtle gradient for depth.
    bg_path = QPainterPath()
    corner_radius = SIZE * 0.223  # macOS-style squircle-ish corner radius
    bg_path.addRoundedRect(QRectF(0, 0, SIZE, SIZE), corner_radius, corner_radius)

    gradient = QLinearGradient(QPointF(0, 0), QPointF(0, SIZE))
    gradient.setColorAt(0.0, QColor("#152338"))
    gradient.setColorAt(1.0, QColor("#08111f"))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QBrush(gradient))
    painter.drawPath(bg_path)


def _draw_shield_glyph(painter: QPainter) -> None:
    # Glyph is authored in a 0-100 local coordinate box, then scaled and
    # centered onto the full canvas with a margin.
    glyph_size = SIZE * 0.62
    offset_x = (SIZE - glyph_size) / 2
    offset_y = (SIZE - glyph_size) / 2 - SIZE * 0.015
    painter.translate(offset_x, offset_y)
    scale = glyph_size / 100.0
    painter.scale(scale, scale)

    shield = QPainterPath()
    shield.addPolygon(
        QPolygonF(
            [
                QPointF(50, 2),
                QPointF(90, 16),
                QPointF(90, 46),
                QPointF(50, 98),
                QPointF(10, 46),
                QPointF(10, 16),
            ]
        )
    )
    shield.closeSubpath()

    # Keyhole cutout: a circle plus a tapered stem, merged into one hole.
    keyhole = QPainterPath()
    keyhole.addEllipse(QRectF(38, 30, 24, 24))

    stem = QPainterPath()
    stem.addPolygon(
        QPolygonF(
            [
                QPointF(44, 48),
                QPointF(56, 48),
                QPointF(60, 74),
                QPointF(40, 74),
            ]
        )
    )
    stem.closeSubpath()

    keyhole = keyhole.united(stem)
    shield_with_hole = shield.subtracted(keyhole)

    shield_gradient = QLinearGradient(QPointF(10, 2), QPointF(90, 98))
    shield_gradient.setColorAt(0.0, QColor("#7CE9D8"))
    shield_gradient.setColorAt(1.0, QColor("#34B39E"))
    painter.setBrush(QBrush(shield_gradient))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawPath(shield_with_hole)


if __name__ == "__main__":
    main()
