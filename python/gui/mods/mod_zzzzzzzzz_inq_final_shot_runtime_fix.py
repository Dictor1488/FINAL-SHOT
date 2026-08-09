# -*- coding: utf-8 -*-
"""Runtime recovery for Final Shot postmortem visibility, impact selection and fatal hit."""

from __future__ import absolute_import

import logging
import types

import BigWorld

logger = logging.getLogger('inq.final_shot.runtime_fix')

try:
    from gui.mods import mod_zzzzz_inq_final_shot_battle_viewer as viewer_mod
except ImportError:
    viewer_mod = None

# The current passive viewer does not register custom input handlers anymore.
# Older stable-marker code probes these names during import, so expose harmless
# empty collections before importing it.
if viewer_mod is not None:
    if not hasattr(viewer_mod, 'g_mouseEventHandlers'):
        viewer_mod.g_mouseEventHandlers = set()
    if not hasattr(viewer_mod, 'g_keyEventHandlers'):
        viewer_mod.g_keyEventHandlers = set()

try:
    from gui.mods import mod_zzzzzzz_inq_final_shot_stable_markers as stable_mod
except Exception:
    stable_mod = None
    logger.exception('failed recovering stable marker module')

try:
    from gui.mods import mod_zzzzzzzz_inq_final_shot_observer_visibility as observer_mod
except Exception:
    observer_mod = None
    logger.exception('failed recovering observer visibility module')

try:
    from gui.mods import mod_inq_final_shot as final_shot
    from gui.mods import mod_zz_inq_final_shot_health as health_mod
    from gui.mods import mod_zzz_inq_final_shot_impacts as impacts_mod
except ImportError:
    final_shot = None
    health_mod = None
    impacts_mod = None


def _current_camera_vehicle_id():
    """Return the vehicle actually selected by the stock postmortem camera.

    AvatarObserver.getObservedVehicleID() falls back to playerVehicleID whenever
    isObserver() is false. During normal postmortem switching that can therefore
    report the dead player's tank while player.vehicle already points at an ally.
    Prefer the live attached vehicle first, then observer internals, then fallback.
    """
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
        if observed:
            return int(observed)

        getter = getattr(player, 'getObservedVehicleID', None)
        if getter is not None:
            value = int(getter() or 0)
            if value:
                return value

        return int(getattr(player, 'playerVehicleID', 0) or 0)
    except Exception:
        return 0


def _install_observer_fix():
    if observer_mod is None:
        return
    observer_mod._observed_vehicle_id = _current_camera_vehicle_id
    logger.warning('runtime observer fix installed: attached vehicle has priority')


def _mark_lethal_hit(controller, attacker_id, damage):
    attacker_id = int(attacker_id or 0)
    damage = int(damage or 0)
    for item in controller.hits:
        item['fatal'] = False

    chosen = None
    for item in reversed(controller.hits):
        if attacker_id and int(item.get('attackerID', 0) or 0) != attacker_id:
            continue
        if damage and int(item.get('damage', 0) or 0) == damage:
            chosen = item
            break
        if chosen is None:
            chosen = item

    if chosen is None and attacker_id:
        try:
            vehicle, player_name = controller._vehicle_identity(attacker_id)
            chosen = {
                'attackerID': attacker_id,
                'vehicle': vehicle,
                'player': player_name if controller.config['showPlayerName'] else u'',
                'damage': damage,
                'shellKey': 'shellUnknown',
                'isGold': False,
                'reason': 'shot',
                'fatal': False,
                '_fallback': True,
                '_time': float(BigWorld.time()),
            }
            controller.hits.append(chosen)
        except Exception:
            chosen = None

    if chosen is not None:
        chosen['fatal'] = True
        controller._inq_authoritative_killer_id = attacker_id


def _install_fatal_authority():
    if final_shot is None or health_mod is None:
        return
    controller = getattr(final_shot, '_controller', None)
    if controller is None or getattr(controller, '_inq_fatal_authority_installed', False):
        return

    original_health = controller._on_vehicle_feedback
    original_killed = controller._on_vehicle_killed

    def health_authoritative(self, event_id, vehicle_id, value):
        lethal = False
        attacker_id = 0
        damage = 0
        try:
            from gui.battle_control.battle_constants import FEEDBACK_EVENT_ID
            if event_id == FEEDBACK_EVENT_ID.VEHICLE_HEALTH and int(vehicle_id or 0) == int(self.player_vehicle_id or 0):
                new_health, attacker_info, reason_id = value
                new_health = max(0, int(new_health or 0))
                previous = int(getattr(self, '_final_shot_last_health', 0) or 0)
                damage = max(0, previous - new_health)
                attacker_id = int(health_mod._vehicle_id_from_info(attacker_info) or 0)
                lethal = new_health == 0 and damage > 0
        except Exception:
            pass

        result = original_health(event_id, vehicle_id, value)
        if lethal:
            _mark_lethal_hit(self, attacker_id, damage)
        return result

    def killed_authoritative(self, target_id, attacker_id=0, *args, **kwargs):
        authoritative = int(getattr(self, '_inq_authoritative_killer_id', 0) or 0)
        if authoritative and int(target_id or 0) == int(self.player_vehicle_id or 0):
            saved = [bool(item.get('fatal')) for item in self.hits]
            result = original_killed(target_id, attacker_id, *args, **kwargs)
            for item, fatal in zip(self.hits, saved):
                item['fatal'] = fatal
            return result
        return original_killed(target_id, attacker_id, *args, **kwargs)

    controller._on_vehicle_feedback = types.MethodType(health_authoritative, controller, controller.__class__)
    controller._on_vehicle_killed = types.MethodType(killed_authoritative, controller, controller.__class__)
    controller._inq_authoritative_killer_id = 0
    controller._inq_fatal_authority_installed = True
    logger.warning('runtime lethal VEHICLE_HEALTH authority installed')


def _find_hit_for_impact(controller, impact, used):
    attacker_id = int(impact.get('attackerID', 0) or 0)
    damage = int(impact.get('damage', 0) or 0)
    best_index = None
    best_score = None
    rows = list(controller.hits)
    for index in range(len(rows) - 1, -1, -1):
        if index in used:
            continue
        hit = rows[index]
        hit_attacker = int(hit.get('attackerID', 0) or 0)
        if attacker_id and hit_attacker and hit_attacker != attacker_id:
            continue
        hit_damage = int(hit.get('damage', 0) or 0)
        diff = abs(hit_damage - damage) if damage and hit_damage else 9999
        score = (0 if attacker_id and hit_attacker == attacker_id else 1, diff, -index)
        if best_score is None or score < best_score:
            best_score = score
            best_index = index
    if best_index is None:
        return None
    used.add(best_index)
    return rows[best_index]


def _cache_last_real_impacts(self):
    """Build markers from the last real showDamageFromShot impacts, not row matches."""
    self._cached_markers = []
    controller = getattr(self, 'controller', None)
    if controller is None or impacts_mod is None:
        return
    try:
        limit = int(controller.config.get('maxHits', 3) or 3)
        impacts = list(getattr(impacts_mod, '_IMPACTS', ()))[-limit:]
        used_hits = set()
        lethal_attacker = int(getattr(controller, '_inq_authoritative_killer_id', 0) or 0)
        lethal_assigned = False

        for hit_index, impact in enumerate(impacts, 1):
            points = impact.get('points') or ()
            if not points:
                continue
            point = points[0]
            if self._world_point(point) is None:
                continue

            attacker_id = int(impact.get('attackerID', 0) or 0)
            matched = _find_hit_for_impact(controller, impact, used_hits)
            vehicle_name = u''
            player_name = u''
            damage = int(impact.get('damage', 0) or 0)
            fatal = False
            if matched is not None:
                vehicle_name = unicode(matched.get('vehicle') or u'')
                player_name = unicode(matched.get('player') or u'')
                damage = int(matched.get('damage', damage) or damage)
                fatal = bool(matched.get('fatal'))

            if not vehicle_name or not player_name:
                try:
                    vehicle_name, player_name = controller._vehicle_identity(attacker_id)
                except Exception:
                    pass

            # The newest real impact from the authoritative lethal attacker wins.
            if lethal_attacker and attacker_id == lethal_attacker:
                fatal = True
                lethal_assigned = True
            elif lethal_attacker:
                fatal = False

            self._cached_markers.append({
                'point': point,
                'world': None,
                'fatal': fatal,
                'player': player_name,
                'vehicle': vehicle_name,
                'damage': damage,
                'icon': self._attacker_icon(attacker_id),
                'side': 1 if hit_index % 2 else -1,
                'offsetY': (-30, 18, -8)[(hit_index - 1) % 3],
            })

        # If the killer fired more than once in the last three impacts, only the
        # newest one should be red.
        if lethal_attacker and lethal_assigned:
            found = False
            for marker in reversed(self._cached_markers):
                if marker.get('fatal') and not found:
                    found = True
                elif marker.get('fatal'):
                    marker['fatal'] = False

        logger.warning('cached %s real impact markers', len(self._cached_markers))
    except Exception:
        logger.exception('failed caching real impact markers')


def _install_impact_cache_fix():
    if viewer_mod is None:
        return
    cls = getattr(viewer_mod, 'BattleViewer', None)
    instance = getattr(viewer_mod, '_viewer', None)
    if cls is None or instance is None:
        return
    cls._cache_hit_data = _cache_last_real_impacts
    logger.warning('runtime impact cache fix installed: last real impacts are authoritative')


_install_observer_fix()
_install_fatal_authority()
_install_impact_cache_fix()
