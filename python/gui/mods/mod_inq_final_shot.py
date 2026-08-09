# -*- coding: utf-8 -*-
"""Single World of Tanks ScriptLoader entry point for INQ Final Shot."""

from __future__ import absolute_import

import sys

# Core creates the controller. ScriptLoader sees only this top-level mod_ file;
# all remaining modules are imported explicitly below in a deterministic order.
from gui.mods.inq_final_shot import core as _core

# Existing internal modules still import gui.mods.mod_inq_final_shot. Point that
# name at the real core module before loading the extensions.
sys.modules[__name__] = _core
sys.modules['gui.mods.mod_inq_final_shot'] = _core

from gui.mods.inq_final_shot import health as _health
sys.modules['gui.mods.mod_inq_final_shot_10_health'] = _health

from gui.mods.inq_final_shot import impacts as _impacts
sys.modules['gui.mods.mod_inq_final_shot_20_impacts'] = _impacts

from gui.mods.inq_final_shot import battle_viewer as _battle_viewer
sys.modules['gui.mods.mod_inq_final_shot_30_battle_viewer'] = _battle_viewer

from gui.mods.inq_final_shot import stable_markers as _stable_markers
sys.modules['gui.mods.mod_inq_final_shot_40_stable_markers'] = _stable_markers

from gui.mods.inq_final_shot import observer_visibility as _observer_visibility
sys.modules['gui.mods.mod_inq_final_shot_50_observer_visibility'] = _observer_visibility

from gui.mods.inq_final_shot import runtime as _runtime
