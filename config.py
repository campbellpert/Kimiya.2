# config.py  —  RP2350-Touch-LCD-2 (MicroPython)
# --------------------------------------------------
# GPIO Pins
# --------------------------------------------------
# Reserved by the board (do not use):
#   GP15       — LCD backlight
#   GP16       — LCD DC
#   GP17       — LCD CS
#   GP18       — LCD SCK  (SPI0)
#   GP19       — LCD MOSI (SPI0)
#   GP20       — LCD RST / touch RST
#   GP12       — Touch I2C SDA
#   GP13       — Touch I2C SCL
#   GP29       — Touch IRQ

# MAX31865 on SPI1 — GP26/27/28 are the valid SPI1 pins available on this board
MAX31865_SCK  = 26   # SPI1 SCK
MAX31865_MOSI = 27   # SPI1 MOSI (TX)
MAX31865_MISO = 28   # SPI1 MISO (RX)
MAX31865_CS   = 5    # Any free GPIO

# Motor (TB6612 or equivalent — all free GPIOs, all PWM-capable)
MOTOR_PWMA = 0       # PWM0 A
MOTOR_AIN1 = 1
MOTOR_AIN2 = 2
MOTOR_STBY = 3

# Heater — needs PWM, must not conflict with SPI1 or motor pins above
HEATER_PIN = 4       # PWM2 A

# --------------------------------------------------
# PWM Settings
# --------------------------------------------------
# NOTE: MicroPython PWM uses frequency in Hz and
#       duty cycle as 0–65535 (duty_u16).
HEATER_PWM_FREQ = 1       # Hz — suits SSR heatpad
MOTOR_PWM_FREQ  = 10000   # Hz — suits DC motor driver

# --------------------------------------------------
# Heater Control
# --------------------------------------------------
TARGET_TEMP    = 60
MAX_SAFE_TEMP  = 90
CONTROL_PERIOD = 0.2      # seconds

# --------------------------------------------------
# PID Tuning
# --------------------------------------------------
PID_KP = 15.0
PID_KI = 2.0
PID_KD = 20.0

# --------------------------------------------------
# Calibration
# --------------------------------------------------
CAL_M = 1.4693
CAL_B = -9.62235

# --------------------------------------------------
# MAX31865 hardware config
# --------------------------------------------------
RTD_NOMINAL  = 100    # PT100
RTD_WIRES    = 3
REF_RESISTOR = 430    # Rref on your MAX31865 board (usually 430 Ω for PT100)

# --------------------------------------------------
# Auto Process Configuration
# --------------------------------------------------
AUTO_ENABLED    = True
AUTO_PUMP_SPEED = 80      # % (0–100)
AUTO_PUMP_TIME  = 5       # seconds

CHAMBER_SEQUENCE = [
    {"name": "Chamber 1", "target_temp": None},
    {"name": "Chamber 2", "target_temp": 60},
    {"name": "Chamber 3", "target_temp": 50},
]

TEMP_TOLERANCE = 2.0