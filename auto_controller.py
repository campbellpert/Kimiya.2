# auto_controller.py  —  RP2350-Touch-LCD-2 (MicroPython)
# --------------------------------------------------
# Replaces: threading  →  uasyncio
# Logic is identical to the original; only concurrency
# primitives change.
# --------------------------------------------------
import uasyncio as asyncio
import config


class AutoController:
    def __init__(self, motor, heater):
        self.motor   = motor
        self.heater  = heater
        self._running = False
        self._task    = None

    # -------------------------
    def start(self):
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_sequence())

    def stop(self):
        if not self._running:
            return
        self._running = False
        if self._task:
            self._task.cancel()
        self.motor.stop()
        self.heater.stop()

    def is_running(self):
        return self._running

    # -------------------------
    async def _run_sequence(self):
        print("Auto sequence started.")
        try:
            for chamber in config.CHAMBER_SEQUENCE:
                if not self._running:
                    break

                name   = chamber["name"]
                target = chamber["target_temp"]
                print(f"Moving to {name}")

                # Pump to chamber
                self.motor.forward(config.AUTO_PUMP_SPEED)
                await asyncio.sleep(config.AUTO_PUMP_TIME)
                self.motor.stop()

                if target is not None:
                    print(f"Heating {name} to {target} °C")
                    self.heater.set_target(target)
                    self.heater.start()

                    # Wait until within tolerance
                    while self._running:
                        temp, _, _, _ = self.heater.get_status()
                        if abs(temp - target) <= config.TEMP_TOLERANCE:
                            break
                        await asyncio.sleep(0.2)

                    print(f"{name} reached target.")

        except asyncio.CancelledError:
            pass

        # Finished or stopped
        self.motor.stop()
        self.heater.stop()
        self._running = False
        print("Auto sequence complete.")
