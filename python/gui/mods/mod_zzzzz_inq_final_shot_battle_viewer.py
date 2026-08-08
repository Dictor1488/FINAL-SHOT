# -*- coding: utf-8 -*-
"""In-battle final-shot viewer for the destroyed player vehicle."""

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
    from gui.shared.gui_items.Vehicle import getContourIconPath
except ImportError:
    getContourIconPath = None

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
OPEN_DELAY = 1.05
# Mouse events can arrive hundreds of times per second. Camera + marker work is
# flushed at most ~30 FPS instead of being done for every raw input event.
FRAME_INTERVAL = 0.033
logger = logging.getLogger('inq.final_shot.viewer')


def _cancel(callback_id):
    try:
        if callback_id is not None:
            BigWorld.cancelCallback(callback_id)
    except Exception:
        pass


def _clamp(low, high, value):
    return max(low, min(high, value))


def _subscribe(collection, handler):
    if handler in collection:
        return
    add = getattr(collection, 'add', None)
    if add is not None:
        add(handler)
    else:
        collection.append(handler)


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
        self.center = Math.Vector3(0.0, 0.0, 0.0)
        self.yaw = math.radians(155.0)
        self.pitch = math.radians(-18.0)
        self.distance = 10.0
        self.free_camera = None
        self.previous_camera = None
        self.view = None
        self.flash_ready = False
        self.inject_callback = None
        self.frame_callback = None
        self.open_callback = None
        self.controller = None
        self._controller_patched = False
        self._camera_dirty = False
        self._markers_dirty = False
        self._cached_markers = []

    def init(self):
        _register_view()
        FinalShotBattleViewerView.viewer = self
        _subscribe(g_keyEventHandlers, self.handle_key)
        _subscribe(g_mouseEventHandlers, self.handle_mouse)
        g_playerEvents.onAccountShowGUI += self._on_leave
        event = getattr(g_playerEvents, 'onAccountBecomeNonPlayer', None)
        if event is not None:
            event += self._on_leave
        event = getattr(g_playerEvents, 'onDisconnected', None)
        if event is not None:
            event += self._on_leave
        self._patch_controller()
        logger.info('battle viewer initialized')

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
                logger.exception('failed to schedule battle viewer')
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
        logger.info('battle viewer controller patch installed')

    def schedule_open(self, vehicle_id):
        _cancel(self.open_callback)
        self.vehicle_id = int(vehicle_id or 0)
        self.open_callback = BigWorld.callback(OPEN_DELAY, self.open)
        logger.info('battle viewer scheduled for vehicle %s', self.vehicle_id)

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
            self.center = self._vehicle_center(vehicle)
            self._cache_hit_data()
            self.previous_camera = BigWorld.camera()
            self.free_camera = FreeCamera()
            self.free_camera.enable(Math.Matrix(self.previous_camera.invViewMatrix))
            self.active = True
            self._camera_dirty = True
            self._markers_dirty = True
            self._inject(0)
            self._schedule_frame(0.0)
            logger.info('battle viewer opened with %s frozen impact markers', len(self._cached_markers))
        except Exception:
            logger.exception('failed to open battle viewer')
            self.close()

    def close(self):
        for callback_id in (self.open_callback, self.inject_callback, self.frame_callback):
            _cancel(callback_id)
        self.open_callback = self.inject_callback = self.frame_callback = None
        if self.view is not None:
            try:
                self.view.flashObject.as_setVisible(False)
                self.view.flashObject.as_updateMarkers([])
            except Exception:
                pass
        if self.active:
            try:
                BigWorld.enableFreeCameraModeForShadowManager(False)
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
        self._camera_dirty = False
        self._markers_dirty = False
        self._cached_markers = []

    def _on_leave(self, *args, **kwargs):
        self.close()

    def _vehicle_center(self, vehicle):
        try:
            return Math.Matrix(vehicle.model.matrix).translation + Math.Vector3(0.0, 1.35, 0.0)
        except Exception:
            try:
                return Math.Vector3(vehicle.position) + Math.Vector3(0.0, 1.35, 0.0)
            except Exception:
                return self.center

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
            if dx or dy:
                self.yaw -= dx * 0.0045
                self.pitch = _clamp(math.radians(-70.0), math.radians(45.0),
                                    self.pitch - dy * 0.0038)
            if dz:
                self.distance = _clamp(3.0, 22.0, self.distance - dz * 0.01)
            if dx or dy or dz:
                # No expensive camera/Scaleform work inside the raw event.
                self._camera_dirty = True
                self._markers_dirty = True
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
                self._camera_dirty = True
                self._markers_dirty = True
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
        self._markers_dirty = True
        try:
            view.flashObject.as_setVisible(bool(self.active))
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
        if self.vehicle is None:
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
                # One visible projectile per received hit. parseHitPoint can contain
                # more than one internal point for the same shot path.
                world = self._world_point(points[0])
                if world is None:
                    continue
                hit_index += 1
                attacker_id = int(hit.get('attackerID', 0) or 0)
                player_name = unicode(hit.get('player') or u'')
                vehicle_name = unicode(hit.get('vehicle') or u'')
                if (not player_name or not vehicle_name) and self.controller is not None:
                    try:
                        vehicle_name, player_name = self.controller._vehicle_identity(attacker_id)
                    except Exception:
                        pass
                self._cached_markers.append({
                    'world': world,
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

    def _marker_data(self):
        markers = []
        if not self._cached_markers:
            return markers
        width, height = GUI.screenResolution()
        width = float(width)
        height = float(height)
        for item in self._cached_markers:
            projected = projectPoint(item['world'])
            if projected.w <= 0.0:
                continue
            if not (-1.08 <= projected.x <= 1.08 and -1.08 <= projected.y <= 1.08):
                continue
            markers.append({
                'x': (projected.x + 1.0) * 0.5 * width,
                'y': (1.0 - projected.y) * 0.5 * height,
                'fatal': item['fatal'],
                'player': item['player'],
                'vehicle': item['vehicle'],
                'damage': item['damage'],
                'icon': item['icon'],
                'side': item['side'],
                'offsetY': item['offsetY'],
            })
        return markers

    def _schedule_frame(self, delay=FRAME_INTERVAL):
        _cancel(self.frame_callback)
        self.frame_callback = BigWorld.callback(delay, self._frame)

    def _frame(self):
        self.frame_callback = None
        if not self.active:
            return
        try:
            camera_changed = self._camera_dirty
            if camera_changed:
                self._camera_dirty = False
                self._apply_camera()
            if self._markers_dirty and self.view is not None and self.flash_ready:
                self._markers_dirty = False
                self.view.flashObject.as_updateMarkers(self._marker_data())
        except Exception:
            logger.exception('battle viewer frame failed')
        if self.active:
            self._schedule_frame()


_viewer = BattleViewer()
_viewer.init()
