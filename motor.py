# motor.py  —  RP2350-Touch-LCD-2 (MicroPython)
# --------------------------------------------------
# Replaces: RPi.GPIO  →  machine.Pin, machine.PWM
# Pin assignments live in config.py
# --------------------------------------------------
from machine import Pin, PWM
import config


class MotorController:
    def __init__(self):
        self._ain1 = Pin(config.MOTOR_AIN1, Pin.OUT, value=0)
        self._ain2 = Pin(config.MOTOR_AIN2, Pin.OUT, value=0)
        self._stby = Pin(config.MOTOR_STBY, Pin.OUT, value=0)
        self._pwm  = PWM(Pin(config.MOTOR_PWMA), freq=config.MOTOR_PWM_FREQ)
        self._pwm.duty_u16(0)
        self._direction = None

    # -------------------------
    def _duty(self, pct):
        """Convert 0–100 % to 0–65535 for duty_u16."""
        return int(max(0, min(100, pct)) * 655.35)

    def _enable(self):
        self._stby.value(1)

    def _disable(self):
        self._stby.value(0)

    # -------------------------
    def forward(self, speed):
        self._enable()
        self._ain1.value(1)
        self._ain2.value(0)
        self._pwm.duty_u16(self._duty(speed))
        self._direction = "forward"

    def reverse(self, speed):
        self._enable()
        self._ain1.value(0)
        self._ain2.value(1)
        self._pwm.duty_u16(self._duty(speed))
        self._direction = "reverse"

    def stop(self):
        self._pwm.duty_u16(0)
        self._ain1.value(0)
        self._ain2.value(0)
        self._disable()
        self._direction = None

    def set_speed(self, speed):
        if self._direction:
            self._pwm.duty_u16(self._duty(speed))

    def cleanup(self):
        self.stop()
        self._pwm.deinit()
