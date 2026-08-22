"""Render the source SVG into a multi-resolution Windows icon."""

from pathlib import Path

from PIL import Image
from PyQt6.QtCore import QByteArray, QSize
from PyQt6.QtGui import QGuiApplication, QImage, QPainter
from PyQt6.QtSvg import QSvgRenderer


ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "assets" / "AimCompanion.svg"
DESTINATION = ROOT / "assets" / "AimCompanion.ico"


def main():
    app = QGuiApplication.instance() or QGuiApplication([])
    renderer = QSvgRenderer(QByteArray(SOURCE.read_bytes()))
    images = []
    for size in (16, 24, 32, 48, 64, 128, 256):
        canvas = QImage(size, size, QImage.Format.Format_ARGB32)
        canvas.fill(0)
        painter = QPainter(canvas)
        renderer.render(painter)
        painter.end()
        png_path = DESTINATION.with_name(f"icon-{size}.png")
        canvas.save(str(png_path), "PNG")
        images.append((png_path, Image.open(png_path).convert("RGBA")))
    images[-1][1].save(
        DESTINATION, format="ICO",
        append_images=[image for _, image in images[:-1]],
        sizes=[(size, size) for size in (16, 24, 32, 48, 64, 128, 256)],
    )
    for path, image in images:
        image.close()
        path.unlink(missing_ok=True)
    app.quit()
    print(DESTINATION)


if __name__ == "__main__":
    main()
