# -*- coding: utf-8 -*-
"""Disable the obsolete FinalShotPanelBattle view.

The current mod renders postmortem hit callouts through FinalShotBattleViewer.
The old summary panel is no longer used, but the base controller still tried to
load its SWF as soon as the Scaleform battle app initialized. At that moment the
client can still be in BattleLoadingSpace, which allowed the panel background to
flash over the battle loading screen.
"""

from __future__ import absolute_import

import types

try:
    from gui.mods import mod_inq_final_shot as final_shot
except ImportError:
    final_shot = None


def _disable_legacy_panel():
    if final_shot is None:
        return
    controller = getattr(final_shot, '_controller', None)
    if controller is None:
        return

    def no_legacy_inject(self, attempt=0):
        self.inject_callback = None
        # The legacy FinalShotPanelBattle is intentionally never loaded.
        # FinalShotBattleViewer is injected independently only after death.
        if self.view is not None:
            try:
                self.view.flashObject.as_setVisible(False)
            except Exception:
                pass
        return

    controller._inject = types.MethodType(no_legacy_inject, controller, controller.__class__)

    # Defensive cleanup for late reloads: if the old view already exists, hide it.
    if getattr(controller, 'view', None) is not None:
        try:
            controller.view.flashObject.as_setVisible(False)
        except Exception:
            pass


_disable_legacy_panel()
