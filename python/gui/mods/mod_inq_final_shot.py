# -*- coding: utf-8 -*-
"""INQ Final Shot: show the last received hits after the player's vehicle dies."""

from __future__ import absolute_import

import json
import logging
import os
from collections import deque

import BigWorld
from PlayerEvents import g_playerEvents
from frameworks.wulf import WindowLayer
from gui.Scaleform.framework import ScopeTemplates, ViewSettings, g_entitiesFactories
from gui.Scaleform.framework.entities.View import View
from gui.Scaleform.framework.managers.loaders import SFViewLoadParams
from gui.shared.personality import ServicesLocator

try:
    from gui.battle_control import g_sessionProvider
except ImportError:
    g_sessionProvider = None

try:
    from gui.battle_control.battle_constants import FEEDBACK_EVENT_ID
except ImportError:
    FEEDBACK_EVENT_ID = None

try:
    from constants import ATTACK_REASONS, BATTLE_LOG_SHELL_TYPES
except ImportError:
    ATTACK_REASONS = None
    BATTLE_LOG_SHELL_TYPES = None


LINKAGE = 'FinalShotPanelBattle'
SWF_FILE = 'FinalShotPanelBattle.swf'
CONFIG_DIR = os.path.normpath(os.path.join(os.getcwd(), 'mods', 'configs', 'inq', 'final_shot'))
CONFIG_FILE = os.path.join(CONFIG_DIR, 'final_shot.json')
L10N_DIR = 'mods/inq.final_shot'
DEFAULTS = {
    'enabled': True,
    'maxHits': 3,
    'displaySeconds': 20.0,
    'position': [-1, 145],
    'scale': 1.0,
    'showPlayerName': True,
}

logger = logging.getLogger('inq.final_shot')
logger.setLevel(logging.DEBUG if os.path.isfile('.debug_mods') else logging.ERROR)


def _int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _cancel(callback_id):
    try:
        if callback_id is not None:
            BigWorld.cancelCallback(callback_id)
    except (AttributeError, ValueError):
        pass


def _mkdir(path):
    if os.path.isdir(path):
        return
    try:
        os.makedirs(path)
    except OSError:
        pass


def _load_config():
    _mkdir(CONFIG_DIR)
    loaded = {}
    if os.path.isfile(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'rb') as stream:
                loaded = json.load(stream)
            if not isinstance(loaded, dict):
                loaded = {}
        except Exception:
            logger.exception('config read failed')
    config = dict(DEFAULTS)
    config.update(loaded)
    config['enabled'] = bool(config.get('enabled', True))
    config['maxHits'] = max(1, min(10, _int(config.get('maxHits'), 3)))
    config['displaySeconds'] = max(0.0, min(120.0, _float(config.get('displaySeconds'), 20.0)))
    config['scale'] = max(0.65, min(1.75, _float(config.get('scale'), 1.0)))
    config['showPlayerName'] = bool(config.get('showPlayerName', True))
    position = config.get('position')
    if not isinstance(position, (list, tuple)) or len(position) < 2:
        position = [-1, 145]
    config['position'] = [_int(position[0], -1), _int(position[1], 145)]
    _save_config(config)
    return config


def _save_config(config):
    _mkdir(CONFIG_DIR)
    try:
        with open(CONFIG_FILE, 'wb') as stream:
            json.dump(config, stream, indent=4, sort_keys=True)
    except Exception:
        logger.exception('config write failed')


def _load_l10n():
    language = 'en'
    try:
        from helpers import getClientLanguage
        language = getClientLanguage() or 'en'
    except Exception:
        pass
    for candidate in (language, 'en'):
        try:
            import ResMgr
            section = ResMgr.openSection('%s/%s.json' % (L10N_DIR, candidate))
            if section is not None:
                return json.loads(section.asBinary)
        except Exception:
            logger.exception('localization load failed: %s', candidate)
    return {}


def _shell_key(shell_type, is_gold):
    if BATTLE_LOG_SHELL_TYPES is not None and shell_type is not None:
        mapping = (
            ('ARMOR_PIERCING', 'shellAP'),
            ('ARMOR_PIERCING_HE', 'shellAPHE'),
            ('ARMOR_PIERCING_CR', 'shellAPCR'),
            ('HOLLOW_CHARGE', 'shellHEAT'),
            ('HE_MODERN', 'shellHE'),
            ('HE_LEGACY_STUN', 'shellHE'),
            ('HE_LEGACY_NO_STUN', 'shellHE'),
        )
        for name, key in mapping:
            try:
                if shell_type == getattr(BATTLE_LOG_SHELL_TYPES, name):
                    return key + ('Gold' if is_gold else '')
            except Exception:
                pass
    return 'shellUnknownGold' if is_gold else 'shellUnknown'


def _attack_reason(extra):
    try:
        if ATTACK_REASONS is not None:
            return unicode(ATTACK_REASONS[extra.getAttackReasonID()])
    except Exception:
        pass
    try:
        if extra.isFire():
            return 'fire'
    except Exception:
        pass
    return 'shot'


class FinalShotView(View):
    controller = None

    def _populate(self):
        super(FinalShotView, self)._populate()
        if self.controller is not None:
            self.controller.on_view_ready(self)

    def _dispose(self):
        if self.controller is not None:
            self.controller.on_view_disposed(self)
        super(FinalShotView, self)._dispose()

    def py_onPanelReady(self):
        if self.controller is not None:
            self.controller.on_panel_ready(self)

    def py_onDragEnd(self, position):
        if self.controller is not None:
            self.controller.on_drag_end(position)


def _register_view():
    try:
        g_entitiesFactories.removeSettings(LINKAGE)
    except Exception:
        pass
    g_entitiesFactories.addSettings(ViewSettings(
        LINKAGE, FinalShotView, SWF_FILE, WindowLayer.WINDOW,
        None, ScopeTemplates.GLOBAL_SCOPE))


class FinalShotController(object):
    def __init__(self):
        self.config = _load_config()
        self.l10n = _load_l10n()
        self.hits = deque(maxlen=self.config['maxHits'])
        self.view = None
        self.panel_ready = False
        self.pending_show = False
        self.in_battle = False
        self.player_vehicle_id = 0
        self.provider = None
        self.feedback = None
        self.arena = None
        self.arena_subscription = None
        self.enter_callback = None
        self.inject_callback = None
        self.hide_callback = None

    def init(self):
        _register_view()
        FinalShotView.controller = self
        g_playerEvents.onAccountShowGUI += self._leave_event
        if getattr(g_playerEvents, 'onAvatarReady', None) is not None:
            g_playerEvents.onAvatarReady += self._avatar_ready
        if getattr(g_playerEvents, 'onAvatarBecomePlayer', None) is not None:
            g_playerEvents.onAvatarBecomePlayer += self._avatar_ready
        if getattr(g_playerEvents, 'onAccountBecomeNonPlayer', None) is not None:
            g_playerEvents.onAccountBecomeNonPlayer += self._leave_event
        if getattr(g_playerEvents, 'onDisconnected', None) is not None:
            g_playerEvents.onDisconnected += self._leave_event
        logger.debug('initialized')

    def _avatar_ready(self, *args, **kwargs):
        _cancel(self.enter_callback)
        self.enter_callback = BigWorld.callback(0.1, lambda: self._try_enter(0))

    def _leave_event(self, *args, **kwargs):
        self.leave_battle()

    def _try_enter(self, attempt):
        self.enter_callback = None
        try:
            player = BigWorld.player()
            vehicle_id = _int(getattr(player, 'playerVehicleID', 0))
            if getattr(player, 'arena', None) is not None and vehicle_id:
                self.enter_battle(player, vehicle_id)
                return
        except Exception:
            logger.exception('battle detection failed')
        if attempt < 40:
            self.enter_callback = BigWorld.callback(0.25, lambda: self._try_enter(attempt + 1))

    def enter_battle(self, player, vehicle_id):
        self.leave_battle()
        self.in_battle = True
        self.player_vehicle_id = vehicle_id
        self.hits = deque(maxlen=self.config['maxHits'])
        self.provider = getattr(player, 'guiSessionProvider', None) or g_sessionProvider
        self._bind_events(player)
        self._inject(0)

    def leave_battle(self):
        self._unbind_events()
        _cancel(self.enter_callback)
        _cancel(self.inject_callback)
        _cancel(self.hide_callback)
        self.enter_callback = self.inject_callback = self.hide_callback = None
        self.in_battle = False
        self.pending_show = False
        self.player_vehicle_id = 0
        self.hits.clear()
        self.provider = None
        if self.view is not None:
            try:
                self.view.flashObject.as_setVisible(False)
            except Exception:
                pass
        self.view = None
        self.panel_ready = False

    def _bind_events(self, player):
        try:
            shared = getattr(self.provider, 'shared', None)
            self.feedback = getattr(shared, 'feedback', None) if shared is not None else None
            if self.feedback is not None:
                self.feedback.onPlayerFeedbackReceived += self._on_feedback
        except Exception:
            logger.exception('feedback subscribe failed')
            self.feedback = None
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
            logger.exception('kill event subscribe failed')
            self.arena = None
            self.arena_subscription = None

    def _unbind_events(self):
        if self.feedback is not None:
            try:
                self.feedback.onPlayerFeedbackReceived -= self._on_feedback
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

    def _on_feedback(self, events):
        if not self.in_battle or not self.config['enabled']:
            return
        for event in events:
            try:
                if FEEDBACK_EVENT_ID is not None and event.getType() != FEEDBACK_EVENT_ID.ENEMY_DAMAGED_HP_PLAYER:
                    continue
                extra = event.getExtra()
                damage = _int(extra.getDamage())
                if damage <= 0:
                    continue
                attacker_id = _int(event.getTargetID())
                shell_type = None
                is_gold = False
                try:
                    shell_type = extra.getShellType()
                    is_gold = bool(extra.isShellGold())
                except Exception:
                    pass
                vehicle, player_name = self._vehicle_identity(attacker_id)
                self.hits.append({
                    'attackerID': attacker_id,
                    'vehicle': vehicle,
                    'player': player_name if self.config['showPlayerName'] else u'',
                    'damage': damage,
                    'shellKey': _shell_key(shell_type, is_gold),
                    'isGold': is_gold,
                    'reason': _attack_reason(extra),
                    'fatal': False,
                })
            except Exception:
                logger.exception('feedback event failed')

    def _on_vehicle_killed(self, target_id, attacker_id=0, *args, **kwargs):
        if not self.in_battle or _int(target_id) != self.player_vehicle_id:
            return
        attacker_id = _int(attacker_id)
        if self.hits:
            fatal = None
            for item in reversed(self.hits):
                if attacker_id and item.get('attackerID') == attacker_id:
                    fatal = item
                    break
            (fatal or self.hits[-1])['fatal'] = True
        self.pending_show = True
        BigWorld.callback(0.15, self._show)

    def _vehicle_identity(self, vehicle_id):
        unknown_vehicle = self._tr('unknownVehicle', u'Unknown vehicle')
        unknown_player = self._tr('unknownPlayer', u'Unknown player')
        try:
            arena_dp = self.provider.getArenaDP() if self.provider is not None else None
            info = arena_dp.getVehicleInfo(vehicle_id) if arena_dp is not None else None
            if info:
                vehicle_type = getattr(info, 'vehicleType', None)
                player = getattr(info, 'player', None)
                return (unicode(getattr(vehicle_type, 'guiName', None) or unknown_vehicle),
                        unicode(getattr(player, 'name', None) or unknown_player))
        except Exception:
            pass
        try:
            arena = getattr(BigWorld.player(), 'arena', None)
            raw = arena.vehicles.get(vehicle_id) if arena is not None else None
            if raw:
                player_name = raw.get('name') or raw.get('playerName') or unknown_player
                vehicle_type = raw.get('vehicleType')
                item_type = getattr(vehicle_type, 'type', None)
                vehicle_name = getattr(item_type, 'userString', None) or raw.get('vehicleTypeName') or unknown_vehicle
                return unicode(vehicle_name), unicode(player_name)
        except Exception:
            pass
        return unknown_vehicle, unknown_player

    def _inject(self, attempt):
        self.inject_callback = None
        if not self.in_battle or self.view is not None:
            return
        try:
            app = ServicesLocator.appLoader.getDefBattleApp()
            if app is not None and app.initialized:
                app.loadView(SFViewLoadParams(LINKAGE))
                return
        except Exception:
            logger.exception('view injection failed: %s', attempt)
        if attempt < 35:
            self.inject_callback = BigWorld.callback(0.4, lambda: self._inject(attempt + 1))

    def on_view_ready(self, view):
        self.view = view
        self.panel_ready = False

    def on_view_disposed(self, view):
        if self.view is view:
            self.view = None
            self.panel_ready = False

    def on_panel_ready(self, view):
        if self.view is not view:
            return
        self.panel_ready = True
        try:
            view.flashObject.as_setPosition(self.config['position'])
            view.flashObject.as_setScale(float(self.config['scale']))
            view.flashObject.as_setVisible(False)
        except Exception:
            logger.exception('panel initialization failed')
        if self.pending_show:
            self._show()

    def on_drag_end(self, position):
        try:
            self.config['position'] = [_int(position[0], -1), _int(position[1], 145)]
            _save_config(self.config)
        except Exception:
            logger.exception('position save failed')

    def _show(self):
        if not self.in_battle or not self.pending_show:
            return
        if self.view is None or not self.panel_ready:
            self._inject(0)
            return
        rows = [{
            'vehicle': hit.get('vehicle', self._tr('unknownVehicle', u'Unknown vehicle')),
            'player': hit.get('player', u''),
            'damage': _int(hit.get('damage')),
            'shell': self._tr(hit.get('shellKey'), self._tr('shellUnknown', u'?')),
            'isGold': bool(hit.get('isGold')),
            'reason': hit.get('reason', 'shot'),
            'fatal': bool(hit.get('fatal')),
        } for hit in self.hits]
        if not rows:
            rows = [{
                'vehicle': self._tr('unknownVehicle', u'Unknown vehicle'),
                'player': u'', 'damage': 0,
                'shell': self._tr('shellUnknown', u'?'),
                'isGold': False, 'reason': 'unknown', 'fatal': True,
            }]
        try:
            self.view.flashObject.as_setData(
                self._tr('title', u'FINAL SHOT'),
                self._tr('subtitle', u'Last hits before destruction'),
                self._tr('fatalLabel', u'DESTRUCTION'), rows)
            self.view.flashObject.as_setVisible(True)
            self.pending_show = False
            _cancel(self.hide_callback)
            duration = float(self.config['displaySeconds'])
            if duration > 0.0:
                self.hide_callback = BigWorld.callback(duration, self._hide)
        except Exception:
            logger.exception('panel display failed')

    def _hide(self):
        self.hide_callback = None
        if self.view is not None:
            try:
                self.view.flashObject.as_setVisible(False)
            except Exception:
                pass

    def _tr(self, key, default=u''):
        try:
            return unicode(self.l10n.get(key, default))
        except Exception:
            return default


_controller = FinalShotController()
_controller.init()
