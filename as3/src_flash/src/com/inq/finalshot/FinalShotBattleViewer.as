package com.inq.finalshot
{
    import flash.display.DisplayObject;
    import flash.display.Shape;
    import flash.display.Sprite;
    import flash.events.Event;
    import flash.events.MouseEvent;
    import flash.filters.DropShadowFilter;
    import flash.text.AntiAliasType;
    import flash.text.TextField;
    import flash.text.TextFieldAutoSize;
    import flash.text.TextFormat;

    import net.wg.gui.components.controls.UILoader;
    import net.wg.infrastructure.base.AbstractView;

    public class FinalShotBattleViewer extends AbstractView
    {
        public var py_onReady:Function = null;
        public var py_onClose:Function = null;

        private var _markers:Sprite;
        private var _rowsPanel:Sprite;
        private var _rowsContainer:Sprite;
        private var _hint:TextField;
        private var _close:Sprite;
        private var _markerViews:Array = [];
        private var _configured:Boolean = false;
        private var _frames:int = 0;
        private var _pendingRows:Array = null;
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
            if (_pendingRows != null)
            {
                var rows:Array = _pendingRows;
                _pendingRows = null;
                as_setRows(rows);
            }
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
            _pendingRows = null;
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

            _rowsPanel = new Sprite();
            _rowsPanel.mouseEnabled = false;
            _rowsPanel.filters = [new DropShadowFilter(3, 90, 0, 0.7, 8, 8, 1, 2)];
            addChild(_rowsPanel);

            _rowsContainer = new Sprite();
            _rowsContainer.mouseEnabled = false;
            _rowsPanel.addChild(_rowsContainer);

            _close = new Sprite();
            _close.buttonMode = true;
            _close.useHandCursor = true;
            _close.mouseEnabled = true;
            _close.graphics.beginFill(0x121921, 0.88);
            _close.graphics.lineStyle(1, 0x6B7884, 0.65);
            _close.graphics.drawRoundRect(0, 0, 34, 30, 6, 6);
            _close.graphics.endFill();
            var closeText:TextField = _text(18, 0xE6EDF3, true);
            closeText.text = "×";
            closeText.x = 10;
            closeText.y = 2;
            _close.addChild(closeText);
            _close.addEventListener(MouseEvent.CLICK, _onClose);
            _rowsPanel.addChild(_close);

            _hint = _text(12, 0xCBD3DA, false);
            _hint.text = "Мышь: вращение   Колесо: масштаб   Space: сброс   V / Esc: закрыть";
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
            if (_rowsPanel)
            {
                _rowsPanel.x = sw - 354;
                _rowsPanel.y = Math.max(115, int((sh - Math.max(190, _rowsPanel.height)) / 2));
            }
            if (_hint)
            {
                _hint.x = int((sw - _hint.width) / 2);
                _hint.y = sh - 52;
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

        private function _clearRows():void
        {
            if (!_rowsContainer)
                return;
            while (_rowsContainer.numChildren > 0)
                _rowsContainer.removeChildAt(0);
        }

        private function _makeRow(data:Object, yPos:Number):Sprite
        {
            var row:Sprite = new Sprite();
            row.mouseEnabled = false;
            row.mouseChildren = false;
            row.y = yPos;

            var fatal:Boolean = Boolean(data.fatal);
            var accent:uint = fatal ? 0xFF5555 : 0xE8C95A;
            var bg:Shape = new Shape();
            bg.graphics.lineStyle(1, fatal ? 0xB43D3D : 0x4A5660, fatal ? 0.95 : 0.65);
            bg.graphics.beginFill(0x0A1017, 0.88);
            bg.graphics.drawRoundRect(0, 0, 324, 72, 8, 8);
            bg.graphics.endFill();
            bg.graphics.beginFill(accent, 1.0);
            bg.graphics.drawRoundRect(0, 0, 4, 72, 4, 4);
            bg.graphics.endFill();
            row.addChild(bg);

            var idx:TextField = _text(15, accent, true);
            idx.text = String(data.index != null ? data.index : "");
            idx.x = 10;
            idx.y = 24;
            row.addChild(idx);

            var loader:UILoader = new UILoader();
            loader.x = 32;
            loader.y = 11;
            loader.width = 86;
            loader.height = 50;
            loader.maintainAspectRatio = true;
            loader.autoSize = false;
            var icon:String = String(data.icon != null ? data.icon : "");
            if (icon.length > 0)
                loader.source = icon;
            row.addChild(loader);

            var vehicle:TextField = _text(15, 0xF2F5F7, true);
            vehicle.text = String(data.vehicle != null ? data.vehicle : "?");
            vehicle.x = 122;
            vehicle.y = 9;
            vehicle.width = 140;
            vehicle.height = 22;
            row.addChild(vehicle);

            var player:TextField = _text(12, 0xAEB8C1, false);
            player.text = String(data.player != null ? data.player : "");
            player.x = 122;
            player.y = 31;
            player.width = 142;
            player.height = 19;
            row.addChild(player);

            var dmg:TextField = _text(17, fatal ? 0xFF6868 : 0xFFFFFF, true);
            dmg.text = "−" + String(data.damage != null ? data.damage : "0");
            dmg.autoSize = TextFieldAutoSize.RIGHT;
            dmg.x = 309 - dmg.width;
            dmg.y = 21;
            row.addChild(dmg);

            if (fatal)
            {
                var fatalText:TextField = _text(10, 0xFF7777, true);
                fatalText.text = "СМЕРТЕЛЬНЫЙ";
                fatalText.x = 122;
                fatalText.y = 49;
                row.addChild(fatalText);
            }
            return row;
        }

        public function as_setRows(rows:Array):void
        {
            if (!_configured)
            {
                _pendingRows = rows;
                return;
            }
            _clearRows();
            if (!rows)
                rows = [];
            var count:int = Math.min(rows.length, 5);
            for (var i:int = 0; i < count; i++)
                _rowsContainer.addChild(_makeRow(rows[i], i * 78));
            _close.x = 289;
            _close.y = count * 78 + 7;
            _positionUI();
        }

        private function _newMarker(data:Object):Sprite
        {
            var marker:Sprite = new Sprite();
            marker.mouseEnabled = false;
            marker.mouseChildren = false;
            marker.name = Boolean(data.fatal) ? "fatal" : "normal";
            _drawMarker(marker, data);
            return marker;
        }

        private function _drawMarker(marker:Sprite, data:Object):void
        {
            marker.graphics.clear();
            while (marker.numChildren > 0)
                marker.removeChildAt(0);
            var fatal:Boolean = Boolean(data.fatal);
            var color:uint = fatal ? 0xFF3434 : 0xFFD447;
            marker.graphics.lineStyle(fatal ? 3 : 2, 0x080808, 0.95);
            marker.graphics.beginFill(color, 0.92);
            marker.graphics.drawCircle(0, 0, fatal ? 10 : 8);
            marker.graphics.endFill();
            marker.graphics.lineStyle(2, color, 0.95);
            marker.graphics.drawCircle(0, 0, fatal ? 17 : 14);
            var label:TextField = _text(12, 0x101010, true);
            label.text = String(data.label != null ? data.label : "");
            label.autoSize = TextFieldAutoSize.CENTER;
            label.x = -label.width / 2;
            label.y = -label.height / 2 - 1;
            marker.addChild(label);
            marker.filters = [new DropShadowFilter(2, 90, 0, 0.8, 4, 4, 1, 1)];
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

            while (_markerViews.length < markers.length)
            {
                var created:Sprite = _newMarker(markers[_markerViews.length]);
                _markerViews.push(created);
                _markers.addChild(created);
            }
            while (_markerViews.length > markers.length)
            {
                var removed:Sprite = _markerViews.pop() as Sprite;
                if (removed && removed.parent)
                    removed.parent.removeChild(removed);
            }

            for (var i:int = 0; i < markers.length; i++)
            {
                var data:Object = markers[i];
                var marker:Sprite = _markerViews[i] as Sprite;
                var kind:String = Boolean(data.fatal) ? "fatal" : "normal";
                if (marker.name != kind)
                {
                    marker.name = kind;
                    _drawMarker(marker, data);
                }
                marker.x = Number(data.x);
                marker.y = Number(data.y);
                marker.visible = true;
            }
        }

        public function as_setVisible(value:Boolean):void
        {
            visible = value;
            if (value)
                _positionUI();
        }
    }
}
