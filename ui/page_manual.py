# ui/page_manual.py
from ui.screen import Screen, Button, GRAY, WHITE, GREEN, BLUE, RED, CYAN, DGRAY


class ManualPage:
    def __init__(self, scr, heater, motor, on_back):
        self._scr    = scr
        self._heater = heater
        self._motor  = motor
        self._speed  = 50
        self._heat_on = False

        BTN_W = 105; BTN_H = 40
        COL1 = 8;    COL2 = 127

        self._btns = [
            Button(COL1, 120, BTN_W, BTN_H, "Forward",  self._fwd),
            Button(COL2, 120, BTN_W, BTN_H, "Reverse",  self._rev),
            Button(COL1, 172, BTN_W, BTN_H, "Stop",     self._stop),
            Button(COL2, 172, BTN_W, BTN_H, "Heat ON",  self._toggle_heat),
            Button(8,    224, 48,    34,    "Spd-",     self._spd_down),
            Button(184,  224, 48,    34,    "Spd+",     self._spd_up),
        ]
        self._heat_btn = self._btns[3]
        self._back_btn = Button(10, 278, 80, 32, "< Back", on_back)

    def _fwd(self):   self._motor.forward(self._speed)
    def _rev(self):   self._motor.reverse(self._speed)
    def _stop(self):  self._motor.stop()

    def _spd_down(self):
        self._speed = max(0, self._speed - 10)
        self._motor.set_speed(self._speed)

    def _spd_up(self):
        self._speed = min(100, self._speed + 10)
        self._motor.set_speed(self._speed)

    def _toggle_heat(self):
        if self._heat_on:
            self._heater.stop()
            self._heat_on = False
            self._heat_btn.label = "Heat ON"
        else:
            self._heater.start()
            self._heat_on = True
            self._heat_btn.label = "Heat OFF"

    def draw(self):
        scr = self._scr
        scr.fill(0x0000)
        scr.header("Manual")

        temp, output, target, heat_running = self._heater.get_status()
        if heat_running:
            col = GREEN if abs(temp - target) <= 3 else (BLUE if temp < target else RED)
            scr.text(f"Temp:  {temp:.1f} C",   10, 36, col)
            scr.text(f"Duty:  {output:.1f} %", 10, 54, WHITE)
            scr.text(f"Setpt: {target:.0f} C", 10, 72, CYAN)
        else:
            scr.text("Temp:  -- C",            10, 36, GRAY)
            scr.text("Duty:  -- %",            10, 54, GRAY)
            scr.text(f"Setpt: {target:.0f} C", 10, 72, GRAY)

        scr.text(f"Speed: {self._speed} %", 10, 94, WHITE)
        bar_w = int(self._speed * 2)
        scr.rect(10, 108, 220, 10, DGRAY, filled=True)
        if bar_w > 0:
            scr.rect(10, 108, bar_w, 10, CYAN, filled=True)
        scr.rect(10, 108, 220, 10, GRAY, filled=False)

        for btn in self._btns:
            btn.draw(scr)
        self._back_btn.draw(scr)
        scr.flush()

    def handle_touch(self, tx, ty):
        for btn in self._btns:
            if btn.hit(tx, ty):
                btn.callback()
                return True
        if self._back_btn.hit(tx, ty):
            self._back_btn.callback()
            return True
        return False