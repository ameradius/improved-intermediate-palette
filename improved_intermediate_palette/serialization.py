# SPDX-FileCopyrightText: 2026 ameradius
# SPDX-License-Identifier: GPL-3.0-or-later
# Based on an original concept by Tayete's Intermediate Palette.

import io
import zipfile
import xml.etree.ElementTree as ET
from .color_math import mk_color


def anchors_to_dict(anchors, rows, cols, solver=None, mixer=None, picked=None):
    d = {
        "rows": rows,
        "cols": cols,
        "anchors": {
            "{},{}".format(r, c): [color.red(), color.green(), color.blue()]
            for (r, c), color in anchors.items()
        }
    }
    if solver:
        d["solver"] = solver
    if mixer:
        d["mixer"] = mixer
    if picked:
        d["picked"] = list(picked)
    return d


def dict_to_anchors(data):
    rows = data.get("rows", 12)
    cols = data.get("cols", 12)
    anchors = {}
    for key, rgb in data.get("anchors", {}).items():
        r, c = map(int, key.split(","))
        anchors[(r, c)] = mk_color(*rgb)
    return anchors, rows, cols


def export_kpl_palette(path, colors, rows, cols):
    """Write color grid to a Krita Palette (.kpl) container."""
    root = ET.Element("Colorset")
    root.set("version", "2.0")
    root.set("name", "Improved Intermediate Palette")
    root.set("comment", "")
    root.set("columns", str(cols))
    root.set("rows", str(rows))

    for r in range(rows):
        for c in range(cols):
            col = colors[r][c]
            entry = ET.SubElement(root, "ColorSetEntry")
            entry.set("name", "")
            entry.set("id", str(r * cols + c))
            entry.set("spot", "false")
            entry.set("bitdepth", "U8")
            rgb_el = ET.SubElement(entry, "RGB")
            rgb_el.set("r", "{:.10f}".format(col.red() / 255.0))
            rgb_el.set("g", "{:.10f}".format(col.green() / 255.0))
            rgb_el.set("b", "{:.10f}".format(col.blue() / 255.0))
            rgb_el.set("space", "sRGB built-in")

    buf = io.BytesIO()
    ET.ElementTree(root).write(buf, encoding="UTF-8", xml_declaration=True)
    xml_bytes = buf.getvalue()

    with zipfile.ZipFile(path, "w") as zf:
        mi = zipfile.ZipInfo("mimetype")
        mi.compress_type = zipfile.ZIP_STORED
        zf.writestr(mi, "application/x-krita-palette")
        zf.writestr("colorset.xml", xml_bytes)
