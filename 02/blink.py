import threading
import time

# GPIO-pinnumre (BCM) til venstre og højre blinklys (relæ eller LED)
LEFT_PIN = 17
RIGHT_PIN = 27

try:
    import RPi.GPIO as GPIO
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(LEFT_PIN, GPIO.OUT, initial=GPIO.LOW)
    GPIO.setup(RIGHT_PIN, GPIO.OUT, initial=GPIO.LOW)
    GPIO_AVAILABLE = True
except Exception:
    GPIO_AVAILABLE = False


class BlinkController:
    """Styrer blinklysene i en separat tråd og holder øje med nav_state.blinkDirection.

    Så længe blinkDirection er 'left' eller 'right', blinker det tilsvarende lys
    hvert halve sekund (1 Hz – samme som et normalt blinklys i en bil).
    Blinkingen stopper, så snart blinkDirection sættes tilbage til None.

    På Raspberry Pi tændes og slukkes en GPIO-pin.
    På andre computere vises en pil i terminalen i stedet.
    """

    HALF_PERIOD = 0.5  # sekunder – giver et blink-interval på 1 sekund i alt (0,5 sek tændt + 0,5 sek slukket)

    def __init__(self, nav_state):
        self._nav = nav_state
        self._running = False
        self._thread = threading.Thread(target=self._loop, daemon=True)

    def start(self):
        self._running = True
        self._thread.start()

    def stop(self):
        self._running = False
        self._all_off()
        if GPIO_AVAILABLE:
            GPIO.cleanup()

    # ------------------------------------------------------------------
    # Interne hjælpemetoder
    # ------------------------------------------------------------------

    def _set_pin(self, direction, state):
        if GPIO_AVAILABLE:
            pin = LEFT_PIN if direction == "left" else RIGHT_PIN
            GPIO.output(pin, GPIO.HIGH if state else GPIO.LOW)
        else:
            if state:
                arrow = "<== VENSTRE" if direction == "left" else "HØJRE ==>"
                print(f"[BLINK] {arrow}")

    def _all_off(self):
        if GPIO_AVAILABLE:
            GPIO.output(LEFT_PIN, GPIO.LOW)
            GPIO.output(RIGHT_PIN, GPIO.LOW)

    def _loop(self):
        blink_on = False
        current_direction = None

        while self._running:
            direction = self._nav.blinkDirection

            if direction != current_direction:
                # Retningen er skiftet – nulstil blink-tilstand og sluk alt
                blink_on = False
                self._all_off()
                current_direction = direction

            if direction in ("left", "right"):
                blink_on = not blink_on
                self._set_pin(direction, blink_on)
            # Ingen retning – blinklysene er allerede slukket, intet at gøre

            time.sleep(self.HALF_PERIOD)
