# -*- coding: utf-8 -*-
"""Smooth passive Final Shot markers for the stock spectator camera.

Wreck matrices are sampled only while the destroyed vehicle is still settling.
Once stable, hit positions are frozen in world space permanently. Camera movement
then performs only cheap world-to-screen projection; no vehicle matrix work is
performed for frozen markers.
"""

from __future__ import absolute_import

import logging

import BigWorld

try:
    from gui.mods.inq_final_shot import battle_viewer as viewer_mod
    from gui.mods.inq_final_shot import impacts
except ImportError:
    viewer_mod = None
    impacts = None

logger = logging.getLogger('inq.final_shot.stable_markers')

# Projection follows the camera closely enough to look attached to the world.
# Ally/hidden state uses the slower interval from observer_visibility.py.
FRAME_INTERVAL = 0.016
WRECK_SAMPLE_INTERVAL = 0.20
STABLE_SECONDS = 1.25
MOVE_EPSILON = 0.012
ROTATE_EPSILON = 0.0025
PIXEL_EPSILON = 0.25

_SHELL_KIND_KEYS = {
    'ARMOR_PIERCING': 'shellAP',
    'ARMOR_PIERCING_HE': 'shellAPHE',
    'ARMOR_PIERCING_CR': 'shellAPCR',
    'HOLLOW_CHARGE': 'shellHEAT',
    'HIGH_EXPLOSIVE': 'shellHE',
}


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
        forward = viewer_mod.Math.Vector3(
            matrix.applyVector(viewer_mod.Math.Vector3(0.0, 0.0, 1.0)))
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


def _shell_key(shot):
    try:
        shell = shot.shell
        key = _SHELL_KIND_KEYS.get(str(shell.kind))
        if key and bool(getattr(shell, 'isGold', False)):
            key += 'Gold'
        return key
    except Exception:
        return None


def _shell_stats_text(self, attacker_id, hit):
    """Resolve nominal shell damage and base (100 m) penetration from the attacker descriptor."""
    try:
        arena = getattr(BigWorld.player(), 'arena', None)
        raw = arena.vehicles.get(int(attacker_id)) if arena is not None else None
        descriptor = raw.get('vehicleType') if raw else None
        gun = getattr(descriptor, 'gun', None)
        shots = getattr(gun, 'shots', ()) if gun is not None else ()
        wanted_key = hit.get('shellKey')
        if not wanted_key:
            return u''

        for shot in shots:
            if _shell_key(shot) != wanted_key:
                continue
            shell = shot.shell
            armor_damage = getattr(shell, 'armorDamage', ())
            piercing_power = getattr(shot, 'piercingPower', ())
            if not armor_damage or not piercing_power:
                continue
            avg_damage = int(round(float(armor_damage[0])))
            base_pen = int(round(float(piercing_power[0])))
            if avg_damage <= 0 and base_pen <= 0:
                return u''
            avg_label = self.controller._tr('avgDamageShort', u'avg dmg')
            pen_unit = self.controller._tr('penetrationUnit', u'mm')
            return u'%d %s · %d %s' % (avg_damage, avg_label, base_pen, pen_unit)
    except Exception:
        logger.debug('failed to resolve shell base stats', exc_info=True)
    return u''


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
                'statsText': _shell_stats_text(self, attacker_id, hit),
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
        logger.info('wreck stable; permanently froze %s impact world points', count)


def _sample_wreck(self, now):
    # Critical: after freeze we never touch the vehicle/model matrices again.
    if self.vehicle is None or getattr(self, '_inq_world_frozen', False):
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
        _refresh_world_points(self, False)
        return

    stable_since = float(getattr(self, '_inq_stable_since', now) or now)
    _refresh_world_points(self, False)
    if now - stable_since >= STABLE_SECONDS:
        _refresh_world_points(self, True)


def _screen_size(self):
    cached = getattr(self, '_inq_screen_size', None)
    if cached is not None:
        return cached
    width, height = viewer_mod.GUI.screenResolution()
    cached = (float(width), float(height))
    self._inq_screen_size = cached
    return cached


def _marker_data(self):
    result = []
    width, height = _screen_size(self)

    for item in self._cached_markers:
        world = item.get('world')
        visible = False
        x = -10000.0
        y = -10000.0
        if world is not None:
            try:
                projected = viewer_mod.projectPoint(world)
                visible = bool(
                    projected.w > 0.0 and
                    -1.08 <= projected.x <= 1.08 and
                    -1.08 <= projected.y <= 1.08)
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
            'statsText': item.get('statsText', u''),
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
        self._inq_screen_size = None
        _refresh_world_points(self, False)
        self._inject(0)
        self._schedule_frame(0.0)
        logger.info('smooth passive viewer opened with %s markers', len(self._cached_markers))
    except Exception:
        logger.exception('failed to open smooth passive viewer')
        self.close()


def _frame(self):
    self.frame_callback = None
    if not self.active:
        return
    try:
        if not getattr(self, '_inq_world_frozen', False):
            _sample_wreck(self, float(BigWorld.time()))
        if self.view is not None and self.flash_ready:
            data = self._marker_data()
            previous = getattr(self, '_inq_last_screen', None)
            if _screen_changed(previous, data):
                # One Scaleform call updates all markers for this frame.
                self.view.flashObject.as_updateMarkers(data)
                self._inq_last_screen = data
    except Exception:
        logger.exception('smooth marker frame failed')
    if self.active:
        self._schedule_frame(FRAME_INTERVAL)


def _close(self):
    result = self._inq_original_close()
    self._inq_last_root_state = None
    self._inq_last_screen = None
    self._inq_screen_size = None
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

    cls._inq_original_close = cls.close
    cls._cache_hit_data = _cache_hits
    cls._marker_data = _marker_data
    cls.open = _open
    cls._frame = _frame
    cls.close = _close
    cls._inq_stable_marker_patch = True

    instance._inq_last_root_state = None
    instance._inq_last_screen = None
    instance._inq_screen_size = None
    instance._inq_world_frozen = False
    logger.info('smooth frozen-world marker patch installed')


_install()
