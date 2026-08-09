# -*- coding: utf-8 -*-
"""Show Final Shot impact markers only while observing the player's own wreck."""

from __future__ import absolute_import

import logging

import BigWorld

try:
    from gui.mods import mod_inq_final_shot_30_battle_viewer as viewer_mod
    from gui.mods import mod_inq_final_shot_40_stable_markers as stable_mod
except ImportError:
    viewer_mod = None
    stable_mod = None

logger = logging.getLogger('inq.final_shot.observer_visibility')


def _observed_vehicle_id():
    try:
        player = BigWorld.player()
        if player is None:
            return 0
        getter = getattr(player, 'getObservedVehicleID', None)
        if getter is not None:
            return int(getter() or 0)
        observed = getattr(player, 'observedVehicleID', None)
        if observed is not None:
            return int(observed or 0)
        vehicle = getattr(player, 'vehicle', None)
        if vehicle is not None:
            return int(getattr(vehicle, 'id', 0) or 0)
        return int(getattr(player, 'playerVehicleID', 0) or 0)
    except Exception:
        return 0


def _set_view_visible(self, visible):
    visible = bool(visible)
    self._inq_observer_visible = visible
    if self.view is None or not self.flash_ready:
        return
    if getattr(self, '_inq_flash_visibility_applied', None) == visible:
        return
    try:
        self.view.flashObject.as_setVisible(visible)
        self._inq_flash_visibility_applied = visible
    except Exception:
        logger.exception('failed changing observer marker visibility')


def _frame_observer_only(self):
    self.frame_callback = None
    if not self.active:
        return
    try:
        observed_id = _observed_vehicle_id()
        own_id = int(getattr(self, 'vehicle_id', 0) or 0)
        observing_own = bool(own_id and observed_id == own_id)
        if not observing_own:
            _set_view_visible(self, False)
            self._inq_last_screen = None
        else:
            _set_view_visible(self, True)
            now = float(BigWorld.time())
            stable_mod._sample_wreck(self, now)
            if self.view is not None and self.flash_ready:
                data = self._marker_data()
                previous = getattr(self, '_inq_last_screen', None)
                if stable_mod._screen_changed(previous, data):
                    self.view.flashObject.as_updateMarkers(data)
                    self._inq_last_screen = data
    except Exception:
        logger.exception('observer-only marker frame failed')
    if self.active:
        self._schedule_frame(stable_mod.PROJECT_INTERVAL)


def _open_observer_only(self):
    self._inq_observer_visible = None
    self._inq_flash_visibility_applied = None
    return self._inq_observer_original_open()


def _close_observer_only(self):
    self._inq_observer_visible = None
    self._inq_flash_visibility_applied = None
    return self._inq_observer_original_close()


def _on_flash_ready_observer_only(self, view):
    result = self._inq_observer_original_flash_ready(view)
    self._inq_flash_visibility_applied = None
    return result


def _install():
    if viewer_mod is None or stable_mod is None:
        logger.error('required Final Shot modules are unavailable')
        return
    cls = getattr(viewer_mod, 'BattleViewer', None)
    instance = getattr(viewer_mod, '_viewer', None)
    if cls is None or instance is None:
        logger.error('battle viewer class or instance unavailable')
        return
    if getattr(cls, '_inq_observer_visibility_patch', False):
        return
    cls._inq_observer_original_open = cls.open
    cls._inq_observer_original_close = cls.close
    cls._inq_observer_original_flash_ready = cls.on_flash_ready
    cls.open = _open_observer_only
    cls.close = _close_observer_only
    cls.on_flash_ready = _on_flash_ready_observer_only
    cls._frame = _frame_observer_only
    cls._inq_observer_visibility_patch = True
    instance._inq_observer_visible = None
    instance._inq_flash_visibility_applied = None
    logger.info('observer visibility patch installed')


_install()
