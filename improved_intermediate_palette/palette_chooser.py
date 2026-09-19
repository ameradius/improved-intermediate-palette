# SPDX-FileCopyrightText: 2026 ameradius
# SPDX-License-Identifier: GPL-3.0-or-later
# Based on an original concept by Tayete's Intermediate Palette.

import os
import json

from PyQt5.QtWidgets import (
    QWidget, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QScrollArea, QFrame, QFileDialog, QMessageBox
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QImage, QPixmap, qRgb

from .solvers import compute_palette_grid
from .serialization import dict_to_anchors


def render_palette_thumbnail(data, size=48):
    """Generate a preview map of the .json palette data."""
    anchors, rows, cols = dict_to_anchors(data)
    solver = data.get("solver", "Steady-State Heat Equation (Laplacian)")
    mixer = data.get("mixer", "Linear sRGB")
    colors = compute_palette_grid(rows, cols, anchors, solver, mixer)

    img = QImage(cols, rows, QImage.Format_RGB32)
    for r in range(rows):
        for c in range(cols):
            col = colors[r][c]
            img.setPixel(c, r, qRgb(col.red(), col.green(), col.blue()))

    scaled = img.scaled(size, size, Qt.IgnoreAspectRatio, Qt.FastTransformation)
    return QPixmap.fromImage(scaled)


class PaletteCardWidget(QFrame):
    doubleClicked = pyqtSignal(dict)
    loadRequested = pyqtSignal(dict)

    def __init__(self, name, file_path, data, parent=None):
        super().__init__(parent)
        self.name = name
        self.file_path = file_path
        self.data = data

        self.setFrameShape(QFrame.StyledPanel)
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet("""
            PaletteCardWidget {
                background-color: rgba(255, 255, 255, 0.03);
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 5px;
            }
            PaletteCardWidget:hover {
                background-color: rgba(255, 255, 255, 0.08);
                border-color: rgba(255, 255, 255, 0.35);
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(10)

        # Grid thumbnail
        self.lbl_thumb = QLabel()
        self.lbl_thumb.setFixedSize(50, 50)
        self.lbl_thumb.setStyleSheet("border: 1px solid #555; border-radius: 2px;")
        try:
            pixmap = render_palette_thumbnail(self.data, size=48)
            self.lbl_thumb.setPixmap(pixmap)
        except Exception:
            self.lbl_thumb.setText("Preview")
        self.lbl_thumb.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.lbl_thumb)

        # Name, solver/mixer, swatches of anchors
        info_layout = QVBoxLayout()
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(2)

        lbl_name = QLabel(self.name)
        font = lbl_name.font()
        font.setBold(True)
        font.setPointSize(10)
        lbl_name.setFont(font)
        info_layout.addWidget(lbl_name)

        solver = self.data.get("solver", "Steady-State Heat Equation (Laplacian)")
        mixer = self.data.get("mixer", "Linear sRGB")
        rows = self.data.get("rows", 12)
        cols = self.data.get("cols", 12)
        lbl_sub = QLabel(f"{solver} · {mixer} ({cols}×{rows})")
        lbl_sub.setStyleSheet("color: #aaa; font-size: 10px;")
        info_layout.addWidget(lbl_sub)

        # Swatch squares of anchors
        swatches_layout = QHBoxLayout()
        swatches_layout.setContentsMargins(0, 2, 0, 0)
        swatches_layout.setSpacing(3)
        swatches_layout.setAlignment(Qt.AlignLeft)

        anchors_dict = self.data.get("anchors", {})
        for key in list(anchors_dict.keys())[:14]:
            rgb = anchors_dict[key]
            sq = QFrame()
            sq.setFixedSize(12, 12)
            sq.setStyleSheet(f"background-color: rgb({rgb[0]},{rgb[1]},{rgb[2]}); border: 1px solid #444; border-radius: 1px;")
            swatches_layout.addWidget(sq)

        if len(anchors_dict) > 14:
            lbl_more = QLabel(f"+{len(anchors_dict) - 14}")
            lbl_more.setStyleSheet("color: #888; font-size: 9px;")
            swatches_layout.addWidget(lbl_more)

        info_layout.addLayout(swatches_layout)
        layout.addLayout(info_layout, stretch=1)

        # Load button
        self.btn_load = QPushButton("Load")
        self.btn_load.setFixedWidth(54)
        self.btn_load.setToolTip(f"Load '{self.name}' into the palette")
        self.btn_load.clicked.connect(lambda: self.loadRequested.emit(self.data))
        layout.addWidget(self.btn_load)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.doubleClicked.emit(self.data)
            event.accept()
        else:
            super().mouseDoubleClickEvent(event)


class PaletteChooserDialog(QDialog):
    paletteLoaded = pyqtSignal(dict)
    dirChanged = pyqtSignal(str)

    def __init__(self, current_dir, docker_ref=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Palette Chooser")
        self.resize(520, 440)
        self.setMinimumSize(400, 320)
        self.current_dir = current_dir
        self.docker_ref = docker_ref

        self._build_ui()
        self._refresh_palettes()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # Header
        dir_layout = QHBoxLayout()
        dir_layout.setSpacing(6)

        lbl_dir = QLabel("Palettes Folder:")
        lbl_dir.setStyleSheet("font-weight: bold;")
        dir_layout.addWidget(lbl_dir)

        self.txt_dir = QLineEdit(self.current_dir)
        self.txt_dir.setReadOnly(True)
        dir_layout.addWidget(self.txt_dir, stretch=1)

        btn_browse = QPushButton("Browse...")
        style = self.style()
        btn_browse.setIcon(style.standardIcon(style.SP_DialogOpenButton))
        btn_browse.clicked.connect(self._browse_directory)
        dir_layout.addWidget(btn_browse)

        btn_reload = QPushButton()
        btn_reload.setIcon(style.standardIcon(getattr(style, "SP_BrowserReload", style.SP_DialogResetButton)))
        btn_reload.setToolTip("Refresh folder contents")
        btn_reload.setFixedWidth(28)
        btn_reload.clicked.connect(self._refresh_palettes)
        dir_layout.addWidget(btn_reload)

        layout.addLayout(dir_layout)

        # Scroll area
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.StyledPanel)

        self.container = QWidget()
        self.cards_layout = QVBoxLayout(self.container)
        self.cards_layout.setContentsMargins(6, 6, 6, 6)
        self.cards_layout.setSpacing(6)
        self.cards_layout.setAlignment(Qt.AlignTop)
        self.scroll.setWidget(self.container)

        layout.addWidget(self.scroll, stretch=1)

        # Footer
        footer = QHBoxLayout()
        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet("color: #999; font-size: 11px;")
        footer.addWidget(self.lbl_status, stretch=1)

        if self.docker_ref:
            btn_save_here = QPushButton("Save Current Palette Here...")
            btn_save_here.clicked.connect(self._save_current_to_dir)
            footer.addWidget(btn_save_here)

        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.reject)
        footer.addWidget(btn_close)

        layout.addLayout(footer)

    def _browse_directory(self):
        new_dir = QFileDialog.getExistingDirectory(
            self, "Choose Palettes Directory", self.current_dir
        )
        if new_dir:
            self.current_dir = new_dir
            self.txt_dir.setText(new_dir)
            self.dirChanged.emit(new_dir)
            if self.docker_ref:
                self.docker_ref._palettes_dir = new_dir
                self.docker_ref._save_session()
            self._refresh_palettes()

    def _refresh_palettes(self):
        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        if not os.path.exists(self.current_dir):
            try:
                os.makedirs(self.current_dir, exist_ok=True)
            except Exception:
                pass

        if not os.path.exists(self.current_dir):
            self.lbl_status.setText("Directory does not exist.")
            return

        json_files = sorted([
            f for f in os.listdir(self.current_dir)
            if f.lower().endswith(".json") and f != "session.json"
        ])

        if not json_files:
            self.lbl_status.setText("No .json palette files found.")
            empty_lbl = QLabel("No .json palette files found.")
            empty_lbl.setAlignment(Qt.AlignCenter)
            empty_lbl.setStyleSheet("color: #777; padding: 20px;")
            self.cards_layout.addWidget(empty_lbl)
            return

        count = 0
        for f_name in json_files:
            file_path = os.path.join(self.current_dir, f_name)
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if not isinstance(data, dict) or "anchors" not in data:
                    continue
                palette_name = os.path.splitext(f_name)[0]
                card = PaletteCardWidget(palette_name, file_path, data, parent=self)
                card.doubleClicked.connect(self._on_palette_selected)
                card.loadRequested.connect(self._on_palette_selected)
                self.cards_layout.addWidget(card)
                count += 1
            except Exception:
                continue

        self.lbl_status.setText(f"{count} palette(s) available")

    def _on_palette_selected(self, data):
        self.paletteLoaded.emit(data)
        self.accept()

    def _save_current_to_dir(self):
        if not self.docker_ref:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Palette to Folder",
            os.path.join(self.current_dir, "My Palette.json"),
            "Anchor file (*.json)"
        )
        if not path:
            return
        try:
            data = self.docker_ref._canvas.get_state()
            data["combo_index"] = self.docker_ref._combo.currentIndex()
            data["solver_index"] = self.docker_ref._solver_combo.currentIndex()
            data["mixer_index"] = self.docker_ref._mixer_combo.currentIndex()
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            self._refresh_palettes()
        except Exception as e:
            QMessageBox.warning(self, "Save Failed", str(e))
