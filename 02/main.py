import math
import time

from blink import BlinkController
from google_maps_api import get_directions, load_properties
from gps_receiver import GpsReader

PROPERTIES_FILE = "application.properties"

# Afstandsgrænser – disse tal styrer hvornår blink og sving sker
BLINK_START_DISTANCE_M = 50.0   # Begynd at blinke, når vi er inden for denne afstand fra et sving
TURN_COMPLETE_OVERSHOOT_M = 3.0  # Stop med at blinke, når vi har kørt så langt forbi svinget
TURN_ENTER_THRESHOLD_M = 20.0   # Vi regner os selv som "ved svinget", når vi er tættere end dette
ARRIVAL_DISTANCE_M = 10.0       # Vi er fremme, når vi er inden for denne afstand fra destinationen


class NavState:
    """Indeholder alle fælles oplysninger som navigationssløjfen og blinket deler."""

    def __init__(self):
        self.steps = []
        self.current_step_index = 0
        self.blinkDirection = None   # Hvilken retning der skal blinkes: None = intet blink, 'left' = venstre, 'right' = højre
        self.arrived = False
        self._closest_dist = float("inf")  # Den korteste afstand vi hidtil har haft til det næste sving


# ---------------------------------------------------------------------------
# Hjælpefunktioner
# ---------------------------------------------------------------------------

def haversine(lat1, lng1, lat2, lng2):
    """Beregner luftlinjeafstanden i meter mellem to GPS-koordinater (bredde- og længdegrad)."""
    R = 6_371_000  # Jordens radius i meter

    # Omregn grader til radianer – matematik-funktionerne kræver radianer, ikke grader
    phi1, phi2 = math.radians(lat1), math.radians(lat2)

    # Beregn forskellen i breddegrad og længdegrad (også i radianer)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)

    # Haversine-formlen: beregner et mellemresultat der tager højde for jordens krumning
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2

    # Omregn mellemresultatet til meter langs jordens overflade og returner
    return 2 * R * math.asin(math.sqrt(a))


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
# Navigationsopdatering – denne funktion kaldes én gang i sekundet
# ---------------------------------------------------------------------------

def navigation_tick(nav_state, gps_reader):
    lat, lng, fix = gps_reader.get_position()
    if not fix or lat is None:
        print("[NAV] Waiting for GPS fix…")
        return

    step = nav_state.steps[nav_state.current_step_index]
    turn_lat = step["end_location"]["lat"]
    turn_lng = step["end_location"]["lng"]
    dist_to_turn = haversine(lat, lng, turn_lat, turn_lng)
    is_last_step = nav_state.current_step_index >= len(nav_state.steps) - 1

    # ---- Er vi fremme ved destinationen? ------------------------------------------------
    if is_last_step and dist_to_turn <= ARRIVAL_DISTANCE_M:
        nav_state.arrived = True
        nav_state.blinkDirection = None
        print("[NAV] Destination reached!")
        return

    # ---- Gem den korteste afstand vi har haft til svinget ---------------------
    if dist_to_turn < nav_state._closest_dist:
        nav_state._closest_dist = dist_to_turn

    # ---- Har vi drejet om hjørnet? --------------------------------------
    # Hvis vi har været tæt nok på svinget og nu er 3 m forbi det nærmeste punkt, er svinget overstået.
    past_turn = (
        nav_state._closest_dist < TURN_ENTER_THRESHOLD_M
        and dist_to_turn > nav_state._closest_dist + TURN_COMPLETE_OVERSHOOT_M
    )
    if past_turn:
        nav_state.blinkDirection = None
        nav_state._closest_dist = float("inf")
        nav_state.current_step_index += 1
        if nav_state.current_step_index < len(nav_state.steps):
            nxt = nav_state.steps[nav_state.current_step_index]
            print(f"[NAV] Step {nav_state.current_step_index}: {nxt['instruction']}")
        return

    # ---- Skal blinket tændes eller slukkes? -----------------------------------------------
    direction = maneuver_to_direction(step["maneuver"])
    if direction and dist_to_turn <= BLINK_START_DISTANCE_M:
        nav_state.blinkDirection = direction
    else:
        nav_state.blinkDirection = None

    print(
        f"[NAV] Step {nav_state.current_step_index}/{len(nav_state.steps) - 1}: "
        f"{step['instruction']} | "
        f"sving om {dist_to_turn:.0f} m | "
        f"blink: {nav_state.blinkDirection or '–'}"
    )


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

    print("[MAIN] Venter på GPS-fix…")
    if not gps_reader.wait_for_fix(timeout=120):
        print("[MAIN] Fik ikke GPS-fix inden for 2 minutter – afslutter.")
        return

    lat, lng, _ = gps_reader.get_position()
    print(f"[MAIN] GPS-fix: {lat:.6f}, {lng:.6f}")

    # Hent vejvisningen fra vores nuværende position til destinationen
    print(f"[MAIN] Henter rute til: {destination}")
    steps = get_directions(api_key, lat, lng, destination)
    if not steps:
        print("[MAIN] Ingen rute fundet – afslutter.")
        return
    print(f"[MAIN] Rute hentet: {len(steps)} trin")
    print(f"[MAIN] Første trin: {steps[0]['instruction']}")

    nav_state = NavState()
    nav_state.steps = steps

    blink = BlinkController(nav_state)
    blink.start()

    try:
        while not nav_state.arrived and nav_state.current_step_index < len(nav_state.steps):
            navigation_tick(nav_state, gps_reader)
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[MAIN] Navigation stoppet af bruger.")
    finally:
        blink.stop()


if __name__ == "__main__":
    main()
