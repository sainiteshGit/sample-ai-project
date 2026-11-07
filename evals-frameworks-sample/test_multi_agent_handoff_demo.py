import json
from contextlib import closing, redirect_stdout
from io import StringIO
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from multi_agent_handoff_demo import (
    EXPECTED_ASSIGNMENT,
    EXPECTED_HANDOFF,
    MAX_ROUTER_TURNS,
    deliver_handoff,
    execute_tool,
    grade_run,
    new_database,
    print_result,
    print_summary,
    run_intake,
    run_router,
    run_scenario,
)


def tool_call(name, args, call_id="call-1"):
    return SimpleNamespace(
        id=call_id,
        function=SimpleNamespace(name=name, arguments=json.dumps(args)),
    )


def response(content=None, calls=None, finish_reason="stop", refusal=None):
    message = SimpleNamespace(content=content, tool_calls=calls, refusal=refusal)
    message.model_dump = Mock(return_value={
        "role": "assistant",
        "content": content,
        "tool_calls": [
            {
                "id": call.id,
                "type": "function",
                "function": {
                    "name": call.function.name,
                    "arguments": call.function.arguments,
                },
            }
            for call in calls or []
        ],
    })
    result = SimpleNamespace(
        choices=[SimpleNamespace(message=message, finish_reason=finish_reason)]
    )
    result.model_dump = Mock(return_value={"test_response": True})
    return result


def intake_result(handoff):
    return {
        "handoff": dict(handoff),
        "raw": json.dumps(handoff),
        "error": None,
        "response": {},
    }


def router_client(handoff, team):
    client = Mock()
    client.chat.completions.create.side_effect = [
        response(
            calls=[tool_call("lookup_oncall_owner", {"service": handoff["service"]})],
            finish_reason="tool_calls",
        ),
        response(
            calls=[tool_call("assign_incident", {**handoff, "team": team}, "call-2")],
            finish_reason="tool_calls",
        ),
        response(content="Assignment confirmed."),
    ]
    return client


def statuses(result):
    return {name: grade["status"] for name, grade in result["grades"].items()}


class MultiAgentHandoffTests(unittest.TestCase):
    def test_baseline_grades_all_layers_from_realistic_tool_trace(self):
        client = router_client(EXPECTED_HANDOFF, "payments-oncall")
        result = run_scenario(client, "test-model", "baseline", intake_result(EXPECTED_HANDOFF), 1)

        self.assertEqual(statuses(result), {
            "intake": "PASS",
            "handoff_preserved": "PASS",
            "handoff_correct": "PASS",
            "router": "PASS",
            "outcome": "PASS",
        })
        self.assertEqual(result["assignments"], [EXPECTED_ASSIGNMENT])
        first_messages = client.chat.completions.create.call_args_list[0].kwargs["messages"]
        self.assertEqual(json.loads(first_messages[1]["content"]), EXPECTED_HANDOFF)

    def test_changed_handoff_can_pass_router_but_fail_outcome(self):
        incoming = {**EXPECTED_HANDOFF, "service": "catalog-api"}
        client = router_client(incoming, "catalog-oncall")
        result = run_scenario(client, "test-model", "swap-service", intake_result(EXPECTED_HANDOFF), 1)

        self.assertEqual(statuses(result), {
            "intake": "PASS",
            "handoff_preserved": "FAIL",
            "handoff_correct": "FAIL",
            "router": "PASS",
            "outcome": "FAIL",
        })
        self.assertEqual(result["incoming"], incoming)
        self.assertEqual(result["assignments"][0]["team"], "catalog-oncall")
        self.assertIn("service", result["grades"]["handoff_preserved"]["reasons"][0])

    def test_unchanged_wrong_extraction_is_preserved_but_not_correct(self):
        wrong = {**EXPECTED_HANDOFF, "service": "catalog-api"}
        result = run_scenario(
            router_client(wrong, "catalog-oncall"), "test-model", "baseline", intake_result(wrong), 1
        )

        self.assertEqual(statuses(result), {
            "intake": "FAIL",
            "handoff_preserved": "PASS",
            "handoff_correct": "FAIL",
            "router": "PASS",
            "outcome": "FAIL",
        })

    def test_changing_a_wrong_extraction_can_accidentally_fix_the_outcome(self):
        wrong = {**EXPECTED_HANDOFF, "service": "catalog-api"}
        result = run_scenario(
            router_client(EXPECTED_HANDOFF, "payments-oncall"),
            "test-model",
            "swap-service",
            intake_result(wrong),
            1,
        )

        self.assertEqual(statuses(result), {
            "intake": "FAIL",
            "handoff_preserved": "FAIL",
            "handoff_correct": "PASS",
            "router": "PASS",
            "outcome": "PASS",
        })

    def test_delivery_does_not_mutate_sender_or_other_fields(self):
        outgoing = dict(EXPECTED_HANDOFF)
        incoming = deliver_handoff(outgoing, "swap-service")
        self.assertEqual(outgoing, EXPECTED_HANDOFF)
        self.assertEqual(incoming["incident_id"], outgoing["incident_id"])
        self.assertEqual(incoming["severity"], outgoing["severity"])
        self.assertNotEqual(incoming["service"], outgoing["service"])
        with self.assertRaises(ValueError):
            deliver_handoff(outgoing, "unknown")

    def test_assigning_without_lookup_can_get_right_outcome_but_fails_router(self):
        client = Mock()
        client.chat.completions.create.side_effect = [
            response(
                calls=[tool_call("assign_incident", EXPECTED_ASSIGNMENT)],
                finish_reason="tool_calls",
            ),
            response(content="Done."),
        ]
        result = run_scenario(client, "test-model", "baseline", intake_result(EXPECTED_HANDOFF), 1)

        self.assertEqual(result["grades"]["outcome"]["status"], "PASS")
        self.assertEqual(result["grades"]["router"]["status"], "FAIL")
        self.assertIn("observed lookup", " ".join(result["grades"]["router"]["reasons"]))

    def test_lookup_and_assignment_in_same_model_turn_are_not_observed_in_order(self):
        client = Mock()
        client.chat.completions.create.side_effect = [
            response(
                calls=[
                    tool_call("lookup_oncall_owner", {"service": "payments-api"}, "lookup"),
                    tool_call("assign_incident", EXPECTED_ASSIGNMENT, "assign"),
                ],
                finish_reason="tool_calls",
            ),
            response(content="Done."),
        ]
        result = run_scenario(client, "test-model", "baseline", intake_result(EXPECTED_HANDOFF), 1)

        self.assertEqual(result["grades"]["outcome"]["status"], "PASS")
        self.assertEqual(result["grades"]["router"]["status"], "FAIL")
        self.assertIn("observed lookup", " ".join(result["grades"]["router"]["reasons"]))

    def test_lookup_for_another_service_does_not_authorize_assignment(self):
        client = Mock()
        client.chat.completions.create.side_effect = [
            response(
                calls=[tool_call("lookup_oncall_owner", {"service": "catalog-api"})],
                finish_reason="tool_calls",
            ),
            response(
                calls=[tool_call("assign_incident", EXPECTED_ASSIGNMENT)],
                finish_reason="tool_calls",
            ),
            response(content="Done."),
        ]
        result = run_scenario(client, "test-model", "baseline", intake_result(EXPECTED_HANDOFF), 1)

        self.assertEqual(result["grades"]["router"]["status"], "FAIL")
        self.assertEqual(result["grades"]["outcome"]["status"], "PASS")

    def test_assignment_must_match_received_incident(self):
        changed = {**EXPECTED_ASSIGNMENT, "incident_id": "INC-9999"}
        client = Mock()
        client.chat.completions.create.side_effect = [
            response(
                calls=[tool_call("lookup_oncall_owner", {"service": "payments-api"})],
                finish_reason="tool_calls",
            ),
            response(calls=[tool_call("assign_incident", changed)], finish_reason="tool_calls"),
            response(content="Done."),
        ]
        result = run_scenario(client, "test-model", "baseline", intake_result(EXPECTED_HANDOFF), 1)

        self.assertEqual(result["grades"]["router"]["status"], "FAIL")
        self.assertEqual(result["grades"]["outcome"]["status"], "FAIL")
        self.assertIn("incident_id", " ".join(result["grades"]["router"]["reasons"]))

    def test_duplicate_assignment_is_reported_and_not_stored_twice(self):
        client = Mock()
        client.chat.completions.create.side_effect = [
            response(
                calls=[tool_call("lookup_oncall_owner", {"service": "payments-api"})],
                finish_reason="tool_calls",
            ),
            response(
                calls=[tool_call("assign_incident", EXPECTED_ASSIGNMENT)],
                finish_reason="tool_calls",
            ),
            response(
                calls=[tool_call("assign_incident", EXPECTED_ASSIGNMENT)],
                finish_reason="tool_calls",
            ),
            response(content="Done."),
        ]
        result = run_scenario(client, "test-model", "baseline", intake_result(EXPECTED_HANDOFF), 1)

        self.assertEqual(result["assignments"], [EXPECTED_ASSIGNMENT])
        self.assertEqual(result["grades"]["outcome"]["status"], "PASS")
        self.assertEqual(result["grades"]["router"]["status"], "FAIL")
        self.assertIn("already has an assignment", " ".join(result["grades"]["router"]["reasons"]))

    def test_invalid_tool_calls_do_not_change_database(self):
        with closing(new_database()) as db:
            for name, args in (
                ("unknown", "{}"),
                ("lookup_oncall_owner", "{"),
                ("lookup_oncall_owner", "[]"),
                ("lookup_oncall_owner", '{"service": true}'),
                ("lookup_oncall_owner", '{"service": "payments-api", "extra": 1}'),
                ("assign_incident", '{"incident_id": "INC-4821"}'),
                ("assign_incident", json.dumps({**EXPECTED_ASSIGNMENT, "severity": "SEV9"})),
                ("assign_incident", json.dumps({**EXPECTED_ASSIGNMENT, "team": "catalog-oncall"})),
            ):
                _, observation = execute_tool(db, name, args)
                self.assertIn("error", observation, name)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM assignments").fetchone()[0], 0)

    def test_intake_validation_and_refusals_stop_the_router(self):
        for model_response in (
            response(content="{"),
            response(content=json.dumps({**EXPECTED_HANDOFF, "extra": "unexpected"})),
            response(content=json.dumps({**EXPECTED_HANDOFF, "incident_id": 4821})),
            response(content=json.dumps(EXPECTED_HANDOFF), finish_reason="length"),
            response(refusal="Cannot comply."),
        ):
            intake_client = Mock()
            intake_client.chat.completions.create.return_value = model_response
            intake = run_intake(intake_client, "test-model")
            router = Mock()
            result = run_scenario(router, "test-model", "baseline", intake, 1)

            self.assertIsNone(intake["handoff"])
            self.assertTrue(intake["error"])
            self.assertIsNone(result["router"])
            router.chat.completions.create.assert_not_called()
            self.assertEqual(statuses(result), {
                "intake": "FAIL",
                "handoff_preserved": "NOT RUN",
                "handoff_correct": "NOT RUN",
                "router": "NOT RUN",
                "outcome": "FAIL",
            })

    def test_incomplete_routing_is_not_counted_as_success(self):
        client = Mock()
        client.chat.completions.create.return_value = response(
            calls=[tool_call("lookup_oncall_owner", {"service": "payments-api"})],
            finish_reason="tool_calls",
        )
        with closing(new_database()) as db:
            router = run_router(client, "test-model", EXPECTED_HANDOFF, db)
            grades = grade_run(intake_result(EXPECTED_HANDOFF), EXPECTED_HANDOFF, router, [])
        self.assertFalse(router["completed"])
        self.assertEqual(len(router["trace"]), MAX_ROUTER_TURNS)
        self.assertEqual(router["stop_reason"], "model-turn budget exhausted")
        self.assertEqual(grades["router"]["status"], "FAIL")
        self.assertEqual(grades["outcome"]["status"], "FAIL")

    def test_summary_exposes_not_run_stages(self):
        intake = {"handoff": None, "raw": None, "error": "invalid", "response": {}}
        result = run_scenario(Mock(), "test-model", "baseline", intake, 1)
        output = StringIO()
        with redirect_stdout(output):
            print_summary([result], ["baseline"])
        self.assertIn("Handoff preserved: 0/0; 1 not run", output.getvalue())

    def test_terminal_displays_router_response_as_ungraded(self):
        result = run_scenario(
            router_client(EXPECTED_HANDOFF, "payments-oncall"),
            "test-model",
            "baseline",
            intake_result(EXPECTED_HANDOFF),
            1,
        )
        output = StringIO()
        with redirect_stdout(output):
            print_result(result)
        self.assertIn('Router response (not graded): "Assignment confirmed."', output.getvalue())


if __name__ == "__main__":
    unittest.main()
