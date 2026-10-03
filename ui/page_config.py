# ui/page_config.py
import config
from ui.screen import Screen, Button, GRAY, WHITE, CYAN, DGRAY, DGREEN, RED

SWIPE_THRESHOLD = 40
ITEMS_PER_PAGE  = 4


class ConfigPage:
    def __init__(self, scr, heater, on_back):
        self._scr    = scr
        self._heater = heater
        self._scroll = 0
        self._touch_down_ty = None
        self._row_btns = []

        self._items = [
            {"label": "Target Temp",  "key": "TARGET_TEMP",     "step": 1,   "min": 0,  "max": 150},
            {"label": "Pump Speed",   "key": "AUTO_PUMP_SPEED", "step": 5,   "min": 0,  "max": 100},
            {"label": "Pump Time",    "key": "AUTO_PUMP_TIME",  "step": 1,   "min": 1,  "max": 60},
            {"label": "Phase Delay",  "key": "AUTO_PHASE_DELAY","step": 1,   "min": 0,  "max": 60},
            {"label": "PID Kp",       "key": "PID_KP",          "step": 0.5, "min": 0,  "max": 100},
            {"label": "PID Ki",       "key": "PID_KI",          "step": 0.1, "min": 0,  "max": 20},
            {"label": "PID Kd",       "key": "PID_KD",          "step": 0.5, "min": 0,  "max": 100},
        ]
        self._back_btn = Button(10, 282, 80, 30, "< Back", on_back)

    def _adjust(self, idx, direction):
        item = self._items[idx]
        val  = getattr(config, item["key"])
        val  = round(val + direction * item["step"], 4)
        val  = max(item["min"], min(item["max"], val))
        setattr(config, item["key"], val)
        if item["key"] == "TARGET_TEMP":
            self._heater.set_target(val)

    def draw(self):
        scr = self._scr
        scr.fill(0x0000)
        scr.header("Config")
        self._row_btns = []

        total   = len(self._items)
        visible = self._items[self._scroll:self._scroll + ITEMS_PER_PAGE]

        for i, item in enumerate(visible):
            real_idx = self._scroll + i
            y   = 36 + i * 58
            val = getattr(config, item["key"])
            vstr = f"{val:.1f}" if isinstance(val, float) else str(val)

            # Row width 210 to leave 6px gap + 4px scrollbar on right
            scr.rect(10, y, 210, 50, DGRAY, filled=True)
            scr.rect(10, y, 210, 50, GRAY,  filled=False)
            scr.text(item["label"], 16, y + 6,  CYAN)
            scr.text(vstr,          16, y + 24, WHITE)

            minus = Button(150, y + 10, 28, 28, "-",
                           lambda idx=real_idx: self._adjust(idx, -1), RED)
            plus  = Button(184, y + 10, 28, 28, "+",
                           lambda idx=real_idx: self._adjust(idx, +1), DGREEN)
            minus.draw(scr)
            plus.draw(scr)
            self._row_btns.append((minus, plus))

        # Scrollbar — track on far right (4px wide, from y=36 to y=268)
        track_x = 234
        track_y = 36
        track_h = 232   # covers the 4 visible rows
        scr.rect(track_x, track_y, 4, track_h, DGRAY, filled=True)

        # Thumb — proportional height and position
        thumb_h = max(20, track_h * ITEMS_PER_PAGE // total)
        max_scroll = total - ITEMS_PER_PAGE
        thumb_y = track_y + (self._scroll * (track_h - thumb_h) // max_scroll
                             if max_scroll > 0 else 0)
        scr.rect(track_x, thumb_y, 4, thumb_h, GRAY, filled=True)

        self._back_btn.draw(scr)
        scr.flush()

    def handle_touch(self, tx, ty):
        """Returns True if touch was consumed. Call with successive touches."""
        # First touch — record Y for swipe detection
        if self._touch_down_ty is None:
            self._touch_down_ty = ty
            return True

        # Second touch — check for swipe
        delta = self._touch_down_ty - ty
        self._touch_down_ty = None

        if delta > SWIPE_THRESHOLD:
            self._scroll = min(len(self._items) - ITEMS_PER_PAGE, self._scroll + 1)
            return True
        elif delta < -SWIPE_THRESHOLD:
            self._scroll = max(0, self._scroll - 1)
            return True

        # Not a swipe — treat as tap
        if self._back_btn.hit(tx, ty):
            self._back_btn.callback()
            return True
        for minus, plus in self._row_btns:
            if minus.hit(tx, ty):
                minus.callback(); return True
            if plus.hit(tx, ty):
                plus.callback();  return True
        return False