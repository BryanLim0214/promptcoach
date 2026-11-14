"""The guided walkthrough script must stay the verified worked example.

The tour is what a committee watches. If its script drifts from the example the
rest of the suite verifies - a reworded prompt, a different task - then the
demonstration would be showing something nobody has checked, and it would drift
silently because TypeScript and Python are not compiled together.

So these read the actual strings out of `web/src/tour.ts` and run them through
the real API.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from promptcoach_ref.api import app
from promptcoach_ref.policy import taskbank

from conftest import WORKED_SPOKEN, WORKED_TYPED

pytestmark = pytest.mark.tour

TOUR_TS = Path(__file__).resolve().parent.parent / "web" / "src" / "tour.ts"
client = TestClient(app)


def const(name: str) -> str:
    """Pull an exported string constant out of tour.ts.

    Handles the `"a" + "b"` concatenation the file uses to stay inside the line
    length, which is why this is not a one-line regex.
    """
    source = TOUR_TS.read_text(encoding="utf-8")
    match = re.search(
        rf"export const {name} =\s*(.+?);\s*$", source, re.S | re.M
    )
    assert match, f"{name} not found in tour.ts"
    body = match.group(1)
    parts = re.findall(r'"((?:[^"\\]|\\.)*)"', body)
    return "".join(p.replace('\\"', '"') for p in parts)


def test_the_tour_file_exists():
    assert TOUR_TS.exists(), "the walkthrough script is part of the deliverable"


def test_the_tour_uses_the_thesis_worked_example_task():
    source = TOUR_TS.read_text(encoding="utf-8")
    assert 'taskId: "b3-babysitting"' in source
    assert taskbank.BY_ID["b3-babysitting"].from_thesis is True


def test_the_tour_strings_match_the_verified_example():
    """Identical to what test_worked_example.py asserts against Chapter 11."""
    assert const("WORKED_INTENT") == WORKED_SPOKEN
    assert const("WORKED_PROMPT") == WORKED_TYPED


def test_the_revision_carries_a_stated_reason():
    """Without one the revision is not scored, and the tour would stall."""
    reason = const("WORKED_REASON")
    assert len("".join(reason.split())) >= 10


def test_the_tour_sets_a_predicted_rating():
    source = TOUR_TS.read_text(encoding="utf-8")
    assert "WORKED_PREDICTION" in source


def test_the_revision_puts_back_what_she_said_aloud():
    """The revision has to restore the dropped threads, or the comparison step
    shows nothing and the whole demonstration falls flat."""
    revision = const("WORKED_REVISION")
    assert "seven year old" in revision  # the reader
    assert "few sentences" in revision  # the length


def test_the_scripted_walkthrough_runs_end_to_end():
    session = client.post(
        "/api/session", json={"platform_use": True, "task_id": "b3-babysitting"}
    ).json()
    sid = session["session_id"]

    first = client.post(
        f"/api/session/{sid}/submit",
        json={
            "stated_intent": const("WORKED_INTENT"),
            "prompt_text": const("WORKED_PROMPT"),
            "intent_modality": "typed",
        },
    ).json()

    # Step "read" needs an answer to read.
    assert first["answer"] is not None and first["answer"]["text"].strip()
    # Step "coach" needs a question to show.
    assert first["respond"] is not None
    assert first["respond"]["level"] == 1
    assert first["diagnose"]["target"] == "intent_drift"

    second = client.post(
        f"/api/session/{sid}/submit",
        json={
            "stated_intent": const("WORKED_INTENT"),
            "prompt_text": const("WORKED_REVISION"),
            "parent_attempt_id": first["elicit"]["record"]["attempt_id"],
            "revision_reason": const("WORKED_REASON"),
        },
    ).json()

    assert second["stopped_at"] == "calibrate", second.get("clarification")
    # Step "compare" needs both sides.
    assert second["previous_answer"] is not None
    assert second["previous_prompt"] == const("WORKED_PROMPT")
    assert second["answer"]["text"] != second["previous_answer"]["text"]


def test_every_step_kind_in_the_script_is_one_the_component_handles():
    """A typo in a step kind would silently do nothing at that step."""
    source = TOUR_TS.read_text(encoding="utf-8")
    declared = set(re.findall(r'kind: "([a-z-]+)"', source))
    handled = {
        "pick",
        "type-intent",
        "type-prompt",
        "predict",
        "submit",
        "read",
        "coach",
        "type-revision",
        "type-reason",
        "compare",
        "done",
    }
    assert declared <= handled, declared - handled


def test_the_script_ends_on_the_done_step():
    source = TOUR_TS.read_text(encoding="utf-8")
    kinds = re.findall(r'kind: "([a-z-]+)"', source)
    assert kinds[-1] == "done"
    assert kinds.count("done") == 1


def test_every_step_carries_a_caption():
    """The rail is the only narration; a step without one is a blank screen."""
    source = TOUR_TS.read_text(encoding="utf-8")
    steps = re.findall(r"\{\s*kind: \"[a-z-]+\",(.*?)\n  \},", source, re.S)
    assert len(steps) >= 8
    for body in steps:
        assert "caption:" in body
