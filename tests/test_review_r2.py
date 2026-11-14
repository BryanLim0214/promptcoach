"""Second review round (review/FINDINGS_LOG_R2.md): D01, D03, D04, D05, D06,
D09 and M16, made executable.

Each test is marked with the tier it belongs to, so `-m mechanism` and the
other tier selections still pick them up.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from promptcoach_ref import about, policy
from promptcoach_ref.engines import DeterministicEngine
from promptcoach_ref.framework import grades, rubric
from promptcoach_ref.framework.contracts import (
    DimensionScore,
    ElicitInput,
    PairedRecord,
    RespondInput,
)
from promptcoach_ref.framework.grades import NeedBasis
from promptcoach_ref.framework.taxonomy import BY_ID as TAXONOMY, Category
from promptcoach_ref.layers import Consent, ElicitLayer, RespondLayer
from promptcoach_ref.policy import escalation, gating, revision as revision_policy
from promptcoach_ref.session import Session

ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# D03 - escalation when the paired dimension is evaluative
# ---------------------------------------------------------------------------

EVALUATIVE_TARGETS = [
    Category.BLIND_ACCEPTANCE,
    Category.UNDIAGNOSED_RETRY,
    Category.DELEGATED_JUDGMENT,
]


def _scores(value: int = 2) -> dict[str, DimensionScore]:
    return {
        d.id: DimensionScore(
            dimension_id=d.id,
            value=value,
            confidence=0.5,
            evidence_span=None,
            evaluative=d.id in {rubric.ITERATION_AWARENESS.id, rubric.REFLECTION.id},
        )
        for d in rubric.DIMENSIONS
    }


def _respond(target, *, levels, previous, text, asked=False, same_top=0):
    record = PairedRecord(
        attempt_id="s:1",
        task_id="b5-standard-first",
        stated_intent="I want a plan for my essay about my book",
        prompt_text=text,
        intent_modality="typed",
        transcript_reviewed=True,
        student_ms=0,
        system_ms=0,
    )
    return RespondLayer(DeterministicEngine()).run(
        RespondInput(
            record=record,
            target=target,
            scores=_scores(),
            levels_already_issued=levels,
            consecutive_same_top=same_top,
            escalation_signals=("asked_for_help",) if asked else (),
            previous_composed_text=previous,
        )
    )


@pytest.mark.mechanism
def test_the_three_evaluative_diagnoses_are_the_ones_the_rule_covers():
    covered = {
        c for c in Category
        if escalation.paired_with_evaluative_only(TAXONOMY[c].paired.dimension_ids)
    }
    assert covered == set(EVALUATIVE_TARGETS)


@pytest.mark.mechanism
@pytest.mark.parametrize("target", EVALUATIVE_TARGETS)
def test_evaluative_pairing_does_not_escalate_on_repeated_attempts(target):
    """Three earlier responses would escalate any other diagnosis. Here a changed
    prompt keeps help where it is: the 'persisted' judgment would be read off
    an evaluative score."""
    out = _respond(
        target,
        levels=(1, 1, 1),
        previous="help me plan my essay, you decide",
        text="help me plan my essay about my book, you decide what is good",
        same_top=4,
    )
    assert out.level == 1
    assert "evaluative" in out.selection_reason


@pytest.mark.mechanism
@pytest.mark.parametrize("target", EVALUATIVE_TARGETS)
def test_evaluative_pairing_escalates_when_the_prompt_is_unchanged(target):
    text = "help me plan my essay about my book, you decide what is good"
    out = _respond(target, levels=(1,), previous="  Help me plan my essay about my book,\nyou decide what is good ", text=text)
    assert out.level == 2
    assert "unchanged" in out.selection_reason


@pytest.mark.mechanism
@pytest.mark.parametrize("target", EVALUATIVE_TARGETS)
def test_evaluative_pairing_escalates_when_she_asks(target):
    out = _respond(
        target, levels=(1,), previous="something else entirely", text="help me plan my essay, you decide", asked=True
    )
    assert out.level == 2
    assert "asked" in out.selection_reason


@pytest.mark.mechanism
def test_other_diagnoses_still_escalate_on_repeated_attempts():
    out = _respond(
        Category.UNDER_SPECIFICATION,
        levels=(1,),
        previous="explain volcanoes",
        text="explain what volcanoes do",
        same_top=escalation.CONSECUTIVE_UNRESOLVED,
    )
    assert out.level == 2
    assert "persisted" in out.selection_reason


@pytest.mark.mechanism
def test_responses_already_issued_are_not_the_escalation_count():
    """E01: the count is consecutive attempts with the same top category, which
    the session supplies. Three earlier responses with no such count do not
    escalate on their own; the old rule read len(levels) and did."""
    out = _respond(
        Category.UNDER_SPECIFICATION,
        levels=(1, 1, 1),
        previous="explain volcanoes",
        text="explain what volcanoes do",
        same_top=1,
    )
    assert out.level == 1


@pytest.mark.mechanism
def test_the_session_passes_the_previous_text_and_holds_on_small_edits(consent):
    """End to end: a delegated-judgment prompt edited each time stays at level
    1 however many times the category repeats.

    Sending the same text again changes the diagnosis: the offline rules rank
    undiagnosed retry (0.90) above delegated judgment (0.85) for an unchanged
    prompt, so a new help cycle opens at level 1 for undiagnosed retry. Sending
    it unchanged once more keeps that category first with the text unchanged,
    which is what moves help up for an evaluative pairing."""
    s = Session(session_id="d03", consent=consent, engine=DeterministicEngine())
    s.task_id = "b5-standard-first"
    base = (
        "Help me plan an essay about my favourite book for my English class, "
        "three paragraphs long, whatever you think is best"
    )
    levels = []
    for i in range(5):
        r = s.submit(
            stated_intent="I want an essay plan for class about my book",
            prompt_text=base + " " + "please " * i,
        )
        assert r.diagnose.target is Category.DELEGATED_JUDGMENT
        levels.append(r.respond.level)
    assert levels == [1, 1, 1, 1, 1]

    same = base + " " + "please " * 4
    r = s.submit(stated_intent="I want an essay plan for class about my book", prompt_text=same)
    assert r.diagnose.target is Category.UNDIAGNOSED_RETRY
    assert r.respond.level == 1
    assert "new cycle" in r.help_cycle

    r = s.submit(stated_intent="I want an essay plan for class about my book", prompt_text=same)
    assert r.diagnose.target is Category.UNDIAGNOSED_RETRY
    assert r.respond.level == 2
    assert "unchanged" in r.respond.selection_reason


@pytest.mark.grade
def test_the_evaluative_rule_is_a_registered_policy_value():
    c = escalation.EVALUATIVE_PAIRING
    assert c in policy.all_choices()
    assert c.thesis_says and c.borrowed_from and c.caveat
    assert c.status is policy.base.IMPLEMENTATION_CHOICE
    assert set(c.value["applies_when_paired_dimension_is"]) == {
        rubric.ITERATION_AWARENESS.id,
        rubric.REFLECTION.id,
    }
    assert "evaluative_escalation" in dict(policy.UNSPECIFIED_BY_THESIS)


# ---------------------------------------------------------------------------
# D04 - what a success is, and what the streak counts
# ---------------------------------------------------------------------------


def _with(values: dict[str, int | None]) -> dict[str, DimensionScore]:
    out = _scores(1)
    for k, v in values.items():
        out[k] = DimensionScore(dimension_id=k, value=v, confidence=0.5, evidence_span=None)
    return out


@pytest.mark.mechanism
def test_bands_one_and_two_need_every_named_dimension_at_three():
    named = (rubric.CONSTRAINT_SETTING.id, rubric.SPECIFICITY.id)
    assert gating.attempt_succeeded(2, named, _with({named[0]: 3, named[1]: 4}))
    assert not gating.attempt_succeeded(2, named, _with({named[0]: 3, named[1]: 2}))
    # Other dimensions do not count.
    assert not gating.attempt_succeeded(
        1, (rubric.AUDIENCE_AWARENESS.id,), _with({rubric.SPECIFICITY.id: 4})
    )


@pytest.mark.mechanism
def test_band_three_needs_three_of_the_four_planning_dimensions():
    p = [d.id for d in rubric.PLANNING_DIMENSIONS]
    assert gating.attempt_succeeded(3, (), _with({p[0]: 3, p[1]: 3, p[2]: 4}))
    assert not gating.attempt_succeeded(3, (), _with({p[0]: 3, p[1]: 3}))


@pytest.mark.mechanism
def test_bands_four_and_five_need_one_evaluative_dimension():
    assert gating.attempt_succeeded(4, (), _with({rubric.REFLECTION.id: 3}))
    assert gating.attempt_succeeded(5, (), _with({rubric.ITERATION_AWARENESS.id: 4}))
    assert not gating.attempt_succeeded(5, (), _with({rubric.SPECIFICITY.id: 4}))


@pytest.mark.mechanism
def test_an_unscored_dimension_is_not_a_success():
    named = (rubric.AUDIENCE_AWARENESS.id,)
    assert not gating.attempt_succeeded(1, named, _with({named[0]: None}))
    assert not gating.attempt_succeeded(1, named, None)


@pytest.mark.mechanism
def test_a_clean_first_attempt_counts_as_a_success():
    """The earlier rule counted only a rising paired dimension, so a first
    attempt with nothing to diagnose (no child, no delta) went into the window
    as a failure. Now its own scores decide."""
    from promptcoach_ref.framework.contracts import CalibrateInput
    from promptcoach_ref.layers import CalibrateLayer

    record = PairedRecord(
        attempt_id="d04:1", task_id="b1-audience",
        stated_intent="volcanoes for my brother", prompt_text="volcano prompt here",
        intent_modality="typed", transcript_reviewed=True, student_ms=0, system_ms=0,
    )
    out = CalibrateLayer().run(CalibrateInput(
        parent=record, child=None, target=Category.UNDER_SPECIFICATION,
        level_issued=0, parent_scores=_with({rubric.AUDIENCE_AWARENESS.id: 3}),
        child_scores=None, band=1,
    ))
    assert out.paired_delta is None
    assert out.attempt_succeeded is True


@pytest.mark.mechanism
def test_the_streak_counts_closed_cycles_not_distinct_tasks(consent):
    """Three revisions of ONE task reach a streak of three. With two tasks per
    band, that is the only way a streak of three can be reached."""
    s = Session(session_id="d04b", consent=consent, engine=DeterministicEngine())
    s.task_id = "b1-audience"
    s.band = 1
    first = s.submit(
        stated_intent="volcano for my brother",
        prompt_text="tell me about volcanoes please",
    )
    parent = first.elicit.record.attempt_id
    good = (
        "Explain what a volcano does for my 8 year old brother, in three short "
        "sentences, so he can understand it before his science test"
    )
    for i in range(3):
        r = s.submit(
            stated_intent="volcano for my brother",
            prompt_text=good + "." * i,
            parent_attempt_id=parent,
            revision_reason="I said who it is for and how long",
        )
        parent = r.elicit.record.attempt_id
    assert s.outcomes[-3:] == (True, True, True)
    assert set(s.attempts_on_task) == {"b1-audience"}


@pytest.mark.grade
def test_the_success_rule_and_streak_unit_are_registered_policy_values():
    ids = {c.id for c in policy.all_choices()}
    assert {"gating.success", "gating.streak_unit"} <= ids
    assert gating.SUCCESS.value["threshold"] == 3
    assert "not distinct tasks" in gating.STREAK_UNIT.caveat
    assert "gating_success" in dict(policy.UNSPECIFIED_BY_THESIS)


@pytest.mark.grade
def test_the_twenty_three_gaps():
    keys = [k for k, _ in policy.UNSPECIFIED_BY_THESIS]
    assert len(keys) == len(set(keys)) == 24


# ---------------------------------------------------------------------------
# D05 - the hold releases itself; nothing claims a teacher release
# ---------------------------------------------------------------------------


def _human_facing_text() -> list[Path]:
    paths = [ROOT / "README.md", ROOT / "promptcoach_ref" / "about.py",
             ROOT / "promptcoach_ref" / "api.py"]
    paths += sorted((ROOT / "web" / "src").rglob("*.ts*"))
    return paths


@pytest.mark.rejection
def test_no_text_claims_a_teacher_can_release_the_hold():
    pattern = re.compile(
        r"teacher[^.\n]{0,40}(release|lift|unlock)|"
        r"(release|lift|unlock)[^.\n]{0,40}by (a|the) teacher",
        re.I,
    )
    for path in _human_facing_text():
        text = path.read_text(encoding="utf-8")
        assert not pattern.search(text), path.name


@pytest.mark.rejection
def test_no_api_route_releases_the_hold():
    from promptcoach_ref.api import app

    for route in app.routes:
        p = getattr(route, "path", "")
        assert "release" not in p and "unlock" not in p, p


@pytest.mark.falsifiability
def test_the_hold_releases_after_four_attempts_and_is_recorded(consent):
    s = Session(session_id="d05", consent=consent, engine=DeterministicEngine())
    s.task_id = "b1-audience"
    for _ in range(revision_policy.EXIT_AFTER_ATTEMPTS - 1):
        s.submit(stated_intent="volcano", prompt_text="tell me about volcanoes now")
        assert s.revision_pending
    s.submit(stated_intent="volcano", prompt_text="tell me about volcanoes now")
    assert revision_policy.EXIT_AFTER_ATTEMPTS == 4
    assert not s.revision_pending
    moved, _ = s.move_to("b1-reading-level")
    assert moved and s.gate_exits == ["b1-audience"]


# ---------------------------------------------------------------------------
# D06 - "different model", not "different vendor", for generator vs judge
# ---------------------------------------------------------------------------


@pytest.mark.rejection
def test_generator_vs_judge_is_never_called_a_different_vendor():
    pattern = re.compile(
        r"(generat\w*|answers? her)[^.\n]{0,80}(different|another|separate) "
        r"(vendor|company|organi[sz]ation)",
        re.I,
    )
    for path in _human_facing_text():
        assert not pattern.search(path.read_text(encoding="utf-8")), path.name
    assert "different model" in about.WHAT_RUNNING_THIS_SHOWS


@pytest.mark.rejection
def test_readme_says_gemini_generator_and_judge_share_a_vendor():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "different *model*, not a different" in text
    assert "all Google models" in text


# ---------------------------------------------------------------------------
# D09 - the typed plan is separate from the typed reason
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_a_typed_plan_before_writing_is_the_first_attempt_path_without_a_microphone():
    layer = ElicitLayer(Consent(platform_use=True, research_participation=False,
                                audio_retention=False))
    out = layer.run(ElicitInput(
        session_id="d09", task_id="b3-babysitting",
        stated_intent="explain the sky to my cousin, she is seven, keep it short",
        prompt_text="explain why the sky is blue",
        intent_modality="typed",
    ))
    assert out.record is not None
    assert out.record.intent_modality == "typed"
    assert out.record.stated_intent.startswith("explain the sky to my cousin")
    assert out.record.revision_reason is None


@pytest.mark.contract
def test_a_reason_does_not_stand_in_for_the_plan():
    layer = ElicitLayer(Consent(True, False, False))
    out = layer.run(ElicitInput(
        session_id="d09", task_id="b3-babysitting",
        stated_intent="",
        prompt_text="explain why the sky is blue for a seven year old",
        parent_attempt_id="d09:parent",
        revision_reason="I added who it is for",
    ))
    assert out.record is None
    assert "what you are trying to do" in out.clarification_required


@pytest.mark.contract
def test_plan_and_reason_are_separate_fields_on_the_record():
    layer = ElicitLayer(Consent(True, False, False))
    out = layer.run(ElicitInput(
        session_id="d09", task_id="b3-babysitting",
        stated_intent="for my seven year old cousin, a few sentences",
        prompt_text="explain why the sky is blue for a seven year old",
        parent_attempt_id="d09:parent",
        revision_reason="I added who it is for",
    ))
    assert out.record.stated_intent == "for my seven year old cousin, a few sentences"
    assert out.record.revision_reason == "I added who it is for"


# ---------------------------------------------------------------------------
# D01 - "User studies", never "Students", as a need-basis label
# ---------------------------------------------------------------------------


@pytest.mark.grade
def test_the_need_basis_label_is_user_studies():
    """R3 item: 'Classroom studies' became 'User studies'; the id is unchanged."""
    assert NeedBasis.STUDENTS.value == "students"
    assert NeedBasis.STUDENTS.label == "User studies"
    assert grades.NEED_DEFINITION[NeedBasis.STUDENTS] == (
        "Need observed in a user study with students, through its design or "
        "its self-report data."
    )


@pytest.mark.grade
def test_traceability_never_labels_the_need_basis_students():
    from promptcoach_ref import traceability

    text = traceability.render()
    assert "User studies" in text
    assert not re.search(r"\| students \||\*\*Students\*\*|\d+ Students\b", text)


@pytest.mark.api
def test_the_api_serves_need_labels():
    from fastapi.testclient import TestClient

    from promptcoach_ref.api import app

    g = TestClient(app).get("/api/framework").json()["grades"]
    assert g["need_labels"]["students"] == "User studies"
    for c in g["components"]:
        assert c["need_label"] in {"User studies", "Builds", "Argument"}


# ---------------------------------------------------------------------------
# M16 - no component text states a withdrawn claim
# ---------------------------------------------------------------------------

WITHDRAWN_COMPONENT_CLAIMS = (
    "Veenman",
    "recreated the overload",
    "not significant",
    "helpful response",
    "p = .11",
    "validated signals",
    "Established in mathematics",
    "no intervals",
)


@pytest.mark.grade
def test_no_component_states_a_claim_the_thesis_withdrew():
    for c in grades.GRADED_COMPONENTS:
        text = f"{c.basis} {c.limit}"
        for claim in WITHDRAWN_COMPONENT_CLAIMS:
            assert claim.lower() not in text.lower(), (c.id, claim)


@pytest.mark.grade
def test_about_page_drops_the_withdrawn_justifications():
    text = " ".join(
        [about.WHY_THE_BOUNDARY.text, about.WHERE_THE_RUBRIC_COMES_FROM.text]
        + [s for _, _, s in about.REQUIREMENTS]
    )
    assert "Veenman" not in text
    assert "helpful response" not in text
    assert "non-significant decline" not in text


@pytest.mark.grade
def test_the_escalation_trigger_is_quoted_as_pypal_states_it():
    assert "I'm stuck" in escalation.FRUSTRATION_TRIGGER.thesis_says
    assert "expressed frustration" not in escalation.FRUSTRATION_TRIGGER.thesis_says
