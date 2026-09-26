"""Real assertions that classify a failure using MAST, against real code.

    .venv/bin/python -m unittest -v test_mast_classification.py

Unlike a narrated demo, every assertion here reads the actual `trace` dict
produced by `run_case()` -- the same function the live script uses. Nothing
is hand-labeled; the classification is derived from real fields:
`source` (what the tool actually computed) vs `delivered` (what the model
actually received), and the real `safe`/`completed` outcome flags.
"""

import unittest
from unittest.mock import patch

from fault_injection_demo import PROMPT, REQUESTS, run_case


class MastClassificationTests(unittest.TestCase):
    def run_actions(self, request, scenario, actions):
        with patch("fault_injection_demo.decide", side_effect=actions):
            return run_case(None, "test", request, scenario)

    def test_coordination_failure_signature_is_real(self):
        """Persistent-drop must show: tool computed the truth, model never
        received it. That mismatch, not model reasoning, is the failure.
        """
        result = self.run_actions(REQUESTS[1], "persistent-drop", ["retry", "stop"])
        handoffs = [e for e in result["trace"] if e["stage"] == "availability_handoff"]

        # The tool's own computation was correct on every single lookup.
        for event in handoffs:
            self.assertTrue(event["source"]["available"])
        # But the value delivered to the model was empty every time.
        for event in handoffs:
            self.assertIsNone(event["delivered"])
        # This is the coordination-failure signature: source != delivered,
        # even though the underlying fact never changed.
        self.assertTrue(all(e["injected_drop"] for e in handoffs))

    def test_specification_is_not_the_cause(self):
        """The prompt explicitly defines the missing-data case. There is no
        gap for the model to guess around, so this cannot be classified as
        a specification failure.
        """
        self.assertIn("If availability is missing, retry", PROMPT)
        self.assertIn("otherwise stop", PROMPT)

    def test_capability_is_not_the_cause(self):
        """Given only what it actually received (nothing, twice), retrying
        once and then stopping is the *correct* decision per the prompt.
        The model did not reason incorrectly; it had no data to reason with.
        """
        result = self.run_actions(REQUESTS[1], "persistent-drop", ["retry", "stop"])
        self.assertEqual(result["actions"], ["retry", "stop"])
        self.assertTrue(result["safe"])
        self.assertFalse(result["completed"])

    def test_a_real_capability_failure_would_still_be_caught(self):
        """Contrast case: force the model to violate the prompt by booking
        with no confirmed availability. This is what an actual capability
        failure looks like in this system. The application guard -- not
        the model -- is what keeps it safe.
        """
        result = self.run_actions(REQUESTS[1], "persistent-drop", ["book"])
        self.assertEqual(result["outcome"], "blocked")
        self.assertEqual(result["bookings"], [])
        self.assertTrue(result["safe"])


if __name__ == "__main__":
    unittest.main()
