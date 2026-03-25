# heatpad.py  —  RP2350-Touch-LCD-2 (MicroPython)
# --------------------------------------------------
# Replaces: RPi.GPIO, board, digitalio, adafruit_max31865, threading
# Uses:     machine.SPI, machine.Pin, machine.PWM + uasyncio
# --------------------------------------------------
import time
import uasyncio as asyncio
from machine import SPI, Pin, PWM
import config

# --------------------------------------------------
# Minimal MAX31865 driver (replaces adafruit_max31865)
# --------------------------------------------------
class MAX31865:
    # Register addresses
    _REG_CONFIG    = 0x00
    _REG_RTD_MSB   = 0x01
    _REG_FAULT     = 0x07

    # Config byte: V_BIAS on, auto-convert, 3-wire, 50 Hz filter
    _CFG_3WIRE     = 0xC2
    _CFG_2_4WIRE   = 0xC0

    def __init__(self, spi, cs, wires=3, ref_resistor=430, rtd_nominal=100):
        self._spi = spi
        self._cs  = cs
        self._cs.value(1)
        self._ref  = ref_resistor
        self._nom  = rtd_nominal
        cfg = self._CFG_3WIRE if wires == 3 else self._CFG_2_4WIRE
        self._write_reg(self._REG_CONFIG, cfg)
        time.sleep_ms(100)   # Allow bias voltage to settle

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
        """Callendar-Van Dusen approximation, accurate to ~0.5 C from -50 to +150 C."""
        r = self.resistance
        # Standard PT100 CVD coefficients
        A =  3.9083e-3
        B = -5.775e-7
        # Quadratic solve: R = R0*(1 + A*T + B*T^2)  →  B*T^2 + A*T + (1 - R/R0) = 0
        R0 = self._nom
        discriminant = A * A - 4 * B * (1.0 - r / R0)
        if discriminant < 0:
            return -999.0   # Sensor fault / open circuit
        temp = (-A + discriminant ** 0.5) / (2 * B)
        return temp

    @property
    def fault(self):
        return self._read_reg(self._REG_FAULT)[0]


# --------------------------------------------------
# Minimal PID (replaces simple_pid — not available in MicroPython)
# --------------------------------------------------
class PID:
    def __init__(self, kp, ki, kd, setpoint, output_limits=(0, 100), sample_time=0.2):
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.setpoint = setpoint
        self.output_limits = output_limits
        self.sample_time = sample_time
        self._integral = 0.0
        self._last_error = 0.0
        self._last_time = time.ticks_ms()

    def __call__(self, measured):
        now = time.ticks_ms()
        dt = time.ticks_diff(now, self._last_time) / 1000.0
        if dt < self.sample_time:
            dt = self.sample_time    # Clamp minimum dt

        error = self.setpoint - measured
        self._integral += error * dt
        derivative = (error - self._last_error) / dt if dt > 0 else 0.0

        output = self.kp * error + self.ki * self._integral + self.kd * derivative

        lo, hi = self.output_limits
        # Anti-windup: clamp integral if output is saturated
        if output > hi:
            output = hi
            self._integral -= error * dt
        elif output < lo:
            output = lo
            self._integral -= error * dt

        self._last_error = error
        self._last_time = now   # Always update time, even when clamped
        return output


# --------------------------------------------------
# HeatPadController
# --------------------------------------------------
class HeatPadController:
    def __init__(self):
        self.target_temp   = config.TARGET_TEMP
        self.control_period = config.CONTROL_PERIOD

        self.pid = PID(
            config.PID_KP,
            config.PID_KI,
            config.PID_KD,
            setpoint=self.target_temp,
            output_limits=(0, 100),
            sample_time=self.control_period,
        )

        # SPI1 — safe, doesn't conflict with LCD (which uses SPI0)
        spi = SPI(
            1,
            baudrate=500_000,
            polarity=0,
            phase=1,
            sck=Pin(config.MAX31865_SCK),
            mosi=Pin(config.MAX31865_MOSI),
            miso=Pin(config.MAX31865_MISO),
        )
        cs = Pin(config.MAX31865_CS, Pin.OUT, value=1)
        self.sensor = MAX31865(
            spi, cs,
            wires=config.RTD_WIRES,
            ref_resistor=config.REF_RESISTOR,
            rtd_nominal=config.RTD_NOMINAL,
        )

        # PWM output for heatpad
        self._pwm = PWM(Pin(config.HEATER_PIN), freq=config.HEATER_PWM_FREQ)
        self._pwm.duty_u16(0)

        self._temp    = 0.0
        self._output  = 0.0
        self._running = False
        self._task    = None

    # -------------------------
    def _duty(self, pct):
        """Convert 0–100 % to 0–65535 for duty_u16."""
        return int(max(0, min(100, pct)) * 655.35)

    # -------------------------
    async def _loop(self):
        while self._running:
            try:
                raw  = self.sensor.temperature
                temp = raw * config.CAL_M + config.CAL_B
            except Exception as e:
                print("Sensor error:", e)
                self._shutdown()
                break

            if temp > config.MAX_SAFE_TEMP or temp < -50:
                print("Safety shutdown triggered.")
                self._shutdown()
                break

            output = self.pid(temp)
            self._pwm.duty_u16(self._duty(output))
            self._temp   = temp
            self._output = output
            await asyncio.sleep(self.control_period)

        self._shutdown()
        self._running = False

    # -------------------------
    def start(self):
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())

    def stop(self):
        self._running = False
        self._shutdown()

    def get_status(self):
        return self._temp, self._output, self.target_temp, self._running

    def set_target(self, value):
        self.target_temp  = value
        self.pid.setpoint = value

    def _shutdown(self):
        self._pwm.duty_u16(0)

    def cleanup(self):
        self.stop()
        self._pwm.deinit()