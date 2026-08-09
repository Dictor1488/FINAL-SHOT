# -*- coding: utf-8 -*-
"""Keep each real impact bound to the attacker that produced it.

The 3D impact hook already receives attackerID from Vehicle.showDamageFromShot.
Damage rows are useful for damage/fatal metadata, but they must never replace the
attacker identity of a concrete impact because event ordering can differ.
"""

from __future__ import absolute_import

import logging

try:
    from gui.mods import mod_zzzzz_inq_final_shot_battle_viewer as viewer_mod
    from gui.mods import mod_zzz_inq_final_shot_impacts as impacts_mod
    from gui.mods import mod_zzzzzzzzz_inq_final_shot_runtime_fix as runtime_fix
except ImportError:
    viewer_mod = None
    impacts_mod = None
    runtime_fix = None

logger = logging.getLogger('inq.final_shot.identity_fix')


def _cache_impacts_with_authoritative_identity(self):
    self._cached_markers = []
    controller = getattr(self, 'controller', None)
    if controller is None or impacts_mod is None or runtime_fix is None:
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
            matched = runtime_fix._find_hit_for_impact(controller, impact, used_hits)
            damage = int(impact.get('damage', 0) or 0)
            fatal = False

            # A matched damage row may enrich damage/fatal data only. It must not
            # overwrite who fired this concrete showDamageFromShot impact.
            if matched is not None:
                matched_damage = int(matched.get('damage', 0) or 0)
                if matched_damage:
                    damage = matched_damage
                fatal = bool(matched.get('fatal'))

            vehicle_name = u''
            player_name = u''
            if attacker_id:
                try:
                    vehicle_name, player_name = controller._vehicle_identity(attacker_id)
                except Exception:
                    pass
            elif matched is not None:
                # Only impacts without an attacker ID may fall back to row identity.
                vehicle_name = unicode(matched.get('vehicle') or u'')
                player_name = unicode(matched.get('player') or u'')

            if lethal_attacker:
                fatal = attacker_id == lethal_attacker

            built.append({
                'attackerID': attacker_id,
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

        # When the killer has multiple impacts among the last three, only the
        # newest impact from that attacker is the fatal one.
        if lethal_attacker:
            found = False
            for marker in reversed(built):
                if int(marker.get('attackerID', 0) or 0) == lethal_attacker and not found:
                    marker['fatal'] = True
                    found = True
                else:
                    marker['fatal'] = False

        self._cached_markers = built
        logger.warning('cached %s impact markers with authoritative attacker identity', len(built))
    except Exception:
        logger.exception('failed caching authoritative impact identities')


def _install():
    if viewer_mod is None:
        return
    cls = getattr(viewer_mod, 'BattleViewer', None)
    if cls is None:
        return
    cls._cache_hit_data = _cache_impacts_with_authoritative_identity
    logger.warning('impact identity fix installed')


_install()
