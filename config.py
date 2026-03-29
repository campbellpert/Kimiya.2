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

# MAX31865 on SPI1 — using pins actually exposed on the board header
# GPIO10 = SPI1 SCK  (header pin 12)
# GPIO11 = SPI1 MOSI (header pin 21)
# GPIO8  = SPI1 MISO (header pin 26)
# GPIO9  = CS        (header pin 27, any free GPIO)
MAX31865_SCK  = 10
MAX31865_MOSI = 11
MAX31865_MISO = 8
MAX31865_CS   = 9

# Motor — free GPIO pins on the header
# GPIO0  = PWMA (header pin 10)
# GPIO1  = AIN1 (header pin 8)
# GPIO3  = AIN2 (header pin 9)
# GPIO5  = STBY (header pin 19)
MOTOR_PWMA = 0
MOTOR_AIN1 = 1
MOTOR_AIN2 = 3
MOTOR_STBY = 5

# Heater PWM — GPIO4 (header pin 11 / pin 20)
HEATER_PIN = 4

# --------------------------------------------------
# PWM Settings
# --------------------------------------------------
# NOTE: MicroPython PWM uses frequency in Hz and
#       duty cycle as 0–65535 (duty_u16).
HEATER_PWM_FREQ = 100     # Hz — safely above RP2350 PWM minimum; fine for MOSFET heatpad
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