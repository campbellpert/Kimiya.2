# peltier_control.py  —  RP2350-Touch-LCD-2 (MicroPython)
# --------------------------------------------------
# Controls a Peltier tile via HW039 (BTS7960 H-bridge)
# Temperature measured by MAX31865 / PT100
# PID loop drives heating (RPWM) or cooling (LPWM)
# Target: 60 degrees C
# --------------------------------------------------
import uasyncio as asyncio
import machine
import framebuf
import time
from machine import SPI, Pin, PWM
from waveshare_lcd import lcd_st7789, touch_cst816d

# --------------------------------------------------
# Pin assignments
# --------------------------------------------------
# MAX31865 on SPI1
SPI_SCK  = 10
SPI_MOSI = 11
SPI_MISO = 8
SPI_CS   = 9

# HW039 (BTS7960) control pins
R_EN  = 29   # Enable right (heating) — header pin 4
L_EN  = 28   # Enable left  (cooling) — header pin 3
RPWM  = 22   # PWM heating            — header pin 25
LPWM  = 23   # PWM cooling            — header pin 22

# Fan
FAN   = 7    # MOSFET gate — header pin 28

# --------------------------------------------------
# Control settings
# --------------------------------------------------
SETPOINT        = 60.0   # Target temperature (C)
TOLERANCE       = 0.5    # Dead-band — no output within +/- this of setpoint
PWM_FREQ        = 1000   # Hz
CONTROL_PERIOD  = 0.05   # seconds — 20Hz PID sampling
DISPLAY_PERIOD  = 0.3    # seconds — ~3Hz display refresh
MAX_SAFE_TEMP   = 90.0   # Safety cutoff (C)
MIN_SAFE_TEMP   = -10.0  # Safety cutoff (C)

# Calibration
CAL_M = 1.4693
CAL_B = -9.62235

# PT100 / MAX31865
RTD_NOMINAL  = 100
REF_RESISTOR = 430
RTD_WIRES    = 3

# PID tuning — reduced Ki to prevent integral windup overshoot,
# increased Kd to brake harder as temp approaches setpoint
PID_KP = 12.0
PID_KI = 0.5
PID_KD = 50.0

# Two-stage cycle
STAGE_HEAT_TARGET  = 60.0   # degrees C
STAGE_COOL_TARGET  = 50.0   # degrees C
STAGE_HEAT_HOLD    = 60     # seconds
STAGE_COOL_HOLD    = 60     # seconds

# Display
W = 240
H = 320


# --------------------------------------------------
# MAX31865 driver
# --------------------------------------------------
class MAX31865:
    _REG_CONFIG  = 0x00
    _REG_RTD_MSB = 0x01
    _REG_FAULT   = 0x07
    _CFG_3WIRE   = 0xC2
    _CFG_2_4WIRE = 0xC0

    def __init__(self, spi, cs, wires=3, ref_resistor=430, rtd_nominal=100):
        self._spi = spi
        self._cs  = cs
        self._cs.value(1)
        self._ref = ref_resistor
        self._nom = rtd_nominal
        cfg = self._CFG_3WIRE if wires == 3 else self._CFG_2_4WIRE
        self._write_reg(self._REG_CONFIG, cfg)
        time.sleep_ms(100)

    def _write_reg(self, reg, value):
        self._cs.value(0)
        self._spi.write(bytes([reg | 0x80, value]))
        self._cs.value(1)

    def _read_reg(self, reg, length=1):
        self._cs.value(0)
        self._spi.write(bytes([reg & 0x7F]))
        result = self._spi.read(length)
        self._cs.value(1)
        return result

    @property
    def resistance(self):
        raw = self._read_reg(self._REG_RTD_MSB, 2)
        rtd = (raw[0] << 8 | raw[1]) >> 1
        return rtd * self._ref / 32768.0

    @property
    def temperature(self):
        r  = self.resistance
        A  =  3.9083e-3
        B  = -5.775e-7
        R0 = self._nom
        discriminant = A * A - 4 * B * (1.0 - r / R0)
        if discriminant < 0:
            return -999.0
        return (-A + discriminant ** 0.5) / (2 * B)

    @property
    def fault(self):
        return self._read_reg(self._REG_FAULT)[0]


# --------------------------------------------------
# PID controller
# --------------------------------------------------
class PID:
    def __init__(self, kp, ki, kd, setpoint, sample_time=0.2):
        self.kp = kp; self.ki = ki; self.kd = kd
        self.setpoint    = setpoint
        self.sample_time = sample_time
        self._integral   = 0.0
        self._last_error = 0.0
        self._last_time  = time.ticks_ms()

    def __call__(self, measured):
        now = time.ticks_ms()
        dt  = max(time.ticks_diff(now, self._last_time) / 1000.0, self.sample_time)
        error      = self.setpoint - measured
        derivative = (error - self._last_error) / dt
        self._integral  += error * dt
        # Clamp integral to prevent windup
        self._integral   = max(-100, min(100, self._integral))
        output = self.kp * error + self.ki * self._integral + self.kd * derivative
        # Clamp output to -100..+100
        output = max(-100, min(100, output))
        self._last_error = error
        self._last_time  = now
        return output

    def reset(self):
        self._integral   = 0.0
        self._last_error = 0.0
        self._last_time  = time.ticks_ms()


# --------------------------------------------------
# Screen (framebuffer)
# --------------------------------------------------
class Screen:
    def __init__(self, lcd):
        self._lcd = lcd
        self._buf = bytearray(W * H * 2)
        self._fb  = framebuf.FrameBuffer(self._buf, W, H, framebuf.RGB565)

    def fill(self, c):           self._fb.fill(c)
    def text(self, s, x, y, c): self._fb.text(s, x, y, c)
    def rect(self, x, y, w, h, c, filled=False):
        if filled: self._fb.fill_rect(x, y, w, h, c)
        else:      self._fb.rect(x, y, w, h, c)

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


# --------------------------------------------------
# Button
# --------------------------------------------------
class Button:
    def __init__(self, x, y, w, h, label, callback, bg=0x2104, fg=0xFFFF):
        self.x=x; self.y=y; self.w=w; self.h=h
        self.label=label; self.callback=callback
        self.bg=bg; self.fg=fg

    def hit(self, tx, ty):
        return self.x <= tx <= self.x+self.w and self.y <= ty <= self.y+self.h

    def draw(self, scr):
        scr.rect(self.x, self.y, self.w, self.h, self.bg, filled=True)
        scr.rect(self.x, self.y, self.w, self.h, 0x7BEF, filled=False)
        tx = self.x + (self.w - len(self.label)*8)//2
        ty = self.y + (self.h - 8)//2
        scr.text(self.label, tx, ty, self.fg)


# --------------------------------------------------
# Peltier controller app
# --------------------------------------------------
class PeltierApp:
    def __init__(self):
        # LCD
        lcd = lcd_st7789()
        time.sleep_ms(200)
        lcd.lcd_fill(0x0000)
        time.sleep_ms(50)
        self._scr   = Screen(lcd)
        self._touch = touch_cst816d()

        # MAX31865
        spi = SPI(1, baudrate=500_000, polarity=0, phase=1,
                  sck=Pin(SPI_SCK), mosi=Pin(SPI_MOSI), miso=Pin(SPI_MISO))
        cs  = Pin(SPI_CS, Pin.OUT, value=1)
        self._sensor = MAX31865(spi, cs,
                                wires=RTD_WIRES,
                                ref_resistor=REF_RESISTOR,
                                rtd_nominal=RTD_NOMINAL)

        # HW039 enable pins — keep enabled always
        self._r_en = Pin(R_EN, Pin.OUT, value=1)
        self._l_en = Pin(L_EN, Pin.OUT, value=1)

        # Fan — on continuously to prevent heatsink saturation
        self._fan = Pin(FAN, Pin.OUT, value=1)

        # PWM outputs
        self._rpwm = PWM(Pin(RPWM), freq=PWM_FREQ)  # heating
        self._lpwm = PWM(Pin(LPWM), freq=PWM_FREQ)  # cooling
        self._rpwm.duty_u16(0)
        self._lpwm.duty_u16(0)

        # PID
        self._pid      = PID(PID_KP, PID_KI, PID_KD, SETPOINT, CONTROL_PERIOD)
        self._setpoint = SETPOINT
        self._running  = False
        self._temp     = 0.0
        self._output   = 0.0
        self._fault    = False

        # Cycle state
        self._stage      = 0
        self._hold_start = 0
        self._hold_left  = 0
        self._hold_total = STAGE_HEAT_HOLD
        self._read_errors = 0        # consecutive sensor read failures
        self._max_errors  = 5        # fault only after this many in a row
        self._transitioning = False  # True during Peltier direction change
        self._transition_start = 0

        # UI state — two pages: main and tune
        self._page = 0   # 0 = main, 1 = tune

        # Main page buttons
        self._start_btn = Button(10,  218, 105, 38, "Start",    self._start,         0x0320)
        self._stop_btn  = Button(125, 218, 105, 38, "Stop",     self._stop,          0x8000)
        self._goto_heat = Button(10,  262, 105, 34, ">> Heat",  self._override_heat, 0x4200)
        self._goto_cool = Button(125, 262, 105, 34, ">> Cool",  self._override_cool, 0x000F)
        self._tune_btn  = Button(10,  302, 220, 30, "Tune PID", lambda: setattr(self, '_page', 1), 0x2104)

        # Tune page — Kp, Ki, Kd each with + and - buttons
        self._tune_params = [
            {"label": "Kp", "attr": "_kp", "step": 0.5,  "min": 0, "max": 50},
            {"label": "Ki", "attr": "_ki", "step": 0.05, "min": 0, "max": 5},
            {"label": "Kd", "attr": "_kd", "step": 1.0,  "min": 0, "max": 100},
        ]
        self._kp = PID_KP
        self._ki = PID_KI
        self._kd = PID_KD
        self._back_btn  = Button(10,  290, 80, 30, "< Back", lambda: setattr(self, '_page', 0))

    # ---- Control ----
    def _start(self):
        self._stage         = 0
        self._setpoint      = STAGE_HEAT_TARGET
        self._pid.setpoint  = self._setpoint
        self._pid.reset()
        self._read_errors   = 0
        self._transitioning = False
        self._running       = True

    def _stop(self):
        self._running       = False
        self._transitioning = False
        self._rpwm.duty_u16(0)
        self._lpwm.duty_u16(0)
        self._output = 0.0
        # Fan stays on to keep heatsink cool even when stopped

    def _override_heat(self):
        """Jump directly to heat stage regardless of current stage."""
        if not self._running:
            self._start()
        self._stage         = 0
        self._setpoint      = STAGE_HEAT_TARGET
        self._pid.setpoint  = self._setpoint
        self._pid.reset()
        self._transitioning = False

    def _override_cool(self):
        """Jump directly to cool stage regardless of current stage."""
        if not self._running:
            self._start()
        self._rpwm.duty_u16(0)
        self._lpwm.duty_u16(0)
        self._transitioning    = True
        self._transition_start = time.ticks_ms()
        self._stage         = 2
        self._setpoint      = STAGE_COOL_TARGET
        self._pid.setpoint  = self._setpoint
        self._pid.reset()

    def _sp_up(self):
        self._setpoint = min(85.0, self._setpoint + 1)
        self._pid.setpoint = self._setpoint

    def _sp_dn(self):
        self._setpoint = max(0.0, self._setpoint - 1)
        self._pid.setpoint = self._setpoint

    def _duty(self, pct):
        return int(abs(pct) * 655.35)

    # ---- Sensor read + PID + stage management ----
    def _update(self):
        # --- Sensor read ---
        try:
            raw = self._sensor.temperature
            temp = raw * CAL_M + CAL_B
            self._temp = temp
            self._read_errors = 0   # reset on successful read
        except Exception as e:
            self._read_errors += 1
            print(f"Sensor read error ({self._read_errors}): {e}")
            if self._read_errors >= self._max_errors:
                print("Too many sensor errors — shutting down")
                self._fault = True
                self._stop()
            return   # skip this cycle, try again next tick

        if self._temp > MAX_SAFE_TEMP or self._temp < MIN_SAFE_TEMP:
            print(f"Safety cutoff at {self._temp:.1f} C")
            self._fault = True
            self._stop()
            return

        if not self._running:
            return

        now = time.ticks_ms()

        # --- Transition ramp: hold output at zero briefly when reversing ---
        # This prevents the sudden current spike that corrupts SPI on reversal
        if self._transitioning:
            self._rpwm.duty_u16(0)
            self._lpwm.duty_u16(0)
            if time.ticks_diff(now, self._transition_start) > 1000:  # 1 second ramp
                self._transitioning = False
            return

        # --- Stage machine ---
        if self._stage == 0:
            # Heating to 60 C
            if abs(self._temp - STAGE_HEAT_TARGET) <= TOLERANCE:
                self._stage      = 1
                self._hold_start = now
                self._hold_total = STAGE_HEAT_HOLD

        elif self._stage == 1:
            # Holding at 60 C
            elapsed = time.ticks_diff(now, self._hold_start) / 1000
            self._hold_left = max(0, self._hold_total - elapsed)
            if elapsed >= self._hold_total:
                self._rpwm.duty_u16(0)
                self._lpwm.duty_u16(0)
                self._transitioning    = True
                self._transition_start = now
                self._stage    = 2
                self._setpoint = STAGE_COOL_TARGET
                self._pid.setpoint = self._setpoint
                self._pid.reset()

        elif self._stage == 2:
            # Cooling to 50 C
            if abs(self._temp - STAGE_COOL_TARGET) <= TOLERANCE:
                self._stage      = 3
                self._hold_start = now
                self._hold_total = STAGE_COOL_HOLD

        elif self._stage == 3:
            # Holding at 50 C
            elapsed = time.ticks_diff(now, self._hold_start) / 1000
            self._hold_left = max(0, self._hold_total - elapsed)
            if elapsed >= self._hold_total:
                self._rpwm.duty_u16(0)
                self._lpwm.duty_u16(0)
                self._transitioning    = True
                self._transition_start = now
                self._stage    = 0
                self._setpoint = STAGE_HEAT_TARGET
                self._pid.setpoint = self._setpoint
                self._pid.reset()

        # --- PID output ---
        output = self._pid(self._temp)
        self._output = output

        if abs(self._temp - self._setpoint) < TOLERANCE:
            self._rpwm.duty_u16(0)
            self._lpwm.duty_u16(0)
        elif output > 0:
            self._rpwm.duty_u16(self._duty(output))
            self._lpwm.duty_u16(0)
        else:
            self._rpwm.duty_u16(0)
            self._lpwm.duty_u16(self._duty(output))

    def _apply_pid(self):
        """Push current Kp/Ki/Kd values into the running PID."""
        self._pid.kp = self._kp
        self._pid.ki = self._ki
        self._pid.kd = self._kd

    def _tune_adjust(self, param, direction):
        current = getattr(self, param["attr"])
        current = round(current + direction * param["step"], 4)
        current = max(param["min"], min(param["max"], current))
        setattr(self, param["attr"], current)
        self._apply_pid()

    # ---- Draw tune page ----
    def _draw_tune(self):
        scr = self._scr
        scr.fill(0x0000)
        scr.rect(0, 0, W, 28, 0x000F, filled=True)
        scr.text("PID Tuning", 8, 10, 0x07FF)
        scr.text("Adjust live - changes apply", 8, 34, 0x7BEF)
        scr.text("immediately without restart", 8, 46, 0x7BEF)

        self._tune_row_btns = []
        for i, param in enumerate(self._tune_params):
            y   = 60 + i * 72
            val = getattr(self, param["attr"])
            scr.rect(10, y, 220, 58, 0x2104, filled=True)
            scr.rect(10, y, 220, 58, 0x7BEF, filled=False)
            scr.text(param["label"], 16, y + 8,  0x07FF)
            scr.text(f"{val:.2f}", 16, y + 30, 0xFFFF)

            minus = Button(156, y + 13, 32, 32, "-",
                           lambda p=param: self._tune_adjust(p, -1), 0x8000)
            plus  = Button(196, y + 13, 32, 32, "+",
                           lambda p=param: self._tune_adjust(p, +1), 0x0320)
            minus.draw(scr)
            plus.draw(scr)
            self._tune_row_btns.append((minus, plus))

        self._back_btn = Button(10, 280, 220, 36, "< Back to Main",
                                lambda: setattr(self, '_page', 0))
        self._back_btn.draw(scr)
        scr.flush()

    # ---- Draw main page ----
    def _draw(self):
        scr = self._scr
        scr.fill(0x0000)

        # Header
        scr.rect(0, 0, W, 28, 0x000F, filled=True)
        scr.text("Peltier Control", 8, 10, 0x07FF)

        # Temperature
        temp = self._temp
        sp   = self._setpoint
        if self._fault:
            col = 0xF800
            scr.text("FAULT - check sensor", 8, 40, 0xF800)
        else:
            if abs(temp - sp) <= TOLERANCE: col = 0x07E0
            elif temp < sp:                 col = 0x001F
            else:                           col = 0xF800

        scr.text("Temp:", 10, 36, 0x7BEF)
        scr.text(f"{temp:.1f} C", 10, 52, col)
        scr.text(f"Setpt: {sp:.0f} C", 130, 52, 0xFFFF)

        # Stage info
        def fmt_time(secs):
            m = int(secs) // 60
            s = int(secs) % 60
            return f"{m:02d}:{s:02d}"

        stage_labels = [
            ("Heating to 60 C",                     0xFD20),
            (f"Hold 60 C  {fmt_time(self._hold_left)} left", 0x07E0),
            ("Cooling to 50 C",                     0x07FF),
            (f"Hold 50 C  {fmt_time(self._hold_left)} left", 0x07E0),
        ]
        if self._running and not self._fault:
            label, lcol = stage_labels[self._stage]
            scr.text("Stage:", 10, 76, 0x7BEF)
            scr.text(label, 10, 90, lcol)
            seg_w = 50; seg_h = 10; seg_y = 108; gap = 5
            seg_cols = [0xFD20, 0x07E0, 0x07FF, 0x07E0]
            for i in range(4):
                x = 10 + i * (seg_w + gap)
                filled_col = seg_cols[i] if i <= self._stage else 0x2104
                scr.rect(x, seg_y, seg_w, seg_h, filled_col, filled=True)
                scr.rect(x, seg_y, seg_w, seg_h, 0x7BEF,     filled=False)
        else:
            status = "FAULT" if self._fault else "Stopped"
            scr.text(status, 10, 76, 0xF800 if self._fault else 0x7BEF)

        # Output bar
        out = self._output
        bar_cx = 120; bar_y = 130; bar_hw = 100; bar_h = 8
        scr.rect(bar_cx - bar_hw, bar_y, bar_hw*2, bar_h, 0x2104, filled=True)
        scr.rect(bar_cx - bar_hw, bar_y, bar_hw*2, bar_h, 0x7BEF, filled=False)
        scr.rect(bar_cx, bar_y, 1, bar_h, 0x7BEF, filled=True)
        if out > 0:
            scr.rect(bar_cx, bar_y, int(out*bar_hw/100), bar_h, 0xFD20, filled=True)
        elif out < 0:
            scr.rect(bar_cx - int(abs(out)*bar_hw/100), bar_y,
                     int(abs(out)*bar_hw/100), bar_h, 0x07FF, filled=True)

        if not self._running:
            mode_str, mode_col = "Stopped", 0x7BEF
        elif self._transitioning:
            mode_str, mode_col = "Reversing...", 0xFFE0
        elif abs(temp - sp) <= TOLERANCE:
            mode_str, mode_col = "At setpoint", 0x07E0
        elif out > 0:
            mode_str, mode_col = f"Heating {abs(out):.0f}%", 0xFD20
        else:
            mode_str, mode_col = f"Cooling {abs(out):.0f}%", 0x07FF
        scr.text(mode_str, 10, 146, mode_col)

        # Fan always on
        scr.text("Fan: ON", 150, 146, 0x07FF)

        # PID summary
        scr.text(f"Kp:{self._kp:.1f} Ki:{self._ki:.2f} Kd:{self._kd:.1f}",
                 10, 164, 0x4208)

        self._start_btn.draw(scr)
        self._stop_btn.draw(scr)
        self._goto_heat.draw(scr)
        self._goto_cool.draw(scr)
        self._tune_btn.draw(scr)
        scr.flush()

    # ---- Touch ----
    def _handle_touch(self):
        try:
            coords = self._touch.get_touch_xy()
        except Exception:
            return
        if coords is None:
            return
        tx = coords[0]["x"]
        ty = coords[0]["y"]

        if self._page == 0:
            for btn in [self._start_btn, self._stop_btn,
                        self._goto_heat, self._goto_cool, self._tune_btn]:
                if btn.hit(tx, ty):
                    btn.callback()
                    time.sleep_ms(200)
                    return
        else:
            if hasattr(self, '_back_btn') and self._back_btn.hit(tx, ty):
                self._back_btn.callback()
                time.sleep_ms(200)
                return
            if hasattr(self, '_tune_row_btns'):
                for minus, plus in self._tune_row_btns:
                    if minus.hit(tx, ty):
                        minus.callback(); time.sleep_ms(150); return
                    if plus.hit(tx, ty):
                        plus.callback();  time.sleep_ms(150); return

    # ---- Main loop ----
    async def run(self):
        last_display = time.ticks_ms()
        while True:
            # PID runs every loop at CONTROL_PERIOD
            self._update()

            # Display and touch only update at DISPLAY_PERIOD
            now = time.ticks_ms()
            if time.ticks_diff(now, last_display) >= int(DISPLAY_PERIOD * 1000):
                self._handle_touch()
                if self._page == 0:
                    self._draw()
                else:
                    self._draw_tune()
                last_display = now

            await asyncio.sleep(CONTROL_PERIOD)

    def cleanup(self):
        self._stop()
        self._fan.value(0)   # fan off on exit
        self._rpwm.deinit()
        self._lpwm.deinit()


# --------------------------------------------------
async def main():
    app = PeltierApp()
    try:
        await app.run()
    finally:
        app.cleanup()

asyncio.run(main())