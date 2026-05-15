#!/usr/bin/env python3
"""
Generate prompt-live.icns from prompt-live.svg using PyQt6.
Run from the project root:  python logo/make_icns.py
"""
import os
import sys
import subprocess
import shutil

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SVG_PATH   = os.path.join(SCRIPT_DIR, "prompt-live.svg")
ICONSET    = os.path.join(SCRIPT_DIR, "prompt-live.iconset")
ICNS_OUT   = os.path.join(SCRIPT_DIR, "prompt-live.icns")

ENTRIES = [
    ("icon_16x16.png",      16),
    ("icon_16x16@2x.png",   32),
    ("icon_32x32.png",      32),
    ("icon_32x32@2x.png",   64),
    ("icon_128x128.png",   128),
    ("icon_128x128@2x.png",256),
    ("icon_256x256.png",   256),
    ("icon_256x256@2x.png",512),
    ("icon_512x512.png",   512),
    ("icon_512x512@2x.png",1024),
]


def main():
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QImage, QPainter
    from PyQt6.QtSvg import QSvgRenderer
    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)

    if not os.path.exists(SVG_PATH):
        print(f"ERROR: SVG not found at {SVG_PATH}")
        sys.exit(1)

    renderer = QSvgRenderer(SVG_PATH)
    if not renderer.isValid():
        print("ERROR: SVG failed to load (invalid)")
        sys.exit(1)

    if os.path.exists(ICONSET):
        shutil.rmtree(ICONSET)
    os.makedirs(ICONSET)

    print(f"Rendering {len(ENTRIES)} icon sizes...")
    for filename, size in ENTRIES:
        img = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
        img.fill(0)
        painter = QPainter(img)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        renderer.render(painter)
        painter.end()
        out = os.path.join(ICONSET, filename)
        img.save(out, "PNG")
        print(f"  {filename:30s}  {size}x{size}")

    print(f"\nRunning iconutil...")
    subprocess.run(
        ["iconutil", "-c", "icns", ICONSET, "-o", ICNS_OUT],
        check=True,
    )
    shutil.rmtree(ICONSET)
    print(f"Done: {ICNS_OUT}")


if __name__ == "__main__":
    main()
