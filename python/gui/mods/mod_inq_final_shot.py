# -*- coding: utf-8 -*-
"""Single World of Tanks ScriptLoader entry point for INQ Final Shot."""

from __future__ import absolute_import

import types

import gui.mods as _mods
from gui.Scaleform.framework import g_entitiesFactories as _factories


# core.py still contains the retired FinalShotPanelBattle registration. The
# factory logs an ERROR when removeSettings() is called for an alias that does
# not exist, even though core.py catches the exception. Suppress only that old
# removal while core initializes; the active FinalShotBattleViewer registration
# is not touched.
_original_remove_settings = _factories.removeSettings


def _remove_settings_without_legacy_error(alias, *args, **kwargs):
    if alias == 'FinalShotPanelBattle':
        return None
    return _original_remove_settings(alias, *args, **kwargs)


_factories.removeSettings = _remove_settings_without_legacy_error
try:
    # Load the real implementation package. Do not replace entries in
    # sys.modules: the WoT embedded Python environment may expose sys as an
    # unavailable stub during early mod discovery.
    from gui.mods.inq_final_shot import core as _core
finally:
    _factories.removeSettings = _original_remove_settings

# core registered the retired view after the suppressed removal. Remove that
# registration now while it is known to exist. This prevents any later attempt
# to load the removed FinalShotPanelBattle.swf.
try:
    _original_remove_settings('FinalShotPanelBattle')
except Exception:
    pass

# Disable the old panel injector at the source. The passive battle viewer loaded
# below is the only UI that should be opened after the player's vehicle dies.
def _no_legacy_inject(self, attempt=0):
    self.inject_callback = None
    return None


try:
    _core._controller._inject = types.MethodType(
        _no_legacy_inject, _core._controller, _core._controller.__class__)
except Exception:
    pass

# Re-export the core namespace through this real ScriptLoader module.
for _name in dir(_core):
    if not _name.startswith('__'):
        globals()[_name] = getattr(_core, _name)

# Publish the core compatibility alias before loading extensions. Some internal
# modules still import gui.mods.mod_inq_final_shot during their module import,
# so the parent package must already expose that attribute at this point.
setattr(_mods, 'mod_inq_final_shot', _core)

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
