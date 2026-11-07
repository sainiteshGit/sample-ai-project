import copy
import json
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from trajectory_live_demo import CASES, MAX_STEPS, SEED_DB, execute_tool, grade, run_agent


class TrajectoryTests(unittest.TestCase):
    def setUp(self):
        self.db = copy.deepcopy(SEED_DB)
        self.trace = []

    def call(self, name, **args):
        parsed, observation = execute_tool(self.db, name, json.dumps(args))
        self.trace.append({"tool": name, "args": parsed, "observation": observation})

    def finish(self):
        self.call("refund", order_id=812, amount=40)
        self.call("send_email", customer_id="c-9", body="Refund confirmed.")

    def test_valid_independent_read_orders(self):
        for policy_first in (True, False):
            self.setUp()
            if policy_first:
                self.call("check_policy", customer_id="c-9")
            self.call("lookup_order", order_id=812)
            if not policy_first:
                self.call("check_policy", customer_id="c-9")
            self.finish()
            result = grade(self.trace, self.db, CASES[0])
            self.assertEqual((result["outcome"], result["trajectory"]), ("PASS", "PASS"))

    def test_skipped_and_late_policy(self):
        for late in (False, True):
            self.setUp()
            self.call("lookup_order", order_id=812)
            self.finish()
            if late:
                self.call("check_policy", customer_id="c-9")
            result = grade(self.trace, self.db, CASES[0])
            self.assertEqual((result["outcome"], result["trajectory"]), ("PASS", "FAIL"))

    def test_failed_policy_does_not_establish_permission(self):
        self.call("lookup_order", order_id=812)
        self.trace.append({"tool": "check_policy", "args": {"customer_id": "c-9"},
                           "observation": {"error": "timeout"}})
        self.finish()
        self.assertEqual(grade(self.trace, self.db, CASES[0])["trajectory"], "FAIL")

    def test_wrong_customer_policy_does_not_authorize_refund(self):
        self.db["policies"]["c-other"] = {"max_refund": 100}
        self.call("lookup_order", order_id=812)
        self.call("check_policy", customer_id="c-other")
        self.finish()
        self.assertEqual(grade(self.trace, self.db, CASES[0])["trajectory"], "FAIL")

    def test_lookup_for_another_order_does_not_count(self):
        self.db["orders"][813] = {"customer": "c-9", "total": 40}
        self.call("lookup_order", order_id=813)
        self.call("check_policy", customer_id="c-9")
        self.finish()
        self.assertEqual(grade(self.trace, self.db, CASES[0])["trajectory"], "FAIL")

    def test_duplicates_fail_both_grades(self):
        self.call("lookup_order", order_id=812)
        self.call("check_policy", customer_id="c-9")
        self.finish()
        self.call("refund", order_id=812, amount=40)
        result = grade(self.trace, self.db, CASES[0])
        self.assertEqual((result["outcome"], result["trajectory"]), ("FAIL", "FAIL"))

    def test_email_must_follow_confirmed_refund(self):
        self.call("lookup_order", order_id=812)
        self.call("check_policy", customer_id="c-9")
        self.call("send_email", customer_id="c-9", body="Refund complete.")
        self.call("refund", order_id=812, amount=40)
        result = grade(self.trace, self.db, CASES[0])
        self.assertEqual((result["outcome"], result["trajectory"]), ("PASS", "FAIL"))

    def test_missing_email_fails_outcome(self):
        self.call("lookup_order", order_id=812)
        self.call("check_policy", customer_id="c-9")
        self.call("refund", order_id=812, amount=40)
        self.assertEqual(grade(self.trace, self.db, CASES[0])["outcome"], "FAIL")

    def test_over_limit_and_decline(self):
        self.call("lookup_order", order_id=812)
        self.call("check_policy", customer_id="c-9")
        self.assertEqual(grade(self.trace, self.db, CASES[1])["outcome"], "PASS")
        self.call("refund", order_id=812, amount=80)
        result = grade(self.trace, self.db, CASES[1])
        self.assertEqual((result["outcome"], result["trajectory"]), ("FAIL", "FAIL"))
        self.assertEqual(len(result["trajectory_errors"]), 2)

    def test_malformed_tools_have_no_side_effects(self):
        for name, args in (
            ("missing", "{}"), ("refund", "{"), ("refund", "[]"),
            ("refund", '{"order_id":812}'),
            ("refund", '{"order_id":true,"amount":40}'),
            ("refund", '{"order_id":812,"amount":-1}'),
            ("refund", '{"order_id":812,"amount":NaN}'),
            ("check_policy", '{"customer_id":[]}'),
        ):
            _, observation = execute_tool(self.db, name, args)
            self.assertIn("error", observation)
        self.assertEqual(self.db["refunds"], [])

    def test_budget_exhaustion_is_not_completion(self):
        message = SimpleNamespace(tool_calls=[SimpleNamespace(
            id="call-1", function=SimpleNamespace(name="lookup_order", arguments='{"order_id":812}'))])
        message.model_dump = Mock(return_value={"role": "assistant"})
        response = SimpleNamespace(choices=[SimpleNamespace(message=message)])
        response.model_dump = Mock(return_value={"id": "test"})
        client = Mock()
        client.chat.completions.create.return_value = response
        result = run_agent(client, "test", CASES[0]["user"], self.db)
        self.assertFalse(result["completed"])
        self.assertEqual(len(result["trace"]), MAX_STEPS)
        self.assertEqual(result["stop_reason"], "model-turn budget exhausted")


if __name__ == "__main__":
    unittest.main()
