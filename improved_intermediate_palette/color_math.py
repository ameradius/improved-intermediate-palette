# SPDX-FileCopyrightText: 2026 ameradius
# SPDX-License-Identifier: GPL-3.0-or-later
# Based on an original concept by Tayete's Intermediate Palette.

import math
from PyQt5.QtGui import QColor
from krita import ManagedColor, Krita

COLOR_MIXERS = [
    "sRGB",
    "Linear sRGB",
    "Oklab",
    "OKLCH",
]


def mk_color(r, g, b):
    c = QColor()
    c.setRgb(int(r), int(g), int(b), 255)
    return c


def contrast_color(color):
    # Black or white contrast to perceived brightness
    lum = 0.299 * color.red() + 0.587 * color.green() + 0.114 * color.blue()
    return mk_color(0, 0, 0) if lum > 130 else mk_color(255, 255, 255)


def hover_color_for(color):
    # Bright color to light up edges on hover
    lum = 0.299 * color.red() + 0.587 * color.green() + 0.114 * color.blue()
    return mk_color(0, 220, 255) if lum > 200 else mk_color(255, 255, 255)


def is_orange_tint(color):
    # Contrasting selection highlight color (amber/orange)
    return color.red() > 180 and 80 < color.green() < 220 and color.blue() < 80


def read_active_color():
    app = Krita.instance()
    win = app.activeWindow()
    if not win:
        return None
    view = win.activeView()
    if not view:
        return None
    managed = view.foregroundColor()
    if managed is None:
        return None
    comps = managed.components()
    if comps is None or len(comps) < 3:
        return None
    b = max(0, min(255, int(round(float(comps[0]) * 255))))
    g = max(0, min(255, int(round(float(comps[1]) * 255))))
    r = max(0, min(255, int(round(float(comps[2]) * 255))))
    return mk_color(r, g, b)


def write_active_color(color):
    app = Krita.instance()
    win = app.activeWindow()
    if not win:
        return
    view = win.activeView()
    if not view:
        return
    managed = ManagedColor("RGBA", "U8", "")
    managed.setComponents([
        color.blue() / 255.0,
        color.green() / 255.0,
        color.red() / 255.0,
        1.0,
    ])
    view.setForeGroundColor(managed)


def srgb_to_linear(c):
    c = max(0.0, min(1.0, c))
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def linear_to_srgb(c):
    c = max(0.0, min(1.0, c))
    return 12.92 * c if c <= 0.0031308 else 1.055 * (c ** (1.0 / 2.4)) - 0.055


def _cbrt(x):
    return math.pow(x, 1.0 / 3.0) if x > 0 else (-math.pow(-x, 1.0 / 3.0) if x < 0 else 0.0)


def rgb_to_oklab(r, g, b):
    lr = srgb_to_linear(r)
    lg = srgb_to_linear(g)
    lb = srgb_to_linear(b)
    l = 0.4122214708 * lr + 0.5363325363 * lg + 0.0514459929 * lb
    m = 0.2119034982 * lr + 0.6806995451 * lg + 0.1073969566 * lb
    s = 0.0883024619 * lr + 0.2817188376 * lg + 0.6299787005 * lb
    l_ = _cbrt(l)
    m_ = _cbrt(m)
    s_ = _cbrt(s)
    L = 0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_
    a = 1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_
    b = 0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_
    return L, a, b


def oklab_to_rgb(L, a, b):
    l_ = L + 0.3963377774 * a + 0.2158037573 * b
    m_ = L - 0.1055613458 * a - 0.0638541728 * b
    s_ = L - 0.0894841775 * a - 1.2914855480 * b
    l = l_ * l_ * l_
    m = m_ * m_ * m_
    s = s_ * s_ * s_
    lr = +4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s
    lg = -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s
    lb = -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s
    r = linear_to_srgb(lr)
    g = linear_to_srgb(lg)
    b = linear_to_srgb(lb)
    return max(0.0, min(1.0, r)), max(0.0, min(1.0, g)), max(0.0, min(1.0, b))


def oklab_to_oklch(L, a, b):
    C = math.hypot(a, b)
    h = math.atan2(b, a)
    if h < 0:
        h += 2.0 * math.pi
    return L, C, h


def oklch_to_oklab(L, C, h):
    return L, C * math.cos(h), C * math.sin(h)


def blend_colors(colors, weights, mode="Linear sRGB"):

    if not colors:
        return mk_color(0, 0, 0)
    if len(colors) == 1:
        return colors[0]

    w_sum = sum(weights)
    if w_sum > 0:
        weights = [w / w_sum for w in weights]
    else:
        weights = [1.0 / len(colors)] * len(colors)

    rgb_tuples = [(c.red(), c.green(), c.blue()) for c in colors]

    # Blend color modes here

    if mode == "sRGB":
        r = sum(w * c[0] for w, c in zip(weights, rgb_tuples))
        g = sum(w * c[1] for w, c in zip(weights, rgb_tuples))
        b = sum(w * c[2] for w, c in zip(weights, rgb_tuples))
        return mk_color(max(0, min(255, int(round(r)))),
                        max(0, min(255, int(round(g)))),
                        max(0, min(255, int(round(b)))))

    elif mode == "Linear sRGB":
        r_lin = sum(w * srgb_to_linear(c[0] / 255.0) for w, c in zip(weights, rgb_tuples))
        g_lin = sum(w * srgb_to_linear(c[1] / 255.0) for w, c in zip(weights, rgb_tuples))
        b_lin = sum(w * srgb_to_linear(c[2] / 255.0) for w, c in zip(weights, rgb_tuples))
        r = linear_to_srgb(r_lin) * 255.0
        g = linear_to_srgb(g_lin) * 255.0
        b = linear_to_srgb(b_lin) * 255.0
        return mk_color(max(0, min(255, int(round(r)))),
                        max(0, min(255, int(round(g)))),
                        max(0, min(255, int(round(b)))))

    elif mode == "Oklab":
        oklabs = [rgb_to_oklab(c[0] / 255.0, c[1] / 255.0, c[2] / 255.0) for c in rgb_tuples]
        L = sum(w * ok[0] for w, ok in zip(weights, oklabs))
        a = sum(w * ok[1] for w, ok in zip(weights, oklabs))
        b = sum(w * ok[2] for w, ok in zip(weights, oklabs))
        r, g, b = oklab_to_rgb(L, a, b)
        return mk_color(max(0, min(255, int(round(r * 255.0)))),
                        max(0, min(255, int(round(g * 255.0)))),
                        max(0, min(255, int(round(b * 255.0)))))

    elif mode == "OKLCH":
        oklabs = [rgb_to_oklab(c[0] / 255.0, c[1] / 255.0, c[2] / 255.0) for c in rgb_tuples]
        oklchs = [oklab_to_oklch(*ok) for ok in oklabs]
        L = sum(w * ok[0] for w, ok in zip(weights, oklchs))
        C = sum(w * ok[1] for w, ok in zip(weights, oklchs))

        if len(colors) == 2:
            h1, h2 = oklchs[0][2], oklchs[1][2]
            if oklchs[0][1] < 1e-4:
                h = h2
            elif oklchs[1][1] < 1e-4:
                h = h1
            else:
                diff = (h2 - h1) % (2.0 * math.pi)
                if diff > math.pi:
                    diff -= 2.0 * math.pi
                h = h1 + weights[1] * diff
        else:
            X = sum(w * ok[1] * math.cos(ok[2]) for w, ok in zip(weights, oklchs))
            Y = sum(w * ok[1] * math.sin(ok[2]) for w, ok in zip(weights, oklchs))
            if math.hypot(X, Y) > 1e-6:
                h = math.atan2(Y, X)
            else:
                h = sum(w * ok[2] for w, ok in zip(weights, oklchs))

        L_val, a_val, b_val = oklch_to_oklab(L, C, h)
        r, g, b = oklab_to_rgb(L_val, a_val, b_val)
        return mk_color(max(0, min(255, int(round(r * 255.0)))),
                        max(0, min(255, int(round(g * 255.0)))),
                        max(0, min(255, int(round(b * 255.0)))))

    return colors[0]


def colmix_transform(c1, c2, t, mode="Linear sRGB"):
    t = max(0.0, min(1.0, float(t)))
    return blend_colors([c1, c2], [1.0 - t, t], mode=mode)
