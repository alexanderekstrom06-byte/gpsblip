import math
import threading
import time

import gps

# Konstanter for afstandsberegning
_METERS_PER_DEGREE = 111_320.0
_DEG_TO_RAD = math.pi / 180.0


def distance_to_point(lat, lng, target_lat, target_lng):
    """Beregner flad afstand i meter mellem nuværende position og et waypoint."""
    mid_lat = (lat + target_lat) * 0.5
    dlat = target_lat - lat
    dlng = target_lng - lng
    x = dlng * _METERS_PER_DEGREE * math.cos(mid_lat * _DEG_TO_RAD)
    y = dlat * _METERS_PER_DEGREE
    return math.sqrt(x * x + y * y)


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

    def check_stability(self, duration_sec=60, interval_sec=2):
        """Måler GPS-stabilitet over tid. Rapporterer afstandsændringer uden at bilen bevæger sig."""
        from datetime import datetime
        print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]} [STABILITY] Måler GPS-stabilitet i {duration_sec} sekunder...")

        measurements = []
        start_time = time.time()

        while time.time() - start_time < duration_sec:
            lat, lng, fix = self.get_position()
            if fix and lat is not None:
                measurements.append((lat, lng, time.time()))
            time.sleep(interval_sec)

        if not measurements:
            print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]} [STABILITY] Ingen GPS-data – kan ikke måle stabilitet")
            return

        # Beregn afstandsændringer mellem successive målinger
        max_drift = 0.0
        avg_drift = 0.0
        drifts = []

        for i in range(1, len(measurements)):
            prev_lat, prev_lng, _ = measurements[i-1]
            curr_lat, curr_lng, _ = measurements[i]
            drift = distance_to_point(prev_lat, prev_lng, curr_lat, curr_lng)
            drifts.append(drift)
            max_drift = max(max_drift, drift)

        if drifts:
            avg_drift = sum(drifts) / len(drifts)

        print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]} [STABILITY] Målinger: {len(measurements)} | Max drift: {max_drift:.1f}m | Gennemsn: {avg_drift:.1f}m")
        print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]} [STABILITY] GPS virker klar til navigation når drift < 1-2 meter")

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
