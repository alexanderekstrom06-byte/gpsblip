import threading
import time

import gps


class GpsReader:
    """Læser GPS-position fra en ublox 7 GPS-modtager via gpsd-tjenesten.

    Sådan bruges klassen:
        reader = GpsReader()
        reader.start()
        reader.wait_for_fix()
        lat, lng, fix = reader.get_position()
    """

    def __init__(self):
        self._lat = None
        self._lng = None
        self._speed = None
        self._fix = False
        self._lock = threading.Lock()
        self._thread = threading.Thread(target=self._read_loop, daemon=True)

    def start(self):
        self._thread.start()

    def get_position(self):
        """Returnerer den aktuelle position som (breddegrad, længdegrad, har_fix).
        Breddegrad og længdegrad er None indtil GPS-modtageren har fundet signal."""
        with self._lock:
            return self._lat, self._lng, self._fix

    def get_speed(self):
        """Returnerer den aktuelle hastighed i km/t, eller None hvis ikke tilgængelig."""
        with self._lock:
            return self._speed * 3.6 if self._speed is not None else None

    def wait_for_fix(self, timeout=300):
        """Venter indtil GPS-modtageren har fundet et signal (2D eller 3D fix).
        Returnerer True hvis det lykkes inden tidsbegrænsningen, ellers False."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            _, _, fix = self.get_position()
            if fix:
                return True
            time.sleep(1)
        return False

    def _read_loop(self):
        while True:
            try:
                session = gps.gps(mode=gps.WATCH_ENABLE)
                print("[GPS] Connected to gpsd")

                while True:
                    report = session.next()
                    if report["class"] == "TPV":
                        lat = getattr(report, "lat", None)
                        lon = getattr(report, "lon", None)
                        mode = getattr(report, "mode", 0)
                        speed = getattr(report, "speed", None)
                        if lat is not None and lon is not None:
                            with self._lock:
                                self._lat = lat
                                self._lng = lon
                                self._speed = speed
                                self._fix = mode >= 2

            except Exception as exc:
                print(f"[GPS] Connection error: {exc} – retrying in 5 s")
                with self._lock:
                    self._fix = False
                time.sleep(5)
