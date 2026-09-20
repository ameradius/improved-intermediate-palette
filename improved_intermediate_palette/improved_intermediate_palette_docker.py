# SPDX-FileCopyrightText: 2026 ameradius
# SPDX-License-Identifier: GPL-3.0-or-later
# Based on an original concept by Tayete's Intermediate Palette.

import os
import json

from krita import DockWidget, Krita
from PyQt5.QtCore import Qt, QPoint
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QComboBox, QPushButton, QFrame, QFileDialog, QMessageBox,
    QScrollArea, QSizePolicy, QColorDialog, QMenu, QAction
)

from .palette_canvas import PaletteCanvas
from .palette_chooser import PaletteChooserDialog
from .solvers import GRID_SOLVERS
from .color_math import COLOR_MIXERS, mk_color, write_active_color
from .serialization import dict_to_anchors, export_kpl_palette

DOCKER_TITLE = "Improved Intermediate Palette"

GRID_SIZES = [
    ("5 × 5",    5,    5),
    ("8 x 8",    8,    8),
    ("10 × 10", 10,   10),
    ("12 × 12", 12,   12).
    ("15 × 15", 15,   15),
    ("20 × 20", 20,   20),
    ("25 × 25", 25,   25),
    ("30 × 30", 30,   30),
]

MAX_HISTORY = 20
SESSION_FILE = os.path.join(os.path.dirname(__file__), "session.json")


class HorizontalScrollArea(QScrollArea):
    def wheelEvent(self, event):
        delta = event.angleDelta().y() or event.angleDelta().x()
        if delta:
            bar = self.horizontalScrollBar()
            bar.setValue(bar.value() - delta)
            event.accept()
        else:
            super().wheelEvent(event)


class AnchorRowWidget(QFrame):
    def __init__(self, r, c, col, sampler_icon, close_icon, on_sample, on_delete, parent=None):
        super().__init__(parent)
        self.r = r
        self.c = c
        self.col = col
        self.on_sample = on_sample
        self.on_delete = on_delete

        self.setMinimumWidth(0)
        self.setFixedHeight(22)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setObjectName("anchorRow")
        self.setStyleSheet("#anchorRow { background-color: transparent; }")

        win_col = self.palette().color(self.backgroundRole())
        is_light = (0.299 * win_col.red() + 0.587 * win_col.green() + 0.114 * win_col.blue()) > 130
        self._hover_bg = "rgba(0, 0, 0, 0.08)" if is_light else "rgba(255, 255, 255, 0.12)"

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 1, 4, 1)
        layout.setSpacing(6)

        # Square anchor color
        sq = QFrame()
        sq.setFixedSize(14, 14)
        sq.setStyleSheet(f"background-color: rgb({col.red()},{col.green()},{col.blue()}); border: 1px solid #555; border-radius: 2px;")
        layout.addWidget(sq)

        # Color in RGB
        lbl_rgb = QLabel(f"rgb({col.red()}, {col.green()}, {col.blue()})")
        lbl_rgb.setStyleSheet("font-size: 11px;")
        lbl_rgb.setMinimumWidth(0)
        layout.addWidget(lbl_rgb)

        # Grid location in "(x, y)"
        lbl_loc = QLabel(f"({c}, {r})")
        lbl_loc.setStyleSheet("font-size: 11px; color: #888;")
        lbl_loc.setMinimumWidth(0)
        layout.addWidget(lbl_loc)

        # Spacer
        layout.addStretch()

        # Button styles
        btn_style = """
            QPushButton {
                color: #888;
                border: none;
                background: transparent;
                padding: 0px;
            }
            QPushButton:hover {
                color: #fff;
                background-color: rgba(255, 255, 255, 0.2);
                border-radius: 3px;
            }
        """

        # Color picker button (external color sampler)
        self.btn_pick = QPushButton()
        self.btn_pick.setIcon(sampler_icon)
        if self.btn_pick.icon().isNull():
            self.btn_pick.setText("⌖")
        self.btn_pick.setFixedSize(16, 16)
        self.btn_pick.setStyleSheet(btn_style)
        self.btn_pick.setToolTip(f"Sample/change color for anchor ({c}, {r})")
        self.btn_pick.clicked.connect(lambda: self.on_sample(self.r, self.c, self.col))
        layout.addWidget(self.btn_pick)

        # Delete button
        self.btn_del = QPushButton()
        self.btn_del.setIcon(close_icon)
        if self.btn_del.icon().isNull():
            self.btn_del.setText("✕")
        self.btn_del.setFixedSize(16, 16)
        self.btn_del.setStyleSheet(btn_style)
        self.btn_del.setToolTip(f"Remove anchor at ({c}, {r})")
        self.btn_del.clicked.connect(lambda: self.on_delete(self.r, self.c))
        layout.addWidget(self.btn_del)

        # Hidden by default until row is hovered
        self.btn_pick.setVisible(False)
        self.btn_del.setVisible(False)

    def enterEvent(self, event):
        self.setStyleSheet(f"#anchorRow {{ background-color: {self._hover_bg}; border-radius: 3px; }}")
        self.btn_pick.setVisible(True)
        self.btn_del.setVisible(True)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.setStyleSheet("#anchorRow { background-color: transparent; }")
        self.btn_pick.setVisible(False)
        self.btn_del.setVisible(False)
        super().leaveEvent(event)


class ImprovedIntermediatePaletteDocker(DockWidget):

    def __init__(self):
        super().__init__()
        self.setWindowTitle(DOCKER_TITLE)
        self.setMinimumWidth(0)
        self._picked_history = []
        self._anchors_collapsed = False
        self._palettes_dir = None
        self._build_ui()
        self._load_session()

    def _build_ui(self):
        main = QWidget()
        main.setMinimumWidth(0)
        self.setWidget(main)
        layout = QVBoxLayout(main)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Row 1: [[grid size changer] [palette chooser] [menu]] [spacer] [instructions]
        row1 = QHBoxLayout()
        row1.setSpacing(4)

        lbl_grid = QLabel("Grid:")
        lbl_grid.setMinimumWidth(0)
        row1.addWidget(lbl_grid)

        self._combo = QComboBox()
        self._combo.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self._combo.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        for label, _, _ in GRID_SIZES:
            self._combo.addItem(label)
        self._combo.setCurrentIndex(2) # 12x12
        self._combo.currentIndexChanged.connect(self._on_size_changed)
        row1.addWidget(self._combo)

        # Palette Chooser button
        btn_chooser = QPushButton()
        btn_chooser.setIcon(self._get_palette_icon())
        if btn_chooser.icon().isNull():
            btn_chooser.setText("🎨")
        btn_chooser.setFixedWidth(26)
        btn_chooser.setToolTip("Palette Chooser (Browse & Load Palettes)")
        btn_chooser.clicked.connect(self._open_palette_chooser)
        row1.addWidget(btn_chooser)

        # Menu button
        btn_menu = QPushButton()
        btn_menu.setIcon(self._get_menu_icon())
        if btn_menu.icon().isNull():
            btn_menu.setText("≡")
        btn_menu.setFixedWidth(26)
        btn_menu.setToolTip("Palette Options (Import / Export)")
        btn_menu.clicked.connect(lambda: self._open_palette_menu(btn_menu))
        row1.addWidget(btn_menu)

        # Spacer
        row1.addStretch()

        # Instruction button
        lbl_help = QLabel("?")
        lbl_help.setAlignment(Qt.AlignCenter)
        lbl_help.setFixedSize(18, 18)
        lbl_help.setStyleSheet("""
            QLabel {
                color: #888;
                border: 1px solid #666;
                border-radius: 9px;
                font-weight: bold;
                font-size: 11px;
                background: transparent;
            }
            QLabel:hover {
                color: #ddd;
                border-color: #aaa;
                background-color: rgba(255, 255, 255, 0.1);
            }
        """)
        lbl_help.setToolTip(
            "<div style='margin: 2px;'>"
            "<b>Controls & Shortcuts:</b><br>"
            "• <b>Click:</b> Use cell as active color<br>"
            "• <b>Double-click:</b> Set anchor from active color<br>"
            "• <b>Ctrl + Click / Double Right-click:</b> Delete anchor<br>"
            "• <b>Ctrl + Long-press / Right-click:</b> Menu"
            "</div>"
        )
        row1.addWidget(lbl_help)

        layout.addLayout(row1)

        # Row 2: Solver & mixer dropdowns
        row2 = QHBoxLayout()
        row2.setSpacing(4)

        lbl_solver = QLabel("Solver:")
        lbl_solver.setMinimumWidth(0)
        row2.addWidget(lbl_solver)

        self._solver_combo = QComboBox()
        self._solver_combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self._solver_combo.setMinimumContentsLength(3)
        self._solver_combo.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        self._solver_combo.setMinimumWidth(0)
        for s_name in GRID_SOLVERS:
            self._solver_combo.addItem(s_name)
        self._solver_combo.setCurrentIndex(1)   # Laplacian
        self._solver_combo.currentIndexChanged.connect(self._on_solver_changed)
        row2.addWidget(self._solver_combo, stretch=3)

        lbl_mixer = QLabel("Mixer:")
        lbl_mixer.setMinimumWidth(0)
        row2.addWidget(lbl_mixer)

        self._mixer_combo = QComboBox()
        self._mixer_combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self._mixer_combo.setMinimumContentsLength(3)
        self._mixer_combo.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        self._mixer_combo.setMinimumWidth(0)
        for m_name in COLOR_MIXERS:
            self._mixer_combo.addItem(m_name)
        self._mixer_combo.setCurrentIndex(1)   # Linear sRGB
        self._mixer_combo.currentIndexChanged.connect(self._on_mixer_changed)
        row2.addWidget(self._mixer_combo, stretch=2)

        layout.addLayout(row2)

        # Separator
        sep1 = QFrame()
        sep1.setFrameShape(QFrame.HLine)
        sep1.setFrameShadow(QFrame.Sunken)
        layout.addWidget(sep1)

        # History row: [color swatches] [spacer] [clear history]
        hist_row = QHBoxLayout()
        hist_row.setContentsMargins(0, 0, 0, 0)
        hist_row.setSpacing(4)

        self._hist_scroll = HorizontalScrollArea()
        self._hist_scroll.setFixedHeight(30)
        self._hist_scroll.setMinimumWidth(0)
        self._hist_scroll.setWidgetResizable(True)
        self._hist_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._hist_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._hist_scroll.setStyleSheet("""
            QScrollArea { border: none; background: transparent; }
            QScrollBar:horizontal {
                height: 4px;
                background: transparent;
                margin: 0px;
            }
            QScrollBar::handle:horizontal {
                background: #555;
                min-width: 14px;
                border-radius: 2px;
            }
            QScrollBar::handle:horizontal:hover {
                background: #888;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0px;
                height: 0px;
            }
        """)

        self._hist_container = QWidget()
        self._hist_layout = QHBoxLayout(self._hist_container)
        self._hist_layout.setContentsMargins(0, 0, 0, 2)
        self._hist_layout.setSpacing(3)
        self._hist_layout.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self._hist_scroll.setWidget(self._hist_container)

        hist_row.addWidget(self._hist_scroll, stretch=1)
        hist_row.addSpacing(2)

        self._btn_clear_hist = QPushButton()
        trash_icon = self.style().standardIcon(
            getattr(self.style(), "SP_TrashIcon", self.style().SP_DialogDiscardButton)
        )
        self._btn_clear_hist.setIcon(trash_icon)
        self._btn_clear_hist.setFixedSize(22, 22)
        self._btn_clear_hist.setToolTip("Clear color history")
        self._btn_clear_hist.clicked.connect(self._clear_history)
        hist_row.addWidget(self._btn_clear_hist)

        layout.addLayout(hist_row)

        # Palette Canvas Grid
        self._canvas = PaletteCanvas(12, 12)
        self._canvas.set_solver(self._solver_combo.currentText())
        self._canvas.set_mixer(self._mixer_combo.currentText())
        self._canvas.colorPicked.connect(self._on_color_picked)
        self._canvas.anchorsChanged.connect(self._refresh_anchors_list)
        layout.addWidget(self._canvas, stretch=1)

        # Separator
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.HLine)
        sep2.setFrameShadow(QFrame.Sunken)
        layout.addWidget(sep2)

        # Anchors list: ["Anchors"] [collapse] [spacer] [reset]
        anchors_header = QHBoxLayout()
        anchors_header.setContentsMargins(0, 0, 0, 0)
        anchors_header.setSpacing(4)

        lbl_anchors = QLabel("Anchors")
        font = lbl_anchors.font()
        font.setBold(True)
        lbl_anchors.setFont(font)
        anchors_header.addWidget(lbl_anchors)

        self._btn_collapse = QPushButton()
        self._btn_collapse.setFixedSize(20, 20)
        self._btn_collapse.setFlat(True)
        self._btn_collapse.clicked.connect(self._toggle_anchors_collapse)
        anchors_header.addWidget(self._btn_collapse)

        anchors_header.addStretch()

        self._btn_reset = QPushButton()
        reload_icon = self.style().standardIcon(
            getattr(self.style(), "SP_BrowserReload", getattr(self.style(), "SP_DialogResetButton", self.style().SP_DialogDiscardButton))
        )
        self._btn_reset.setIcon(reload_icon)
        self._btn_reset.setFixedSize(22, 22)
        self._btn_reset.setToolTip("Reset anchors to defaults")
        self._btn_reset.clicked.connect(self._on_reset)
        anchors_header.addWidget(self._btn_reset)

        layout.addLayout(anchors_header)

        self._anchors_scroll = QScrollArea()
        self._anchors_scroll.setFixedHeight(140)
        self._anchors_scroll.setMinimumWidth(0)
        self._anchors_scroll.setWidgetResizable(True)
        self._anchors_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._anchors_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._anchors_scroll.setFrameShape(QFrame.StyledPanel)

        self._anchors_container = QWidget()
        self._anchors_container.setMinimumWidth(0)
        self._anchors_layout = QVBoxLayout(self._anchors_container)
        self._anchors_layout.setContentsMargins(3, 3, 3, 3)
        self._anchors_layout.setSpacing(2)
        self._anchors_layout.setAlignment(Qt.AlignTop)
        self._anchors_scroll.setWidget(self._anchors_container)

        layout.addWidget(self._anchors_scroll)

        self._update_collapse_ui(initial=True)
        self._refresh_anchors_list()
        self._refresh_history_ui()

    # Icons helpers

    def _get_palette_icon(self):
        app = Krita.instance() if Krita else None
        if app:
            for name in ["palette-library", "view-color-palette", "color-management", "fill-color"]:
                ic = app.icon(name)
                if ic and not ic.isNull():
                    return ic
        return self.style().standardIcon(self.style().SP_FileDialogDetailedView)

    def _get_menu_icon(self):
        app = Krita.instance() if Krita else None
        if app:
            for name in ["application-menu", "view-more-symbolic", "overflow-menu", "menu"]:
                ic = app.icon(name)
                if ic and not ic.isNull():
                    return ic
        return self.style().standardIcon(self.style().SP_ToolBarHorizontalExtensionButton)

    def _get_sampler_icon(self):
        app = Krita.instance() if Krita else None
        if app:
            for name in ["krita_tool_color_sampler", "color-picker", "tool_color_sampler", "edit-color"]:
                ic = app.icon(name)
                if ic and not ic.isNull():
                    return ic
        return self.style().standardIcon(self.style().SP_FileDialogContentsView)

    # Extra menu

    def _open_palette_menu(self, btn):
        menu = QMenu(self)

        a0 = QAction("Palette Chooser...", menu)
        a0.setIcon(self._get_palette_icon())
        a0.triggered.connect(self._open_palette_chooser)
        menu.addAction(a0)
        menu.addSeparator()

        a1 = QAction("Save grid as Krita palette (.kpl)...", menu)
        a1.setIcon(self.style().standardIcon(self.style().SP_DialogSaveButton))
        a1.triggered.connect(self._save_kpl)
        menu.addAction(a1)

        a2 = QAction("Save anchor points to file (.json)...", menu)
        a2.setIcon(self.style().standardIcon(self.style().SP_DriveFDIcon))
        a2.triggered.connect(self._save_anchors)
        menu.addAction(a2)

        a3 = QAction("Load anchor points from file (.json)...", menu)
        a3.setIcon(self.style().standardIcon(self.style().SP_DialogOpenButton))
        a3.triggered.connect(self._load_anchors)
        menu.addAction(a3)

        menu.exec_(btn.mapToGlobal(QPoint(0, btn.height())))

    def _open_palette_chooser(self):
        default_dir = self._palettes_dir
        if not default_dir or not os.path.exists(default_dir):
            default_dir = os.path.join(os.path.dirname(__file__), "palettes")
            try:
                os.makedirs(default_dir, exist_ok=True)
            except Exception:
                pass

        dialog = PaletteChooserDialog(default_dir, docker_ref=self, parent=self)
        dialog.paletteLoaded.connect(self._load_palette_dict)
        dialog.dirChanged.connect(self._on_palettes_dir_changed)

        dialog.exec_()

        # Persistent directory location
        if dialog.current_dir and os.path.exists(dialog.current_dir):
            self._palettes_dir = dialog.current_dir
            self._save_session()

    def _on_palettes_dir_changed(self, new_dir):
        if new_dir and os.path.exists(new_dir):
            self._palettes_dir = new_dir
            self._save_session()

    def _load_palette_dict(self, data):
        anchors, rows, cols = dict_to_anchors(data)

        # Restore combo silently
        combo_index = data.get("combo_index")
        if combo_index is None:
            for idx, (lbl, r, c) in enumerate(GRID_SIZES):
                if r == rows and c == cols:
                    combo_index = idx
                    break
        if combo_index is not None and 0 <= combo_index < len(GRID_SIZES):
            self._combo.blockSignals(True)
            self._combo.setCurrentIndex(combo_index)
            self._combo.blockSignals(False)

        solver = data.get("solver")
        if solver and solver in GRID_SOLVERS:
            s_idx = self._solver_combo.findText(solver)
            if s_idx >= 0:
                self._solver_combo.blockSignals(True)
                self._solver_combo.setCurrentIndex(s_idx)
                self._solver_combo.blockSignals(False)

        mixer = data.get("mixer")
        if mixer and mixer in COLOR_MIXERS:
            m_idx = self._mixer_combo.findText(mixer)
            if m_idx >= 0:
                self._mixer_combo.blockSignals(True)
                self._mixer_combo.setCurrentIndex(m_idx)
                self._mixer_combo.blockSignals(False)

        picked = tuple(data["picked"]) if "picked" in data and data["picked"] else None
        self._canvas.load_anchors(anchors, rows, cols, picked,
                                  solver=self._solver_combo.currentText(),
                                  mixer=self._mixer_combo.currentText())
        self._save_session()

    # Collapsible anchors list logic

    def _toggle_anchors_collapse(self):
        self._anchors_collapsed = not self._anchors_collapsed
        self._update_collapse_ui()
        self._save_session()

    def _update_collapse_ui(self, initial=False):
        self._anchors_scroll.setVisible(not self._anchors_collapsed)
        arrow_type = self.style().SP_ArrowDown if self._anchors_collapsed else self.style().SP_ArrowUp
        icon = self.style().standardIcon(arrow_type)
        self._btn_collapse.setIcon(icon)
        if icon.isNull():
            self._btn_collapse.setText("▼" if self._anchors_collapsed else "▲")
        else:
            self._btn_collapse.setText("")
        self._btn_collapse.setToolTip("Expand anchor list" if self._anchors_collapsed else "Collapse anchor list")

        if initial:
            return

        # Resize floating window smoothly without squashing the canvas (if you read this, I need help)
        scroll_h = self._anchors_scroll.height() if self._anchors_scroll.height() > 0 else 140
        if self.isFloating():
            win = self.window()
            if self._anchors_collapsed:
                win.resize(win.width(), max(180, win.height() - scroll_h))
            else:
                win.resize(win.width(), win.height() + scroll_h)

    # History handlers

    def _on_color_picked(self, color):
        """Add picked color to history ordered from the left as most recent."""
        r, g, b = color.red(), color.green(), color.blue()
        for i, c in enumerate(self._picked_history):
            if c.red() == r and c.green() == g and c.blue() == b:
                self._picked_history.pop(i)
                break
        self._picked_history.insert(0, color)
        if len(self._picked_history) > MAX_HISTORY:
            self._picked_history = self._picked_history[:MAX_HISTORY]
        self._refresh_history_ui()
        self._save_session()

    def _on_history_clicked(self, color):
        write_active_color(color)
        self._on_color_picked(color)

    def _clear_history(self):
        self._picked_history = []
        self._refresh_history_ui()
        self._save_session()

    def _refresh_history_ui(self):
        while self._hist_layout.count():
            item = self._hist_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        for col in self._picked_history:
            r, g, b = col.red(), col.green(), col.blue()
            btn = QPushButton()
            btn.setFixedSize(18, 18)
            btn.setStyleSheet(f"background-color: rgb({r},{g},{b}); border: 1px solid #444; border-radius: 2px;")
            btn.setToolTip(f"rgb({r}, {g}, {b})")
            btn.clicked.connect(lambda ch, c=col: self._on_history_clicked(c))
            self._hist_layout.addWidget(btn)

    # Anchors list handlers

    def _on_sample_anchor_row(self, r, c, current_col):
        # TODO: Native Krita colorpicking?
        color = QColorDialog.getColor(current_col, self, f"Sample Anchor Color ({c}, {r})")
        if color.isValid():
            self._canvas.set_anchor_color(r, c, color)
            write_active_color(color)

    def _refresh_anchors_list(self):
        while self._anchors_layout.count():
            item = self._anchors_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        sorted_anchors = sorted(self._canvas._anchors.items(), key=lambda item: (item[0][0], item[0][1]))
        close_icon = self.style().standardIcon(self.style().SP_TitleBarCloseButton)
        sampler_icon = self._get_sampler_icon()

        for (r, c), col in sorted_anchors:
            row_widget = AnchorRowWidget(
                r, c, col, sampler_icon, close_icon,
                on_sample=self._on_sample_anchor_row,
                on_delete=self._canvas.remove_anchor,
                parent=self._anchors_container
            )
            self._anchors_layout.addWidget(row_widget)

    # Toolbar signal handlers

    def _on_size_changed(self, index):
        _, rows, cols = GRID_SIZES[index]
        self._canvas.rebuild(rows, cols)
        self._save_session()

    def _on_solver_changed(self, index):
        self._canvas.set_solver(self._solver_combo.currentText())
        self._save_session()

    def _on_mixer_changed(self, index):
        self._canvas.set_mixer(self._mixer_combo.currentText())
        self._save_session()

    def _on_reset(self):
        self._canvas.reset()
        self._save_session()

    # Session auto-save/load

    def _save_session(self):
        try:
            data = self._canvas.get_state()
            data["combo_index"] = self._combo.currentIndex()
            data["solver_index"] = self._solver_combo.currentIndex()
            data["mixer_index"] = self._mixer_combo.currentIndex()
            data["anchors_collapsed"] = self._anchors_collapsed
            data["palettes_dir"] = self._palettes_dir
            data["history"] = [[c.red(), c.green(), c.blue()] for c in self._picked_history]
            with open(SESSION_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f)
        except Exception:
            pass

    def _load_session(self):
        if not os.path.exists(SESSION_FILE):
            return
        try:
            with open(SESSION_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            anchors, rows, cols = dict_to_anchors(data)
            combo_index = data.get("combo_index", 2)
            self._combo.blockSignals(True)
            self._combo.setCurrentIndex(combo_index)
            self._combo.blockSignals(False)

            solver_idx = data.get("solver_index")
            if solver_idx is None and "solver" in data:
                solver_idx = self._solver_combo.findText(data["solver"])
            if solver_idx is not None and 0 <= solver_idx < len(GRID_SOLVERS):
                self._solver_combo.blockSignals(True)
                self._solver_combo.setCurrentIndex(solver_idx)
                self._solver_combo.blockSignals(False)

            mixer_idx = data.get("mixer_index")
            if mixer_idx is None and "mixer" in data:
                mixer_idx = self._mixer_combo.findText(data["mixer"])
            if mixer_idx is not None and 0 <= mixer_idx < len(COLOR_MIXERS):
                self._mixer_combo.blockSignals(True)
                self._mixer_combo.setCurrentIndex(mixer_idx)
                self._mixer_combo.blockSignals(False)

            self._anchors_collapsed = bool(data.get("anchors_collapsed", False))
            self._update_collapse_ui(initial=True)
            self._palettes_dir = data.get("palettes_dir")

            picked = tuple(data["picked"]) if "picked" in data and data["picked"] else None
            self._canvas.load_anchors(anchors, rows, cols, picked,
                                      solver=self._solver_combo.currentText(),
                                      mixer=self._mixer_combo.currentText())

            if "history" in data:
                self._picked_history = [mk_color(*rgb) for rgb in data["history"]][:MAX_HISTORY]
                self._refresh_history_ui()
        except Exception:
            pass

    # Save/load anchor files

    def _save_anchors(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Anchor Points", "anchors.json",
            "Anchor file (*.json)"
        )
        if not path:
            return
        try:
            data = self._canvas.get_state()
            data["combo_index"] = self._combo.currentIndex()
            data["solver_index"] = self._solver_combo.currentIndex()
            data["mixer_index"] = self._mixer_combo.currentIndex()
            data["anchors_collapsed"] = self._anchors_collapsed
            data["palettes_dir"] = self._palettes_dir
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            self._save_session()
            QMessageBox.information(self, "Saved", "Anchor points saved to:\n{}".format(path))
        except Exception as e:
            QMessageBox.warning(self, "Save Failed", str(e))

    def _load_anchors(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Load Anchor Points", "",
            "Anchor file (*.json)"
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._load_palette_dict(data)
            QMessageBox.information(self, "Loaded", "Anchor points loaded successfully.")
        except Exception as e:
            QMessageBox.warning(self, "Load Failed", str(e))

    # Save KPL palette

    def _save_kpl(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Krita Palette", "intermediate_palette.kpl",
            "Krita Palette (*.kpl)"
        )
        if not path:
            return

        try:
            export_kpl_palette(path, self._canvas._colors, self._canvas._rows, self._canvas._cols)
            QMessageBox.information(
                self, "Palette Saved",
                "Saved {} colours.\nLoad via Palettes docker → Import Palette.".format(
                    self._canvas._rows * self._canvas._cols
                )
            )
        except Exception as e:
            QMessageBox.warning(self, "Save Failed", str(e))

    def canvasChanged(self, canvas):
        self._save_session()
