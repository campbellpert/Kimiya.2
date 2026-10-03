# ui/page_auto.py
import config
from ui.screen import Screen, Button, GRAY, WHITE, GREEN, BLUE, RED, CYAN, DGREEN


class AutoPage:
    def __init__(self, scr, heater, motor, auto, on_back):
        self._scr    = scr
        self._heater = heater
        self._auto   = auto
        self._running = False

        self._auto_btn = Button(10, 200, 220, 44, "AutoStart",
                                self._toggle_auto, DGREEN)
        self._back_btn = Button(10, 282, 80, 30, "< Back", on_back)

    def _toggle_auto(self):
        if self._running:
            self._auto.stop()
            self._running = False
            self._auto_btn.label = "AutoStart"
            self._auto_btn.bg    = DGREEN
        else:
            self._auto.start()
            self._running = True
            self._auto_btn.label = "AutoStop"
            self._auto_btn.bg    = RED

    def draw(self):
        scr = self._scr
        scr.fill(0x0000)
        scr.header("Auto Mode")

        temp, _, target, heat_running = self._heater.get_status()

        scr.text("Chamber Sequence:", 10, 36, WHITE)
        y = 52
        for i, ch in enumerate(config.CHAMBER_SEQUENCE):
            tstr = f"{ch['target_temp']}C" if ch['target_temp'] is not None else "No heat"
            scr.text(f"{i+1}. {ch['name']} - {tstr}", 14, y, CYAN)
            y += 16

        scr.text("Current temp:", 10, y + 8, GRAY)
        if heat_running:
            col = GREEN if abs(temp - config.TARGET_TEMP) <= 3 else (BLUE if temp < config.TARGET_TEMP else RED)
            scr.text(f"{temp:.1f} C", 130, y + 8, col)
        else:
            scr.text("-- C", 130, y + 8, GRAY)

        status = "Running..." if self._running else "Stopped"
        scr.text(f"Status: {status}", 10, y + 28,
                 GREEN if self._running else GRAY)

        self._auto_btn.draw(scr)
        self._back_btn.draw(scr)
        scr.flush()

    def handle_touch(self, tx, ty):
        if self._auto_btn.hit(tx, ty):
            self._toggle_auto()
            return True
        if self._back_btn.hit(tx, ty):
            self._back_btn.callback()
            return True
        return False