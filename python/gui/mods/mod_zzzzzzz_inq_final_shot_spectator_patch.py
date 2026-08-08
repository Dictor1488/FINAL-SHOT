# -*- coding: utf-8 -*-
"""Passive spectator-mode Final Shot viewer.

Keeps the stock WoT postmortem/spectator camera fully in control. Impact points are
frozen once the wreck has settled, then only projected to screen while spectating.
"""

from __future__ import absolute_import

import logging

import BigWorld

try:
    from gui.mods import mod_zzzzz_inq_final_shot_battle_viewer as viewer_mod
    from gui.mods import mod_zzz_inq_final_shot_impacts as impacts
except ImportError:
    viewer_mod = None
    impacts = None

logger = logging.getLogger('inq.final_shot.spectator')
SETTLE_DELAY = 1.35
PROJECT_INTERVAL = 0.05


def _cache_local_hits(self):
    self._cached_markers = []
    if self.controller is None:
        return
    try:
        if impacts is not None:
            impacts._decorate_hits(self.controller)
        hit_index = 0
        for hit in self.controller.hits:
            points = hit.get('impactPoints') or ()
            if not points:
                continue
            point = points[0]
            hit_index += 1
            attacker_id = int(hit.get('attackerID', 0) or 0)
            player_name = unicode(hit.get('player') or u'')
            vehicle_name = unicode(hit.get('vehicle') or u'')
            if not player_name or not vehicle_name:
                try:
                    vehicle_name, player_name = self.controller._vehicle_identity(attacker_id)
                except Exception:
                    pass
            self._cached_markers.append({
                'point': point,
                'world': None,
                'fatal': bool(hit.get('fatal')),
                'player': player_name,
                'vehicle': vehicle_name,
                'damage': int(hit.get('damage', 0) or 0),
                'icon': self._attacker_icon(attacker_id),
                'side': 1 if hit_index % 2 else -1,
                'offsetY': (-30, 18, -8)[(hit_index - 1) % 3],
            })
    except Exception:
        logger.exception('failed to cache spectator hit anchors')


def _freeze_world_points(self):
    self._inq_freeze_callback = None
    if not self.active:
        return
    frozen = 0
    for item in self._cached_markers:
        try:
            world = self._world_point(item.get('point'))
            if world is not None:
                item['world'] = viewer_mod.Math.Vector3(world)
                frozen += 1
        except Exception:
            pass
    self._inq_points_frozen = True
    logger.info('frozen %s impact points after wreck settle', frozen)


def _marker_data_passive(self):
    markers = []
    if not self._cached_markers:
        return markers
    width, height = viewer_mod.GUI.screenResolution()
    width = float(width)
    height = float(height)
    for item in self._cached_markers:
        world = item.get('world')
        if world is None:
            # During the short settling window, follow the part so the marker does
            # not visibly detach from a still-moving wreck.
            world = self._world_point(item.get('point'))
        if world is None:
            continue
        projected = viewer_mod.projectPoint(world)
        if projected.w <= 0.0:
            continue
        if not (-1.08 <= projected.x <= 1.08 and -1.08 <= projected.y <= 1.08):
            continue
        markers.append({
            'x': (projected.x + 1.0) * 0.5 * width,
            'y': (1.0 - projected.y) * 0.5 * height,
            'fatal': item['fatal'],
            'player': item['player'],
            'vehicle': item['vehicle'],
            'damage': item['damage'],
            'icon': item['icon'],
            'side': item['side'],
            'offsetY': item['offsetY'],
        })
    return markers


def _open_passive(self):
    self.open_callback = None
    if self.active or not self.vehicle_id:
        return
    try:
        vehicle = BigWorld.entity(self.vehicle_id)
        if vehicle is None:
            vehicle = BigWorld.entities.get(self.vehicle_id)
        if vehicle is None:
            logger.warning('destroyed player vehicle is unavailable')
            return
        self.vehicle = vehicle
        self._cache_hit_data()
        self.active = True
        self._inq_points_frozen = False
        self._inq_freeze_callback = BigWorld.callback(SETTLE_DELAY, lambda: _freeze_world_points(self))
        self._inject(0)
        self._schedule_frame(0.0)
        logger.info('passive spectator viewer opened with %s impact markers', len(self._cached_markers))
    except Exception:
        logger.exception('failed to open passive spectator viewer')
        self.close()


def _frame_passive(self):
    self.frame_callback = None
    if not self.active:
        return
    try:
        # Never touch BigWorld.camera() and never consume input. The stock
        # postmortem/spectator camera can rotate and switch allied vehicles freely.
        if self.view is not None and self.flash_ready:
            self.view.flashObject.as_updateMarkers(self._marker_data())
    except Exception:
        logger.exception('passive spectator projection failed')
    if self.active:
        self._schedule_frame(PROJECT_INTERVAL)


def _close_passive(self):
    freeze_callback = getattr(self, '_inq_freeze_callback', None)
    try:
        if freeze_callback is not None:
            BigWorld.cancelCallback(freeze_callback)
    except Exception:
        pass
    self._inq_freeze_callback = None
    # Call the original viewer close after neutralizing camera fields so it cannot
    # restore/replace a spectator camera that belongs to the game.
    self.free_camera = None
    self.previous_camera = None
    return self._inq_original_close()


def _install():
    if viewer_mod is None:
        logger.error('battle viewer module unavailable')
        return
    cls = getattr(viewer_mod, 'BattleViewer', None)
    instance = getattr(viewer_mod, '_viewer', None)
    if cls is None or instance is None:
        logger.error('battle viewer class or instance unavailable')
        return
    if getattr(cls, '_inq_passive_spectator_patch', False):
        return

    cls._inq_original_close = cls.close
    cls._cache_hit_data = _cache_local_hits
    cls._marker_data = _marker_data_passive
    cls.open = _open_passive
    cls._frame = _frame_passive
    cls.close = _close_passive

    # Disable every custom input/camera path from the older implementation.
    cls.handle_mouse = lambda self, event: False
    cls.handle_key = lambda self, event: False
    cls._apply_camera = lambda self: None

    cls._inq_passive_spectator_patch = True
    instance._inq_points_frozen = False
    instance._inq_freeze_callback = None
    logger.info('passive spectator patch installed')


_install()
