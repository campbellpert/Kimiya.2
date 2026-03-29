# main.py  —  RP2350-Touch-LCD-2 (MicroPython)
import uasyncio as asyncio
import machine
import framebuf
import time
from waveshare_lcd import lcd_st7789, touch_cst816d
from heatpad import HeatPadController
from motor import MotorController
from auto_controller import AutoController

W = 240
H = 320

# framebuf.RGB565 is little-endian (byte-swapped vs the raw RGB565 values).
# Pass raw RGB565 values directly — framebuf handles the byte order internally.
BLACK  = 0x0000
WHITE  = 0xFFFF
GREEN  = 0x07E0
BLUE   = 0x001F
RED    = 0xF800
ORANGE = 0xFD20
CYAN   = 0x07FF
GRAY   = 0x7BEF
DGRAY  = 0x2104


class Screen:
    def __init__(self, lcd):
        self._lcd = lcd
        # Use GS_LSBFIRST (big-endian RGB565) so bytes go to LCD unchanged
        self._buf = bytearray(W * H * 2)
        self._fb  = framebuf.FrameBuffer(self._buf, W, H, framebuf.RGB565)

    def fill(self, color):
        self._fb.fill(color)

    def text(self, s, x, y, color):
        self._fb.text(s, x, y, color)

    def rect(self, x, y, w, h, color, filled=False):
        if filled:
            self._fb.fill_rect(x, y, w, h, color)
        else:
            self._fb.rect(x, y, w, h, color)

    def flush(self):
        """Byte-swap every pixel then send to LCD."""
        lcd = self._lcd
        # framebuf.RGB565 stores pixels little-endian; LCD needs big-endian.
        # Swap bytes in-place before sending.
        buf = self._buf
        for i in range(0, len(buf), 2):
            buf[i], buf[i+1] = buf[i+1], buf[i]
        lcd.set_windows(0, 0, W - 1, H - 1)
        lcd.dc(1)
        lcd.cs(0)
        lcd.bus.write(buf)
        lcd.cs(1)
        # Swap back so framebuf colours stay correct next frame
        for i in range(0, len(buf), 2):
            buf[i], buf[i+1] = buf[i+1], buf[i]


class Button:
    def __init__(self, x, y, w, h, label, callback):
        self.x = x; self.y = y; self.w = w; self.h = h
        self.label = label
        self.callback = callback

    def hit(self, tx, ty):
        return self.x <= tx <= self.x + self.w and self.y <= ty <= self.y + self.h

    def draw(self, scr):
        scr.rect(self.x, self.y, self.w, self.h, DGRAY, filled=True)
        scr.rect(self.x, self.y, self.w, self.h, GRAY,  filled=False)
        tx = self.x + (self.w - len(self.label) * 8) // 2
        ty = self.y + (self.h - 8) // 2
        scr.text(self.label, tx, ty, WHITE)


class App:
    def __init__(self):
        self._lcd = lcd_st7789()
        time.sleep_ms(200)
        self._lcd.lcd_fill(0x0000)
        time.sleep_ms(50)

        self._scr   = Screen(self._lcd)
        self._touch = touch_cst816d()
        self.heater = HeatPadController()
        self.motor  = MotorController()
        self.auto   = AutoController(self.motor, self.heater)

        self._speed   = 50
        self._heat_on = False
        self._auto_on = False

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

    def _fwd(self):        self.motor.forward(self._speed)
    def _rev(self):        self.motor.reverse(self._speed)
    def _stop_motor(self): self.motor.stop()
    def _spd_down(self):   self._speed = max(0,   self._speed - 10)
    def _spd_up(self):     self._speed = min(100, self._speed + 10)

    def _toggle_heat(self):
        if self._heat_on:
            self.heater.stop()
            self._heat_on = False
            self._heat_btn.label = "Heat ON"
        else:
            self.heater.start()
            self._heat_on = True
            self._heat_btn.label = "Heat OFF"

    def _toggle_auto(self):
        if self._auto_on:
            self.auto.stop()
            self._auto_on = False
            self._auto_btn.label = "AutoStart"
        else:
            self.auto.start()
            self._auto_on = True
            self._auto_btn.label = "AutoStop"

    def _draw(self):
        scr = self._scr
        scr.fill(BLACK)
        scr.text("Kimiya Controller", 10, 8, WHITE)

        temp, output, target, heat_running = self.heater.get_status()
        if heat_running:
            col = GREEN if abs(temp - target) <= 3 else (BLUE if temp < target else RED)
            scr.text(f"Temp:  {temp:.1f} C",   10, 40, col)
            scr.text(f"Duty:  {output:.1f} %", 10, 60, WHITE)
            scr.text(f"Setpt: {target:.0f} C", 10, 80, CYAN)
        else:
            scr.text("Temp:  -- C",            10, 40, GRAY)
            scr.text("Duty:  -- %",            10, 60, GRAY)
            scr.text(f"Setpt: {target:.0f} C", 10, 80, GRAY)

        scr.text(f"Speed: {self._speed} %", 10, 110, WHITE)
        bar_w = int(self._speed * 2)
        scr.rect(10, 128, 200, 12, DGRAY, filled=True)
        if bar_w > 0:
            scr.rect(10, 128, bar_w, 12, CYAN, filled=True)
        scr.rect(10, 128, 200, 12, GRAY, filled=False)
        scr.text("- Spd +", 72, 152, ORANGE)

        for btn in self.buttons:
            btn.draw(scr)

        scr.flush()

    async def _handle_touch(self):
        coords = self._touch.get_touch_xy()
        if coords is None:
            return
        tx = W - coords[0]["x"]
        ty = coords[0]["y"]
        for btn in self.buttons:
            if btn.hit(tx, ty):
                btn.callback()
                await asyncio.sleep_ms(200)
                break

    async def run(self):
        while True:
            await self._handle_touch()
            self._draw()
            await asyncio.sleep_ms(300)

    def cleanup(self):
        self.heater.cleanup()
        self.motor.cleanup()


async def main():
    app = App()
    try:
        await app.run()
    finally:
        app.cleanup()

asyncio.run(main())