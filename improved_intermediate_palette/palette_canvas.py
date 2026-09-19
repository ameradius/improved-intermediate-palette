# SPDX-FileCopyrightText: 2026 ameradius
# SPDX-License-Identifier: GPL-3.0-or-later
# Based on an original concept by Tayete's Intermediate Palette.

from PyQt5.QtWidgets import QWidget, QSizePolicy, QMenu, QAction, QColorDialog
from PyQt5.QtCore import Qt, QRect, QPoint, QTimer, QSize, pyqtSignal
from PyQt5.QtGui import QColor, QPainter, QBrush, QPen, QPolygon, QPalette

from .color_math import (
    mk_color, contrast_color, hover_color_for, is_orange_tint,
    read_active_color, write_active_color, COLOR_MIXERS
)
from .solvers import GRID_SOLVERS, compute_palette_grid
from .serialization import anchors_to_dict

GAP_PX = 1
PADDING_PX = 1
STEP_INCREMENT = 1


class PaletteCanvas(QWidget):
    colorPicked = pyqtSignal(object)
    anchorsChanged = pyqtSignal()

    def __init__(self, rows=12, cols=12, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_OpaquePaintEvent, True)
        self.setFocusPolicy(Qt.NoFocus)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumSize(40, 40)
        self._rows = rows
        self._cols = cols
        self._anchors = {}
        self._colors = []
        self._cell_px = 18
        self._offset_x = 0
        self._offset_y = 0

        self._solver = "Steady-State Heat Equation (Laplacian)"
        self._mixer = "Linear sRGB"

        self._hovered_cell = None
        self._picked_cell = None

        # Left-click timer (single = pick as active color, double = set anchor)
        self._lclick_timer = QTimer()
        self._lclick_timer.setSingleShot(True)
        self._lclick_timer.setInterval(250)
        self._lclick_timer.timeout.connect(self._do_single_lclick)
        self._lpending = None

        # Right-click timer (single = menu, double = remove anchor)
        self._rclick_timer = QTimer()
        self._rclick_timer.setSingleShot(True)
        self._rclick_timer.setInterval(250)
        self._rclick_timer.timeout.connect(self._do_single_rclick)
        self._rpending = None

        # Tablet / Keyboard shortcut (Ctrl + Click = remove anchor, Ctrl + Long-press = menu)
        self._ctrl_press_pos = None
        self._ctrl_timer = QTimer()
        self._ctrl_timer.setSingleShot(True)
        self._ctrl_timer.setInterval(450)
        self._ctrl_timer.timeout.connect(self._on_ctrl_long_press)

        self._init_default_anchors()
        self._recompute()
        self.setMouseTracking(True)

    def sizeHint(self):
        return QSize(200, 200)

    def minimumSizeHint(self):
        return QSize(40, 40)

    def set_solver(self, solver_name):
        if solver_name in GRID_SOLVERS and solver_name != self._solver:
            self._solver = solver_name
            self._recompute()
            self.update()

    def set_mixer(self, mixer_name):
        if mixer_name in COLOR_MIXERS and mixer_name != self._mixer:
            self._mixer = mixer_name
            self._recompute()
            self.update()

    def get_solver(self):
        return self._solver

    def get_mixer(self):
        return self._mixer

    def rebuild(self, rows, cols):
        old_anchors = dict(self._anchors)
        old_rows, old_cols = self._rows, self._cols
        self._rows = rows
        self._cols = cols
        self._anchors = {}
        for (r, c), color in old_anchors.items():
            nr = int(round(r * (rows - 1) / max(old_rows - 1, 1)))
            nc = int(round(c * (cols - 1) / max(old_cols - 1, 1)))
            self._anchors[(max(0, min(rows - 1, nr)), max(0, min(cols - 1, nc)))] = color

        if self._picked_cell is not None:
            pr, pc = self._picked_cell
            nr = int(round(pr * (rows - 1) / max(old_rows - 1, 1)))
            nc = int(round(pc * (cols - 1) / max(old_cols - 1, 1)))
            self._picked_cell = (max(0, min(rows - 1, nr)), max(0, min(cols - 1, nc)))
        self._hovered_cell = None

        self._recompute()
        self.anchorsChanged.emit()
        self.update()

    def reset(self):
        self._anchors = {}
        self._picked_cell = None
        self._hovered_cell = None
        self._init_default_anchors()
        self._recompute()
        self.anchorsChanged.emit()
        self.update()

    def load_anchors(self, anchors, rows, cols, picked=None, solver=None, mixer=None):
        self._rows = rows
        self._cols = cols
        self._anchors = anchors
        self._picked_cell = picked
        if solver in GRID_SOLVERS:
            self._solver = solver
        if mixer in COLOR_MIXERS:
            self._mixer = mixer
        self._hovered_cell = None
        self._recompute()
        self.anchorsChanged.emit()
        self.update()

    def set_anchor_color(self, r, c, color):
        if color and color.isValid():
            self._anchors[(r, c)] = color
            self._recompute()
            self.anchorsChanged.emit()
            self.update()

    def remove_anchor(self, r, c):
        if (r, c) in self._anchors:
            del self._anchors[(r, c)]
            self._recompute()
            self.anchorsChanged.emit()
            self.update()

    def set_picked_cell(self, cell):
        self._picked_cell = cell
        self.update()

    def get_picked_cell(self):
        return self._picked_cell

    def get_state(self):
        return anchors_to_dict(self._anchors, self._rows, self._cols,
                               self._solver, self._mixer, self._picked_cell)

    # Internals

    def _init_default_anchors(self):
        # TODO: Making this modifiable to users
        R, C = self._rows - 1, self._cols - 1
        self._anchors = {
            (0, 0): mk_color(220, 60, 60),
            (0, C): mk_color(60, 180, 220),
            (R, 0): mk_color(240, 200, 60),
            (R, C): mk_color(80, 200, 100),
        }

    def _recompute(self):
        self._colors = compute_palette_grid(
            self._rows, self._cols, self._anchors, self._solver, self._mixer
        )

    # Geometry helpers

    def _step(self):
        return self._cell_px + GAP_PX

    def _cell_rect(self, r, c):
        s = self._step()
        return QRect(self._offset_x + c * s, self._offset_y + r * s, self._cell_px, self._cell_px)

    def _cell_at(self, x, y):
        s = self._step()
        rel_x = x - self._offset_x
        rel_y = y - self._offset_y
        if rel_x < 0 or rel_y < 0:
            return None
        c = rel_x // s
        r = rel_y // s
        if 0 <= r < self._rows and 0 <= c < self._cols:
            if self._cell_rect(r, c).contains(x, y):
                return (r, c)
        return None

    def _recalc_cell_size(self):
        # TODO: Changing this code again in conjunction with resizeEvent()
        w, h = self.width(), self.height()
        avail_w = max(0, w - PADDING_PX * 2)
        avail_h = max(0, h - PADDING_PX * 2)
        if self._cols > 0 and self._rows > 0:
            cell_w = max(4, (avail_w - (self._cols - 1) * GAP_PX) // self._cols)
            cell_h = max(4, (avail_h - (self._rows - 1) * GAP_PX) // self._rows)
            raw_px = min(cell_w, cell_h)

            self._cell_px = max(4, (raw_px // STEP_INCREMENT) * STEP_INCREMENT)
            total_w = self._cols * self._cell_px + (self._cols - 1) * GAP_PX
            total_h = self._rows * self._cell_px + (self._rows - 1) * GAP_PX
            self._offset_x = max(0, (w - total_w) // 2)
            self._offset_y = max(0, (h - total_h) // 2)

    # Paint

    def resizeEvent(self, event):
        old_px = self._cell_px
        old_ox = self._offset_x
        old_oy = self._offset_y
        self._recalc_cell_size()
        # Only schedule repaint when cell size or centering offsets actually change
        if self._cell_px != old_px or self._offset_x != old_ox or self._offset_y != old_oy:
            self.update()

    def paintEvent(self, event):
        self._recalc_cell_size()
        p = QPainter(self)
        bg_color = self.palette().color(QPalette.Window)
        p.fillRect(self.rect(), bg_color)

        tri_size = max(3, min(self._cell_px - 1, int(round(self._cell_px * 0.35))))
        s = self._step()
        ox = self._offset_x
        oy = self._offset_y
        cell_px = self._cell_px
        fallback_col = mk_color(0, 0, 0)

        # Swatches & corner triangle anchors
        for r in range(self._rows):
            y = oy + r * s
            row_colors = self._colors[r] if (self._colors and r < len(self._colors)) else None
            for c in range(self._cols):
                x = ox + c * s
                col = row_colors[c] if (row_colors and c < len(row_colors)) else fallback_col
                p.fillRect(x, y, cell_px, cell_px, col)

                if (r, c) in self._anchors:
                    c_fill = contrast_color(col)
                    p.setPen(c_fill)
                    p.setBrush(QBrush(c_fill))
                    poly = QPolygon([
                        QPoint(x, y),
                        QPoint(x + tri_size, y),
                        QPoint(x, y + tri_size),
                    ])
                    p.drawPolygon(poly)

        # Latest picked color highlight
        if self._picked_cell is not None:
            pr, pc = self._picked_cell
            if 0 <= pr < self._rows and 0 <= pc < self._cols:
                rect = self._cell_rect(pr, pc)
                col = self._colors[pr][pc] if self._colors else fallback_col
                is_hovered = (self._picked_cell == self._hovered_cell)
                self._draw_picked_highlight(p, rect, col, is_hovered)

        # Hover highlight
        if self._hovered_cell is not None and self._hovered_cell != self._picked_cell:
            hr, hc = self._hovered_cell
            if 0 <= hr < self._rows and 0 <= hc < self._cols:
                rect = self._cell_rect(hr, hc)
                col = self._colors[hr][hc] if self._colors else fallback_col
                self._draw_hover_highlight(p, rect, col)

        p.end()

    def _draw_hover_highlight(self, p, rect, col):
        p.setBrush(Qt.NoBrush)
        h_col = hover_color_for(col)
        p.setPen(QPen(h_col, 1))
        p.drawRect(rect.adjusted(0, 0, -1, -1))
        if self._cell_px >= 24:
            p.drawRect(rect.adjusted(1, 1, -2, -2))

    def _draw_picked_highlight(self, p, rect, col, is_hovered=False):
        p.setBrush(Qt.NoBrush)
        picked_accent = mk_color(255, 170, 0)
        if is_orange_tint(col):
            picked_accent = contrast_color(col)

        if is_hovered:
            h_col = hover_color_for(col)
            p.setPen(QPen(h_col, 1))
            p.drawRect(rect.adjusted(0, 0, -1, -1))
            if self._cell_px >= 12:
                p.setPen(QPen(picked_accent, 1))
                p.drawRect(rect.adjusted(1, 1, -2, -2))
        else:
            if self._cell_px >= 14:
                p.setPen(QPen(picked_accent, 1))
                p.drawRect(rect.adjusted(0, 0, -1, -1))
                p.setPen(QPen(contrast_color(col), 1))
                p.drawRect(rect.adjusted(1, 1, -2, -2))
            else:
                p.setPen(QPen(picked_accent, 1))
                p.drawRect(rect.adjusted(0, 0, -1, -1))

    # Mouse events & tablet shortcuts

    def mousePressEvent(self, event):
        x, y = event.pos().x(), event.pos().y()
        hit = self._cell_at(x, y)
        if hit is None:
            event.ignore()
            return
        event.accept()
        r, c = hit

        if event.button() == Qt.LeftButton and (event.modifiers() & Qt.ControlModifier):
            self._ctrl_press_pos = (r, c)
            self._ctrl_timer.start()
            return

        if event.button() == Qt.LeftButton:
            if self._lclick_timer.isActive():
                self._lclick_timer.stop()
                self._lpending = None
                self._do_set(r, c)
            else:
                self._lpending = (r, c)
                self._lclick_timer.start()

        elif event.button() == Qt.RightButton:
            self._lclick_timer.stop()
            self._lpending = None
            if self._rclick_timer.isActive():
                self._rclick_timer.stop()
                self._rpending = None
                self.remove_anchor(r, c)
            else:
                self._rpending = (r, c)
                self._rclick_timer.start()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self._ctrl_press_pos is not None:
            r, c = self._ctrl_press_pos
            self._ctrl_press_pos = None
            if self._ctrl_timer.isActive():
                self._ctrl_timer.stop()
                self.remove_anchor(r, c)
            return
        super().mouseReleaseEvent(event)

    def _on_ctrl_long_press(self):
        if self._ctrl_press_pos is not None:
            r, c = self._ctrl_press_pos
            self._ctrl_press_pos = None
            self._show_context_menu(r, c)

    def _pick_cell(self, r, c, color=None):
        if self._colors and 0 <= r < self._rows and 0 <= c < self._cols:
            self._picked_cell = (r, c)
            if color is None:
                color = self._colors[r][c]
            write_active_color(color)
            self.colorPicked.emit(color)
            self.update()

    def _do_single_lclick(self):
        if self._lpending is None:
            return
        r, c = self._lpending
        self._lpending = None
        self._pick_cell(r, c)

    def _do_single_rclick(self):
        if self._rpending is None:
            return
        r, c = self._rpending
        self._rpending = None
        self._show_context_menu(r, c)

    def _do_sample_anchor(self, r, c):
        current = self._anchors.get((r, c), read_active_color() or mk_color(128, 128, 128))
        color = QColorDialog.getColor(current, self, "Anchor from Color Sampler")
        if color.isValid():
            self.set_anchor_color(r, c, color)
            write_active_color(color)

    def _show_context_menu(self, r, c):
        if not (0 <= r < self._rows and 0 <= c < self._cols):
            return
        cell_color = self._colors[r][c] if self._colors else None
        menu = QMenu(self)

        a1 = QAction("Anchor from active color", menu)
        a1.triggered.connect(lambda ch, rr=r, cc=c: self._do_set(rr, cc))
        menu.addAction(a1)

        a2 = QAction("Anchor from color sampler", menu)
        a2.triggered.connect(lambda ch, rr=r, cc=c: self._do_sample_anchor(rr, cc))
        menu.addAction(a2)

        if (r, c) in self._anchors:
            a3 = QAction("Remove anchor", menu)
            a3.triggered.connect(lambda ch, rr=r, cc=c: self.remove_anchor(rr, cc))
            menu.addAction(a3)

        if cell_color is not None:
            a4 = QAction("Use as active color", menu)
            a4.triggered.connect(lambda ch, rr=r, cc=c, col=cell_color: self._pick_cell(rr, cc, col))
            menu.addAction(a4)

        menu.exec_(self.mapToGlobal(self._cell_rect(r, c).topLeft()))

    def mouseMoveEvent(self, event):
        x, y = event.pos().x(), event.pos().y()
        hit = self._cell_at(x, y)

        if self._ctrl_press_pos is not None and hit != self._ctrl_press_pos:
            self._ctrl_timer.stop()
            self._ctrl_press_pos = None

        if hit != self._hovered_cell:
            self._hovered_cell = hit
            self.update()

        if hit:
            r, c = hit
            col = self._colors[r][c] if self._colors else mk_color(0, 0, 0)
            red, green, blue = col.red(), col.green(), col.blue()
            c_hex = f"#{red:02x}{green:02x}{blue:02x}"
            lum = 0.299 * red + 0.587 * green + 0.114 * blue
            contrast_txt = "#000000" if lum > 130 else "#ffffff"

            tags = []
            if (r, c) in self._anchors:
                tags.append(f"<span style='border: 1px solid {contrast_txt}; border-radius: 2px; padding: 0 3px;'>anchor</span>")
            if (r, c) == self._picked_cell:
                tags.append(f"<span style='border: 1px solid {contrast_txt}; border-radius: 2px; padding: 0 3px;'>picked</span>")
            tag_str = ("&nbsp; " + " ".join(tags)) if tags else ""

            tip = (
                f"<div style='background-color: {c_hex}; color: {contrast_txt}; "
                f"border: 1px solid {contrast_txt}; border-radius: 3px; padding: 3px 6px; font-weight: bold;'>"
                f"({c}, {r}) &nbsp; rgb({red}, {green}, {blue}){tag_str}"
                f"</div>"
            )
            self.setToolTip(tip)
        else:
            self.setToolTip("")

    def leaveEvent(self, event):
        if self._hovered_cell is not None:
            self._hovered_cell = None
            self.update()
        if self._ctrl_press_pos is not None:
            self._ctrl_timer.stop()
            self._ctrl_press_pos = None
        super().leaveEvent(event)

    def _do_set(self, r, c):
        color = read_active_color()
        if color is not None:
            self._anchors[(r, c)] = color
            self._recompute()
            self.anchorsChanged.emit()
            self.update()
