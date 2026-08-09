# -*- coding: utf-8 -*-
"""Runtime recovery for observer visibility and authoritative fatal hit selection."""

from __future__ import absolute_import

import logging
import types

import BigWorld

logger = logging.getLogger('inq.final_shot.runtime_fix')

try:
    from gui.mods import mod_zzzzz_inq_final_shot_battle_viewer as viewer_mod
except ImportError:
    viewer_mod = None

# The current passive viewer no longer registers custom input handlers. Older
# stable-marker code still probes these names during import; provide harmless
# empty collections so that module can initialize instead of aborting ScriptLoader.
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
except ImportError:
    final_shot = None
    health_mod = None


def _mark_lethal_hit(controller, attacker_id, damage):
    attacker_id = int(attacker_id or 0)
    damage = int(damage or 0)
    for item in controller.hits:
        item['fatal'] = False

    # Prefer the newest row from the attacker that actually reduced HP to zero.
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
        # Read the lethal event before the compatibility handler mutates rows.
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
        # If VEHICLE_HEALTH already told us who removed the last HP, do not let a
        # later arena kill notification move the red marker to another hit.
        authoritative = int(getattr(self, '_inq_authoritative_killer_id', 0) or 0)
        if authoritative and int(target_id or 0) == int(self.player_vehicle_id or 0):
            saved = []
            for item in self.hits:
                saved.append(bool(item.get('fatal')))
            result = original_killed(target_id, attacker_id, *args, **kwargs)
            for item, fatal in zip(self.hits, saved):
                item['fatal'] = fatal
            return result
        return original_killed(target_id, attacker_id, *args, **kwargs)

    controller._on_vehicle_feedback = types.MethodType(health_authoritative, controller, controller.__class__)
    controller._on_vehicle_killed = types.MethodType(killed_authoritative, controller, controller.__class__)
    controller._inq_authoritative_killer_id = 0
    controller._inq_fatal_authority_installed = True
    logger.warning('runtime fix installed: observer recovery + lethal VEHICLE_HEALTH authority')


_install_fatal_authority()
