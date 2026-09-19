# SPDX-FileCopyrightText: 2026 ameradius
# SPDX-License-Identifier: GPL-3.0-or-later
# Based on an original concept by Tayete's Intermediate Palette.

from krita import Krita, DockWidgetFactory, DockWidgetFactoryBase
from .improved_intermediate_palette_docker import ImprovedIntermediatePaletteDocker

DOCKER_ID = "improved_intermediate_palette_docker"

instance = Krita.instance()
dock_widget_factory = DockWidgetFactory(
    DOCKER_ID,
    DockWidgetFactoryBase.DockRight,
    ImprovedIntermediatePaletteDocker
)
instance.addDockWidgetFactory(dock_widget_factory)
