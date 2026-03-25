# main_gui.py  —  RP2350-Touch-LCD-2 (MicroPython)
# --------------------------------------------------
# Replaces: tkinter  →  lcd_st7789 + touch_cst816d
#           (both classes live in RP2350-Touch-LCD-2.py
#            — rename that file to waveshare_lcd.py and
#            upload it to the board alongside this file)
# Replaces: threading  →  uasyncio
#
# Upload checklist (via Thonny):
#   1. Flash Waveshare .uf2 firmware
#   2. Rename RP2350-Touch-LCD-2.py  →  waveshare_lcd.py
#   3. Upload waveshare_lcd.py, heatpad.py, motor.py,
#      auto_controller.py, config.py, main_gui.py
# --------------------------------------------------
import uasyncio as asyncio
import machine
import framebuf
import time
from waveshare_lcd import lcd_st7789, touch_cst816d
from heatpad import HeatPadController
from motor import MotorController
from auto_controller import AutoController

# --------------------------------------------------
# Colour palette (RGB565)
# --------------------------------------------------
BLACK  = 0x0000
WHITE  = 0xFFFF
GREEN  = 0x07E0
BLUE   = 0x001F
RED    = 0xF800
ORANGE = 0xFD20
CYAN   = 0x07FF
GRAY   = 0x7BEF
DGRAY  = 0x2104

# --------------------------------------------------
# Text renderer
# lcd_st7789 has no built-in text method — we use a
# 1-bit framebuffer to rasterise MicroPython's built-in
# 8×8 font, then blit each lit pixel as a draw_point.
# --------------------------------------------------
_CHAR_W = 8
_CHAR_H = 8

def draw_text(lcd, s, x, y, color):
    """Draw string s at (x, y) using the built-in 8×8 font."""
    buf = bytearray((_CHAR_W * len(s) + 7) // 8 * _CHAR_H)
    fb  = framebuf.FrameBuffer(buf, _CHAR_W * len(s), _CHAR_H, framebuf.MONO_HLSB)
    fb.text(s, 0, 0, 1)
    for row in range(_CHAR_H):
        for col in range(_CHAR_W * len(s)):
            byte_idx = (row * ((_CHAR_W * len(s) + 7) // 8)) + (col // 8)
            bit      = 7 - (col % 8)
            if buf[byte_idx] & (1 << bit):
                lcd.draw_point(x + col, y + row, color)

def fill_rect(lcd, x, y, w, h, color):
    """Filled rectangle. draw_square(x, y, s) fills (s+1)×(s+1) pixels."""
    for row in range(h):
        lcd.draw_square(x, y + row, w - 1, color)

def draw_rect(lcd, x, y, w, h, color):
    """Outline rectangle (4 edges as 1-px lines)."""
    for i in range(w):
        lcd.draw_point(x + i, y,         color)
        lcd.draw_point(x + i, y + h - 1, color)
    for i in range(h):
        lcd.draw_point(x,         y + i, color)
        lcd.draw_point(x + w - 1, y + i, color)


# --------------------------------------------------
# Touch-button
# --------------------------------------------------
class Button:
    def __init__(self, x, y, w, h, label, callback):
        self.x = x; self.y = y; self.w = w; self.h = h
        self.label    = label
        self.callback = callback

    def hit(self, tx, ty):
        # Touch X is mirrored on this display (width - x)
        return self.x <= tx <= self.x + self.w and self.y <= ty <= self.y + self.h

    def draw(self, lcd):
        fill_rect(lcd, self.x,     self.y,     self.w,     self.h,     DGRAY)
        draw_rect(lcd, self.x,     self.y,     self.w,     self.h,     GRAY)
        # Centre label
        tx = self.x + (self.w - len(self.label) * _CHAR_W) // 2
        ty = self.y + (self.h - _CHAR_H) // 2
        draw_text(lcd, self.label, tx, ty, WHITE)


# --------------------------------------------------
# Application
# --------------------------------------------------
class App:
    def __init__(self):
        self.lcd    = lcd_st7789()
        self.touch  = touch_cst816d()
        self.heater = HeatPadController()
        self.motor  = MotorController()
        self.auto   = AutoController(self.motor, self.heater)

        self._speed   = 50
        self._heat_on = False
        self._auto_on = False

        # Layout: 240 wide × 320 tall (portrait)
        BTN_W = 100; BTN_H = 36
        COL1 = 10;   COL2 = 130

        self.buttons = [
            Button(COL1,    200, BTN_W, BTN_H, "Forward",   self._fwd),
            Button(COL2,    200, BTN_W, BTN_H, "Reverse",   self._rev),
            Button(COL1,    246, BTN_W, BTN_H, "Stop",      self._stop_motor),
            Button(COL2,    246, BTN_W, BTN_H, "Heat ON",   self._toggle_heat),
            Button(COL1,    292, BTN_W, BTN_H, "AutoStart", self._toggle_auto),
            Button(COL1,    154, 44,    30,    "Spd-",      self._spd_down),
            Button(COL2+56, 154, 44,    30,    "Spd+",      self._spd_up),
        ]
        self._heat_btn = self.buttons[3]
        self._auto_btn = self.buttons[4]

    # ---- Motor ----
    def _fwd(self):        self.motor.forward(self._speed)
    def _rev(self):        self.motor.reverse(self._speed)
    def _stop_motor(self): self.motor.stop()
    def _spd_down(self):   self._speed = max(0,   self._speed - 10)
    def _spd_up(self):     self._speed = min(100, self._speed + 10)

    # ---- Heater ----
    def _toggle_heat(self):
        if self._heat_on:
            self.heater.stop()
            self._heat_on = False
            self._heat_btn.label = "Heat ON"
        else:
            self.heater.start()
            self._heat_on = True
            self._heat_btn.label = "Heat OFF"

    # ---- Auto ----
    def _toggle_auto(self):
        if self._auto_on:
            self.auto.stop()
            self._auto_on = False
            self._auto_btn.label = "AutoStart"
        else:
            self.auto.start()
            self._auto_on = True
            self._auto_btn.label = "AutoStop"

    # ---- Draw ----
    def _draw(self):
        lcd = self.lcd
        lcd.lcd_fill(BLACK)

        draw_text(lcd, "Kimiya Controller", 10, 8, WHITE)

        temp, output, target, heat_running = self.heater.get_status()
        if heat_running:
            col = GREEN if abs(temp - target) <= 3 else (BLUE if temp < target else RED)
            draw_text(lcd, f"Temp: {temp:.1f}C",    10, 40, col)
            draw_text(lcd, f"Duty: {output:.1f}%",  10, 60, WHITE)
            draw_text(lcd, f"Setpt:{target:.0f}C",  10, 80, CYAN)
        else:
            draw_text(lcd, "Temp: -- C",            10, 40, GRAY)
            draw_text(lcd, "Duty: -- %",            10, 60, GRAY)
            draw_text(lcd, f"Setpt:{target:.0f}C",  10, 80, GRAY)

        draw_text(lcd, f"Speed: {self._speed}%",    10, 110, WHITE)
        draw_text(lcd, "< Spd >",                   90, 162, ORANGE)

        for btn in self.buttons:
            btn.draw(lcd)

    # ---- Touch ----
    async def _handle_touch(self):
        coords = self.touch.get_touch_xy()
        if coords is None:
            return
        # Mirror X to match display orientation
        raw_x = coords[0]["x"]
        raw_y = coords[0]["y"]
        tx = 240 - raw_x
        ty = raw_y
        for btn in self.buttons:
            if btn.hit(tx, ty):
                btn.callback()
                await asyncio.sleep_ms(200)   # debounce
                break

    # ---- Main loop ----
    async def run(self):
        while True:
            await self._handle_touch()
            self._draw()
            await asyncio.sleep_ms(300)

    def cleanup(self):
        self.heater.cleanup()
        self.motor.cleanup()


# --------------------------------------------------
# Entry point
# --------------------------------------------------
async def main():
    app = App()
    try:
        await app.run()
    finally:
        app.cleanup()

asyncio.run(main())