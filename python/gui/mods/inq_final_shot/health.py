# -*- coding: utf-8 -*-
"""Compatibility layer based on current WoT client event signatures.

Adds the reliable VEHICLE_HEALTH channel and keeps the detailed player feedback
channel for shell information. Duplicate events are merged into one hit row.
"""

from __future__ import absolute_import

import types

import BigWorld
from gui.battle_control.battle_constants import FEEDBACK_EVENT_ID

import gui.mods.mod_inq_final_shot as final_shot


def _now():
    try:
        return float(BigWorld.time())
    except Exception:
        return 0.0


def _vehicle_id_from_info(info):
    if info is None:
        return 0
    for name in ('vehicleID', 'vehicleId', 'vehID', 'id'):
        try:
            value = int(getattr(info, name, 0) or 0)
            if value:
                return value
        except Exception:
            pass
    try:
        getter = getattr(info, 'getVehicleID', None)
        if callable(getter):
            return int(getter() or 0)
    except Exception:
        pass
    return 0


def _player_health(controller):
    try:
        entity = BigWorld.entity(controller.player_vehicle_id)
        if entity is not None:
            return int(getattr(entity, 'health', 0) or 0)
    except Exception:
        pass
    try:
        arena = getattr(BigWorld.player(), 'arena', None)
        raw = arena.vehicles.get(controller.player_vehicle_id) if arena is not None else None
        vehicle_type = raw.get('vehicleType') if raw else None
        return int(getattr(vehicle_type, 'maxHealth', 0) or 0)
    except Exception:
        return 0


def _reason_key(reason_id):
    try:
        from constants import ATTACK_REASON
        return unicode(ATTACK_REASON[reason_id])
    except Exception:
        return 'shot'


def _append_fallback_hit(controller, attacker_id, damage, reason_id):
    vehicle, player_name = controller._vehicle_identity(attacker_id)
    controller.hits.append({
        'attackerID': attacker_id,
        'vehicle': vehicle,
        'player': player_name if controller.config['showPlayerName'] else u'',
        'damage': damage,
        'shellKey': 'shellUnknown',
        'isGold': False,
        'reason': _reason_key(reason_id),
        'fatal': False,
        '_fallback': True,
        '_time': _now(),
    })


def _on_vehicle_feedback(self, event_id, vehicle_id, value):
    if not self.in_battle or not self.config['enabled']:
        return
    if event_id != FEEDBACK_EVENT_ID.VEHICLE_HEALTH:
        return
    if final_shot._int(vehicle_id) != self.player_vehicle_id:
        return
    try:
        new_health, attacker_info, reason_id = value
    except Exception:
        return
    new_health = max(0, final_shot._int(new_health))
    previous = final_shot._int(getattr(self, '_final_shot_last_health', 0))
    self._final_shot_last_health = new_health
    damage = max(0, previous - new_health)
    if damage <= 0:
        return
    attacker_id = _vehicle_id_from_info(attacker_info)
    if self.hits:
        latest = self.hits[-1]
        if (latest.get('attackerID') == attacker_id and
                final_shot._int(latest.get('damage')) == damage and
                _now() - float(latest.get('_time', _now())) < 1.0):
            return
    _append_fallback_hit(self, attacker_id, damage, reason_id)


def _on_detailed_feedback(self, events):
    if not self.in_battle or not self.config['enabled']:
        return
    for event in events:
        try:
            if event.getType() != FEEDBACK_EVENT_ID.ENEMY_DAMAGED_HP_PLAYER:
                continue
            extra = event.getExtra()
            damage = final_shot._int(extra.getDamage())
            if damage <= 0:
                continue
            attacker_id = final_shot._int(event.getTargetID())
            shell_type = None
            is_gold = False
            try:
                shell_type = extra.getShellType()
                is_gold = bool(extra.isShellGold())
            except Exception:
                pass
            vehicle, player_name = self._vehicle_identity(attacker_id)
            detailed = {
                'attackerID': attacker_id,
                'vehicle': vehicle,
                'player': player_name if self.config['showPlayerName'] else u'',
                'damage': damage,
                'shellKey': final_shot._shell_key(shell_type, is_gold),
                'isGold': is_gold,
                'reason': final_shot._attack_reason(extra),
                'fatal': False,
                '_fallback': False,
                '_time': _now(),
            }
            if self.hits:
                latest = self.hits[-1]
                if (latest.get('_fallback') and
                        final_shot._int(latest.get('damage')) == damage and
                        (not attacker_id or latest.get('attackerID') in (0, attacker_id)) and
                        _now() - float(latest.get('_time', _now())) < 1.0):
                    was_fatal = bool(latest.get('fatal'))
                    latest.update(detailed)
                    latest['fatal'] = was_fatal
                    continue
            self.hits.append(detailed)
        except Exception:
            final_shot.logger.exception('detailed feedback event failed')


def _bind_events(self, player):
    try:
        shared = getattr(self.provider, 'shared', None)
        self.feedback = getattr(shared, 'feedback', None) if shared is not None else None
        if self.feedback is not None:
            self.feedback.onPlayerFeedbackReceived += self._on_feedback
            self.feedback.onVehicleFeedbackReceived += self._on_vehicle_feedback
    except Exception:
        final_shot.logger.exception('feedback subscribe failed')
        self.feedback = None
    self._final_shot_last_health = _player_health(self)
    try:
        self.arena = getattr(player, 'arena', None)
        if self.arena is not None:
            self.arena.onVehicleKilled += self._on_vehicle_killed
        else:
            visitor = getattr(self.provider, 'arenaVisitor', None)
            self.arena_subscription = visitor.getArenaSubscription() if visitor is not None else None
            if self.arena_subscription is not None:
                self.arena_subscription.onVehicleKilled += self._on_vehicle_killed
    except Exception:
        final_shot.logger.exception('kill event subscribe failed')
        self.arena = None
        self.arena_subscription = None


def _unbind_events(self):
    if self.feedback is not None:
        try:
            self.feedback.onPlayerFeedbackReceived -= self._on_feedback
        except Exception:
            pass
        try:
            self.feedback.onVehicleFeedbackReceived -= self._on_vehicle_feedback
        except Exception:
            pass
    if self.arena is not None:
        try:
            self.arena.onVehicleKilled -= self._on_vehicle_killed
        except Exception:
            pass
    if self.arena_subscription is not None:
        try:
            self.arena_subscription.onVehicleKilled -= self._on_vehicle_killed
        except Exception:
            pass
    self.feedback = self.arena = self.arena_subscription = None
    self._final_shot_last_health = 0


controller = final_shot._controller
controller._on_feedback = types.MethodType(_on_detailed_feedback, controller, controller.__class__)
controller._on_vehicle_feedback = types.MethodType(_on_vehicle_feedback, controller, controller.__class__)
controller._bind_events = types.MethodType(_bind_events, controller, controller.__class__)
controller._unbind_events = types.MethodType(_unbind_events, controller, controller.__class__)

if controller.in_battle:
    try:
        player = BigWorld.player()
        controller._unbind_events()
        controller._bind_events(player)
    except Exception:
        final_shot.logger.exception('health compatibility late bind failed')
