# -*- coding: utf-8 -*-
"""Passive in-battle Final Shot overlay for the destroyed player vehicle.

The mod never replaces or consumes the stock WoT postmortem/spectator camera.
Impact anchors follow the wreck briefly while physics settles, then freeze in world
space. After that only cheap world-to-screen projections are refreshed.
"""

from __future__ import absolute_import

import logging

import BigWorld
import GUI
import Math

from AvatarInputHandler.cameras import projectPoint
from PlayerEvents import g_playerEvents
from frameworks.wulf import WindowLayer
from gui.Scaleform.framework import ScopeTemplates, ViewSettings, g_entitiesFactories
from gui.Scaleform.framework.entities.View import View
from gui.Scaleform.framework.managers.loaders import SFViewLoadParams
from gui.shared.personality import ServicesLocator

try:
    from gui.shared.gui_items.Vehicle import getContourIconPath
except ImportError:
    getContourIconPath = None

try:
    from vehicle_systems.tankStructure import TankPartIndexes
except ImportError:
    TankPartIndexes = None

try:
    from gui.mods import mod_inq_final_shot as final_shot
    from gui.mods import mod_inq_final_shot_20_impacts as impacts
except ImportError:
    final_shot = None
    impacts = None

LINKAGE = 'FinalShotBattleViewer'
SWF_FILE = 'FinalShotBattleViewer.swf'
OPEN_DELAY = 1.05
SETTLE_DELAY = 1.35
PROJECT_INTERVAL = 0.05
logger = logging.getLogger('inq.final_shot.viewer')


def _cancel(callback_id):
    try:
        if callback_id is not None:
            BigWorld.cancelCallback(callback_id)
    except Exception:
        pass


def _part_name(index):
    try:
        if TankPartIndexes is not None and index in TankPartIndexes.ALL:
            return TankPartIndexes.getName(index)
    except Exception:
        pass
    return None


class FinalShotBattleViewerView(View):
    viewer = None

    def _populate(self):
        super(FinalShotBattleViewerView, self)._populate()
        if self.viewer is not None:
            self.viewer.on_view_ready(self)

    def _dispose(self):
        if self.viewer is not None:
            self.viewer.on_view_disposed(self)
        super(FinalShotBattleViewerView, self)._dispose()

    def py_onReady(self):
        if self.viewer is not None:
            self.viewer.on_flash_ready(self)


def _register_view():
    try:
        g_entitiesFactories.addSettings(ViewSettings(
            LINKAGE, FinalShotBattleViewerView, SWF_FILE, WindowLayer.WINDOW,
            None, ScopeTemplates.GLOBAL_SCOPE))
    except Exception:
        logger.debug('viewer settings already registered', exc_info=True)


class BattleViewer(object):
    def __init__(self):
        self.active = False
        self.vehicle_id = 0
        self.vehicle = None
        self.view = None
        self.flash_ready = False
        self.inject_callback = None
        self.frame_callback = None
        self.open_callback = None
        self.freeze_callback = None
        self.controller = None
        self._controller_patched = False
        self._cached_markers = []
        self._points_frozen = False

    def init(self):
        _register_view()
        FinalShotBattleViewerView.viewer = self
        g_playerEvents.onAccountShowGUI += self._on_leave
        event = getattr(g_playerEvents, 'onAccountBecomeNonPlayer', None)
        if event is not None:
            event += self._on_leave
        event = getattr(g_playerEvents, 'onDisconnected', None)
        if event is not None:
            event += self._on_leave
        self._patch_controller()
        logger.info('passive battle viewer initialized')

    def _patch_controller(self):
        if final_shot is None:
            logger.error('main Final Shot controller is unavailable')
            return
        controller = getattr(final_shot, '_controller', None)
        if controller is None or self._controller_patched:
            return
        self.controller = controller
        original_killed = controller._on_vehicle_killed
        original_leave = controller.leave_battle
        viewer = self

        def killed(target_id, attacker_id=0, *args, **kwargs):
            result = original_killed(target_id, attacker_id, *args, **kwargs)
            try:
                if int(target_id) == int(controller.player_vehicle_id):
                    viewer.schedule_open(int(target_id))
            except Exception:
                logger.exception('failed to schedule passive battle viewer')
            return result

        def leave():
            viewer.close()
            return original_leave()

        def show_without_old_panel():
            try:
                if impacts is not None:
                    impacts._decorate_hits(controller)
                controller.pending_show = False
                _cancel(getattr(controller, 'hide_callback', None))
                controller.hide_callback = None
                if controller.view is not None:
                    controller.view.flashObject.as_setVisible(False)
            except Exception:
                logger.exception('failed to suppress old summary panel')

        controller._on_vehicle_killed = killed
        controller.leave_battle = leave
        controller._show = show_without_old_panel
        controller._battle_viewer = self
        self._controller_patched = True
        logger.info('passive battle viewer controller patch installed')

    def schedule_open(self, vehicle_id):
        _cancel(self.open_callback)
        self.vehicle_id = int(vehicle_id or 0)
        self.open_callback = BigWorld.callback(OPEN_DELAY, self.open)

    def open(self):
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
            self._points_frozen = False
            self.freeze_callback = BigWorld.callback(SETTLE_DELAY, self._freeze_world_points)
            self._inject(0)
            self._schedule_frame(0.0)
            logger.info('passive viewer opened with %s impact markers', len(self._cached_markers))
        except Exception:
            logger.exception('failed to open passive battle viewer')
            self.close()

    def close(self):
        for callback_id in (self.open_callback, self.inject_callback, self.frame_callback, self.freeze_callback):
            _cancel(callback_id)
        self.open_callback = None
        self.inject_callback = None
        self.frame_callback = None
        self.freeze_callback = None
        if self.view is not None:
            try:
                self.view.flashObject.as_setVisible(False)
                self.view.flashObject.as_updateMarkers([])
            except Exception:
                pass
        self.active = False
        self.vehicle_id = 0
        self.vehicle = None
        self.flash_ready = False
        self._cached_markers = []
        self._points_frozen = False

    def _on_leave(self, *args, **kwargs):
        self.close()

    def _inject(self, attempt):
        self.inject_callback = None
        if not self.active or self.view is not None:
            return
        try:
            app = ServicesLocator.appLoader.getDefBattleApp()
            if app is not None and app.initialized:
                app.loadView(SFViewLoadParams(LINKAGE))
                return
        except Exception:
            logger.exception('battle viewer injection failed')
        if attempt < 35:
            self.inject_callback = BigWorld.callback(0.25, lambda: self._inject(attempt + 1))

    def on_view_ready(self, view):
        self.view = view
        self.flash_ready = False

    def on_view_disposed(self, view):
        if self.view is view:
            self.view = None
            self.flash_ready = False

    def on_flash_ready(self, view):
        if self.view is not view:
            return
        self.flash_ready = True
        try:
            view.flashObject.as_setVisible(bool(self.active))
            view.flashObject.as_updateMarkers(self._marker_data())
        except Exception:
            logger.exception('battle viewer flash initialization failed')

    def _attacker_icon(self, attacker_id):
        if getContourIconPath is None or not attacker_id:
            return u''
        try:
            arena = getattr(BigWorld.player(), 'arena', None)
            raw = arena.vehicles.get(int(attacker_id)) if arena is not None else None
            descriptor = raw.get('vehicleType') if raw else None
            item_type = getattr(descriptor, 'type', None)
            name = getattr(item_type, 'name', None)
            if name:
                return unicode(getContourIconPath(name))
        except Exception:
            pass
        return u''

    def _world_point(self, point):
        if self.vehicle is None or point is None:
            return None
        local = Math.Vector3(point.get('end') or (0.0, 0.0, 0.0))
        part_index = int(point.get('partIndex', -1))
        try:
            compound = self.vehicle.appearance.compoundModel
            part_name = _part_name(part_index)
            if part_name:
                return Math.Vector3(Math.Matrix(compound.node(part_name)).applyPoint(local))
        except Exception:
            pass
        try:
            return Math.Vector3(Math.Matrix(self.vehicle.model.matrix).applyPoint(local))
        except Exception:
            return None

    def _cache_hit_data(self):
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
                    'point': points[0],
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
            logger.exception('failed to cache hit data')

    def _freeze_world_points(self):
        self.freeze_callback = None
        if not self.active:
            return
        frozen = 0
        for item in self._cached_markers:
            world = self._world_point(item.get('point'))
            if world is not None:
                item['world'] = Math.Vector3(world)
                frozen += 1
        self._points_frozen = True
        logger.info('frozen %s impact points after wreck settle', frozen)

    def _marker_data(self):
        markers = []
        if not self._cached_markers:
            return markers
        width, height = GUI.screenResolution()
        width = float(width)
        height = float(height)
        for item in self._cached_markers:
            data = {
                'x': 0.0,
                'y': 0.0,
                'visible': False,
                'fatal': item['fatal'],
                'player': item['player'],
                'vehicle': item['vehicle'],
                'damage': item['damage'],
                'icon': item['icon'],
                'side': item['side'],
                'offsetY': item['offsetY'],
            }
            world = item.get('world')
            if world is None:
                world = self._world_point(item.get('point'))
            if world is not None:
                try:
                    projected = projectPoint(world)
                    if (projected.w > 0.0 and
                            -1.08 <= projected.x <= 1.08 and
                            -1.08 <= projected.y <= 1.08):
                        data['x'] = (projected.x + 1.0) * 0.5 * width
                        data['y'] = (1.0 - projected.y) * 0.5 * height
                        data['visible'] = True
                except Exception:
                    pass
            markers.append(data)
        return markers

    def _schedule_frame(self, delay=PROJECT_INTERVAL):
        _cancel(self.frame_callback)
        self.frame_callback = BigWorld.callback(delay, self._frame)

    def _frame(self):
        self.frame_callback = None
        if not self.active:
            return
        try:
            if self.view is not None and self.flash_ready:
                self.view.flashObject.as_updateMarkers(self._marker_data())
        except Exception:
            logger.exception('passive spectator projection failed')
        if self.active:
            self._schedule_frame()


_viewer = BattleViewer()
_viewer.init()
