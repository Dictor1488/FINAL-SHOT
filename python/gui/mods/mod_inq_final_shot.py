# -*- coding: utf-8 -*-
"""Single World of Tanks ScriptLoader entry point for INQ Final Shot."""

from __future__ import absolute_import

import gui.mods as _mods

# Load the real implementation package. Do not replace entries in sys.modules:
# the WoT embedded Python environment may expose sys as an unavailable stub
# during early mod discovery, which crashes the whole client.
from gui.mods.inq_final_shot import core as _core

# Re-export the core namespace through this real ScriptLoader module so legacy
# internal references to gui.mods.mod_inq_final_shot keep working naturally.
for _name in dir(_core):
    if not _name.startswith('__'):
        globals()[_name] = getattr(_core, _name)

# Load extensions in one explicit order. Compatibility attributes are placed on
# the gui.mods package itself; `from gui.mods import <name>` can resolve them
# without touching sys.modules and without creating additional top-level files.
from gui.mods.inq_final_shot import health as _health
setattr(_mods, 'mod_inq_final_shot_10_health', _health)

from gui.mods.inq_final_shot import impacts as _impacts
setattr(_mods, 'mod_inq_final_shot_20_impacts', _impacts)

from gui.mods.inq_final_shot import battle_viewer as _battle_viewer
setattr(_mods, 'mod_inq_final_shot_30_battle_viewer', _battle_viewer)

from gui.mods.inq_final_shot import stable_markers as _stable_markers
setattr(_mods, 'mod_inq_final_shot_40_stable_markers', _stable_markers)

from gui.mods.inq_final_shot import observer_visibility as _observer_visibility
setattr(_mods, 'mod_inq_final_shot_50_observer_visibility', _observer_visibility)

from gui.mods.inq_final_shot import runtime as _runtime
