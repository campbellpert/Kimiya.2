# fan_test.py — standalone fan test script
# Run this directly in Thonny to verify fan wiring
# independently of the main peltier_control.py
from machine import Pin
import time

FAN_PIN = 7   # GPIO7, header pin 28

fan = Pin(FAN_PIN, Pin.OUT, value=0)

print("Fan test starting...")
print()

print("Step 1: Fan ON for 5 seconds — you should hear/feel it spinning")
fan.value(1)
time.sleep(5)

print("Step 2: Fan OFF for 3 seconds")
fan.value(0)
time.sleep(3)

print("Step 3: Fan ON again for 3 seconds")
fan.value(1)
time.sleep(3)

print("Step 4: Fan OFF — test complete")
fan.value(0)

print()
print("If the fan spun in steps 1 and 3, wiring is correct.")
print("If nothing happened, check MOSFET wiring and 5V supply.")