# ui/screen.py — shared Screen, Button, MenuItem classes
import framebuf

W = 240
H = 320

# Colours (raw RGB565)
BLACK  = 0x0000
WHITE  = 0xFFFF
GREEN  = 0x07E0
BLUE   = 0x001F
RED    = 0xF800
ORANGE = 0xFD20
CYAN   = 0x07FF
GRAY   = 0x7BEF
DGRAY  = 0x2104
DGREEN = 0x0320
NAVY   = 0x000F
PURPLE = 0x780F


class Screen:
    """Full 240x320 RGB565 framebuffer — compose then flush in one SPI burst."""
    def __init__(self, lcd):
        self._lcd = lcd
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

    def header(self, title):
        """Standard page header bar."""
        self.rect(0, 0, W, 28, NAVY, filled=True)
        self.text("Kimiya", 8, 10, CYAN)
        tx = W - len(title) * 8 - 8
        self.text(title, tx, 10, WHITE)

    def flush(self):
        b = self._buf
        for i in range(0, len(b), 2):
            b[i], b[i+1] = b[i+1], b[i]
        lcd = self._lcd
        lcd.set_windows(0, 0, W - 1, H - 1)
        lcd.dc(1); lcd.cs(0)
        lcd.bus.write(b)
        lcd.cs(1)
        for i in range(0, len(b), 2):
            b[i], b[i+1] = b[i+1], b[i]


class Button:
    def __init__(self, x, y, w, h, label, callback, bg=None, fg=WHITE):
        self.x = x; self.y = y; self.w = w; self.h = h
        self.label    = label
        self.callback = callback
        self.bg       = bg if bg is not None else DGRAY
        self.fg       = fg

    def hit(self, tx, ty):
        return self.x <= tx <= self.x + self.w and self.y <= ty <= self.y + self.h

    def draw(self, scr):
        scr.rect(self.x, self.y, self.w, self.h, self.bg,  filled=True)
        scr.rect(self.x, self.y, self.w, self.h, GRAY,     filled=False)
        tx = self.x + (self.w - len(self.label) * 8) // 2
        ty = self.y + (self.h - 8) // 2
        scr.text(self.label, tx, ty, self.fg)


class MenuItem:
    """Full-width tappable menu row with right arrow."""
    def __init__(self, y, label, callback, bg=DGRAY):
        self.x = 10; self.y = y; self.w = 220; self.h = 44
        self.label    = label
        self.callback = callback
        self.bg       = bg

    def hit(self, tx, ty):
        return self.x <= tx <= self.x + self.w and self.y <= ty <= self.y + self.h

    def draw(self, scr):
        scr.rect(self.x, self.y, self.w, self.h, self.bg,  filled=True)
        scr.rect(self.x, self.y, self.w, self.h, GRAY,     filled=False)
        scr.text(self.label, self.x + 12, self.y + 18, WHITE)
        scr.text(">", self.x + self.w - 16, self.y + 18, GRAY)