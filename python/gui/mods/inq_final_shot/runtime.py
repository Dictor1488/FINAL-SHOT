# -*- coding: utf-8 -*-
"""Runtime fixes for Final Shot postmortem visibility, impacts and fatal hit."""

from __future__ import absolute_import

import logging
import types

import BigWorld

logger = logging.getLogger('inq.final_shot.runtime')

try:
    from gui.mods import mod_inq_final_shot_30_battle_viewer as viewer_mod
except ImportError:
    viewer_mod = None

if viewer_mod is not None:
    if not hasattr(viewer_mod, 'g_mouseEventHandlers'):
        viewer_mod.g_mouseEventHandlers = set()
    if not hasattr(viewer_mod, 'g_keyEventHandlers'):
        viewer_mod.g_keyEventHandlers = set()

try:
    from gui.mods import mod_inq_final_shot_40_stable_markers as stable_mod
except Exception:
    stable_mod = None
    logger.exception('failed recovering stable marker module')

try:
    from gui.mods import mod_inq_final_shot_50_observer_visibility as observer_mod
except Exception:
    observer_mod = None
    logger.exception('failed recovering observer visibility module')

try:
    from gui.mods import mod_inq_final_shot as final_shot
    from gui.mods import mod_inq_final_shot_10_health as health_mod
    from gui.mods import mod_inq_final_shot_20_impacts as impacts_mod
except ImportError:
    final_shot = None
    health_mod = None
    impacts_mod = None


def _disable_legacy_panel():
    if final_shot is None:
        return
    controller = getattr(final_shot, '_controller', None)
    if controller is None:
        return

    def no_legacy_inject(self, attempt=0):
        self.inject_callback = None
        if self.view is not None:
            try:
                self.view.flashObject.as_setVisible(False)
            except Exception:
                pass
        return

    controller._inject = types.MethodType(no_legacy_inject, controller, controller.__class__)
    if getattr(controller, 'view', None) is not None:
        try:
            controller.view.flashObject.as_setVisible(False)
        except Exception:
            pass
    logger.warning('legacy FinalShotPanelBattle injection disabled')


def _current_camera_vehicle_id():
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
        target_id = int(target_id or 0)
        attacker_id = int(attacker_id or 0)
        is_player = target_id == int(self.player_vehicle_id or 0)
        if is_player and attacker_id:
            _mark_lethal_hit(self, attacker_id, 0)
            saved = [bool(item.get('fatal')) for item in self.hits]
            result = original_killed(target_id, attacker_id, *args, **kwargs)
            for item, fatal in zip(self.hits, saved):
                item['fatal'] = fatal
            self._inq_authoritative_killer_id = attacker_id
            logger.warning('arena kill event confirmed killer vehicle id=%s', attacker_id)
            return result
        authoritative = int(getattr(self, '_inq_authoritative_killer_id', 0) or 0)
        if is_player and authoritative:
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
    logger.warning('runtime lethal authority installed: arena kill event has final priority')


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


def _marker_stats_text(self, impact, matched, attacker_id, damage):
    """Keep the shell base penetration/average-damage line in the runtime cache.

    stable_markers normally builds this field itself. The runtime impact cache
    replaces that builder to preserve exact impact/attacker identity, so it must
    explicitly carry the same statsText value into every marker.
    """
    if stable_mod is None:
        return u''
    try:
        stats_hit = dict(matched) if matched is not None else {}
        stats_hit['damage'] = int(damage or 0)

        # Prefer the exact shell resolved from the captured shot effects. This is
        # especially useful when detailed feedback arrived late or used an unknown
        # shell key; stable_markers still retains its damage-based fallback.
        try:
            effects_index = int(impact.get('effectsIndex', 0) or 0)
            exact_key = impacts_mod._shell_key_from_effects(attacker_id, effects_index)
            if exact_key:
                stats_hit['shellKey'] = exact_key
                stats_hit['isGold'] = unicode(exact_key).endswith(u'Gold')
        except Exception:
            pass

        return stable_mod._shell_stats_text(self, attacker_id, stats_hit)
    except Exception:
        logger.exception('failed restoring shell stats text')
        return u''


def _cache_last_real_impacts(self):
    self._cached_markers = []
    controller = getattr(self, 'controller', None)
    if controller is None or impacts_mod is None:
        return
    try:
        limit = int(controller.config.get('maxHits', 3) or 3)
        impacts = list(getattr(impacts_mod, '_IMPACTS', ()))[-limit:]
        used_hits = set()
        lethal_attacker = int(getattr(controller, '_inq_authoritative_killer_id', 0) or 0)
        built = []

        for hit_index, impact in enumerate(impacts, 1):
            points = impact.get('points') or ()
            if not points:
                continue
            point = points[0]
            if self._world_point(point) is None:
                continue

            attacker_id = int(impact.get('attackerID', 0) or 0)
            matched = _find_hit_for_impact(controller, impact, used_hits)
            damage = int(impact.get('damage', 0) or 0)
            if matched is not None:
                matched_damage = int(matched.get('damage', 0) or 0)
                if matched_damage:
                    damage = matched_damage

            vehicle_name = u''
            player_name = u''
            if attacker_id:
                try:
                    vehicle_name, player_name = controller._vehicle_identity(attacker_id)
                except Exception:
                    pass
            elif matched is not None:
                vehicle_name = unicode(matched.get('vehicle') or u'')
                player_name = unicode(matched.get('player') or u'')

            stats_text = _marker_stats_text(self, impact, matched, attacker_id, damage)
            if stable_mod is not None:
                offsets = getattr(stable_mod, '_MARKER_OFFSETS', (-66, 66, 0))
            else:
                offsets = (-66, 66, 0)

            built.append({
                'attackerID': attacker_id,
                'point': point,
                'world': None,
                'fatal': False,
                'player': player_name,
                'vehicle': vehicle_name,
                'damage': damage,
                'statsText': stats_text,
                'icon': self._attacker_icon(attacker_id),
                'side': 1 if hit_index % 2 else -1,
                'offsetY': offsets[(hit_index - 1) % len(offsets)],
            })

        if lethal_attacker:
            found = False
            for marker in reversed(built):
                if int(marker.get('attackerID', 0) or 0) == lethal_attacker and not found:
                    marker['fatal'] = True
                    found = True
                else:
                    marker['fatal'] = False

        self._cached_markers = built
        logger.warning('cached %s real impact markers with authoritative attacker identity', len(built))
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
    logger.warning('runtime impact identity fix installed')


_disable_legacy_panel()
_install_observer_fix()
_install_fatal_authority()
_install_impact_cache_fix()
