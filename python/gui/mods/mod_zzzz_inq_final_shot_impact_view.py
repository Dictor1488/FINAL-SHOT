# -*- coding: utf-8 -*-
"""Add decoded Battle Hits impact information to the Final Shot rows."""

from __future__ import absolute_import

import BigWorld

try:
    from gui.mods import mod_inq_final_shot as final_shot
    from gui.mods import mod_zzz_inq_final_shot_impacts as impacts
except ImportError:
    final_shot = None
    impacts = None


def _coordinate_text(hit):
    part = hit.get('impactPart')
    if not part:
        return u''
    return u'%s  [%.2f, %.2f, %.2f]' % (
        unicode(part),
        float(hit.get('impactX', 0.0)),
        float(hit.get('impactY', 0.0)),
        float(hit.get('impactZ', 0.0)),
    )


def _install():
    if final_shot is None or impacts is None:
        return
    controller = getattr(final_shot, '_controller', None)
    if controller is None or getattr(controller, '_impact_view_installed', False):
        return

    def show():
        if not controller.in_battle or not controller.pending_show:
            return
        if controller.view is None or not controller.panel_ready:
            controller._inject(0)
            return

        impacts._decorate_hits(controller)
        rows = []
        for hit in controller.hits:
            shell = controller._tr(hit.get('shellKey'), controller._tr('shellUnknown', u'?'))
            coordinates = _coordinate_text(hit)
            if coordinates:
                shell = u'%s · %s' % (shell, coordinates)
            rows.append({
                'vehicle': hit.get('vehicle', controller._tr('unknownVehicle', u'Unknown vehicle')),
                'player': hit.get('player', u''),
                'damage': final_shot._int(hit.get('damage')),
                'shell': shell,
                'isGold': bool(hit.get('isGold')),
                'reason': hit.get('reason', 'shot'),
                'fatal': bool(hit.get('fatal')),
                'impactPart': hit.get('impactPart', ''),
                'impactEffect': final_shot._int(hit.get('impactEffect')),
                'impactX': float(hit.get('impactX', 0.0)),
                'impactY': float(hit.get('impactY', 0.0)),
                'impactZ': float(hit.get('impactZ', 0.0)),
                'directionX': float(hit.get('directionX', 0.0)),
                'directionY': float(hit.get('directionY', 0.0)),
                'directionZ': float(hit.get('directionZ', 0.0)),
            })

        if not rows:
            rows = [{
                'vehicle': controller._tr('unknownVehicle', u'Unknown vehicle'),
                'player': u'',
                'damage': 0,
                'shell': controller._tr('shellUnknown', u'?'),
                'isGold': False,
                'reason': 'unknown',
                'fatal': True,
                'impactPart': '',
            }]

        try:
            controller.view.flashObject.as_setData(
                controller._tr('title', u'FINAL SHOT'),
                controller._tr('subtitle', u'Last hits before destruction'),
                controller._tr('fatalLabel', u'DESTRUCTION'),
                rows,
            )
            controller.view.flashObject.as_setVisible(True)
            controller.pending_show = False
            final_shot._cancel(controller.hide_callback)
            duration = float(controller.config['displaySeconds'])
            if duration > 0.0:
                controller.hide_callback = BigWorld.callback(duration, controller._hide)
        except Exception:
            final_shot.logger.exception('impact panel display failed')

    controller._show = show
    controller._impact_view_installed = True


_install()
