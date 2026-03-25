# config.py  —  RP2350-Touch-LCD-2 (MicroPython)
# --------------------------------------------------
# GPIO Pins
# --------------------------------------------------
# Heater (PWM-capable, free on RP2350-Touch-LCD-2)
HEATER_PIN = 28

# Motor (TB6612 or equivalent, all PWM/GPIO-capable)
MOTOR_PWMA = 26
MOTOR_AIN1 = 6
MOTOR_AIN2 = 7
MOTOR_STBY = 8

# MAX31865 on SPI1 — DO NOT use SPI0 (reserved for LCD on GP18/19)
# Also avoid GP12/13 (touch I2C SDA/SCL), GP29 (touch IRQ), GP20 (touch/LCD RST)
MAX31865_SCK  = 2
MAX31865_MOSI = 3
MAX31865_MISO = 4
MAX31865_CS   = 5

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