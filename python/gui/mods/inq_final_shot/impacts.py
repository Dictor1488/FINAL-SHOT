# -*- coding: utf-8 -*-
"""Capture exact shot impact points using the same client hook as Battle Hits."""

from __future__ import absolute_import

import logging
from collections import deque

import BigWorld
from Vehicle import Vehicle
from VehicleEffects import DamageFromShotDecoder

try:
    from vehicle_systems.tankStructure import TankPartIndexes
except ImportError:
    TankPartIndexes = None

try:
    from gui.mods import mod_inq_final_shot as final_shot
except ImportError:
    final_shot = None

logger = logging.getLogger('inq.final_shot.impacts')
_IMPACTS = deque(maxlen=20)
_ORIGINAL_SHOW_DAMAGE = getattr(Vehicle, 'showDamageFromShot', None)

_SHELL_KIND_KEYS = {
    'ARMOR_PIERCING': 'shellAP',
    'ARMOR_PIERCING_HE': 'shellAPHE',
    'ARMOR_PIERCING_CR': 'shellAPCR',
    'HOLLOW_CHARGE': 'shellHEAT',
    'HIGH_EXPLOSIVE': 'shellHE',
}


def _part_name(index):
    if TankPartIndexes is not None:
        for attr, name in (
                ('CHASSIS', 'chassis'),
                ('HULL', 'hull'),
                ('TURRET', 'turret'),
                ('GUN', 'gun')):
            try:
                if index == getattr(TankPartIndexes, attr):
                    return name
            except Exception:
                pass
    return 'part_%s' % index


def _vec3(value):
    try:
        return [float(value.x), float(value.y), float(value.z)]
    except Exception:
        try:
            return [float(value[0]), float(value[1]), float(value[2])]
        except Exception:
            return [0.0, 0.0, 0.0]


def _capture(vehicle, attacker_id, hit_points, effects_index, damage, damage_factor):
    try:
        player = BigWorld.player()
        if vehicle is None or player is None:
            return
        if int(getattr(vehicle, 'id', 0)) != int(getattr(player, 'playerVehicleID', 0)):
            return
        appearance = getattr(vehicle, 'appearance', None)
        collisions = getattr(appearance, 'collisions', None)
        if collisions is None:
            return

        decoded = []
        for packed_point in hit_points or ():
            try:
                values = DamageFromShotDecoder.parseHitPoint(packed_point, collisions)
                component = values[0]
                start = values[2]
                end = values[3]
                hit_effect = values[4]
                decoded.append({
                    'part': _part_name(component),
                    'partIndex': int(component),
                    'effect': int(hit_effect),
                    'start': _vec3(start),
                    'end': _vec3(end),
                })
            except Exception:
                logger.exception('failed to decode hit point')

        if not decoded:
            return
        _IMPACTS.append({
            'attackerID': int(attacker_id or 0),
            'effectsIndex': int(effects_index or 0),
            'damage': int(damage or 0),
            'damageFactor': float(damage_factor or 0.0),
            'points': decoded,
            'time': float(BigWorld.time()),
        })
    except Exception:
        logger.exception('impact capture failed')


def _show_damage_from_shot(self, *args, **kwargs):
    result = None
    if _ORIGINAL_SHOW_DAMAGE is not None:
        result = _ORIGINAL_SHOW_DAMAGE(self, *args, **kwargs)
    try:
        _capture(self, args[0], args[1], args[2], args[4], args[5])
    except Exception:
        logger.exception('showDamageFromShot hook failed')
    return result


def _match_impact(hit):
    attacker_id = int(hit.get('attackerID', 0) or 0)
    hit_damage = int(hit.get('damage', 0) or 0)
    best = None
    for impact in reversed(_IMPACTS):
        if attacker_id and impact.get('attackerID') != attacker_id:
            continue
        damage = int(impact.get('damage', 0) or 0)
        if hit_damage and damage and abs(hit_damage - damage) > 3:
            continue
        best = impact
        break
    return best


def _shell_key_from_effects(attacker_id, effects_index):
    """Resolve the exact configured shell using the shot effects index from showDamageFromShot."""
    try:
        entity = BigWorld.entity(int(attacker_id))
        if entity is None:
            entity = BigWorld.entities.get(int(attacker_id))
        descriptor = getattr(entity, 'typeDescriptor', None) if entity is not None else None
        gun = getattr(descriptor, 'gun', None) if descriptor is not None else None
        shots = getattr(gun, 'shots', ()) if gun is not None else ()
        wanted = int(effects_index or 0)
        if not wanted:
            return None

        for shot in shots:
            shell = getattr(shot, 'shell', None)
            if shell is None:
                continue
            shell_effects = getattr(shell, 'effectsIndex', None)
            shot_effects = getattr(shot, 'effectsIndex', None)
            if shell_effects != wanted and shot_effects != wanted:
                continue
            key = _SHELL_KIND_KEYS.get(str(getattr(shell, 'kind', '')))
            if key and bool(getattr(shell, 'isGold', False)):
                key += 'Gold'
            return key
    except Exception:
        logger.debug('failed to resolve shell from effects index', exc_info=True)
    return None


def _decorate_hits(controller):
    try:
        for hit in controller.hits:
            impact = _match_impact(hit)
            if not impact:
                continue
            points = impact.get('points') or []
            if not points:
                continue
            point = points[0]
            end = point.get('end') or [0.0, 0.0, 0.0]
            start = point.get('start') or [0.0, 0.0, 0.0]
            effects_index = int(impact.get('effectsIndex', 0) or 0)
            hit['impactPart'] = point.get('part', 'unknown')
            hit['impactEffect'] = int(point.get('effect', 0))
            hit['effectsIndex'] = effects_index
            hit['shellKey'] = _shell_key_from_effects(hit.get('attackerID', 0), effects_index)
            hit['impactX'] = float(end[0])
            hit['impactY'] = float(end[1])
            hit['impactZ'] = float(end[2])
            hit['directionX'] = float(end[0] - start[0])
            hit['directionY'] = float(end[1] - start[1])
            hit['directionZ'] = float(end[2] - start[2])
            hit['impactPoints'] = points
    except Exception:
        logger.exception('hit decoration failed')


def _install_controller_patch():
    if final_shot is None:
        return
    controller = getattr(final_shot, '_controller', None)
    if controller is None or getattr(controller, '_impact_patch_installed', False):
        return
    original_show = controller._show

    def show_with_impacts():
        _decorate_hits(controller)
        return original_show()

    controller._show = show_with_impacts
    controller._impact_patch_installed = True


if _ORIGINAL_SHOW_DAMAGE is not None and not getattr(Vehicle.showDamageFromShot, '_inq_impact_hook', False):
    _show_damage_from_shot._inq_impact_hook = True
    Vehicle.showDamageFromShot = _show_damage_from_shot

_install_controller_patch()
