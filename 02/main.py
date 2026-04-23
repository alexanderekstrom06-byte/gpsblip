import os
import time
from datetime import datetime

from blink import BlinkController
from google_maps_api import get_directions, load_properties
from gps_receiver import GpsReader, distance_to_point

PROPERTIES_FILE = "application.properties"

# Afstandsgrænser – disse tal styrer hvornår blink og sving sker
BLINK_START_DISTANCE_M = 50.0   # Begynd at blinke, når vi er inden for denne afstand fra et sving
TURN_COMPLETE_OVERSHOOT_M = 3.0  # Stop med at blinke, når vi har kørt så langt forbi svinget
TURN_ENTER_THRESHOLD_M = 20.0   # Vi regner os selv som "ved svinget", når vi er tættere end dette
ARRIVAL_DISTANCE_M = 10.0       # Vi er fremme, når vi er inden for denne afstand fra destinationen


class NavigationController:
    """Styrer navigationslogikken: sving-detektion, destination-check og blink-kontrol."""

    def __init__(self, steps, gps_reader):
        self.steps = steps
        self.current_step_index = 0
        self.arrived = False
        self.blink_direction = None
        self._closest_dist = float("inf")
        self._gps = gps_reader

    def tick(self):
        """Opdaterer navigationstilstanden baseret på nuværende GPS-position."""
        lat, lng, fix = self._gps.get_position()
        if not fix or lat is None:
            print(f"{get_timestamp()} [NAV] Waiting for GPS fix…")
            return

        step = self.steps[self.current_step_index]
        dist = distance_to_point(lat, lng, step["end_location"]["lat"], step["end_location"]["lng"])

        if self._check_arrival(dist):
            return
        self._update_closest(dist)
        if self._check_turn_complete(dist):
            return
        self._update_blink(dist, step)
        self._log(dist, step)

    def _check_arrival(self, dist):
        """Tjekker om vi er nået destinationen."""
        is_last = self.current_step_index >= len(self.steps) - 1
        if is_last and dist <= ARRIVAL_DISTANCE_M:
            self.arrived = True
            self.blink_direction = None
            print(f"{get_timestamp()} [NAV] Destination reached!")
            return True
        return False

    def _update_closest(self, dist):
        """Gem den korteste afstand vi har haft til det næste sving."""
        if dist < self._closest_dist:
            self._closest_dist = dist

    def _check_turn_complete(self, dist):
        """Tjekker om vi har drejet og skal til næste trin."""
        past = (
            self._closest_dist < TURN_ENTER_THRESHOLD_M
            and dist > self._closest_dist + TURN_COMPLETE_OVERSHOOT_M
        )
        if past:
            self.blink_direction = None
            self._closest_dist = float("inf")
            self.current_step_index += 1
            if self.current_step_index < len(self.steps):
                nxt = self.steps[self.current_step_index]
                print(f"{get_timestamp()} [NAV] Step {self.current_step_index}: {nxt['instruction']}")
            return True
        return False

    def _update_blink(self, dist, step):
        """Opdaterer blink-retning baseret på afstand til sving ved slutningen af dette trin."""
        direction = maneuver_to_direction(step["maneuver"])
        self.blink_direction = direction if direction and dist <= BLINK_START_DISTANCE_M else None

    def _log(self, dist, step):
        """Logger navigationsstatus til terminalen."""
        next_instruction = ""
        if self.current_step_index + 1 < len(self.steps):
            nxt = self.steps[self.current_step_index + 1]
            next_instruction = f" → Næste: {nxt['instruction']}"
        print(
            f"{get_timestamp()} [NAV] Step {self.current_step_index}/{len(self.steps) - 1}: "
            f"{step['instruction']} | "
            f"sving om {dist:.1f} m | "
            f"blink: {self.blink_direction or '–'} |"
            f"{next_instruction}"
        )


# ---------------------------------------------------------------------------
# Hjælpefunktioner
# ---------------------------------------------------------------------------
def get_timestamp():
    """Returnerer tidsstempel i formatet YYYY-MM-DD HH:mm:ss.sss"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

def maneuver_to_direction(maneuver):
    """Oversætter Googles sving-betegnelse til 'left' (venstre), 'right' (højre) eller None (ingen blink)."""
    if not maneuver:
        return None
    m = maneuver.lower()
    if "left" in m:
        return "left"
    if "right" in m:
        return "right"
    return None


# ---------------------------------------------------------------------------
# Her starter programmet
# ---------------------------------------------------------------------------

def main():
    props = load_properties(PROPERTIES_FILE)
    api_key = props["google.api.key"]
    destination = props["destination"]

    # Start GPS-læseren (forbinder til gpsd-tjenesten, som taler med ublox 7 via USB)
    gps_reader = GpsReader()
    gps_reader.start()

    print(f"{get_timestamp()} [MAIN] Venter på GPS-fix…")
    if not gps_reader.wait_for_fix(timeout=120):
        print(f"{get_timestamp()} [MAIN] Fik ikke GPS-fix inden for 2 minutter – afslutter.")
        return

    lat, lng, _ = gps_reader.get_position()
    print(f"{get_timestamp()} [MAIN] GPS-fix: {lat:.6f}, {lng:.6f}")

    # Mål GPS-stabilitet før navigation starter (kan springes over med SKIP_GPS_STABILITY=1)
    if not os.getenv("SKIP_GPS_STABILITY"):
        gps_reader.check_stability(duration_sec=60, interval_sec=2)

    # Hent vejvisningen fra vores nuværende position til destinationen
    print(f"{get_timestamp()} [MAIN] Henter rute til: {destination}")
    steps = get_directions(api_key, lat, lng, destination)
    if not steps:
        print(f"{get_timestamp()} [MAIN] Ingen rute fundet – afslutter.")
        return

    total_distance_m = sum(step.get("distance_m", 0) for step in steps)
    print(f"{get_timestamp()} [MAIN] Rute hentet: {len(steps)} trin ({total_distance_m/1000:.1f} km)")
    print(f"{get_timestamp()} [MAIN] Ruteoversigt:")
    for i, step in enumerate(steps):
        dist_km = step.get("distance_m", 0) / 1000
        print(f"{get_timestamp()} [MAIN]   {i}: {step['instruction']} ({dist_km:.1f} km)")
    print(f"{get_timestamp()} [MAIN]   {len(steps)}: Destination")

    nav = NavigationController(steps, gps_reader)
    blink = BlinkController(nav)
    blink.start()

    try:
        while not nav.arrived and nav.current_step_index < len(nav.steps):
            nav.tick()
            time.sleep(0.5)
    except KeyboardInterrupt:
        print(f"\n{get_timestamp()} [MAIN] Navigation stoppet af bruger.")
    finally:
        blink.stop()


if __name__ == "__main__":
    main()
