import googlemaps
import json
from datetime import datetime

class GpsSim:
    def __init__(self, api_key=None):
        if api_key:
            self.client = googlemaps.Client(key=api_key)
        else:
            self.client = None

    def get_route(self, origin, destination):
        # Hent ruten fra Google Directions API
        now = datetime.now()
        directions_result = self.client.directions(origin,
                                                  destination,
                                                  mode="driving",
                                                  departure_time=now)
        return directions_result

    def analyze_step(self, step):
        """
        Analyserer et step i ruten og returnerer om der skal blinkes, og i hvilken retning.
        Returnerer: (should_blink, direction)
        """
        html_instructions = step.get('html_instructions', '').lower()
        maneuver = step.get('maneuver', '').lower()

        # Rundkørsel tjek - ifølge beskrivelse skal der IKKE blinkes i rundkørsler
        if 'roundabout' in html_instructions or 'roundabout' in maneuver:
            return False, None

        # Tjek for højre eller venstre sving
        if 'turn right' in html_instructions or 'right' in maneuver:
            return True, 'Højre'
        if 'turn left' in html_instructions or 'left' in maneuver:
            return True, 'Venstre'

        return False, None

    def simulate_route(self, directions_result):
        if not directions_result:
            print("Ingen rute fundet.")
            return

        leg = directions_result[0]['legs'][0]
        steps = leg['steps']

        print(f"Starter rute fra {leg['start_address']} til {leg['end_address']}")
        print("-" * 50)

        for i, step in enumerate(steps):
            distance_meters = step['distance']['value']
            instruction = step['html_instructions'].replace('<b>', '').replace('</b>', '')
            
            # Vi kigger på det NÆSTE step for at vide om vi skal blinke i slutningen af dette step
            should_blink = False
            blink_direction = None
            
            if i + 1 < len(steps):
                next_step = steps[i+1]
                should_blink, blink_direction = self.analyze_step(next_step)

            # Simulering af kørsel gennem steppet
            # I en rigtig app ville vi løbende tjekke afstanden til næste sving
            # Her simulerer vi det ved at printe status
            
            print(f"Kører: {instruction} ({distance_meters} m)")
            
            if should_blink:
                # Vi skal blinke når vi er 50m fra svinget (slutningen af nuværende step)
                if distance_meters > 50:
                    print(f"  ... køre køre ...")
                    print(f"  [50 m til sving] BLINKER {blink_direction}!")
                else:
                    # Hvis steppet er kortere end 50m, begynder vi at blinke med det samme
                    print(f"  [Kort stykke] BLINKER {blink_direction} med det samme!")
            
            print(f"Færdig med step.\n")

        print("Destination nået!")

    def pretty_print_directions(self, directions_result):
        if not directions_result:
            print("Ingen directions-response at vise.")
            return
        print("Google Directions API response (formatteret):")
        print(json.dumps(directions_result, indent=2, ensure_ascii=False, default=str))
