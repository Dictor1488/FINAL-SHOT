package com.inq.finalshot
{
    import flash.display.Shape;
    import flash.display.Sprite;
    import flash.events.Event;
    import flash.events.MouseEvent;
    import flash.filters.DropShadowFilter;
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
        private var _header:Sprite;
        private var _title:TextField;
        private var _help:TextField;
        private var _close:Sprite;
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
                as_setMarkers(markers);
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
            super.onDispose();
        }

        private function _build():void
        {
            _markers = new Sprite();
            _markers.mouseEnabled = false;
            _markers.mouseChildren = false;
            addChild(_markers);

            _header = new Sprite();
            _header.filters = [new DropShadowFilter(3, 90, 0, 0.7, 8, 8, 1, 2)];
            addChild(_header);

            var bg:Shape = new Shape();
            bg.graphics.lineStyle(1, 0x657585, 0.9);
            bg.graphics.beginFill(0x0D151E, 0.92);
            bg.graphics.drawRoundRect(0, 0, 660, 58, 10, 10);
            bg.graphics.endFill();
            _header.addChild(bg);

            _title = _text(18, 0xFFFFFF, true);
            _title.x = 16;
            _title.y = 7;
            _header.addChild(_title);

            _help = _text(12, 0xAEBAC6, false);
            _help.x = 16;
            _help.y = 32;
            _header.addChild(_help);

            _close = new Sprite();
            _close.buttonMode = true;
            _close.useHandCursor = true;
            _close.graphics.beginFill(0x253342, 1.0);
            _close.graphics.drawRoundRect(0, 0, 42, 32, 7, 7);
            _close.graphics.endFill();
            var closeText:TextField = _text(18, 0xFFFFFF, true);
            closeText.text = "×";
            closeText.x = 14;
            closeText.y = 3;
            _close.addChild(closeText);
            _close.x = 608;
            _close.y = 13;
            _close.addEventListener(MouseEvent.CLICK, _onClose);
            _header.addChild(_close);

            _positionHeader();
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

        private function _positionHeader():void
        {
            if (!_header || !App.instance || !App.instance.stage)
                return;
            _header.x = int((App.instance.stage.stageWidth - 660) / 2);
            _header.y = 18;
        }

        private function _onResize(event:Event):void
        {
            _positionHeader();
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

        private function _clearMarkers():void
        {
            if (!_markers)
                return;
            while (_markers.numChildren > 0)
                _markers.removeChildAt(0);
        }

        private function _makeMarker(data:Object):Sprite
        {
            var marker:Sprite = new Sprite();
            marker.mouseEnabled = false;
            marker.mouseChildren = false;

            var fatal:Boolean = Boolean(data.fatal);
            var color:uint = fatal ? 0xFF4D4D : 0xFFD65A;
            marker.graphics.lineStyle(2, 0x000000, 0.8);
            marker.graphics.beginFill(color, 0.95);
            marker.graphics.drawCircle(0, 0, fatal ? 13 : 11);
            marker.graphics.endFill();
            marker.graphics.lineStyle(2, color, 0.9);
            marker.graphics.drawCircle(0, 0, fatal ? 19 : 16);

            var label:TextField = _text(13, 0x111111, true);
            label.text = String(data.label != null ? data.label : "");
            label.autoSize = TextFieldAutoSize.CENTER;
            label.x = -label.width / 2;
            label.y = -label.height / 2 - 1;
            marker.addChild(label);

            var caption:TextField = _text(12, 0xFFFFFF, true);
            var damage:String = String(data.damage != null ? data.damage : "");
            var part:String = String(data.part != null ? data.part : "");
            caption.text = (fatal ? "СМЕРТЕЛЬНЫЙ · " : "") + damage + (part.length > 0 ? " · " + part : "");
            caption.x = 22;
            caption.y = -10;
            caption.filters = [new DropShadowFilter(2, 90, 0, 1, 4, 4, 2, 1)];
            marker.addChild(caption);
            return marker;
        }

        public function as_setTitle(title:String, help:String):void
        {
            if (!_configured)
                return;
            _title.text = title != null ? title : "FINAL SHOT · 3D";
            _help.text = help != null ? help : "";
        }

        public function as_setMarkers(markers:Array):void
        {
            if (!_configured)
            {
                _pendingMarkers = markers;
                return;
            }
            _clearMarkers();
            if (!markers)
                return;
            for (var i:int = 0; i < markers.length; i++)
            {
                var data:Object = markers[i];
                var marker:Sprite = _makeMarker(data);
                marker.x = Number(data.x);
                marker.y = Number(data.y);
                _markers.addChild(marker);
            }
        }

        public function as_setVisible(value:Boolean):void
        {
            visible = value;
            if (!value)
                _clearMarkers();
            else
                _positionHeader();
        }
    }
}
