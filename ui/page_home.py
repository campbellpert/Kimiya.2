# ui/page_home.py
from ui.screen import Screen, MenuItem, WHITE

BLUE_DARK   = 0x0014   # darkest blue
BLUE_MID    = 0x0198   # mid blue
BLUE_LIGHT  = 0x039D   # lighter blue


class HomePage:
    def __init__(self, scr, on_manual, on_auto, on_config):
        self._scr   = scr
        self._items = [
            MenuItem(90,  "Manual Mode", on_manual, BLUE_DARK),
            MenuItem(150, "Auto Mode",   on_auto,   BLUE_MID),
            MenuItem(210, "Config",      on_config, BLUE_LIGHT),
        ]

    def draw(self):
        scr = self._scr
        scr.fill(0x0000)
        scr.rect(0, 0, 240, 28, 0x000F, filled=True)
        scr.text("Kimiya Controller", 8, 10, 0x07FF)
        scr.text("Select mode:", 10, 60, WHITE)
        for item in self._items:
            item.draw(scr)
        scr.flush()

    def handle_touch(self, tx, ty):
        for item in self._items:
            if item.hit(tx, ty):
                item.callback()
                return True
        return False