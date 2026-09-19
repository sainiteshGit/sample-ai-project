import unittest
from unittest.mock import patch

from fault_injection_demo import Environment, REQUESTS, run_case


class FaultInjectionTests(unittest.TestCase):
    def run_actions(self, request, scenario, actions):
        with patch("fault_injection_demo.decide", side_effect=actions):
            return run_case(None, "test", request, scenario)

    def test_baseline_booking_and_decline(self):
        for request, action, count in ((REQUESTS[0], "decline", 0), (REQUESTS[1], "book", 1)):
            result = self.run_actions(request, "baseline", [action])
            self.assertTrue(result["safe"])
            self.assertTrue(result["completed"])
            self.assertIsNone(result["recovered"])
            self.assertEqual(len(result["bookings"]), count)

    def test_transient_fault_recovers(self):
        for request, action in ((REQUESTS[0], "decline"), (REQUESTS[1], "book")):
            result = self.run_actions(request, "transient-drop", ["retry", action])
            self.assertTrue(result["recovered"])
            self.assertTrue(result["completed"])
            events = [e for e in result["trace"] if e["stage"] == "availability_handoff"]
            self.assertIsNone(events[0]["delivered"])
            self.assertEqual(events[1]["delivered"], events[1]["source"])

    def test_persistent_drop_stops_safely(self):
        for request in REQUESTS:
            result = self.run_actions(request, "persistent-drop", ["retry", "stop"])
            self.assertTrue(result["safe"])
            self.assertFalse(result["completed"])
            self.assertFalse(result["recovered"])
            self.assertEqual(result["bookings"], [])

    def test_booking_without_permission_is_blocked(self):
        for request in REQUESTS:
            result = self.run_actions(request, "persistent-drop", ["book"])
            self.assertEqual(result["outcome"], "blocked")
            self.assertTrue(result["safe"])
            self.assertFalse(result["completed"])
        result = self.run_actions(REQUESTS[0], "baseline", ["book"])
        self.assertEqual(result["outcome"], "blocked")

    def test_mismatched_request_is_blocked(self):
        env = Environment(REQUESTS[1], "baseline")
        env.lookup()
        env.delivered["request"]["party_size"] = 3
        self.assertFalse(env.book())
        self.assertEqual(env.bookings, [])

    def test_unsupported_decline_is_not_completion(self):
        result = self.run_actions(REQUESTS[0], "persistent-drop", ["decline"])
        self.assertFalse(result["completed"])
        self.assertEqual(result["outcome"], "unverified_decline")

    def test_retry_budget_and_invalid_response(self):
        result = self.run_actions(REQUESTS[1], "persistent-drop", ["retry", "retry"])
        self.assertEqual(result["lookups"], 2)
        self.assertEqual(result["outcome"], "retry_limit")
        result = self.run_actions(REQUESTS[1], "baseline", [ValueError("Invalid JSON")])
        self.assertEqual(result["model_error"], "Invalid JSON")
        self.assertFalse(result["completed"])
        self.assertEqual(result["bookings"], [])


if __name__ == "__main__":
    unittest.main()
