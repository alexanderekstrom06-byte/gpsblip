import json
import re
from datetime import datetime

import requests


def load_properties(file_path):
    properties = {}
    with open(file_path, "r", encoding="utf-8") as file:
        for raw_line in file:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            properties[key.strip()] = value.strip()
    return properties


def get_directions(api_key, origin_lat, origin_lng, destination):
    """Henter en kørerute fra Google Maps.

    Rundkørsler springes over.

    Returnerer en liste af vejvisnings-trin, hvor hvert trin indeholder:
        'start_location' – GPS-koordinat for hvor trinnet begynder
        'end_location'   – GPS-koordinat for hvor trinnet slutter (svingets punkt)
        'maneuver'       – svingets type, fx 'turn-right' eller 'turn-left' (kan være None)
        'distance_m'     – afstand i meter for dette trin
        'instruction'    – tekst-vejledning, fx "Drej til højre ad Hovedgaden"
    """
    url = "https://maps.googleapis.com/maps/api/directions/json"
    params = {
        "origin": f"{origin_lat},{origin_lng}",
        "destination": destination,
        "key": api_key,
        "mode": "driving",
        "language": "da",
    }
    resp = requests.get(url, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()

    if data["status"] != "OK":
        raise RuntimeError(f"Directions API returned status: {data['status']}")

    # Udskriv råt API-respons
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"{timestamp} [API] Råt API-respons:")
    print(json.dumps(data, indent=2, ensure_ascii=False))

    # Saml alle steps først
    raw_steps = []
    for raw in data["routes"][0]["legs"][0]["steps"]:
        maneuver = raw.get("maneuver") or None
        if maneuver and "roundabout" in maneuver:
            continue
        instruction = re.sub(r"<[^>]+>", "", raw.get("html_instructions", ""))
        raw_steps.append({
            "start_location": raw["start_location"],
            "end_location": raw["end_location"],
            "maneuver": maneuver,
            "distance_m": raw["distance"]["value"],
            "instruction": instruction,
        })

    # Tildel maneuver fra NÆSTE step (svingen ved slutningen af nuværende step)
    steps = []
    for i, step in enumerate(raw_steps):
        next_maneuver = raw_steps[i + 1]["maneuver"] if i + 1 < len(raw_steps) else None
        step["maneuver"] = next_maneuver
        steps.append(step)

    # Udskriv API-respons som JSON
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"{timestamp} [API] Directions API-respons (JSON):")
    print(json.dumps(steps, indent=2, ensure_ascii=False))

    return steps
