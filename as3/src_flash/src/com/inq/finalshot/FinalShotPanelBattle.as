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

    public class FinalShotPanelBattle extends AbstractView
    {
        public var py_onPanelReady:Function = null;
        public var py_onDragEnd:Function = null;

        private static const WIDTH:int = 520;
        private static const HEADER_HEIGHT:int = 70;
        private static const ROW_HEIGHT:int = 38;
        private static const PADDING:int = 14;

        private var _root:Sprite;
        private var _background:Shape;
        private var _rows:Sprite;
        private var _title:TextField;
        private var _subtitle:TextField;
        private var _dragArea:Sprite;
        private var _position:Array = [-1, 145];
        private var _scaleValue:Number = 1.0;
        private var _configured:Boolean = false;
        private var _frameCount:int = 0;
        private var _pendingData:Object = null;

        public function FinalShotPanelBattle()
        {
            super();
        }

        override protected function configUI():void
        {
            super.configUI();
            _build();
            _configured = true;
            visible = false;
            updatePosition();
            if (App.instance && App.instance.stage)
                App.instance.stage.addEventListener(Event.RESIZE, _onResize);
            addEventListener(Event.ENTER_FRAME, _onReadyFrame);
            if (_pendingData != null)
            {
                var data:Object = _pendingData;
                _pendingData = null;
                as_setData(data.title, data.subtitle, data.fatalLabel, data.rows);
            }
        }

        override protected function onDispose():void
        {
            removeEventListener(Event.ENTER_FRAME, _onReadyFrame);
            if (App.instance && App.instance.stage)
            {
                App.instance.stage.removeEventListener(Event.RESIZE, _onResize);
                App.instance.stage.removeEventListener(MouseEvent.MOUSE_UP, _onDragStop);
            }
            if (_dragArea)
                _dragArea.removeEventListener(MouseEvent.MOUSE_DOWN, _onDragStart);
            py_onPanelReady = null;
            py_onDragEnd = null;
            _pendingData = null;
            super.onDispose();
        }

        private function _build():void
        {
            _root = new Sprite();
            _root.filters = [new DropShadowFilter(4, 90, 0x000000, 0.72, 10, 10, 1.1, 2)];
            addChild(_root);

            _background = new Shape();
            _root.addChild(_background);

            _dragArea = new Sprite();
            _dragArea.buttonMode = true;
            _dragArea.useHandCursor = true;
            _dragArea.addEventListener(MouseEvent.MOUSE_DOWN, _onDragStart);
            _root.addChild(_dragArea);

            _title = _makeText(22, 0xF2F4F7, true);
            _title.x = PADDING;
            _title.y = 10;
            _root.addChild(_title);

            _subtitle = _makeText(14, 0x98A6B3, false);
            _subtitle.x = PADDING;
            _subtitle.y = 39;
            _root.addChild(_subtitle);

            _rows = new Sprite();
            _rows.y = HEADER_HEIGHT;
            _root.addChild(_rows);

            _drawBackground(HEADER_HEIGHT + PADDING);
        }

        private function _makeText(size:int, color:uint, bold:Boolean):TextField
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

        private function _drawBackground(height:Number):void
        {
            _background.graphics.clear();
            _background.graphics.lineStyle(1, 0x596675, 0.9);
            _background.graphics.beginFill(0x0E151E, 0.94);
            _background.graphics.drawRoundRect(0, 0, WIDTH, height, 10, 10);
            _background.graphics.endFill();

            _dragArea.graphics.clear();
            _dragArea.graphics.beginFill(0x000000, 0.001);
            _dragArea.graphics.drawRoundRect(0, 0, WIDTH, HEADER_HEIGHT, 10, 10);
            _dragArea.graphics.endFill();
        }

        private function _clearRows():void
        {
            while (_rows.numChildren > 0)
                _rows.removeChildAt(0);
        }

        private function _drawRows(rows:Array, fatalLabel:String):void
        {
            _clearRows();
            var count:int = rows ? rows.length : 0;
            for (var i:int = 0; i < count; i++)
            {
                var data:Object = rows[i];
                var row:Sprite = new Sprite();
                var fatal:Boolean = Boolean(data.fatal);
                row.graphics.beginFill(fatal ? 0x4A1518 : (i % 2 == 0 ? 0x17212D : 0x121B25), fatal ? 0.94 : 0.78);
                row.graphics.drawRect(0, 0, WIDTH, ROW_HEIGHT - 2);
                row.graphics.endFill();
                if (fatal)
                {
                    row.graphics.beginFill(0xE15757, 1.0);
                    row.graphics.drawRect(0, 0, 4, ROW_HEIGHT - 2);
                    row.graphics.endFill();
                }

                var number:TextField = _makeText(16, fatal ? 0xFF9A9A : 0x7F8D9C, true);
                number.text = String(i + 1) + ".";
                number.x = 12;
                number.y = 7;
                row.addChild(number);

                var vehicle:TextField = _makeText(16, fatal ? 0xFFFFFF : 0xE3E8EE, true);
                var vehicleText:String = String(data.vehicle != null ? data.vehicle : "?");
                var playerText:String = String(data.player != null ? data.player : "");
                vehicle.text = playerText.length > 0 ? vehicleText + "  ·  " + playerText : vehicleText;
                vehicle.x = 43;
                vehicle.y = 5;
                vehicle.width = 288;
                vehicle.height = 27;
                vehicle.autoSize = TextFieldAutoSize.NONE;
                row.addChild(vehicle);

                var shell:TextField = _makeText(14, Boolean(data.isGold) ? 0xF1C96A : 0xA9B6C4, false);
                shell.text = String(data.shell != null ? data.shell : "?");
                shell.x = 341;
                shell.y = 7;
                shell.width = 70;
                shell.height = 24;
                shell.autoSize = TextFieldAutoSize.NONE;
                row.addChild(shell);

                var damage:TextField = _makeText(18, fatal ? 0xFF8B8B : 0xFFFFFF, true);
                damage.text = String(int(data.damage != null ? data.damage : 0));
                damage.x = 420;
                damage.y = 5;
                damage.width = 84;
                damage.height = 27;
                damage.autoSize = TextFieldAutoSize.NONE;
                damage.defaultTextFormat = new TextFormat("$TitleFont", 18, fatal ? 0xFF8B8B : 0xFFFFFF, true, null, null, null, null, "right");
                damage.setTextFormat(damage.defaultTextFormat);
                row.addChild(damage);

                if (fatal)
                {
                    var badge:TextField = _makeText(10, 0xFFB0B0, true);
                    badge.text = fatalLabel;
                    badge.x = 342;
                    badge.y = 24;
                    row.addChild(badge);
                }

                row.y = i * ROW_HEIGHT;
                _rows.addChild(row);
            }
            _drawBackground(HEADER_HEIGHT + count * ROW_HEIGHT + PADDING);
        }

        private function _onReadyFrame(event:Event):void
        {
            _frameCount++;
            if (_frameCount < 5)
                return;
            removeEventListener(Event.ENTER_FRAME, _onReadyFrame);
            if (py_onPanelReady != null)
                py_onPanelReady();
        }

        private function _onResize(event:Event):void
        {
            updatePosition();
        }

        private function _onDragStart(event:MouseEvent):void
        {
            if (!App.instance || !App.instance.stage)
                return;
            _root.startDrag();
            App.instance.stage.addEventListener(MouseEvent.MOUSE_UP, _onDragStop);
        }

        private function _onDragStop(event:MouseEvent):void
        {
            if (!App.instance || !App.instance.stage)
                return;
            App.instance.stage.removeEventListener(MouseEvent.MOUSE_UP, _onDragStop);
            _root.stopDrag();
            _clampPosition();
            _position = [int(_root.x), int(_root.y)];
            if (py_onDragEnd != null)
                py_onDragEnd(_position.concat());
        }

        private function _clampPosition():void
        {
            if (!App.instance || !App.instance.stage)
                return;
            var stageW:Number = App.instance.stage.stageWidth;
            var stageH:Number = App.instance.stage.stageHeight;
            var panelW:Number = WIDTH * _scaleValue;
            var panelH:Number = Math.max(HEADER_HEIGHT, _background.height) * _scaleValue;
            _root.x = Math.max(0, Math.min(_root.x, stageW - panelW));
            _root.y = Math.max(0, Math.min(_root.y, stageH - panelH));
        }

        public function updatePosition():void
        {
            if (!_root || !App.instance || !App.instance.stage)
                return;
            _root.scaleX = _root.scaleY = _scaleValue;
            var xValue:int = int(_position[0]);
            var yValue:int = int(_position[1]);
            if (xValue < 0)
                xValue = int((App.instance.stage.stageWidth - WIDTH * _scaleValue) / 2);
            _root.x = xValue;
            _root.y = yValue;
            _clampPosition();
        }

        public function as_setPosition(position:Array):void
        {
            if (position && position.length >= 2)
                _position = [int(position[0]), int(position[1])];
            updatePosition();
        }

        public function as_setScale(value:Number):void
        {
            _scaleValue = Math.max(0.65, Math.min(1.75, value));
            updatePosition();
        }

        public function as_setData(title:String, subtitle:String, fatalLabel:String, rows:Array):void
        {
            if (!_configured)
            {
                _pendingData = {title: title, subtitle: subtitle, fatalLabel: fatalLabel, rows: rows};
                return;
            }
            _title.text = (title != null && title.length > 0) ? title : "FINAL SHOT";
            _subtitle.text = subtitle != null ? subtitle : "";
            _drawRows(rows, (fatalLabel != null && fatalLabel.length > 0) ? fatalLabel : "DESTROYED");
            updatePosition();
        }

        public function as_setVisible(value:Boolean):void
        {
            visible = value;
            if (value)
                updatePosition();
        }
    }
}
