# -*- coding: utf-8 -*-
"""Show Final Shot markers only while observing the player's own wreck."""

from __future__ import absolute_import

import logging

import BigWorld

try:
    from gui.mods.inq_final_shot import battle_viewer as viewer_mod
    from gui.mods.inq_final_shot import stable_markers as stable_mod
except ImportError:
    viewer_mod = None
    stable_mod = None

try:
    from gui.mods import mod_inq_final_shot_10_health as health_mod
except ImportError:
    health_mod = None

logger = logging.getLogger('inq.final_shot.observer_visibility')
IDLE_INTERVAL = 0.10


def _observed_vehicle_id():
    try:
        player = BigWorld.player()
        if player is None:
            return 0
        attached = getattr(player, 'vehicle', None)
        if attached is not None:
            attached_id = int(getattr(attached, 'id', 0) or 0)
            if attached_id:
                return attached_id
        observed = getattr(player, 'observedVehicleID', None)
        if observed is not None:
            return int(observed or 0)
        getter = getattr(player, 'getObservedVehicleID', None)
        if getter is not None:
            return int(getter() or 0)
        return int(getattr(player, 'playerVehicleID', 0) or 0)
    except Exception:
        return 0


def _attached_live_vehicle():
    """Return the avatar-attached live vehicle, or (None, 0, 0)."""
    try:
        player = BigWorld.player()
        if player is None:
            return None, 0, 0
        attached = getattr(player, 'vehicle', None)
        if attached is None:
            return None, 0, 0
        vehicle_id = int(getattr(attached, 'id', 0) or 0)
        health = int(getattr(attached, 'health', 0) or 0)
        if not vehicle_id or health <= 0:
            return None, vehicle_id, health
        return attached, vehicle_id, health
    except Exception:
        return None, 0, 0


def _reset_if_respawned(self):
    """Close stale death markers when Frontline reattaches a living own vehicle.

    Epic/Frontline can reuse exactly the same vehicle entity ID after death. In
    that flow a positive VEHICLE_HEALTH feedback event is not guaranteed, so the
    reliable signal is the avatar being attached again to a live vehicle while
    the postmortem Final Shot viewer is still active.
    """
    attached, attached_id, health = _attached_live_vehicle()
    if attached is None:
        return False

    dead_vehicle_id = int(getattr(self, 'vehicle_id', 0) or 0)
    if not dead_vehicle_id or attached_id != dead_vehicle_id:
        return False

    controller = getattr(self, 'controller', None)
    if controller is None:
        self.close()
        return True

    try:
        if health_mod is not None:
            reset = getattr(health_mod, '_reset_respawn_state', None)
            if reset is not None:
                reset(controller, attached_id, health)
                logger.info('live avatar reattach detected; closed stale Final Shot after respawn')
                return True
    except Exception:
        logger.exception('health reset helper failed after respawn')

    # Safety fallback: never leave stale markers on a newly alive player even if
    # the health compatibility helper is unavailable in a particular package.
    try:
        self.close()
    except Exception:
        pass
    try:
        controller.pending_show = False
        controller.hits.clear()
        controller.player_vehicle_id = attached_id
        controller._final_shot_last_health = health
        controller._final_shot_dead = False
        controller._inq_authoritative_killer_id = 0
    except Exception:
        logger.exception('fallback Final Shot reset failed after respawn')
    return True


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

    # Frontline/replay respawn path: the same playerVehicleID can come back to
    # life without a positive health feedback event. Check the actual avatar
    # attachment every viewer tick and tear down the previous-life overlay first.
    if _reset_if_respawned(self):
        return

    delay = IDLE_INTERVAL
    try:
        observed_id = _observed_vehicle_id()
        own_id = int(getattr(self, 'vehicle_id', 0) or 0)
        observing_own = bool(own_id and observed_id == own_id)

        if not observing_own:
            # Hidden on allies: no matrices, no projection, no Scaleform marker traffic.
            _set_view_visible(self, False)
            self._inq_last_screen = None
        else:
            _set_view_visible(self, True)

            # Wreck transforms are touched only until the world points are frozen.
            if not getattr(self, '_inq_world_frozen', False):
                stable_mod._sample_wreck(self, float(BigWorld.time()))

            if self.view is not None and self.flash_ready:
                data = self._marker_data()
                previous = getattr(self, '_inq_last_screen', None)
                if stable_mod._screen_changed(previous, data):
                    self.view.flashObject.as_updateMarkers(data)
                    self._inq_last_screen = data

            # While looking at our wreck, follow the stock camera closely.
            delay = stable_mod.FRAME_INTERVAL
    except Exception:
        logger.exception('observer-only marker frame failed')

    if self.active:
        self._schedule_frame(delay)


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
    logger.info('frame-synced observer visibility patch installed')


_install()
