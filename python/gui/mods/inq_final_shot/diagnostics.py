# -*- coding: utf-8 -*-
"""Temporary runtime diagnostics for shell-stat lookup."""

from __future__ import absolute_import

import logging

from gui.mods.inq_final_shot import stable_markers

logger = logging.getLogger('inq.final_shot.shell_diag')
logger.setLevel(logging.ERROR)

_original = getattr(stable_markers, '_shell_stats_text', None)


def _safe(value):
    try:
        return repr(value)
    except Exception:
        return '<unrepr>'


def _diagnostic_shell_stats_text(self, attacker_id, hit):
    try:
        descriptor = stable_markers._attacker_descriptor(attacker_id)
        gun = getattr(descriptor, 'gun', None) if descriptor is not None else None
        shots = list(getattr(gun, 'shots', ()) if gun is not None else ())
        logger.error(
            '[SHELL_DIAG] attacker=%s vehicle=%s damage=%s shellKey=%s isGold=%s descriptor=%s gun=%s shots=%s',
            attacker_id,
            _safe(hit.get('vehicle')),
            hit.get('damage'),
            _safe(hit.get('shellKey')),
            hit.get('isGold'),
            type(descriptor).__name__ if descriptor is not None else None,
            type(gun).__name__ if gun is not None else None,
            len(shots))
        for index, shot in enumerate(shots):
            shell = getattr(shot, 'shell', None)
            logger.error(
                '[SHELL_DIAG] shot=%s kind=%s isGold=%s shellKey=%s armorDamage=%s piercingPower=%s values=%s',
                index,
                _safe(getattr(shell, 'kind', None)),
                _safe(getattr(shell, 'isGold', None)),
                _safe(stable_markers._shell_key(shot)),
                _safe(getattr(shell, 'armorDamage', None)),
                _safe(getattr(shot, 'piercingPower', None)),
                _safe(stable_markers._shot_values(shot)))
    except Exception:
        logger.exception('[SHELL_DIAG] dump failed attacker=%s', attacker_id)
    if _original is None:
        return u''
    result = _original(self, attacker_id, hit)
    logger.error('[SHELL_DIAG] result attacker=%s text=%s', attacker_id, _safe(result))
    return result


if _original is not None and not getattr(stable_markers, '_inq_shell_diag_installed', False):
    stable_markers._shell_stats_text = _diagnostic_shell_stats_text
    stable_markers._inq_shell_diag_installed = True
    logger.error('[SHELL_DIAG] diagnostics installed')
