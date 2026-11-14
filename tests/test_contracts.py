"""Tier 1 - layer contracts.

Each layer takes only its declared input and emits only its declared output.
The one thing that is *not* a straight pipeline is deliberate: Layer 3 reads
Layer 1 directly as well as Layer 2, because sec:diagnose says four of the seven
categories "cannot be detected from the prompt text alone".
"""

from __future__ import annotations

import pytest

from promptcoach_ref.framework import contracts
from promptcoach_ref.framework.taxonomy import (
    CATEGORIES,
    DetectableFrom,
    detectable_from_prompt_alone,
    requires_session_history,
    requires_spoken_record,
)
from promptcoach_ref.layers import (
    CalibrateLayer,
    DiagnoseLayer,
    ElicitLayer,
    MeasureLayer,
    RespondLayer,
)

pytestmark = pytest.mark.contract


def test_each_layer_implements_its_protocol(engine, consent):
    assert isinstance(ElicitLayer(consent), contracts.Elicit)
    assert isinstance(MeasureLayer(engine), contracts.Measure)
    assert isinstance(DiagnoseLayer(engine), contracts.Diagnose)
    assert isinstance(RespondLayer(engine), contracts.Respond)
    assert isinstance(CalibrateLayer(), contracts.Calibrate)


def test_elicit_reads_nothing_upstream(consent):
    assert ElicitLayer(consent).READS == ()


def test_diagnose_reads_layer_one_directly(engine):
    """The DAG edge. Without it, four of seven categories are undetectable."""
    reads = DiagnoseLayer(engine).READS
    assert "elicit" in reads
    assert "measure" in reads
    assert "history" in reads


def test_measure_does_not_read_history(engine):
    """Measure scores an artifact. It has no business with the session."""
    assert "history" not in MeasureLayer(engine).READS


def test_the_dependency_is_not_a_chain():
    reads = contracts.LAYER_READS
    assert reads["measure"] == ("elicit",)
    # Layers 2-5 all reach back to Layer 1's paired record.
    for layer in ("measure", "diagnose", "respond", "calibrate"):
        assert "elicit" in reads[layer], layer


def test_four_of_seven_categories_need_more_than_the_prompt():
    assert len(CATEGORIES) == 7
    assert len(detectable_from_prompt_alone()) == 3
    assert len(requires_spoken_record()) == 1
    assert len(requires_session_history()) == 3


def test_intent_drift_is_the_one_that_needs_the_spoken_record():
    (only,) = requires_spoken_record()
    assert only.id.value == "intent_drift"
    assert only.detectable_from is DetectableFrom.PAIRED_SPOKEN_RECORD


def test_a_dimension_score_outside_the_rubric_cannot_be_constructed():
    with pytest.raises(ValueError):
        contracts.DimensionScore(
            dimension_id="specificity", value=9, confidence=1.0, evidence_span=None
        )


def test_a_diagnosis_target_must_be_the_top_ranked_assignment():
    """sec:diagnose requires the response layer to act on the top ranked failure only.
    A target that is not rank 1 would make the ranking decorative."""
    from promptcoach_ref.framework.taxonomy import Category

    a = contracts.CategoryAssignment(
        category=Category.INTENT_DRIFT, rank=1, confidence=0.9, trigger="t"
    )
    b = contracts.CategoryAssignment(
        category=Category.UNDER_SPECIFICATION, rank=2, confidence=0.8, trigger="t"
    )
    contracts.DiagnoseOutput(assignments=(a, b), target=Category.INTENT_DRIFT)
    with pytest.raises(ValueError):
        contracts.DiagnoseOutput(
            assignments=(a, b), target=Category.UNDER_SPECIFICATION
        )


def test_assignments_must_be_in_rank_order():
    from promptcoach_ref.framework.taxonomy import Category

    a = contracts.CategoryAssignment(
        category=Category.INTENT_DRIFT, rank=2, confidence=0.9, trigger="t"
    )
    b = contracts.CategoryAssignment(
        category=Category.UNDER_SPECIFICATION, rank=1, confidence=0.8, trigger="t"
    )
    with pytest.raises(ValueError):
        contracts.DiagnoseOutput(assignments=(a, b), target=Category.INTENT_DRIFT)


def test_every_layer_output_states_whether_the_thesis_specified_it():
    for cls in (
        contracts.ElicitOutput,
        contracts.MeasureOutput,
        contracts.DiagnoseOutput,
        contracts.RespondOutput,
        contracts.CalibrateOutput,
    ):
        assert isinstance(cls.THESIS_SPECIFIED, bool)


# --- the redesigned framework's contract additions --------------------------


def _record(**kw):
    base = dict(
        attempt_id="a",
        task_id="t",
        stated_intent="i want it for my cousin",
        prompt_text="explain the sky for a seven year old",
        intent_modality="typed",
        transcript_reviewed=True,
        student_ms=0,
        system_ms=0,
    )
    base.update(kw)
    return contracts.PairedRecord(**base)


def test_elicit_input_and_paired_record_carry_the_three_new_fields():
    for cls in (contracts.ElicitInput, contracts.PairedRecord):
        fields = cls.__dataclass_fields__
        assert {"predicted_rating", "revision_reason", "inserted_spans"} <= set(fields)
    r = _record()
    assert r.predicted_rating is None
    assert r.revision_reason is None
    assert r.inserted_spans == ()


def test_predicted_rating_is_on_the_rubric_scale():
    assert (contracts.PREDICTED_MIN, contracts.PREDICTED_MAX) == (1, 4)
    for ok in (1, 2, 3, 4):
        assert _record(predicted_rating=ok).predicted_rating == ok
    for bad in (0, 5):
        with pytest.raises(ValueError):
            _record(predicted_rating=bad)


def test_composed_text_drops_inserted_spans():
    prompt = "explain the sky for a seven year old"
    start = prompt.index("for a seven year old")
    r = _record(prompt_text=prompt, inserted_spans=(contracts.Span(start, len(prompt)),))
    assert r.composed_text == "explain the sky"
    assert contracts.inserted_text(prompt, r.inserted_spans) == "for a seven year old"
    # The prompt itself is untouched.
    assert r.prompt_text == prompt


def test_an_inserted_span_past_the_end_cannot_be_constructed():
    with pytest.raises(ValueError):
        _record(prompt_text="short prompt here", inserted_spans=(contracts.Span(0, 99),))
    with pytest.raises(ValueError):
        contracts.Span(5, 2)


def test_measure_output_records_judge_and_generator():
    fields = contracts.MeasureOutput.__dataclass_fields__
    assert {
        "judge_model",
        "generator_model",
        "judge_independent_of_generator",
    } <= set(fields)


def test_calibrate_output_carries_the_gap_and_the_revision_hold():
    fields = contracts.CalibrateOutput.__dataclass_fields__
    assert {"calibration_gap", "revision_pending"} <= set(fields)


def test_the_calibration_gap_is_predicted_minus_measured():
    assert contracts.calibration_gap(3, 1.5) == 1.5
    assert contracts.calibration_gap(1, 2.25) == -1.25
    # Missing on either side is not zero.
    assert contracts.calibration_gap(None, 2.0) is None
    assert contracts.calibration_gap(3, None) is None


def test_measure_and_calibrate_report_the_new_fields_end_to_end(session):
    from conftest import WORKED_REASON, WORKED_REVISION, WORKED_SPOKEN, WORKED_TYPED

    first = session.submit(
        stated_intent=WORKED_SPOKEN, prompt_text=WORKED_TYPED, predicted_rating=3
    )
    m = first.measure
    assert m.judge_model and m.generator_model
    assert m.judge_independent_of_generator is True
    assert first.calibration_gap == contracts.calibration_gap(3, m.overall)

    second = session.submit(
        stated_intent=WORKED_SPOKEN,
        prompt_text=WORKED_REVISION,
        parent_attempt_id=first.elicit.record.attempt_id,
        revision_reason=WORKED_REASON,
        predicted_rating=4,
    )
    c = second.calibrate
    assert c is not None
    assert c.predicted_rating == 4
    assert c.calibration_gap == contracts.calibration_gap(4, second.measure.overall)
    assert c.revision_pending is False
