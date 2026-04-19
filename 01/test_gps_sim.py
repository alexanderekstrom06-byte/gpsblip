import unittest
from gps_sim import GpsSim

class TestGpsSim(unittest.TestCase):
    def setUp(self):
        # Vi sender ikke en API nøgle for at undgå valideringsfejl under test
        self.sim = GpsSim()

    def test_analyze_step_right_turn(self):
        step = {
            'html_instructions': 'Drej til <b>højre</b> mod Gaden',
            'maneuver': 'turn-right'
        }
        should_blink, direction = self.sim.analyze_step(step)
        self.assertTrue(should_blink)
        self.assertEqual(direction, 'Højre')

    def test_analyze_step_left_turn(self):
        step = {
            'html_instructions': 'Drej til <b>venstre</b> mod Gaden',
            'maneuver': 'turn-left'
        }
        should_blink, direction = self.sim.analyze_step(step)
        self.assertTrue(should_blink)
        self.assertEqual(direction, 'Venstre')

    def test_analyze_step_roundabout(self):
        step = {
            'html_instructions': 'Tag den 2. afkørsel i <b>rundkørslen</b>',
            'maneuver': 'roundabout-right'
        }
        should_blink, direction = self.sim.analyze_step(step)
        # Ifølge kravet: Ved rundkørseler skal der blinkes skal der ikke blikkes.
        self.assertFalse(should_blink)

    def test_simulate_route_mocked(self):
        # Mocking af Google Directions API svar
        mock_result = [{
            'legs': [{
                'start_address': 'Aarhus',
                'end_address': 'København',
                'steps': [
                    {
                        'distance': {'value': 1000},
                        'html_instructions': 'Kør ligeud af E20',
                        'maneuver': None
                    },
                    {
                        'distance': {'value': 100},
                        'html_instructions': 'Drej til <b>højre</b>',
                        'maneuver': 'turn-right'
                    },
                    {
                        'distance': {'value': 40},
                        'html_instructions': 'Drej til <b>venstre</b>',
                        'maneuver': 'turn-left'
                    },
                    {
                        'distance': {'value': 500},
                        'html_instructions': 'Tag den 1. afkørsel i rundkørslen',
                        'maneuver': 'roundabout-right'
                    }
                ]
            }]
        }]
        
        # Vi verificerer at vi kan køre simulationen uden fejl med dette mock
        # Vi overvåger print for at se om logic virker
        print("\nStarter unit test simulation...")
        self.sim.simulate_route(mock_result)

if __name__ == '__main__':
    unittest.main()
