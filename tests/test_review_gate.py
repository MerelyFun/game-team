import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("review_gate", ROOT / "tools/review_gate.py")
review_gate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(review_gate)


def example_packet():
    """Synthetic fixture only; never a real game review or completion claim."""
    binding = {"task_id": "synthetic-task", "round_id": "synthetic-round-2", "candidate_id": "synthetic-build-42"}
    ballots = [{
        "reviewer_id": reviewer,
        "role_version": "1.1",
        **binding,
        "evidence_ids": ["synthetic-play-recording"],
        "decision": "pass",
        "gate_answer": "yes",
        "gate_reason": "Synthetic test fixture, not a review of a game.",
    } for reviewer in review_gate.REVIEWERS]
    ballots[2].update(details_ready="yes", commercial_ready="yes")
    return {"schema_version": 1, **binding, "evidence_ids": ["synthetic-play-recording", "synthetic-screenshot"], "ballots": ballots}


class ReviewGateTest(unittest.TestCase):
    def setUp(self):
        self.packet = example_packet()

    def test_three_passes_and_two_passes_one_rejection_both_pass(self):
        result = review_gate.evaluate_packet(self.packet)
        self.assertEqual((result["quality_gate"], result["passed_count"]), ("passed", 3))
        self.packet["ballots"][0].update(decision="reject", gate_answer="no")
        result = review_gate.evaluate_packet(self.packet)
        self.assertEqual((result["quality_gate"], result["passed_count"]), ("passed", 2))
        self.assertEqual(result["non_pass"][0]["reviewer_id"], review_gate.REVIEWERS[0])

    def test_one_pass_fails_with_all_three_valid_ballots(self):
        self.packet["ballots"][0].update(decision="reject", gate_answer="no")
        self.packet["ballots"][1].update(decision="revise", gate_answer="yes")
        result = review_gate.evaluate_packet(self.packet)
        self.assertEqual((result["quality_gate"], result["passed_count"]), ("not_passed", 1))

    def test_all_three_ballots_are_required_even_with_two_passes(self):
        self.packet["ballots"].pop()
        with self.assertRaises(ValueError):
            review_gate.evaluate_packet(self.packet)

    def test_duplicate_or_unrecognized_reviewer_is_invalid(self):
        for replacement in (review_gate.REVIEWERS[0], "game-producer"):
            with self.subTest(replacement=replacement):
                packet = example_packet()
                packet["ballots"][1]["reviewer_id"] = replacement
                with self.assertRaises(ValueError):
                    review_gate.evaluate_packet(packet)

    def test_stale_task_round_or_candidate_cannot_supply_a_vote(self):
        for field in ("task_id", "round_id", "candidate_id"):
            with self.subTest(field=field):
                packet = example_packet()
                packet["ballots"][0][field] = "old-binding"
                with self.assertRaises(ValueError):
                    review_gate.evaluate_packet(packet)

    def test_old_or_malformed_role_versions_are_invalid(self):
        for version in ("1.0", 1.1, None, "", "  "):
            with self.subTest(version=version):
                packet = example_packet()
                packet["ballots"][0]["role_version"] = version
                with self.assertRaises(ValueError):
                    review_gate.evaluate_packet(packet)

    def test_unwilling_or_unknown_ten_yuan_answer_cannot_pass(self):
        for reviewer_index in (0, 1):
            for answer in ("no", "unknown"):
                with self.subTest(reviewer=reviewer_index, answer=answer):
                    packet = example_packet()
                    packet["ballots"][reviewer_index]["gate_answer"] = answer
                    with self.assertRaises(ValueError):
                        review_gate.evaluate_packet(packet)

    def test_no_and_unknown_answers_require_matching_non_pass_decisions(self):
        for answer, required in (("no", "reject"), ("unknown", "insufficient")):
            for decision in review_gate.DECISIONS:
                with self.subTest(answer=answer, decision=decision):
                    packet = example_packet()
                    packet["ballots"][0].update(gate_answer=answer, decision=decision)
                    if decision == required:
                        self.assertEqual(review_gate.evaluate_packet(packet)["passed_count"], 2)
                    else:
                        with self.assertRaises(ValueError):
                            review_gate.evaluate_packet(packet)

    def test_yes_can_still_be_a_non_pass_vote(self):
        for decision in ("revise", "reject", "insufficient"):
            with self.subTest(decision=decision):
                packet = example_packet()
                packet["ballots"][0]["decision"] = decision
                self.assertEqual(review_gate.evaluate_packet(packet)["passed_count"], 2)

    def test_screenshot_proven_player_rejection_can_precede_unknown_paid_answer(self):
        for reviewer_index in (0, 1):
            with self.subTest(reviewer=reviewer_index):
                packet = example_packet()
                packet["ballots"][reviewer_index].update(
                    decision="reject", gate_answer="unknown", hard_rejections=["V1"],
                    evidence_ids=["synthetic-screenshot"],
                )
                result = review_gate.evaluate_packet(packet)
                self.assertEqual((result["quality_gate"], result["passed_count"]), ("passed", 2))
                self.assertEqual(result["non_pass"][0]["hard_rejections"], ["V1"])

    def test_unknown_rejection_needs_proven_valid_hard_rejection_and_evidence(self):
        for rejections, evidence in (([], ["synthetic-screenshot"]), (["V1"], []), (["P10"], ["synthetic-screenshot"])):
            with self.subTest(rejections=rejections, evidence=evidence):
                packet = example_packet()
                packet["ballots"][0].update(
                    decision="reject", gate_answer="unknown", hard_rejections=rejections, evidence_ids=evidence,
                )
                with self.assertRaises(ValueError):
                    review_gate.evaluate_packet(packet)

    def test_hard_rejection_identifiers_are_typed_unique_and_role_specific(self):
        for reviewer_index, rejections in (
            (0, "V1"), (0, None), (0, [""]), (0, [None]), (0, ["V1", "V1"]),
            (0, ["A4"]), (2, ["V1"]), (2, ["A4", "A4"]),
        ):
            with self.subTest(reviewer=reviewer_index, rejections=rejections):
                packet = example_packet()
                packet["ballots"][reviewer_index].update(decision="reject", hard_rejections=rejections)
                with self.assertRaises(ValueError):
                    review_gate.evaluate_packet(packet)

    def test_proven_hard_rejection_never_allows_pass_revise_or_insufficient(self):
        for decision in ("pass", "revise", "insufficient"):
            with self.subTest(decision=decision):
                packet = example_packet()
                packet["ballots"][0].update(decision=decision, hard_rejections=["V1"])
                with self.assertRaises(ValueError):
                    review_gate.evaluate_packet(packet)
        self.packet["ballots"][0].update(decision="reject", gate_answer="no", hard_rejections=["V1"], evidence_ids=[])
        with self.assertRaises(ValueError):
            review_gate.evaluate_packet(self.packet)

    def test_screenshot_proven_art_rejection_can_precede_unknown_final_readiness(self):
        self.packet["ballots"][2].update(
            decision="reject", gate_answer="unknown", details_ready="unknown", commercial_ready="unknown",
            hard_rejections=["A4"], evidence_ids=["synthetic-screenshot"],
        )
        result = review_gate.evaluate_packet(self.packet)
        self.assertEqual((result["quality_gate"], result["passed_count"]), ("passed", 2))
        self.packet["ballots"][2]["evidence_ids"] = []
        with self.assertRaises(ValueError):
            review_gate.evaluate_packet(self.packet)

    def test_paid_hard_rejection_requires_explicit_unwilling_answer(self):
        self.packet["ballots"][0].update(decision="reject", gate_answer="no", hard_rejections=["P10"])
        self.assertEqual(review_gate.evaluate_packet(self.packet)["passed_count"], 2)
        for answer in ("yes", "unknown"):
            with self.subTest(answer=answer):
                packet = copy.deepcopy(self.packet)
                packet["ballots"][0]["gate_answer"] = answer
                with self.assertRaises(ValueError):
                    review_gate.evaluate_packet(packet)

    def test_commercial_hard_rejection_requires_one_negative_readiness_answer(self):
        for details, commercial, answer, valid in (
            ("unknown", "unknown", "unknown", False),
            ("yes", "unknown", "unknown", False),
            ("yes", "yes", "yes", False),
            ("no", "unknown", "no", True),
            ("yes", "no", "no", True),
        ):
            with self.subTest(details=details, commercial=commercial):
                packet = example_packet()
                packet["ballots"][2].update(
                    decision="reject", gate_answer=answer, details_ready=details, commercial_ready=commercial,
                    hard_rejections=["C1"],
                )
                if valid:
                    self.assertEqual(review_gate.evaluate_packet(packet)["passed_count"], 2)
                else:
                    with self.assertRaises(ValueError):
                        review_gate.evaluate_packet(packet)

    def test_each_art_subquestion_must_be_yes_to_pass(self):
        for field in ("details_ready", "commercial_ready"):
            for answer in ("no", "unknown"):
                with self.subTest(field=field, answer=answer):
                    packet = example_packet()
                    art = packet["ballots"][2]
                    art[field] = answer
                    art["gate_answer"] = answer
                    with self.assertRaises(ValueError):
                        review_gate.evaluate_packet(packet)

    def test_art_aggregate_no_precedes_unknown_and_must_match(self):
        art = self.packet["ballots"][2]
        art.update(details_ready="no", commercial_ready="unknown", gate_answer="no", decision="reject")
        self.assertEqual(review_gate.evaluate_packet(self.packet)["passed_count"], 2)
        art["gate_answer"] = "unknown"
        art["decision"] = "insufficient"
        with self.assertRaises(ValueError):
            review_gate.evaluate_packet(self.packet)

    def test_art_unknown_can_return_insufficient_but_not_pass(self):
        self.packet["ballots"][2].update(details_ready="unknown", gate_answer="unknown", decision="insufficient")
        result = review_gate.evaluate_packet(self.packet)
        self.assertEqual(result["passed_count"], 2)
        self.assertEqual(result["non_pass"][0]["decision"], "insufficient")

    def test_evidence_must_be_unique_non_empty_strings_and_within_packet(self):
        for evidence in (["not-supplied"], ["synthetic-play-recording"] * 2, [""], [None], "synthetic-play-recording", None):
            with self.subTest(evidence=evidence):
                packet = example_packet()
                packet["ballots"][0]["evidence_ids"] = evidence
                with self.assertRaises(ValueError):
                    review_gate.evaluate_packet(packet)

    def test_empty_evidence_allows_missing_evidence_ballot_but_never_pass(self):
        self.packet["ballots"][0]["evidence_ids"] = []
        with self.assertRaises(ValueError):
            review_gate.evaluate_packet(self.packet)
        self.packet["ballots"][0].update(decision="insufficient", gate_answer="unknown")
        self.assertEqual(review_gate.evaluate_packet(self.packet)["passed_count"], 2)

    def test_packet_evidence_is_required_unique_and_non_empty(self):
        for evidence in ([], ["synthetic-play-recording"] * 2, [" "], [4], {}, None):
            with self.subTest(evidence=evidence):
                packet = example_packet()
                packet["evidence_ids"] = evidence
                with self.assertRaises(ValueError):
                    review_gate.evaluate_packet(packet)

    def test_missing_or_wrong_type_fields_are_rejected_without_type_errors(self):
        invalid_changes = (
            ("schema_version", True), ("schema_version", "1"), ("schema_version", 1.0),
            ("task_id", []), ("round_id", None), ("candidate_id", "  "),
            ("ballots", {}), ("ballots", [None] * 3),
        )
        for field, value in invalid_changes:
            with self.subTest(field=field, value=value):
                packet = example_packet()
                packet[field] = value
                with self.assertRaises(ValueError):
                    review_gate.evaluate_packet(packet)
        for field, value in (("gate_reason", " "), ("gate_reason", 1), ("decision", []), ("gate_answer", True), ("reviewer_id", {})):
            with self.subTest(ballot_field=field, value=value):
                packet = example_packet()
                packet["ballots"][0][field] = value
                with self.assertRaises(ValueError):
                    review_gate.evaluate_packet(packet)
        for packet in (None, [], "packet"):
            with self.subTest(packet=packet):
                with self.assertRaises(ValueError):
                    review_gate.evaluate_packet(packet)

    def test_missing_required_fields_fail(self):
        for scope in ("packet", "ballot", "art"):
            fields = {
                "packet": ("schema_version", "task_id", "round_id", "candidate_id", "evidence_ids", "ballots"),
                "ballot": ("reviewer_id", "role_version", "task_id", "round_id", "candidate_id", "evidence_ids", "decision", "gate_answer", "gate_reason"),
                "art": ("details_ready", "commercial_ready"),
            }[scope]
            for field in fields:
                with self.subTest(scope=scope, field=field):
                    packet = example_packet()
                    target = packet if scope == "packet" else packet["ballots"][2 if scope == "art" else 0]
                    del target[field]
                    with self.assertRaises(ValueError):
                        review_gate.evaluate_packet(packet)

    def test_evaluation_does_not_modify_input(self):
        before = copy.deepcopy(self.packet)
        review_gate.evaluate_packet(self.packet)
        self.assertEqual(self.packet, before)

    def test_cli_exit_codes_are_distinct_and_always_emit_json(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "synthetic-packet.json"
            for expected, decision in ((0, "pass"), (1, "revise"), (2, "bad-decision")):
                with self.subTest(exit_code=expected):
                    packet = example_packet()
                    packet["ballots"][0]["decision"] = decision
                    packet["ballots"][1]["decision"] = decision
                    path.write_text(json.dumps(packet), encoding="utf-8")
                    result = subprocess.run([sys.executable, str(ROOT / "tools/review_gate.py"), str(path)], capture_output=True, text=True, encoding="utf-8", timeout=10)
                    self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
                    output = json.loads(result.stdout)
                    self.assertEqual(output["required"], 2)
                    self.assertEqual(output["reviewer_count"], 3)
                    self.assertIn("cannot prove", output["limitation"])
                    self.assertEqual(output["quality_gate"], {0: "passed", 1: "not_passed", 2: "invalid"}[expected])

    def test_cli_rejects_malformed_missing_and_duplicate_key_json(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "synthetic-packet.json"
            for content in ("not json", '{"schema_version":1,"schema_version":1}'):
                with self.subTest(content=content):
                    path.write_text(content, encoding="utf-8")
                    result = subprocess.run([sys.executable, str(ROOT / "tools/review_gate.py"), str(path)], capture_output=True, text=True, encoding="utf-8", timeout=10)
                    self.assertEqual(result.returncode, 2)
                    self.assertEqual(json.loads(result.stdout)["quality_gate"], "invalid")
            missing = Path(temporary) / "missing.json"
            result = subprocess.run([sys.executable, str(ROOT / "tools/review_gate.py"), str(missing)], capture_output=True, text=True, encoding="utf-8", timeout=10)
            self.assertEqual(result.returncode, 2)
            self.assertTrue(json.loads(result.stdout)["errors"])


if __name__ == "__main__":
    unittest.main()
