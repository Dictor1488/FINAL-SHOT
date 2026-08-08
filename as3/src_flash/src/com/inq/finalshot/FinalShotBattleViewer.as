package com.inq.finalshot
{
    import flash.display.DisplayObject;
    import flash.display.Loader;
    import flash.display.Shape;
    import flash.display.Sprite;
    import flash.events.Event;
    import flash.events.IOErrorEvent;
    import flash.events.MouseEvent;
    import flash.filters.DropShadowFilter;
    import flash.net.URLRequest;
    import flash.text.AntiAliasType;
    import flash.text.TextField;
    import flash.text.TextFieldAutoSize;
    import flash.text.TextFormat;

    import net.wg.infrastructure.base.AbstractView;

    public class FinalShotBattleViewer extends AbstractView
    {
        public var py_onReady:Function = null;
        public var py_onClose:Function = null;

        private var _markers:Sprite;
        private var _hint:TextField;
        private var _close:Sprite;
        private var _markerViews:Array = [];
        private var _configured:Boolean = false;
        private var _frames:int = 0;
        private var _pendingMarkers:Array = null;

        public function FinalShotBattleViewer()
        {
            super();
            mouseEnabled = false;
        }

        override protected function configUI():void
        {
            super.configUI();
            _build();
            _configured = true;
            visible = false;
            if (App.instance && App.instance.stage)
                App.instance.stage.addEventListener(Event.RESIZE, _onResize);
            addEventListener(Event.ENTER_FRAME, _readyFrame);
            if (_pendingMarkers != null)
            {
                var markers:Array = _pendingMarkers;
                _pendingMarkers = null;
                as_updateMarkers(markers);
            }
        }

        override protected function onDispose():void
        {
            removeEventListener(Event.ENTER_FRAME, _readyFrame);
            if (App.instance && App.instance.stage)
                App.instance.stage.removeEventListener(Event.RESIZE, _onResize);
            if (_close)
                _close.removeEventListener(MouseEvent.CLICK, _onClose);
            py_onReady = null;
            py_onClose = null;
            _pendingMarkers = null;
            _markerViews = [];
            super.onDispose();
        }

        private function _build():void
        {
            _markers = new Sprite();
            _markers.mouseEnabled = false;
            _markers.mouseChildren = false;
            addChild(_markers);

            _close = new Sprite();
            _close.buttonMode = true;
            _close.useHandCursor = true;
            _close.mouseEnabled = true;
            _close.graphics.lineStyle(1, 0x73808C, 0.65);
            _close.graphics.beginFill(0x0A1017, 0.78);
            _close.graphics.drawRoundRect(0, 0, 30, 26, 6, 6);
            _close.graphics.endFill();
            var closeText:TextField = _text(17, 0xE8EDF1, true);
            closeText.text = "x";
            closeText.x = 10;
            closeText.y = 1;
            _close.addChild(closeText);
            _close.addEventListener(MouseEvent.CLICK, _onClose);
            addChild(_close);

            _hint = _text(12, 0xD5DCE2, false);
            _hint.text = "Mouse: rotate   Wheel: zoom   Space: reset   V / Esc: close";
            _hint.filters = [new DropShadowFilter(2, 90, 0, 0.95, 4, 4, 1, 1)];
            addChild(_hint);

            _positionUI();
        }

        private function _text(size:int, color:uint, bold:Boolean):TextField
        {
            var field:TextField = new TextField();
            field.defaultTextFormat = new TextFormat(bold ? "$TitleFont" : "$FieldFont", size, color, bold);
            field.antiAliasType = AntiAliasType.ADVANCED;
            field.autoSize = TextFieldAutoSize.LEFT;
            field.selectable = false;
            field.mouseEnabled = false;
            field.embedFonts = false;
            return field;
        }

        private function _positionUI():void
        {
            if (!App.instance || !App.instance.stage)
                return;
            var sw:Number = App.instance.stage.stageWidth;
            var sh:Number = App.instance.stage.stageHeight;
            if (_hint)
            {
                _hint.x = int((sw - _hint.width) / 2);
                _hint.y = sh - 48;
            }
            if (_close)
            {
                _close.x = sw - 48;
                _close.y = 20;
            }
        }

        private function _onResize(event:Event):void
        {
            _positionUI();
        }

        private function _readyFrame(event:Event):void
        {
            _frames++;
            if (_frames < 4)
                return;
            removeEventListener(Event.ENTER_FRAME, _readyFrame);
            if (py_onReady != null)
                py_onReady();
        }

        private function _onClose(event:MouseEvent):void
        {
            if (py_onClose != null)
                py_onClose();
        }

        private function _drawProjectile(target:Sprite, color:uint, fatal:Boolean):void
        {
            target.graphics.lineStyle(1.5, 0x111111, 0.95);
            target.graphics.beginFill(color, 0.98);
            target.graphics.drawRoundRect(-8, -3, 14, 6, 4, 4);
            target.graphics.endFill();
            target.graphics.beginFill(color, 0.98);
            target.graphics.moveTo(6, -3);
            target.graphics.lineTo(13, 0);
            target.graphics.lineTo(6, 3);
            target.graphics.lineTo(6, -3);
            target.graphics.endFill();
            target.graphics.lineStyle(fatal ? 2 : 1, color, 0.85);
            target.graphics.drawCircle(0, 0, fatal ? 11 : 9);
        }

        private function _drawDashes(target:Sprite, x1:Number, y1:Number, x2:Number, y2:Number, color:uint):void
        {
            var dx:Number = x2 - x1;
            var dy:Number = y2 - y1;
            var len:Number = Math.sqrt(dx * dx + dy * dy);
            if (len <= 0)
                return;
            var ux:Number = dx / len;
            var uy:Number = dy / len;
            var dash:Number = 5;
            var gap:Number = 4;
            var pos:Number = 0;
            target.graphics.lineStyle(1.5, color, 0.85);
            while (pos < len)
            {
                var end:Number = Math.min(pos + dash, len);
                target.graphics.moveTo(x1 + ux * pos, y1 + uy * pos);
                target.graphics.lineTo(x1 + ux * end, y1 + uy * end);
                pos += dash + gap;
            }
        }

        private function _addIcon(holder:Sprite, icon:String):void
        {
            if (icon == null || icon.length == 0)
                return;
            var loader:Loader = new Loader();
            loader.contentLoaderInfo.addEventListener(Event.COMPLETE, function(event:Event):void
            {
                var content:DisplayObject = loader.content;
                if (content == null || content.width <= 0 || content.height <= 0)
                    return;
                var scale:Number = Math.min(58 / content.width, 32 / content.height);
                content.scaleX = scale;
                content.scaleY = scale;
                content.x = (58 - content.width) / 2;
                content.y = (32 - content.height) / 2;
            });
            loader.contentLoaderInfo.addEventListener(IOErrorEvent.IO_ERROR, function(event:IOErrorEvent):void {});
            holder.addChild(loader);
            try
            {
                loader.load(new URLRequest(icon));
            }
            catch (error:Error)
            {
            }
        }

        private function _newMarker(data:Object):Sprite
        {
            var marker:Sprite = new Sprite();
            marker.mouseEnabled = false;
            marker.mouseChildren = false;

            var fatal:Boolean = Boolean(data.fatal);
            var color:uint = fatal ? 0xFF4141 : 0xF3C94A;
            var side:Number = Number(data.side) >= 0 ? 1 : -1;
            var offsetY:Number = Number(data.offsetY);
            var calloutX:Number = side * 94;
            var calloutY:Number = offsetY;

            var projectile:Sprite = new Sprite();
            projectile.rotation = side > 0 ? 0 : 180;
            _drawProjectile(projectile, color, fatal);
            projectile.filters = [new DropShadowFilter(2, 90, 0, 0.9, 4, 4, 1, 1)];
            marker.addChild(projectile);

            var line:Sprite = new Sprite();
            _drawDashes(line, side * 15, 0, calloutX - side * 8, calloutY, color);
            marker.addChildAt(line, 0);

            var card:Sprite = new Sprite();
            card.x = side > 0 ? calloutX : calloutX - 186;
            card.y = calloutY - 20;
            card.graphics.lineStyle(1, color, fatal ? 0.9 : 0.55);
            card.graphics.beginFill(0x081018, 0.82);
            card.graphics.drawRoundRect(0, 0, 186, 42, 7, 7);
            card.graphics.endFill();
            marker.addChild(card);

            var iconHolder:Sprite = new Sprite();
            iconHolder.x = 3;
            iconHolder.y = 5;
            card.addChild(iconHolder);
            _addIcon(iconHolder, String(data.icon != null ? data.icon : ""));

            var nick:TextField = _text(13, fatal ? 0xFF7575 : 0xFFFFFF, true);
            nick.text = String(data.player != null && String(data.player).length > 0 ? data.player : data.vehicle);
            nick.x = 64;
            nick.y = 4;
            nick.width = 116;
            nick.height = 19;
            card.addChild(nick);

            var sub:TextField = _text(10, 0xB9C2CA, false);
            var vehicle:String = String(data.vehicle != null ? data.vehicle : "");
            var damage:String = String(data.damage != null ? data.damage : "");
            sub.text = vehicle + (damage.length > 0 ? "   -" + damage : "");
            sub.x = 64;
            sub.y = 22;
            sub.width = 116;
            sub.height = 16;
            card.addChild(sub);

            card.filters = [new DropShadowFilter(2, 90, 0, 0.85, 5, 5, 1, 1)];
            return marker;
        }

        private function _clearMarkers():void
        {
            while (_markers && _markers.numChildren > 0)
                _markers.removeChildAt(0);
            _markerViews = [];
        }

        public function as_updateMarkers(markers:Array):void
        {
            if (!_configured)
            {
                _pendingMarkers = markers;
                return;
            }
            if (!markers)
                markers = [];

            if (_markerViews.length != markers.length)
            {
                _clearMarkers();
                for (var c:int = 0; c < markers.length; c++)
                {
                    var created:Sprite = _newMarker(markers[c]);
                    _markerViews.push(created);
                    _markers.addChild(created);
                }
            }

            for (var i:int = 0; i < markers.length; i++)
            {
                var data:Object = markers[i];
                var marker:Sprite = _markerViews[i] as Sprite;
                marker.x = Number(data.x);
                marker.y = Number(data.y);
                marker.visible = true;
            }
        }

        // Compatibility no-op for older Python builds that may call it during a
        // soft GUI reload. The separate right-side hit list was intentionally removed.
        public function as_setRows(rows:Array):void
        {
        }

        public function as_setVisible(value:Boolean):void
        {
            visible = value;
            if (value)
                _positionUI();
        }
    }
}
