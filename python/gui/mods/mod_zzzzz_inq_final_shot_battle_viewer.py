# -*- coding: utf-8 -*-
"""Interactive in-battle 3D inspection of the destroyed player vehicle.

The viewer keeps the real vehicle model in the arena, switches to a temporary
free orbit camera and projects the decoded Battle Hits impact points on top of
that model.  It intentionally does not create a hangar scene.
"""

from __future__ import absolute_import

import logging
import math

import BigWorld
import GUI
import Keys
import Math

from AvatarInputHandler.cameras import FreeCamera, projectPoint
from PlayerEvents import g_playerEvents
from frameworks.wulf import WindowLayer
from gui import g_keyEventHandlers, g_mouseEventHandlers
from gui.Scaleform.framework import ScopeTemplates, ViewSettings, g_entitiesFactories
from gui.Scaleform.framework.entities.View import View
from gui.Scaleform.framework.managers.loaders import SFViewLoadParams
from gui.shared.personality import ServicesLocator

try:
    from vehicle_systems.tankStructure import TankPartIndexes
except ImportError:
    TankPartIndexes = None

try:
    from gui.mods import mod_inq_final_shot as final_shot
    from gui.mods import mod_zzz_inq_final_shot_impacts as impacts
except ImportError:
    final_shot = None
    impacts = None


LINKAGE = 'FinalShotBattleViewer'
SWF_FILE = 'FinalShotBattleViewer.swf'
logger = logging.getLogger('inq.final_shot.viewer')


def _cancel(callback_id):
    try:
        if callback_id is not None:
            BigWorld.cancelCallback(callback_id)
    except Exception:
        pass


def _clamp(low, high, value):
    return max(low, min(high, value))


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

    def py_onClose(self):
        if self.viewer is not None:
            self.viewer.close()


def _register_view():
    try:
        g_entitiesFactories.removeSettings(LINKAGE)
    except Exception:
        pass
    g_entitiesFactories.addSettings(ViewSettings(
        LINKAGE,
        FinalShotBattleViewerView,
        SWF_FILE,
        WindowLayer.WINDOW,
        None,
        ScopeTemplates.GLOBAL_SCOPE,
    ))


class BattleViewer(object):
    def __init__(self):
        self.active = False
        self.vehicle_id = 0
        self.vehicle = None
        self.center = Math.Vector3(0.0, 0.0, 0.0)
        self.yaw = math.radians(155.0)
        self.pitch = math.radians(-18.0)
        self.distance = 10.0
        self.free_camera = None
        self.previous_camera = None
        self.view = None
        self.flash_ready = False
        self.inject_callback = None
        self.update_callback = None
        self.open_callback = None
        self.auto_close_callback = None
        self.controller = None
        self._controller_patched = False

    def init(self):
        _register_view()
        FinalShotBattleViewerView.viewer = self
        if self.handle_key not in g_keyEventHandlers:
            g_keyEventHandlers.append(self.handle_key)
        if self.handle_mouse not in g_mouseEventHandlers:
            g_mouseEventHandlers.append(self.handle_mouse)
        g_playerEvents.onAccountShowGUI += self._on_leave
        if getattr(g_playerEvents, 'onAccountBecomeNonPlayer', None) is not None:
            g_playerEvents.onAccountBecomeNonPlayer += self._on_leave
        if getattr(g_playerEvents, 'onDisconnected', None) is not None:
            g_playerEvents.onDisconnected += self._on_leave
        self._patch_controller()

    def _patch_controller(self):
        if final_shot is None:
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
                logger.exception('failed to schedule battle viewer')
            return result

        def leave():
            viewer.close()
            return original_leave()

        controller._on_vehicle_killed = killed
        controller.leave_battle = leave
        controller._battle_viewer = self
        self._controller_patched = True

    def schedule_open(self, vehicle_id):
        _cancel(self.open_callback)
        self.vehicle_id = int(vehicle_id or 0)
        self.open_callback = BigWorld.callback(0.45, self.open)

    def open(self):
        self.open_callback = None
        if self.active or not self.vehicle_id:
            return
        try:
            vehicle = BigWorld.entity(self.vehicle_id)
            if vehicle is None:
                vehicle = BigWorld.entities.get(self.vehicle_id)
            if vehicle is None:
                logger.warning('player vehicle entity is no longer available')
                return
            self.vehicle = vehicle
            self.center = self._vehicle_center(vehicle)
            self.previous_camera = BigWorld.camera()
            self.free_camera = FreeCamera()
            self.free_camera.enable()
            self.active = True
            self._apply_camera()
            self._inject(0)
            self._update()
            duration = 0.0
            if self.controller is not None:
                duration = float(self.controller.config.get('displaySeconds', 0.0))
            if duration > 0.0:
                self.auto_close_callback = BigWorld.callback(max(10.0, duration), self.close)
        except Exception:
            logger.exception('failed to open battle viewer')
            self.close()

    def close(self):
        _cancel(self.open_callback)
        _cancel(self.inject_callback)
        _cancel(self.update_callback)
        _cancel(self.auto_close_callback)
        self.open_callback = None
        self.inject_callback = None
        self.update_callback = None
        self.auto_close_callback = None
        if self.view is not None:
            try:
                self.view.flashObject.as_setVisible(False)
                self.view.flashObject.as_setMarkers([])
            except Exception:
                pass
        if self.active:
            try:
                BigWorld.enableFreeCameraModeForShadowManager(False)
            except Exception:
                pass
            try:
                if self.previous_camera is not None:
                    BigWorld.camera(self.previous_camera)
            except Exception:
                logger.exception('failed to restore battle camera')
        self.active = False
        self.vehicle_id = 0
        self.vehicle = None
        self.free_camera = None
        self.previous_camera = None
        self.flash_ready = False

    def _on_leave(self, *args, **kwargs):
        self.close()

    def _vehicle_center(self, vehicle):
        try:
            matrix = Math.Matrix(vehicle.model.matrix)
            return matrix.translation + Math.Vector3(0.0, 1.35, 0.0)
        except Exception:
            try:
                return Math.Vector3(vehicle.position) + Math.Vector3(0.0, 1.35, 0.0)
            except Exception:
                return Math.Vector3(0.0, 1.35, 0.0)

    def _apply_camera(self):
        if not self.active or self.free_camera is None:
            return
        rotation = Math.Matrix()
        rotation.setRotateYPR((self.yaw, self.pitch, 0.0))
        forward = rotation.applyVector(Math.Vector3(0.0, 0.0, 1.0))
        position = self.center - forward.scale(self.distance)
        world = Math.Matrix(rotation)
        world.translation = position
        self.free_camera.setWorldMatrix(world)

    def handle_mouse(self, event):
        if not self.active:
            return False
        try:
            dx = float(getattr(event, 'dx', 0.0))
            dy = float(getattr(event, 'dy', 0.0))
            dz = float(getattr(event, 'dz', 0.0))
            self.yaw -= dx * 0.0045
            self.pitch = _clamp(math.radians(-70.0), math.radians(45.0), self.pitch - dy * 0.0038)
            if dz:
                self.distance = _clamp(3.0, 22.0, self.distance - dz * 0.01)
            self._apply_camera()
            return True
        except Exception:
            logger.exception('viewer mouse input failed')
            return False

    def handle_key(self, event):
        if not self.active:
            return False
        try:
            if not event.isKeyDown() or event.isRepeatedEvent():
                return False
            if event.key in (Keys.KEY_ESCAPE, Keys.KEY_V):
                self.close()
                return True
            if event.key == Keys.KEY_SPACE:
                self.yaw = math.radians(155.0)
                self.pitch = math.radians(-18.0)
                self.distance = 10.0
                self._apply_camera()
                return True
        except Exception:
            logger.exception('viewer key input failed')
        return False

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
            view.flashObject.as_setTitle(
                u'FINAL SHOT · 3D',
                u'Мышь — вращение · колесо — масштаб · Space — сброс · V/Esc — закрыть',
            )
            view.flashObject.as_setVisible(bool(self.active))
        except Exception:
            logger.exception('battle viewer flash initialization failed')

    def _world_point(self, point):
        if self.vehicle is None:
            return None
        local = Math.Vector3(point.get('end') or (0.0, 0.0, 0.0))
        part_index = int(point.get('partIndex', -1))
        try:
            appearance = self.vehicle.appearance
            compound = appearance.compoundModel
            part_name = _part_name(part_index)
            if part_name:
                matrix = Math.Matrix(compound.node(part_name))
                return matrix.applyPoint(local)
        except Exception:
            pass
        try:
            return Math.Matrix(self.vehicle.model.matrix).applyPoint(local)
        except Exception:
            return None

    def _marker_data(self):
        markers = []
        if self.controller is None or impacts is None:
            return markers
        try:
            impacts._decorate_hits(self.controller)
            width, height = GUI.screenResolution()
            width = float(width)
            height = float(height)
            number = 0
            for hit in self.controller.hits:
                for point in hit.get('impactPoints') or ():
                    world = self._world_point(point)
                    if world is None:
                        continue
                    projected = projectPoint(world)
                    if projected.w <= 0.0:
                        continue
                    if not (-1.05 <= projected.x <= 1.05 and -1.05 <= projected.y <= 1.05):
                        continue
                    number += 1
                    markers.append({
                        'x': (projected.x + 1.0) * 0.5 * width,
                        'y': (1.0 - projected.y) * 0.5 * height,
                        'label': unicode(number),
                        'fatal': bool(hit.get('fatal')),
                        'damage': int(hit.get('damage', 0) or 0),
                        'part': unicode(point.get('part') or hit.get('impactPart') or ''),
                    })
            return markers
        except Exception:
            logger.exception('failed to project impact markers')
            return []

    def _update(self):
        self.update_callback = None
        if not self.active:
            return
        try:
            if self.vehicle is None or BigWorld.entity(self.vehicle_id) is None:
                self.close()
                return
            self.center = self._vehicle_center(self.vehicle)
            self._apply_camera()
            if self.view is not None and self.flash_ready:
                self.view.flashObject.as_setVisible(True)
                self.view.flashObject.as_setMarkers(self._marker_data())
        except Exception:
            logger.exception('battle viewer update failed')
        if self.active:
            self.update_callback = BigWorld.callback(0.033, self._update)


_viewer = BattleViewer()
_viewer.init()
