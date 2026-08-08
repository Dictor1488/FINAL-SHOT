# -*- coding: utf-8 -*-
"""Keep Final Shot impact callouts attached to the live wreck transforms."""

from __future__ import absolute_import

import logging

import BigWorld

try:
    from gui.mods import mod_zzzzz_inq_final_shot_battle_viewer as viewer_mod
    from gui.mods import mod_zzz_inq_final_shot_impacts as impacts
except ImportError:
    viewer_mod = None
    impacts = None

logger = logging.getLogger('inq.final_shot.attachment')
ATTACH_INTERVAL = 0.05


def _cache_hit_data_live(self):
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
            # Validate the point once, but keep the original local hit point.
            # World-space is recalculated from the current hull/turret/gun node
            # so the callout follows a wreck that slides, rocks or settles.
            if self._world_point(point) is None:
                continue
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
                'fatal': bool(hit.get('fatal')),
                'player': player_name,
                'vehicle': vehicle_name,
                'damage': int(hit.get('damage', 0) or 0),
                'icon': self._attacker_icon(attacker_id),
                'side': 1 if hit_index % 2 else -1,
                'offsetY': (-30, 18, -8)[(hit_index - 1) % 3],
            })
    except Exception:
        logger.exception('failed to cache live hit anchors')


def _marker_data_live(self):
    markers = []
    if not self._cached_markers:
        return markers
    width, height = viewer_mod.GUI.screenResolution()
    width = float(width)
    height = float(height)
    for item in self._cached_markers:
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


def _frame_live(self):
    self.frame_callback = None
    if not self.active:
        return
    try:
        now = float(BigWorld.time())
        camera_changed = self._camera_dirty
        if camera_changed:
            self._camera_dirty = False

        next_attach = float(getattr(self, '_inq_next_attach_update', 0.0) or 0.0)
        if now >= next_attach:
            self._inq_next_attach_update = now + ATTACH_INTERVAL
            # The wreck can still move for several seconds after destruction.
            # Follow its center only when it really changed.
            if self.vehicle is not None:
                new_center = self._vehicle_center(self.vehicle)
                try:
                    moved = (abs(new_center.x - self.center.x) > 0.001 or
                             abs(new_center.y - self.center.y) > 0.001 or
                             abs(new_center.z - self.center.z) > 0.001)
                except Exception:
                    moved = True
                if moved:
                    self.center = new_center
                    camera_changed = True
            # Part transforms (especially turret/gun and a settling wreck) can
            # change even when the root vehicle position barely changes.
            self._markers_dirty = True

        if camera_changed:
            self._apply_camera()
        if self._markers_dirty and self.view is not None and self.flash_ready:
            self._markers_dirty = False
            self.view.flashObject.as_updateMarkers(self._marker_data())
    except Exception:
        logger.exception('live attachment frame failed')
    if self.active:
        self._schedule_frame()


def _install():
    if viewer_mod is None:
        logger.error('battle viewer module unavailable')
        return
    cls = getattr(viewer_mod, 'BattleViewer', None)
    instance = getattr(viewer_mod, '_viewer', None)
    if cls is None or instance is None:
        logger.error('battle viewer class or instance unavailable')
        return
    if getattr(cls, '_inq_live_attachment_patch', False):
        return
    cls._cache_hit_data = _cache_hit_data_live
    cls._marker_data = _marker_data_live
    cls._frame = _frame_live
    cls._inq_live_attachment_patch = True
    instance._inq_next_attach_update = 0.0
    logger.info('live wreck attachment patch installed')


_install()
