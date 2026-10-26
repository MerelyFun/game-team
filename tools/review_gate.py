"""Validate three independent reviewer ballots for one locked game candidate.

This checks the submitted packet, not the reviewers' actual independence or play.
It does not replace functional verification, platform checks, or other release gates.
"""

import argparse
import json
from pathlib import Path
import sys


REVIEWERS = (
    "douyin-male-player-reviewer",
    "douyin-female-player-reviewer",
    "independent-game-art-reviewer",
)
ROLE_VERSION = "1.1"
ART_REVIEWER = "independent-game-art-reviewer"
DECISIONS = frozenset(("pass", "revise", "reject", "insufficient"))
ANSWERS = frozenset(("yes", "no", "unknown"))
PLAYER_HARD_REJECTIONS = frozenset(("V1", "G1", "U1", "T1", "P10"))
ART_HARD_REJECTIONS = frozenset(("A1", "A2", "A3", "A4", "C1"))
LIMITATION = (
    "Validates ballot structure and decision rules only; cannot prove independent "
    "review or actual play, and does not replace other verification or platform gates."
)


def _require_string(value, field):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value


def _require_enum(value, allowed, field):
    if not isinstance(value, str) or value not in allowed:
        raise ValueError(f"{field} must be one of {', '.join(sorted(allowed))}")
    return value


def _evidence_ids(value, field, *, allow_empty):
    if not isinstance(value, list) or (not allow_empty and not value):
        raise ValueError(f"{field} must be {'a' if allow_empty else 'a non-empty'} list")
    identifiers = [_require_string(item, f"{field}[{index}]") for index, item in enumerate(value)]
    if len(set(identifiers)) != len(identifiers):
        raise ValueError(f"{field} must contain unique identifiers")
    return set(identifiers)


def _combined_art_answer(details, commercial):
    if "no" in (details, commercial):
        return "no"
    if "unknown" in (details, commercial):
        return "unknown"
    return "yes"


def evaluate_packet(packet):
    """Return a valid packet's gate result, or raise ValueError for invalid input.

    All three distinct roles must return current-version ballots bound to the
    same task, round, candidate and supplied evidence. Only ``decision=pass``
    counts; two passes and one rejection satisfy this quality gate.
    """
    if not isinstance(packet, dict):
        raise ValueError("packet must be an object")
    if type(packet.get("schema_version")) is not int or packet["schema_version"] != 1:
        raise ValueError("schema_version must be integer 1")
    binding = {
        field: _require_string(packet.get(field), field)
        for field in ("task_id", "round_id", "candidate_id")
    }
    available_evidence = _evidence_ids(packet.get("evidence_ids"), "evidence_ids", allow_empty=False)
    ballots = packet.get("ballots")
    if not isinstance(ballots, list) or len(ballots) != len(REVIEWERS):
        raise ValueError("ballots must contain exactly three reviewer ballots")

    seen = set()
    non_pass = []
    passed_count = 0
    for index, ballot in enumerate(ballots):
        prefix = f"ballots[{index}]"
        if not isinstance(ballot, dict):
            raise ValueError(f"{prefix} must be an object")
        reviewer = _require_enum(ballot.get("reviewer_id"), REVIEWERS, f"{prefix}.reviewer_id")
        if reviewer in seen:
            raise ValueError(f"duplicate reviewer_id: {reviewer}")
        seen.add(reviewer)
        if ballot.get("role_version") != ROLE_VERSION:
            raise ValueError(f"{prefix}.role_version must be {ROLE_VERSION!r}")
        for field, expected in binding.items():
            actual = _require_string(ballot.get(field), f"{prefix}.{field}")
            if actual != expected:
                raise ValueError(f"{prefix}.{field} does not match the packet")
        evidence = _evidence_ids(ballot.get("evidence_ids"), f"{prefix}.evidence_ids", allow_empty=True)
        if not evidence.issubset(available_evidence):
            raise ValueError(f"{prefix}.evidence_ids references evidence outside the packet")
        decision = _require_enum(ballot.get("decision"), DECISIONS, f"{prefix}.decision")
        answer = _require_enum(ballot.get("gate_answer"), ANSWERS, f"{prefix}.gate_answer")
        reason = _require_string(ballot.get("gate_reason"), f"{prefix}.gate_reason")
        hard_rejections = ballot.get("hard_rejections", [])
        if not isinstance(hard_rejections, list):
            raise ValueError(f"{prefix}.hard_rejections must be a list")
        allowed_rejections = ART_HARD_REJECTIONS if reviewer == ART_REVIEWER else PLAYER_HARD_REJECTIONS
        for rejection_index, rejection in enumerate(hard_rejections):
            _require_enum(rejection, allowed_rejections, f"{prefix}.hard_rejections[{rejection_index}]")
        if len(set(hard_rejections)) != len(hard_rejections):
            raise ValueError(f"{prefix}.hard_rejections must contain unique identifiers")
        if hard_rejections and (decision != "reject" or not evidence):
            raise ValueError(f"{prefix}: proven hard_rejections require decision=reject and non-empty evidence_ids")
        if "P10" in hard_rejections and answer != "no":
            raise ValueError(f"{prefix}: P10 requires gate_answer=no")

        if reviewer == ART_REVIEWER:
            details = _require_enum(ballot.get("details_ready"), ANSWERS, f"{prefix}.details_ready")
            commercial = _require_enum(ballot.get("commercial_ready"), ANSWERS, f"{prefix}.commercial_ready")
            if answer != _combined_art_answer(details, commercial):
                raise ValueError(f"{prefix}.gate_answer does not match the two art readiness answers")
            if "C1" in hard_rejections and "no" not in (details, commercial):
                raise ValueError(f"{prefix}: C1 requires at least one art readiness answer=no")

        if answer == "no" and decision != "reject":
            raise ValueError(f"{prefix}: gate_answer=no requires decision=reject")
        if answer == "unknown" and decision != "insufficient" and not (decision == "reject" and hard_rejections):
            raise ValueError(f"{prefix}: gate_answer=unknown requires decision=insufficient or an evidenced hard rejection")
        if decision == "pass":
            if answer != "yes" or not evidence:
                raise ValueError(f"{prefix}: pass requires gate_answer=yes and non-empty evidence_ids")
            passed_count += 1
        else:
            non_pass.append({
                "reviewer_id": reviewer,
                "decision": decision,
                "gate_answer": answer,
                "gate_reason": reason,
                "hard_rejections": list(hard_rejections),
            })

    return {
        "quality_gate": "passed" if passed_count >= 2 else "not_passed",
        "passed_count": passed_count,
        "required": 2,
        "reviewer_count": len(REVIEWERS),
        **binding,
        "non_pass": non_pass,
        "limitation": LIMITATION,
    }


def _reject_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON object key: {key}")
        result[key] = value
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("packet", type=Path, help="JSON packet containing all three ballots")
    arguments = parser.parse_args(argv)
    try:
        packet = json.loads(arguments.packet.read_text(encoding="utf-8-sig"), object_pairs_hook=_reject_duplicate_keys)
        result = evaluate_packet(packet)
    except (OSError, UnicodeError, ValueError) as error:
        result = {
            "quality_gate": "invalid",
            "passed_count": None,
            "required": 2,
            "reviewer_count": len(REVIEWERS),
            "errors": [str(error)],
            "limitation": LIMITATION,
        }
        exit_code = 2
    else:
        exit_code = 0 if result["quality_gate"] == "passed" else 1
    # ASCII JSON stays valid across Windows console code pages and UTF-8 pipes.
    print(json.dumps(result, ensure_ascii=True))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
