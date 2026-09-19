# SPDX-FileCopyrightText: 2026 ameradius
# SPDX-License-Identifier: GPL-3.0-or-later
# Based on an original concept by Tayete's Intermediate Palette.

import math
from .color_math import mk_color, blend_colors, colmix_transform

GRID_SOLVERS = [
    "Linear Interpolation with Heuristic Voronoi Fallback",
    "Steady-State Heat Equation (Laplacian)",
    "Coons Grid-Line Patching Interpolation",
    "Shepard's Method (Inverse Distance Weighting)",
]


def solve_linpol(rows, cols, anchors, mixer_mode):
    ar = sorted({r for (r, _) in anchors} | {0, rows - 1})
    ac = sorted({c for (_, c) in anchors} | {0, cols - 1})

    def patch_corner(r, c, r0, r1, c0, c1):
        if (r, c) in anchors:
            return anchors[(r, c)]
        sr = sorted(cc for (rr, cc) in anchors if rr == r and c0 <= cc <= c1)
        if len(sr) >= 2:
            L = max(x for x in sr if x <= c)
            R = min(x for x in sr if x >= c)
            if L != R:
                return colmix_transform(anchors[(r, L)], anchors[(r, R)], (c - L) / (R - L), mode=mixer_mode)
            return anchors[(r, L)]
        sc = sorted(rr for (rr, cc) in anchors if cc == c and r0 <= rr <= r1)
        if len(sc) >= 2:
            T = max(x for x in sc if x <= r)
            B = min(x for x in sc if x >= r)
            if T != B:
                return colmix_transform(anchors[(T, c)], anchors[(B, c)], (r - T) / (B - T), mode=mixer_mode)
            return anchors[(T, c)]
        best = min(anchors.keys(), key=lambda p: (p[0] - r) ** 2 + (p[1] - c) ** 2)
        return anchors[best]

    grid = []
    for r in range(rows):
        row = []
        r0 = max(x for x in ar if x <= r)
        r1 = min(x for x in ar if x >= r)
        for c in range(cols):
            if (r, c) in anchors:
                row.append(anchors[(r, c)])
            else:
                c0 = max(x for x in ac if x <= c)
                c1 = min(x for x in ac if x >= c)
                tl = patch_corner(r0, c0, r0, r1, c0, c1)
                tr = patch_corner(r0, c1, r0, r1, c0, c1)
                bl = patch_corner(r1, c0, r0, r1, c0, c1)
                br = patch_corner(r1, c1, r0, r1, c0, c1)
                tx = (c - c0) / (c1 - c0) if c1 != c0 else 0.0
                ty = (r - r0) / (r1 - r0) if r1 != r0 else 0.0
                top = colmix_transform(tl, tr, tx, mode=mixer_mode)
                bot = colmix_transform(bl, br, tx, mode=mixer_mode)
                row.append(colmix_transform(top, bot, ty, mode=mixer_mode))
        grid.append(row)
    return grid


def solve_laplacian(rows, cols, anchors, mixer_mode):
    ar = sorted({r for (r, _) in anchors} | {0, rows - 1})
    ac = sorted({c for (_, c) in anchors} | {0, cols - 1})
    m, n = len(ar), len(ac)

    junctions = [[None for _ in range(n)] for _ in range(m)]
    fixed = [[False for _ in range(n)] for _ in range(m)]

    all_colors = list(anchors.values())
    default_color = blend_colors(all_colors, [1.0] * len(all_colors), mode=mixer_mode)

    for i in range(m):
        for j in range(n):
            pos = (ar[i], ac[j])
            if pos in anchors:
                junctions[i][j] = anchors[pos]
                fixed[i][j] = True
            else:
                junctions[i][j] = default_color

    dr = [ar[i + 1] - ar[i] for i in range(m - 1)] if m > 1 else [1]
    dc = [ac[j + 1] - ac[j] for j in range(n - 1)] if n > 1 else [1]

    # Iterative Gauss-Seidel
    for _ in range(40):
        for i in range(m):
            for j in range(n):
                if fixed[i][j]:
                    continue
                neigh_colors = []
                neigh_weights = []
                if i > 0:
                    w = 1.0 / max(1, dr[i - 1])
                    neigh_colors.append(junctions[i - 1][j])
                    neigh_weights.append(w)
                if i < m - 1:
                    w = 1.0 / max(1, dr[i])
                    neigh_colors.append(junctions[i + 1][j])
                    neigh_weights.append(w)
                if j > 0:
                    w = 1.0 / max(1, dc[j - 1])
                    neigh_colors.append(junctions[i][j - 1])
                    neigh_weights.append(w)
                if j < n - 1:
                    w = 1.0 / max(1, dc[j])
                    neigh_colors.append(junctions[i][j + 1])
                    neigh_weights.append(w)
                if neigh_colors:
                    junctions[i][j] = blend_colors(neigh_colors, neigh_weights, mode=mixer_mode)

    # Bilinearly interpolate patches using the diffused junctions
    grid = []
    ar_map = {val: idx for idx, val in enumerate(ar)}
    ac_map = {val: idx for idx, val in enumerate(ac)}

    for r in range(rows):
        row = []
        r0 = max(x for x in ar if x <= r)
        r1 = min(x for x in ar if x >= r)
        i0 = ar_map[r0]
        i1 = ar_map[r1]
        for c in range(cols):
            if (r, c) in anchors:
                row.append(anchors[(r, c)])
            else:
                c0 = max(x for x in ac if x <= c)
                c1 = min(x for x in ac if x >= c)
                j0 = ac_map[c0]
                j1 = ac_map[c1]

                tl = junctions[i0][j0]
                tr = junctions[i0][j1]
                bl = junctions[i1][j0]
                br = junctions[i1][j1]

                tx = (c - c0) / (c1 - c0) if c1 != c0 else 0.0
                ty = (r - r0) / (r1 - r0) if r1 != r0 else 0.0
                top = colmix_transform(tl, tr, tx, mode=mixer_mode)
                bot = colmix_transform(bl, br, tx, mode=mixer_mode)
                row.append(colmix_transform(top, bot, ty, mode=mixer_mode))
        grid.append(row)
    return grid


def solve_coons_patch(rows, cols, anchors, mixer_mode):

    # Project anchors and grid bounds to Cartesian grid lines
    ar = sorted({r for (r, _) in anchors} | {0, rows - 1})
    ac = sorted({c for (_, c) in anchors} | {0, cols - 1})
    m, n = len(ar), len(ac)

    # Grid corners (anchors or nearest)
    corners = [(0, 0), (0, cols - 1), (rows - 1, 0), (rows - 1, cols - 1)]
    corner_colors = {}
    for cr, cc in corners:
        if (cr, cc) in anchors:
            corner_colors[(cr, cc)] = anchors[(cr, cc)]
        else:
            best = min(anchors.keys(), key=lambda p: (p[0] - cr) ** 2 + (p[1] - cc) ** 2)
            corner_colors[(cr, cc)] = anchors[best]

    TL = corner_colors[(0, 0)]
    TR = corner_colors[(0, cols - 1)]
    BL = corner_colors[(rows - 1, 0)]
    BR = corner_colors[(rows - 1, cols - 1)]

    # Interpolation stuff
    def interpolate_1d(length, fixed_start, fixed_end, line_anchors):
        pts = [(0, fixed_start)]
        for idx in sorted(line_anchors.keys()):
            if 0 < idx < length - 1:
                pts.append((idx, line_anchors[idx]))
        pts.append((length - 1, fixed_end))

        line = [None] * length
        for k in range(len(pts) - 1):
            i0, v0 = pts[k]
            i1, v1 = pts[k + 1]
            span = max(1, i1 - i0)
            for idx in range(i0, i1 + 1):
                t = (idx - i0) / span
                line[idx] = colmix_transform(v0, v1, t, mode=mixer_mode)
        return line

    top_edge = interpolate_1d(cols, TL, TR, {c: anchors[(0, c)] for c in range(cols) if (0, c) in anchors})
    bottom_edge = interpolate_1d(cols, BL, BR, {c: anchors[(rows - 1, c)] for c in range(cols) if (rows - 1, c) in anchors})
    left_edge = interpolate_1d(rows, TL, BL, {r: anchors[(r, 0)] for r in range(rows) if (r, 0) in anchors})
    right_edge = interpolate_1d(rows, TR, BR, {r: anchors[(r, cols - 1)] for r in range(rows) if (r, cols - 1) in anchors})

    # 1D piecewise linear interpolation for the horizontal and vertical lines at junctions
    H_junc = [[None for _ in range(n)] for _ in range(m)]
    for i, r in enumerate(ar):
        row_anc = {c: anchors[(r, c)] for c in range(cols) if (r, c) in anchors}
        row_line = interpolate_1d(cols, left_edge[r], right_edge[r], row_anc)
        for j, c in enumerate(ac):
            H_junc[i][j] = row_line[c]

    V_junc = [[None for _ in range(n)] for _ in range(m)]
    for j, c in enumerate(ac):
        col_anc = {r: anchors[(r, c)] for r in range(rows) if (r, c) in anchors}
        col_line = interpolate_1d(rows, top_edge[c], bottom_edge[c], col_anc)
        for i, r in enumerate(ar):
            V_junc[i][j] = col_line[r]

    # Solve junctions with Coons Boolean sum
    junctions = [[None for _ in range(n)] for _ in range(m)]
    for i, r in enumerate(ar):
        v = r / max(1, rows - 1)
        for j, c in enumerate(ac):
            if (r, c) in anchors:
                junctions[i][j] = anchors[(r, c)]
            else:
                u = c / max(1, cols - 1)
                top_b = colmix_transform(TL, TR, u, mode=mixer_mode)
                bot_b = colmix_transform(BL, BR, u, mode=mixer_mode)
                B = colmix_transform(top_b, bot_b, v, mode=mixer_mode)

                H = H_junc[i][j]
                V = V_junc[i][j]

                cr = max(0, min(255, int(round(H.red() + V.red() - B.red()))))
                cg = max(0, min(255, int(round(H.green() + V.green() - B.green()))))
                cb = max(0, min(255, int(round(H.blue() + V.blue() - B.blue()))))
                junctions[i][j] = mk_color(cr, cg, cb)

    # Evaluate each patch
    grid = []
    ar_map = {val: idx for idx, val in enumerate(ar)}
    ac_map = {val: idx for idx, val in enumerate(ac)}

    for r in range(rows):
        row = []
        r0 = max(x for x in ar if x <= r)
        r1 = min(x for x in ar if x >= r)
        i0, i1 = ar_map[r0], ar_map[r1]
        ty = (r - r0) / (r1 - r0) if r1 != r0 else 0.0

        for c in range(cols):
            if (r, c) in anchors:
                row.append(anchors[(r, c)])
            else:
                c0 = max(x for x in ac if x <= c)
                c1 = min(x for x in ac if x >= c)
                j0, j1 = ac_map[c0], ac_map[c1]
                tx = (c - c0) / (c1 - c0) if c1 != c0 else 0.0

                tl = junctions[i0][j0]
                tr = junctions[i0][j1]
                bl = junctions[i1][j0]
                br = junctions[i1][j1]

                top = colmix_transform(tl, tr, tx, mode=mixer_mode)
                bot = colmix_transform(bl, br, tx, mode=mixer_mode)
                row.append(colmix_transform(top, bot, ty, mode=mixer_mode))
        grid.append(row)

    return grid


def solve_idw(rows, cols, anchors, mixer_mode):
    pts = list(anchors.keys())
    colors = [anchors[pt] for pt in pts]

    grid = []
    for r in range(rows):
        row = []
        for c in range(cols):
            if (r, c) in anchors:
                row.append(anchors[(r, c)])
                continue
            dists = [math.hypot(r - pr, c - pc) for (pr, pc) in pts]
            weights = [1.0 / (d * d) for d in dists]
            row.append(blend_colors(colors, weights, mode=mixer_mode))
        grid.append(row)
    return grid


def compute_palette_grid(rows, cols, anchors, solver_name, mixer_name):
    num_anchors = len(anchors)
    if num_anchors == 0:
        black = mk_color(0, 0, 0)
        return [[black for _ in range(cols)] for _ in range(rows)]
    if num_anchors == 1:
        single_color = next(iter(anchors.values()))
        return [[single_color for _ in range(cols)] for _ in range(rows)]

    if solver_name in ("Steady-State Heat Equation (Laplacian)"):
        return solve_laplacian(rows, cols, anchors, mixer_name)
    elif solver_name in ("Coons Grid-Line Patching Interpolation"):
        return solve_coons_patch(rows, cols, anchors, mixer_name)
    elif solver_name in ("Shepard's Method (Inverse Distance Weighting)"):
        return solve_idw(rows, cols, anchors, mixer_name)
    else:
        return solve_linpol(rows, cols, anchors, mixer_name)
