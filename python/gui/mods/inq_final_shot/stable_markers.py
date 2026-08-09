# -*- coding: utf-8 -*-
"""Low-cost passive Final Shot markers for the stock spectator camera."""

from __future__ import absolute_import

import logging

import BigWorld

try:
    from gui.mods import mod_inq_final_shot_30_battle_viewer as viewer_mod
    from gui.mods import mod_inq_final_shot_20_impacts as impacts
except ImportError:
    viewer_mod = None
    impacts = None

logger = logging.getLogger('inq.final_shot.stable_markers')

PROJECT_INTERVAL = 0.10
WRECK_SAMPLE_INTERVAL = 0.25
STABLE_SECONDS = 1.50
MOVE_EPSILON = 0.012
ROTATE_EPSILON = 0.0025
PIXEL_EPSILON = 1.5


def _distance_sq(a, b):
    try:
        dx = float(a.x - b.x)
        dy = float(a.y - b.y)
        dz = float(a.z - b.z)
        return dx * dx + dy * dy + dz * dz
    except Exception:
        return 999999.0


def _root_state(self):
    if self.vehicle is None:
        return None
    try:
        matrix = viewer_mod.Math.Matrix(self.vehicle.model.matrix)
        pos = viewer_mod.Math.Vector3(matrix.translation)
        forward = viewer_mod.Math.Vector3(matrix.applyVector(viewer_mod.Math.Vector3(0.0, 0.0, 1.0)))
        return pos, forward
    except Exception:
        try:
            pos = viewer_mod.Math.Vector3(self.vehicle.position)
            return pos, viewer_mod.Math.Vector3(0.0, 0.0, 1.0)
        except Exception:
            return None


def _root_moved(previous, current):
    if previous is None or current is None:
        return True
    old_pos, old_forward = previous
    new_pos, new_forward = current
    if _distance_sq(old_pos, new_pos) > MOVE_EPSILON * MOVE_EPSILON:
        return True
    return _distance_sq(old_forward, new_forward) > ROTATE_EPSILON * ROTATE_EPSILON


def _remove_legacy_input_handlers(instance):
    mouse_handlers = getattr(viewer_mod, 'g_mouseEventHandlers', ())
    key_handlers = getattr(viewer_mod, 'g_keyEventHandlers', ())
    for collection, method_name in ((mouse_handlers, 'handle_mouse'), (key_handlers, 'handle_key')):
        try:
            for handler in list(collection):
                owner = getattr(handler, 'im_self', getattr(handler, '__self__', None))
                func = getattr(handler, 'im_func', getattr(handler, '__func__', None))
                name = getattr(func, '__name__', getattr(handler, '__name__', ''))
                if owner is instance and name == method_name:
                    discard = getattr(collection, 'discard', None)
                    if discard is not None:
                        discard(handler)
                    else:
                        collection.remove(handler)
        except Exception:
            logger.exception('failed removing legacy %s handler', method_name)


def _cache_hits(self):
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
        logger.exception('failed to cache hit markers')


def _refresh_world_points(self, freeze=False):
    count = 0
    for item in self._cached_markers:
        try:
            world = self._world_point(item.get('point'))
            if world is not None:
                item['world'] = viewer_mod.Math.Vector3(world)
                count += 1
        except Exception:
            pass
    if freeze:
        self._inq_world_frozen = True
        logger.info('wreck stable; froze %s impact world points', count)


def _sample_wreck(self, now):
    if self.vehicle is None:
        return
    if now < float(getattr(self, '_inq_next_wreck_sample', 0.0) or 0.0):
        return
    self._inq_next_wreck_sample = now + WRECK_SAMPLE_INTERVAL
    current = _root_state(self)
    previous = getattr(self, '_inq_last_root_state', None)
    moved = _root_moved(previous, current)
    self._inq_last_root_state = current
    if moved:
        self._inq_stable_since = now
        self._inq_world_frozen = False
        _refresh_world_points(self, False)
        return
    if not getattr(self, '_inq_world_frozen', False):
        stable_since = float(getattr(self, '_inq_stable_since', now) or now)
        _refresh_world_points(self, False)
        if now - stable_since >= STABLE_SECONDS:
            _refresh_world_points(self, True)


def _marker_data(self):
    result = []
    width, height = viewer_mod.GUI.screenResolution()
    width = float(width)
    height = float(height)
    for item in self._cached_markers:
        world = item.get('world')
        visible = False
        x = -10000.0
        y = -10000.0
        if world is not None:
            try:
                projected = viewer_mod.projectPoint(world)
                visible = bool(projected.w > 0.0 and -1.08 <= projected.x <= 1.08 and -1.08 <= projected.y <= 1.08)
                if visible:
                    x = (projected.x + 1.0) * 0.5 * width
                    y = (1.0 - projected.y) * 0.5 * height
            except Exception:
                visible = False
        result.append({
            'x': x,
            'y': y,
            'visible': visible,
            'fatal': item['fatal'],
            'player': item['player'],
            'vehicle': item['vehicle'],
            'damage': item['damage'],
            'icon': item['icon'],
            'side': item['side'],
            'offsetY': item['offsetY'],
        })
    return result


def _screen_changed(previous, current):
    if previous is None or len(previous) != len(current):
        return True
    for old, new in zip(previous, current):
        if bool(old.get('visible')) != bool(new.get('visible')):
            return True
        if not new.get('visible'):
            continue
        if abs(float(old.get('x', 0.0)) - float(new.get('x', 0.0))) >= PIXEL_EPSILON:
            return True
        if abs(float(old.get('y', 0.0)) - float(new.get('y', 0.0))) >= PIXEL_EPSILON:
            return True
    return False


def _open(self):
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
        now = float(BigWorld.time())
        self._inq_last_root_state = _root_state(self)
        self._inq_stable_since = now
        self._inq_next_wreck_sample = now
        self._inq_world_frozen = False
        self._inq_last_screen = None
        _refresh_world_points(self, False)
        self._inject(0)
        self._schedule_frame(0.0)
        logger.info('stable passive viewer opened with %s markers', len(self._cached_markers))
    except Exception:
        logger.exception('failed to open stable passive viewer')
        self.close()


def _frame(self):
    self.frame_callback = None
    if not self.active:
        return
    try:
        now = float(BigWorld.time())
        _sample_wreck(self, now)
        if self.view is not None and self.flash_ready:
            data = self._marker_data()
            previous = getattr(self, '_inq_last_screen', None)
            if _screen_changed(previous, data):
                self.view.flashObject.as_updateMarkers(data)
                self._inq_last_screen = data
    except Exception:
        logger.exception('stable marker frame failed')
    if self.active:
        self._schedule_frame(PROJECT_INTERVAL)


def _close(self):
    self.free_camera = None
    self.previous_camera = None
    result = self._inq_original_close()
    self._inq_last_root_state = None
    self._inq_last_screen = None
    self._inq_world_frozen = False
    return result


def _install():
    if viewer_mod is None:
        logger.error('battle viewer module unavailable')
        return
    cls = getattr(viewer_mod, 'BattleViewer', None)
    instance = getattr(viewer_mod, '_viewer', None)
    if cls is None or instance is None:
        logger.error('battle viewer class or instance unavailable')
        return
    if getattr(cls, '_inq_stable_marker_patch', False):
        return
    _remove_legacy_input_handlers(instance)
    cls._inq_original_close = cls.close
    cls._cache_hit_data = _cache_hits
    cls._marker_data = _marker_data
    cls.open = _open
    cls._frame = _frame
    cls.close = _close
    cls.handle_mouse = lambda self, event: False
    cls.handle_key = lambda self, event: False
    cls._apply_camera = lambda self: None
    cls._inq_stable_marker_patch = True
    instance._inq_last_root_state = None
    instance._inq_last_screen = None
    instance._inq_world_frozen = False
    logger.info('stable low-lag marker patch installed')


_install()
