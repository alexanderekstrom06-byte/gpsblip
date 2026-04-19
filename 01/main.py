# This is a sample Python script.

# Press ⌃R to execute it or replace it with your code.
# Press Double ⇧ to search everywhere for classes, files, tool windows, actions, and settings.


import argparse
import os
import sys
from gps_input import get_origin_from_usb_gps
from gps_sim import GpsSim


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


def parse_args():
    parser = argparse.ArgumentParser(description="GPS simulation med Google Directions")
    parser.add_argument(
        "--position-source",
        choices=["manual", "gps"],
        default="manual",
        help="Vælg hvor startposition (origin) kommer fra",
    )
    parser.add_argument(
        "--gps-port",
        default=None,
        help="Specifik serial-port til GPS, fx /dev/ttyUSB0 eller /dev/tty.usbserial-xxxx",
    )
    parser.add_argument(
        "--gps-timeout",
        type=int,
        default=20,
        help="Timeout i sekunder for læsning fra GPS-modtager",
    )
    parser.add_argument(
        "--origin",
        default="Rådhuspladsen, København",
        help="Manuel origin når --position-source=manual",
    )
    parser.add_argument(
        "--destination",
        default="Kongens Nytorv, København",
        help="Destination til ruteplanlægning",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    properties_path = "./01/application.properties"

    if not os.path.exists(properties_path):
        print(f"Fejl: Mangler {properties_path}")
        print("Opret filen og sæt google.api.key=<DIN_GOOGLE_API_KEY>")
        sys.exit(1)

    properties = load_properties(properties_path)
    api_key = properties.get("google.api.key", "")

    if not api_key or api_key == "DIN_GOOGLE_API_KEY_HER":
        print(f"Fejl: Du skal indsætte en gyldig Google API nøgle i {properties_path}")
        print("Du kan også køre 'python3 test_gps_sim.py' for at se en simulation med mock data.")
        sys.exit(1)

    sim = GpsSim(api_key)

    origin = args.origin
    destination = args.destination

    if args.position_source == "gps":
        try:
            origin, used_port = get_origin_from_usb_gps(
                port=args.gps_port,
                timeout_seconds=args.gps_timeout,
            )
            print(f"GPS-position modtaget fra {used_port}: {origin}")
        except Exception as e:
            print(f"Fejl ved GPS-indlæsning: {e}")
            print("Faldt tilbage til manuel origin fra --origin.")

    try:
        route = sim.get_route(origin, destination)
        sim.pretty_print_directions(route)
        sim.simulate_route(route)
    except Exception as e:
        print(f"Der opstod en fejl under hentning af rute: {e}")


if __name__ == '__main__':
    main()

# See PyCharm help at https://www.jetbrains.com/help/pycharm/
