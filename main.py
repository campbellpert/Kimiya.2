# main.py  —  RP2350-Touch-LCD-2 (MicroPython)
# Entry point — wires together hardware and UI pages.
import uasyncio as asyncio
import time
from waveshare_lcd import lcd_st7789, touch_cst816d
from heatpad import HeatPadController
from motor import MotorController
from auto_controller import AutoController
from ui.screen import Screen
from ui.page_home   import HomePage
from ui.page_manual import ManualPage
from ui.page_auto   import AutoPage
from ui.page_config import ConfigPage

PAGE_HOME   = 0
PAGE_MANUAL = 1
PAGE_AUTO   = 2
PAGE_CONFIG = 3


class App:
    def __init__(self):
        lcd = lcd_st7789()
        time.sleep_ms(200)
        lcd.lcd_fill(0x0000)
        time.sleep_ms(50)

        self._scr   = Screen(lcd)
        self._touch = touch_cst816d()
        heater = HeatPadController()
        motor  = MotorController()
        auto   = AutoController(motor, heater)

        self._page = PAGE_HOME

        # Instantiate pages, passing navigation callbacks
        self._pages = {
            PAGE_HOME:   HomePage(self._scr,
                                  on_manual=lambda: self._goto(PAGE_MANUAL),
                                  on_auto=  lambda: self._goto(PAGE_AUTO),
                                  on_config=lambda: self._goto(PAGE_CONFIG)),
            PAGE_MANUAL: ManualPage(self._scr, heater, motor,
                                    on_back=lambda: self._goto(PAGE_HOME)),
            PAGE_AUTO:   AutoPage(self._scr, heater, motor, auto,
                                  on_back=lambda: self._goto(PAGE_HOME)),
            PAGE_CONFIG: ConfigPage(self._scr, heater,
                                    on_back=lambda: self._goto(PAGE_HOME)),
        }
        self._heater = heater
        self._motor  = motor

    def _goto(self, page):
        self._page = page

    async def run(self):
        while True:
            coords = self._touch.get_touch_xy()
            if coords is not None:
                tx = coords[0]["x"]
                ty = coords[0]["y"]
                self._pages[self._page].handle_touch(tx, ty)
                await asyncio.sleep_ms(200)

            self._pages[self._page].draw()
            await asyncio.sleep_ms(300)

    def cleanup(self):
        self._heater.cleanup()
        self._motor.cleanup()


async def main():
    app = App()
    try:
        await app.run()
    finally:
        app.cleanup()

asyncio.run(main())
