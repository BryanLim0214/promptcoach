"""Tier 5 - the implementation does not foreclose its own refutation.

Chapter 12 (sec:falsify) states what would show the framework is wrong: F1 to F6
carried over from the earlier draft, and three new ones - F7 (requiring a
reasoned revision changes nothing), F8 (showing the calibration gap does not
narrow it, or lowers revisions), and F9 (an independent judge and a self-judging
generator differ by no more than paraphrase noise).

None of them can be a unit test, because every one of them needs students.
What *can* be tested is whether this implementation keeps the data and the
switches those experiments would need. A system that recorded only the paired
dimension's movement, that could only ever require a reason, or that could only
ever show the gap, would make the thesis's own refutation impossible to run -
and would be a worse artifact for it.

Each test below names the condition it protects.
"""

from __future__ import annotations

import pytest

from promptcoach_ref.framework import progression, rubric
from promptcoach_ref.framework.contracts import CalibrateOutput
from promptcoach_ref.framework.taxonomy import BY_ID as TAXONOMY, Category
from promptcoach_ref.layers import RespondLayer
from promptcoach_ref.policy import classifier

from conftest import WORKED_REASON, WORKED_SPOKEN, WORKED_TYPED

pytestmark = pytest.mark.falsifiability


def test_f2_calibrate_emits_unpaired_deltas_as_well_as_the_paired_one(session):
    """F2: "for each diagnosis, the paired dimension should move more than the
    unpaired dimensions do. If it does not, Layer 5 is measuring the derivation
    and not the coaching."

    A comparative test needs both sides. Storing only the paired delta would
    leave F2 unrunnable.
    """
    first = session.submit(
        stated_intent=WORKED_SPOKEN,
        prompt_text=WORKED_TYPED,
        intent_modality="speech",
    )
    revision = session.submit(
        stated_intent=WORKED_SPOKEN,
        prompt_text=(
            "explain why the sky is blue for a seven year old, "
            "keep it to a few sentences"
        ),
        parent_attempt_id=first.elicit.record.attempt_id,
        revision_reason=WORKED_REASON,
    )
    assert revision.calibrate is not None
    assert revision.calibrate.paired_delta is not None
    assert revision.calibrate.unpaired_deltas, (
        "F2 is comparative; without unpaired movement it cannot be evaluated"
    )


def test_f2_pairing_strictness_is_recorded():
    """sec:design - the pairings "differ in strictness, and a system that treated them
    as equivalent would find more improvement after some diagnoses than others
    for reasons that have nothing to do with the student"."""
    assert "pairing_strictness" in CalibrateOutput.__dataclass_fields__

    broad = TAXONOMY[Category.INTENT_DRIFT].paired
    narrow = TAXONOMY[Category.DELEGATED_JUDGMENT].paired
    assert len(broad.dimension_ids) > len(narrow.dimension_ids)
    assert narrow.dimension_ids == (rubric.REFLECTION.id,)


def test_f3_the_axis_join_is_recorded_on_every_band_change():
    """F3's third sub-test: "if band 4 is easier than band 3, the two axes cannot
    be laid end to end and the progression is two orderings rather than one."

    That needs band performance kept separable across the join.
    """
    assert "crossed_axis_join" in CalibrateOutput.__dataclass_fields__
    assert progression.AXIS_JOIN == (3, 4)
    assert not progression.same_axis(3, 4)
    assert progression.same_axis(1, 3)
    assert progression.same_axis(4, 5)


def test_f3_the_two_halves_are_separately_identifiable():
    """The thesis treats them as separately refutable, so the code must be able
    to tell them apart."""
    lower = [b for b in progression.BANDS if b.axis is progression.Axis.PLANNING_DIMENSION_COUNT]
    upper = [b for b in progression.BANDS if b.axis is progression.Axis.EVALUATIVE_OUTPUT_VISIBILITY]
    assert [b.number for b in lower] == [1, 2, 3]
    assert [b.number for b in upper] == [4, 5]


def test_f4_both_selection_modes_exist(engine):
    """F4: "if diagnosis adds nothing over score alone, that is, if responses
    selected by diagnosis produce no better revision than responses selected by
    the weakest dimension. This is the cheapest experiment in the list and should
    be run first."

    Running it needs both arms.
    """
    assert set(classifier.SELECTION_MODES) == {"diagnosis", "weakest_dimension"}
    RespondLayer(engine, selection_mode="diagnosis")
    RespondLayer(engine, selection_mode="weakest_dimension")
    with pytest.raises(ValueError):
        RespondLayer(engine, selection_mode="whatever_feels_right")


def test_f4_the_two_modes_can_target_different_dimensions(session, engine):
    """If both arms always chose the same dimension, the experiment would be
    vacuous even with both switches present."""
    from promptcoach_ref.framework.contracts import RespondInput

    first = session.submit(
        stated_intent=WORKED_SPOKEN,
        prompt_text=WORKED_TYPED,
        intent_modality="speech",
    )
    data = RespondInput(
        record=first.elicit.record,
        target=Category.DELEGATED_JUDGMENT,
        scores=first.measure.scores,
    )
    by_diagnosis = RespondLayer(engine, "diagnosis")._weakest(data)
    by_score = RespondLayer(engine, "weakest_dimension")._weakest(data)
    # Delegated judgment pairs with Reflection; the lowest raw score need not be.
    assert by_diagnosis == rubric.REFLECTION.id
    assert isinstance(by_score, str)


def test_f5_the_terminal_level_is_distinguishable_from_a_plain_hint():
    """F5 compares the worked contrast against a plain hint. The two have to be
    different objects for the comparison to mean anything."""
    from promptcoach_ref.framework import ladder

    assert ladder.LEVEL_4.gives != ladder.LEVEL_1.gives
    assert "contrast" in ladder.LEVEL_4.gives.lower()
    assert ladder.LEVEL_4.grade.value == "argued"


def test_unbuildability_the_typed_fallback_exists(engine, consent):
    """Not a refutation but an unbuildability condition: if speech capture
    fails in a classroom, "the typed intent fallback is what stands between that
    outcome and total loss, and it has not been built or tested either."

    It is built here. Whether it is enough is still an open question.
    """
    from promptcoach_ref.layers import Consent
    from promptcoach_ref.policy import taskbank
    from promptcoach_ref.session import Session

    s = Session(
        session_id="typed-only",
        consent=Consent(
            platform_use=True, research_participation=False, audio_retention=False
        ),
        engine=engine,
    )
    s.task_id = taskbank.WORKED_EXAMPLE_ID
    r = s.submit(
        stated_intent="I want to tell my cousin about the sky, she is seven",
        prompt_text=WORKED_TYPED,
        intent_modality="typed",
    )
    assert r.elicit.record is not None
    assert r.elicit.record.intent_is_degraded is True
    assert r.diagnose is not None, "the loop must complete without speech"


def test_the_degradation_is_reported_rather_than_hidden(engine):
    """sec:method - the fallback "degrades the diagnosis rather than blocking it".
    A degradation nobody is told about is indistinguishable from none."""
    from promptcoach_ref.layers import Consent
    from promptcoach_ref.policy import taskbank
    from promptcoach_ref.session import Session

    s = Session(
        session_id="degraded",
        consent=Consent(
            platform_use=True, research_participation=False, audio_retention=False
        ),
        engine=engine,
    )
    s.task_id = taskbank.WORKED_EXAMPLE_ID
    r = s.submit(
        stated_intent="I want to tell my cousin about the sky",
        prompt_text=WORKED_TYPED,
        intent_modality="typed",
    )
    assert any("lower fidelity" in t for t in r.diagnose.reason_trace)


# --- F7, F8 and F9: the redesigned framework's own refutations ---------------


def _session(engine, **kw):
    from promptcoach_ref.layers import Consent
    from promptcoach_ref.policy import taskbank
    from promptcoach_ref.session import Session

    s = Session(
        session_id="f-arm",
        consent=Consent(
            platform_use=True, research_participation=False, audio_retention=False
        ),
        engine=engine,
        **kw,
    )
    s.task_id = taskbank.WORKED_EXAMPLE_ID
    return s


def test_f7_the_revision_requirement_can_be_switched_off(engine):
    """F7: "Requiring a reasoned revision produces no larger change between first
    and revised prompt scores than not requiring it." Running it needs a control
    arm in which an unreasoned revision is scored, and the two arms must record
    the same first-to-revised change so they can be compared."""
    from conftest import WORKED_REVISION
    from promptcoach_ref.framework import revision

    assert "Requiring a reasoned revision" in revision.F7

    required = _session(engine)
    control = _session(engine, require_reason=False)
    assert required.require_reason is True
    assert control.require_reason is False

    deltas = {}
    for arm, s in (("required", required), ("control", control)):
        first = s.submit(stated_intent=WORKED_SPOKEN, prompt_text=WORKED_TYPED)
        unreasoned = s.submit(
            stated_intent=WORKED_SPOKEN,
            prompt_text=WORKED_REVISION,
            parent_attempt_id=first.elicit.record.attempt_id,
        )
        if arm == "required":
            assert unreasoned.measure is None, "the treatment arm asks for a reason"
            unreasoned = s.submit(
                stated_intent=WORKED_SPOKEN,
                prompt_text=WORKED_REVISION,
                parent_attempt_id=first.elicit.record.attempt_id,
                revision_reason=WORKED_REASON,
            )
        else:
            assert unreasoned.measure is not None, "the control arm scores it anyway"
        deltas[arm] = unreasoned.measure.overall - first.measure.overall

    # Both arms produce the comparable quantity F7 is about.
    assert set(deltas) == {"required", "control"}
    # The control arm never holds the next task.
    assert control.revision_pending is False


def test_f7_the_hold_releases_through_the_policy_exit_and_is_counted(engine):
    from promptcoach_ref.policy import revision as revision_policy

    s = _session(engine)
    for _ in range(revision_policy.EXIT_AFTER_ATTEMPTS - 1):
        s.submit(stated_intent=WORKED_SPOKEN, prompt_text=WORKED_TYPED)
        assert s.revision_pending is True
        moved, _why = s.move_to("b1-audience")
        assert moved is False
    s.submit(stated_intent=WORKED_SPOKEN, prompt_text=WORKED_TYPED)
    assert s.revision_pending is False
    moved, _ = s.move_to("b1-audience")
    assert moved is True
    # Released without a reasoned revision, and recorded as such for F7.
    assert s.gate_exits == ["b3-babysitting"]


def test_f8_the_gap_display_can_be_switched_off_and_the_gap_is_still_recorded(engine):
    """F8: "Showing the calibration gap does not narrow it over a session, or it
    lowers the number of revisions." Both arms must record the gap; only the
    display differs."""
    from promptcoach_ref.policy import calibration as calibration_policy

    assert calibration_policy.SHOW_GAP_TO_STUDENT.value is True

    shown = _session(engine)
    hidden = _session(engine, show_gap=False)
    a = shown.submit(stated_intent=WORKED_SPOKEN, prompt_text=WORKED_TYPED, predicted_rating=4)
    b = hidden.submit(stated_intent=WORKED_SPOKEN, prompt_text=WORKED_TYPED, predicted_rating=4)
    assert a.gap_visible is True and b.gap_visible is False
    # Recorded in both arms, so "does it narrow over a session" can be computed.
    assert a.calibration_gap is not None
    assert b.calibration_gap == a.calibration_gap


def test_f8_the_number_of_revisions_is_countable(engine):
    """F8's second half - showing the gap lowers the number of revisions - needs
    revisions counted per task."""
    from conftest import WORKED_REVISION

    s = _session(engine)
    first = s.submit(stated_intent=WORKED_SPOKEN, prompt_text=WORKED_TYPED)
    s.submit(
        stated_intent=WORKED_SPOKEN,
        prompt_text=WORKED_REVISION,
        parent_attempt_id=first.elicit.record.attempt_id,
        revision_reason=WORKED_REASON,
    )
    assert s.reasoned_revisions["b3-babysitting"] == 1


def test_the_predicted_rating_is_stored_with_the_attempt(engine):
    s = _session(engine)
    r = s.submit(stated_intent=WORKED_SPOKEN, prompt_text=WORKED_TYPED, predicted_rating=2)
    stored = s.store.get(r.elicit.record.attempt_id)
    assert stored.predicted_rating == 2
    # Skipping it is allowed and is not a prediction of anything.
    r2 = s.submit(stated_intent=WORKED_SPOKEN, prompt_text=WORKED_TYPED)
    assert s.store.get(r2.elicit.record.attempt_id).predicted_rating is None
    assert r2.calibration_gap is None


def test_f9_judge_and_generator_are_recorded_per_attempt(engine):
    """F9: scores from an independent judge and from the generating model judging
    itself differ by no more than paraphrase noise (0.134 points). Running it
    needs both names on every scored attempt, and a way to point the judge at
    the generator for the comparison arm."""
    s = _session(engine)
    r = s.submit(stated_intent=WORKED_SPOKEN, prompt_text=WORKED_TYPED)
    assert r.measure.judge_model == engine.name
    assert r.measure.generator_model == "scripted-responder"
    assert r.measure.judge_independent_of_generator is True

    from promptcoach_ref.layers import MeasureLayer

    self_judging = MeasureLayer(engine, generator_model=engine.name)
    from promptcoach_ref.framework.contracts import MeasureInput

    out = self_judging.run(MeasureInput(record=r.elicit.record))
    assert out.judge_independent_of_generator is False
