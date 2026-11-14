"""Third review round (review/FINDINGS_LOG_R3.md E01, E02; R3_CHAIR.md C1),
and the blind-acceptance bug found by the Layers 3-4 run
(eval/results/layers34-20261024-141743.md), made executable.

E01: help escalates across revisions of the same task while the top-ranked
category persists. Before this, a revision closed the cycle and reset the
level, so in the student's session help never rose above level 1.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import httpx
import pytest

from promptcoach_ref import policy
from promptcoach_ref.engines import DeterministicEngine
from promptcoach_ref.engines.base import DiagnosisRequest, EngineError
from promptcoach_ref.engines.gemini import GeminiEngine
from promptcoach_ref.framework import ladder, sentinel
from promptcoach_ref.framework.contracts import CalibrateInput, PairedRecord
from promptcoach_ref.framework.taxonomy import Category
from promptcoach_ref.layers import CalibrateLayer
from promptcoach_ref.policy import escalation, revision as revision_policy
from promptcoach_ref.session import Session, Stage

ROOT = Path(__file__).resolve().parent.parent

# A non-evaluative diagnosis (under-specification, paired with the four
# planning dimensions). Each revision changes the words and adds no planning
# dimension, so the category stays first and the paired dimension does not rise.
VOLCANO_PLAN = "I want to learn about volcanoes"
VOLCANO = [
    "explain volcanoes",
    "explain how volcanoes work",
    "explain about volcanoes and lava",
    "explain volcanoes and how they erupt",
]
REASON = "I changed the wording of it"

# An evaluative diagnosis (delegated judgment, paired with Reflection only).
ESSAY_PLAN = "I want an essay plan for class about my book"
ESSAY = [
    "Help me plan an essay about my favourite book for my English class, "
    "three paragraphs long, whatever you think is best",
    "Help me plan an essay about my favourite book for my English class, "
    "three paragraphs long, whatever you think is best overall",
    "Help me plan an essay about my favourite novel for my English class, "
    "three paragraphs long, whatever you think is best overall",
    "Help me plan an essay on my favourite novel for my English class, "
    "three paragraphs long, whatever you think is best overall",
]


def _session(consent, task_id: str, **kw) -> Session:
    s = Session(session_id="r3", consent=consent, engine=DeterministicEngine(), **kw)
    s.task_id = task_id
    return s


def _chain(s: Session, plan: str, prompts: list[str], asks=None):
    """A first attempt, then each later prompt as a reasoned revision of the
    one before, through Session.submit with parent_attempt_id."""
    out = []
    parent = None
    for i, p in enumerate(prompts):
        r = s.submit(
            stated_intent=plan,
            prompt_text=p,
            parent_attempt_id=parent,
            revision_reason=REASON if parent else None,
            asked_for_help=bool(asks and asks[i]),
        )
        out.append(r)
        parent = r.elicit.record.attempt_id
    return out


# ---------------------------------------------------------------------------
# E01 - the ladder climbs across revisions
# ---------------------------------------------------------------------------


@pytest.mark.mechanism
def test_attempt_and_three_revisions_reach_the_worked_contrast(consent):
    """C1's acceptance test. Attempt -> revision -> revision -> revision, all
    through Session.submit with parent_attempt_id, a non-evaluative category
    ranked first throughout: help goes 1, 2, 3, 4, and level 4 is the worked
    contrast."""
    s = _session(consent, "b1-audience")
    results = _chain(s, VOLCANO_PLAN, VOLCANO)

    assert [r.elicit.record.is_revision for r in results] == [False, True, True, True]
    assert all(r.diagnose.target is Category.UNDER_SPECIFICATION for r in results)
    assert all(r.stopped_at is Stage.RESPOND for r in results)
    assert [r.respond.level for r in results] == [1, 2, 3, 4]
    assert s.levels_issued == (1, 2, 3, 4)

    # Layer 5 measured every revision against its parent before Layer 4 ran.
    assert results[0].calibrate is None
    for r in results[1:]:
        assert r.calibrate is not None
        assert r.calibrate.paired_delta is not None and r.calibrate.paired_delta <= 0
    assert [step.layer for step in results[1].trace.steps][-2:] == ["calibrate", "respond"]

    # The escalation reason is the same-top count, not the responses issued.
    assert "2 consecutive attempts" in results[1].respond.selection_reason

    top = results[-1].respond
    assert top.level == ladder.TERMINAL_LEVEL
    assert re.search(r"\bA\.\s.+\bB\.\s", top.text, re.S), "not a worked contrast"
    assert top.used_template_floor in (True, False)


@pytest.mark.mechanism
def test_the_attempt_after_level_four_closes_the_cycle_and_records_it(consent):
    """escalation.after_terminal: level 4 is not repeated. The next revision is
    measured by Layer 5, the cycle closes, and the category is recorded as
    unresolved because the paired dimension did not rise."""
    s = _session(consent, "b1-audience")
    results = _chain(s, VOLCANO_PLAN, VOLCANO + ["explain volcanoes and what they do"])
    last = results[-1]
    assert last.stopped_at is Stage.CALIBRATE
    assert last.respond is None
    assert "level 4" in last.help_cycle
    assert s.levels_issued == ()
    assert s.unresolved == [("b1-audience", "under_specification")]


@pytest.mark.mechanism
def test_an_improved_paired_dimension_closes_the_cycle(consent):
    s = _session(consent, "b1-audience")
    first, second = _chain(
        s, VOLCANO_PLAN, ["explain volcanoes", "explain volcanoes for my little brother"]
    )
    assert first.respond.level == 1
    assert second.stopped_at is Stage.CALIBRATE
    assert second.respond is None
    assert second.help_cycle == "closed: the paired dimension improved"
    assert s.levels_issued == ()


@pytest.mark.mechanism
def test_asking_for_help_keeps_an_improved_cycle_open_and_climbs(consent):
    s = _session(consent, "b1-audience")
    first, second = _chain(
        s,
        VOLCANO_PLAN,
        ["explain volcanoes", "explain volcanoes for my little brother"],
        asks=[False, True],
    )
    assert second.stopped_at is Stage.RESPOND
    assert second.respond.level == 2
    assert "asked" in second.respond.selection_reason


@pytest.mark.mechanism
def test_an_evaluative_category_stays_put_across_revisions(consent):
    """D03 inside the new cycle: delegated judgment is paired with Reflection
    only, so the same-top count does not move help. Four attempts, four
    level 1 responses."""
    s = _session(consent, "b5-standard-first")
    results = _chain(s, ESSAY_PLAN, ESSAY)
    assert all(r.diagnose.target is Category.DELEGATED_JUDGMENT for r in results)
    assert [r.respond.level for r in results] == [1, 1, 1, 1]
    assert "evaluative" in results[-1].respond.selection_reason


@pytest.mark.mechanism
def test_an_evaluative_category_moves_up_when_she_asks(consent):
    s = _session(consent, "b5-standard-first")
    results = _chain(s, ESSAY_PLAN, ESSAY, asks=[False, False, False, True])
    assert [r.respond.level for r in results] == [1, 1, 1, 2]
    assert "asked" in results[-1].respond.selection_reason


@pytest.mark.mechanism
def test_a_new_task_starts_the_ladder_and_the_count_again(consent):
    s = _session(consent, "b1-audience")
    _chain(s, VOLCANO_PLAN, VOLCANO[:3])
    assert s.levels_issued == (1, 2, 3)
    moved, _ = s.move_to("b1-reading-level")
    assert moved
    assert s.levels_issued == () and s.cycle_category is None
    r = s.submit(stated_intent=VOLCANO_PLAN, prompt_text="explain volcanoes")
    assert r.respond.level == 1


# ---------------------------------------------------------------------------
# E01 - the revision hold and the ladder, together
# ---------------------------------------------------------------------------


@pytest.mark.mechanism
def test_the_first_reasoned_revision_releases_the_hold_while_help_keeps_climbing(consent):
    s = _session(consent, "b1-audience")
    first, second = _chain(s, VOLCANO_PLAN, VOLCANO[:2])
    assert first.revision_pending is True
    assert second.revision_pending is False  # the hold is satisfied ...
    assert second.respond.level == 2  # ... and the help cycle is still open
    assert s.move_to("b1-reading-level")[0] is True


@pytest.mark.mechanism
def test_an_unreasoned_revision_neither_raises_nor_resets_help(consent):
    s = _session(consent, "b1-audience")
    first = s.submit(stated_intent=VOLCANO_PLAN, prompt_text=VOLCANO[0])
    pid = first.elicit.record.attempt_id
    held = s.submit(
        stated_intent=VOLCANO_PLAN, prompt_text=VOLCANO[1], parent_attempt_id=pid
    )
    assert held.stopped_at is Stage.ELICIT
    assert held.clarification
    assert s.levels_issued == (1,)

    reasoned = s.submit(
        stated_intent=VOLCANO_PLAN,
        prompt_text=VOLCANO[1],
        parent_attempt_id=pid,
        revision_reason=REASON,
    )
    assert reasoned.respond.level == 2  # one rung, not two


@pytest.mark.mechanism
def test_the_hold_auto_release_leaves_the_ladder_where_it_was(consent):
    """Four attempts on a task release the hold (policy revision.exit); the
    three unreasoned revisions were never scored, so help is still level 1 and
    the next reasoned revision climbs one rung."""
    s = _session(consent, "b1-audience")
    first = s.submit(stated_intent=VOLCANO_PLAN, prompt_text=VOLCANO[0])
    pid = first.elicit.record.attempt_id
    for p in VOLCANO[1:]:
        r = s.submit(stated_intent=VOLCANO_PLAN, prompt_text=p, parent_attempt_id=pid)
        assert r.stopped_at is Stage.ELICIT
    assert s.attempts_on_task["b1-audience"] == revision_policy.EXIT_AFTER_ATTEMPTS
    assert s.revision_pending is False
    assert s.levels_issued == (1,)
    r = s.submit(
        stated_intent=VOLCANO_PLAN,
        prompt_text=VOLCANO[1],
        parent_attempt_id=pid,
        revision_reason=REASON,
    )
    assert r.respond.level == 2


@pytest.mark.grade
def test_the_cycle_rule_and_the_count_are_registered_policy_values():
    ids = {c.id for c in policy.all_choices()}
    assert {"escalation.cycle", "escalation.consecutive_unresolved"} <= ids
    assert escalation.CONSECUTIVE_TRIGGER.value == 2
    assert "same top-ranked category" in escalation.CONSECUTIVE_TRIGGER.caveat or (
        "top-ranked category is the same" in escalation.CONSECUTIVE_TRIGGER.caveat
    )
    c = escalation.CYCLE_RULE
    assert c.thesis_says and c.borrowed_from and c.caveat
    assert c.status is policy.base.IMPLEMENTATION_CHOICE


# ---------------------------------------------------------------------------
# E01 - "I need more help", over HTTP and in the web source
# ---------------------------------------------------------------------------


@pytest.mark.api
def test_asked_for_help_over_http_climbs_an_evaluative_cycle():
    from fastapi.testclient import TestClient

    from promptcoach_ref.api import app

    c = TestClient(app)
    sid = c.post("/api/session", json={"task_id": "b5-standard-first"}).json()["session_id"]
    first = c.post(
        f"/api/session/{sid}/submit",
        json={"stated_intent": ESSAY_PLAN, "prompt_text": ESSAY[0]},
    ).json()
    pid = first["elicit"]["record"]["attempt_id"]
    second = c.post(
        f"/api/session/{sid}/submit",
        json={
            "stated_intent": ESSAY_PLAN,
            "prompt_text": ESSAY[1],
            "parent_attempt_id": pid,
            "revision_reason": REASON,
            "asked_for_help": True,
        },
    ).json()
    assert first["respond"]["level"] == 1
    assert second["respond"]["level"] == 2
    assert second["help_cycle"].startswith("open")
    assert second["state"]["levels_issued"] == [1, 2]


@pytest.mark.api
def test_both_student_views_offer_i_need_more_help_and_send_it():
    for name in ("Coach.tsx", "Session.tsx"):
        src = (ROOT / "web" / "src" / "views" / name).read_text(encoding="utf-8")
        assert "I need more help" in src, name
        assert re.search(r"asked_for_help:\s*\w", src), name


# ---------------------------------------------------------------------------
# The blind-acceptance bug: the session now records that help was given
# ---------------------------------------------------------------------------


@pytest.mark.mechanism
def test_an_attempt_after_help_carries_the_help_it_followed(consent):
    s = _session(consent, "b1-audience")
    first = s.submit(stated_intent=VOLCANO_PLAN, prompt_text="explain volcanoes")
    assert first.elicit.record.triggering_intervention_id is None
    second = s.submit(stated_intent=VOLCANO_PLAN, prompt_text="explain volcanoes")
    assert second.elicit.record.triggering_intervention_id == (
        f"{first.elicit.record.attempt_id}:help:L1"
    )


@pytest.mark.mechanism
def test_blind_acceptance_fires_after_help_on_an_unchanged_resubmission(consent):
    """The run found Blind Acceptance unreachable through Session.submit. Now,
    help on one attempt and the same prompt sent again puts it in the ranked
    list (below undiagnosed retry, which the same rules rank higher)."""
    s = _session(consent, "b1-audience")
    s.submit(stated_intent=VOLCANO_PLAN, prompt_text="explain volcanoes")
    again = s.submit(stated_intent=VOLCANO_PLAN, prompt_text="explain volcanoes")
    cats = [a.category for a in again.diagnose.assignments]
    assert Category.BLIND_ACCEPTANCE in cats


@pytest.mark.mechanism
def test_blind_acceptance_fires_on_an_unchanged_revision_after_help(consent):
    s = _session(consent, "b1-audience")
    first = s.submit(stated_intent=VOLCANO_PLAN, prompt_text="explain volcanoes")
    rev = s.submit(
        stated_intent=VOLCANO_PLAN,
        prompt_text="explain volcanoes",
        parent_attempt_id=first.elicit.record.attempt_id,
        revision_reason="I think it was fine as it was",
    )
    assert Category.BLIND_ACCEPTANCE in [a.category for a in rev.diagnose.assignments]


@pytest.mark.mechanism
def test_no_help_given_means_no_blind_acceptance(consent):
    """Two identical attempts where the first got no help (nothing diagnosed)
    are not blind acceptance."""
    s = _session(consent, "b1-audience")
    good = (
        "Explain what a volcano does for my 8 year old brother in a short list "
        "of three sentences so that he can understand it"
    )
    first = s.submit(stated_intent="volcano for my brother", prompt_text=good)
    assert first.respond is None
    again = s.submit(stated_intent="volcano for my brother", prompt_text=good)
    assert again.elicit.record.triggering_intervention_id is None
    cats = [a.category for a in (again.diagnose.assignments if again.diagnose else ())]
    assert Category.BLIND_ACCEPTANCE not in cats


# ---------------------------------------------------------------------------
# E02 - Layer 5 calls the engine's detector; keyword rules only offline
# ---------------------------------------------------------------------------


def _calibrate_input(prompt: str = "explain volcanoes, whatever you think") -> CalibrateInput:
    rec = PairedRecord(
        attempt_id="e02:1", task_id="b1-audience", stated_intent=VOLCANO_PLAN,
        prompt_text=prompt, intent_modality="typed", transcript_reviewed=True,
        student_ms=0, system_ms=0,
    )
    return CalibrateInput(
        parent=rec, child=None, target=Category.UNDER_SPECIFICATION, level_issued=0,
        parent_scores={}, child_scores=None, band=1,
    )


def _gemini(handler) -> GeminiEngine:
    e = GeminiEngine(model="test-model", api_key="fake-key", read_env_file=False,
                     backoff_base=0.001)
    e._client = httpx.Client(transport=httpx.MockTransport(handler))
    return e


@pytest.mark.engine
def test_a_live_judge_s_model_based_detector_is_what_layer_five_calls():
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = request.content.decode()
        calls.append(body)
        payload = {"signals": [
            {"signal": "transcript_prompt_disconnect", "value": 0.11},
            {"signal": "excessive_deference", "value": 0.22},
            {"signal": "mindless_retry", "value": 0.33},
            {"signal": "copied_ai_content", "value": 0.44},
        ]}
        return httpx.Response(200, json={
            "candidates": [{"content": {"parts": [{"text": json.dumps(payload)}]}}],
            "usageMetadata": {"promptTokenCount": 1, "candidatesTokenCount": 1},
        })

    out = CalibrateLayer(_gemini(handler)).run(_calibrate_input())
    assert len(calls) == 1 and "over-reliance" in calls[0]
    # The model's values, not the keyword rules' (which would give 0.8 for
    # "whatever you think").
    assert out.sentinel == {
        "transcript_prompt_disconnect": 0.11,
        "excessive_deference": 0.22,
        "mindless_retry": 0.33,
        "copied_ai_content": 0.44,
    }
    assert "model-based" in out.sentinel_source
    assert "benchmark" in out.sentinel_source


@pytest.mark.engine
def test_a_failed_detector_call_is_not_replaced_by_the_keyword_rules():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "down"})

    out = CalibrateLayer(_gemini(handler)).run(_calibrate_input())
    assert out.sentinel == {}
    assert out.sentinel_source.startswith("none")


@pytest.mark.mechanism
def test_an_engine_without_a_detector_gets_no_borrowed_keyword_values():
    class NoDetector:
        name = "no-detector"
        organisation = "none"

    out = CalibrateLayer(NoDetector()).run(_calibrate_input())  # type: ignore[arg-type]
    assert out.sentinel == {}
    assert "no over-reliance detector" in out.sentinel_source


@pytest.mark.mechanism
def test_offline_the_keyword_rules_run_and_say_they_are_an_author_tested_stand_in(consent):
    s = _session(consent, "b1-audience")
    first = s.submit(stated_intent=VOLCANO_PLAN, prompt_text="explain volcanoes")
    rev = s.submit(
        stated_intent=VOLCANO_PLAN,
        prompt_text="explain volcanoes for my little brother",
        parent_attempt_id=first.elicit.record.attempt_id,
        revision_reason=REASON,
    )
    src = rev.calibrate.sentinel_source
    assert "offline keyword rules" in src and "author-tested stand-in" in src
    assert set(rev.calibrate.sentinel) == {s.id for s in sentinel.SIGNALS}
    assert "author-tested" in DeterministicEngine.sentinel.__doc__


@pytest.mark.contract
def test_layer_three_does_not_read_the_sentinel(consent):
    """Layer 3's request carries plan, prompt, scores and history; nothing from
    the detector. In a session the detector is only ever called after
    diagnosis, by Layer 5."""
    fields = set(DiagnosisRequest.__dataclass_fields__)
    assert not any("sentinel" in f or "signal" in f for f in fields)

    order: list[str] = []

    class Spy(DeterministicEngine):
        def diagnose(self, request):
            order.append("diagnose")
            return super().diagnose(request)

        def sentinel(self, *a):
            order.append("sentinel")
            return super().sentinel(*a)

    s = Session(session_id="spy", consent=consent, engine=Spy())
    s.task_id = "b1-audience"
    first = s.submit(stated_intent=VOLCANO_PLAN, prompt_text="explain volcanoes")
    s.submit(
        stated_intent=VOLCANO_PLAN,
        prompt_text="explain volcanoes for my little brother",
        parent_attempt_id=first.elicit.record.attempt_id,
        revision_reason=REASON,
    )
    assert order == ["diagnose", "diagnose", "sentinel"]


@pytest.mark.rejection
def test_docs_say_the_live_detector_is_the_model_and_the_rules_are_a_stand_in():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "author-tested" in readme
    assert "Layer 3 does not read" in readme
    from promptcoach_ref.layers import calibrate, diagnose

    assert "author-tested stand-in" in calibrate.__doc__
    assert "does not read the over-reliance sentinel" in diagnose.__doc__


@pytest.mark.engine
def test_a_detector_error_inside_a_session_does_not_stop_the_cycle(consent):
    class Flaky(DeterministicEngine):
        def sentinel(self, *a):
            raise EngineError("detector timed out")

    s = Session(session_id="flaky", consent=consent, engine=Flaky())
    s.task_id = "b1-audience"
    first = s.submit(stated_intent=VOLCANO_PLAN, prompt_text="explain volcanoes")
    rev = s.submit(
        stated_intent=VOLCANO_PLAN,
        prompt_text="explain volcanoes for my little brother",
        parent_attempt_id=first.elicit.record.attempt_id,
        revision_reason=REASON,
    )
    assert rev.stopped_at is Stage.CALIBRATE
    assert rev.calibrate.sentinel == {}
    assert "failed" in rev.calibrate.sentinel_source


# ---------------------------------------------------------------------------
# "Classroom studies" -> "User studies" (need-basis label); ids unchanged
# ---------------------------------------------------------------------------


@pytest.mark.grade
def test_no_human_facing_text_uses_the_old_need_basis_label():
    from promptcoach_ref import traceability
    from promptcoach_ref.framework.grades import NeedBasis

    assert NeedBasis.STUDENTS.value == "students"
    texts = {"TRACEABILITY (rendered)": traceability.render()}
    paths = [ROOT / "README.md", ROOT / "promptcoach_ref" / "about.py",
             ROOT / "promptcoach_ref" / "api.py"]
    paths += sorted((ROOT / "web" / "src").rglob("*.ts*"))
    for path in paths:
        texts[path.name] = path.read_text(encoding="utf-8")
    for name, text in texts.items():
        assert "Classroom studies" not in text, name
    assert "**User studies** - Need observed in a user study with students" in (
        texts["TRACEABILITY (rendered)"]
    )
