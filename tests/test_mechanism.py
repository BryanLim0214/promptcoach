"""Tier 3 - the transferred mechanisms behave as the source builds specified.

The dual-condition gate gets the most attention here, because
sec:build2 says requiring both conditions "is the detail that
matters, because either alone makes the tier oscillate on a single lucky or
unlucky answer". An implementation that promoted on rate alone would look correct
in a demo and be wrong in exactly the way Build 2 warns about.
"""

from __future__ import annotations

import pytest

from promptcoach_ref.framework import ladder, progression, rubric
from promptcoach_ref.framework.taxonomy import Category
from promptcoach_ref.layers import validate
from promptcoach_ref.policy import affect, decomposition, escalation, gating, taskbank

pytestmark = pytest.mark.mechanism


# --- the dual condition ---------------------------------------------------


def test_rate_alone_does_not_promote():
    outcomes = (True,) * 9 + (False,)  # 90% but the streak is broken
    decision = gating.evaluate(outcomes)
    assert decision.direction == 0
    assert decision.rate_condition_met is True
    assert decision.streak_condition_met is False
    assert "single condition does not move the band" in decision.reason


def test_streak_alone_does_not_promote():
    outcomes = (False,) * 7 + (True, True, True)  # streak of 3 but 30%
    decision = gating.evaluate(outcomes)
    assert decision.direction == 0
    assert decision.rate_condition_met is False
    assert decision.streak_condition_met is True


def test_both_conditions_promote():
    decision = gating.evaluate((True,) * 10)
    assert decision.direction == 1
    assert decision.rate_condition_met and decision.streak_condition_met


def test_both_conditions_demote():
    decision = gating.evaluate((False,) * 10)
    assert decision.direction == -1


def test_a_single_success_does_not_move_the_band():
    """sec:design, on the worked example: "The band holds at 3 either way, because a
    single success does not satisfy both the rate and the streak condition." """
    decision = gating.evaluate((True,))
    assert decision.direction == 0
    band, crossed, _ = gating.apply(3, decision)
    assert band == 3
    assert crossed is False


def test_the_band_does_not_cross_the_axis_join_on_accuracy():
    """sec:calibrate - the two axes are not commensurable, so promoting from 3 to 4 on
    an accuracy rule would assert a comparison the thesis refuses to make."""
    decision = gating.evaluate((True,) * 10)
    band, crossed, reason = gating.apply(3, decision)
    assert band == 3
    assert crossed is False
    assert "axis join" in reason


def test_the_band_moves_freely_within_an_axis():
    decision = gating.evaluate((True,) * 10)
    band, crossed, _ = gating.apply(1, decision)
    assert band == 2
    assert crossed is False


def test_crosses_join_detects_the_boundary_in_both_directions():
    assert progression.crosses_join(3, 4) is True
    assert progression.crosses_join(4, 3) is True
    assert progression.crosses_join(1, 3) is False
    assert progression.crosses_join(4, 5) is False


# --- the ladder -----------------------------------------------------------


def test_the_ladder_never_skips_a_rung():
    assert ladder.next_level(None) == 1
    assert ladder.next_level(1) == 2
    assert ladder.next_level(2) == 3
    assert ladder.next_level(3) == 4


def test_the_ladder_stops_at_the_terminal_level():
    assert ladder.next_level(4) == 4
    assert ladder.is_terminal(4)


def test_first_help_on_a_cycle_is_always_the_lowest_level():
    state = escalation.EscalationState(levels_issued=())
    should, why = escalation.should_escalate(state)
    assert should is False
    assert "lowest level" in why


def test_elapsed_time_alone_does_not_escalate():
    """sec:calibrate - a long pause before a prompt "may be evidence of planning, which
    is the behavior the whole system is trying to produce"."""
    state = escalation.EscalationState(levels_issued=(1,))
    should, why = escalation.should_escalate(state)
    assert not hasattr(state, "idle_seconds"), "there is no idle clock to read"
    assert should is False
    assert "planning" in why


def test_asking_for_help_escalates():
    state = escalation.EscalationState(levels_issued=(1,), student_asked_for_help=True)
    should, _ = escalation.should_escalate(state)
    assert should is True


def test_persisting_target_escalates():
    state = escalation.EscalationState(levels_issued=(1, 2), consecutive_unresolved=3)
    should, why = escalation.should_escalate(state)
    assert should is True
    assert "persisted" in why


def test_the_inactivity_trigger_is_removed():
    """Component 16 drops inactivity as a trigger. It is recorded as removed,
    not carried switched off."""
    assert escalation.INACTIVITY_REMOVED.value == "removed"
    assert not hasattr(escalation, "INACTIVITY_TRIGGER")
    assert not hasattr(escalation, "INACTIVITY_SECONDS")


def test_latency_affect_inference_is_recorded_as_removed():
    assert affect.LATENCY_INFERENCE_REMOVED.value == "removed"
    assert "sec:not-adopted" in affect.LATENCY_INFERENCE_REMOVED.thesis_says


# --- every template floor cell validates ---------------------------------


@pytest.mark.parametrize("category", list(Category))
@pytest.mark.parametrize("level", [lv.number for lv in ladder.LEVELS])
def test_every_template_floor_cell_passes_its_own_validation(category, level):
    """The specified safe path must itself be safe. 7 categories x 4 levels."""
    from promptcoach_ref.engines.base import ComposeRequest
    from promptcoach_ref.engines.deterministic import template_floor

    request = ComposeRequest(
        level=level,
        category=category,
        prompt_text="explain why the sky is blue",
        stated_intent="I want to tell my cousin about the sky",
        weakest_dimension_id=rubric.AUDIENCE_AWARENESS.id,
        protected_judgment="what counts as an explanation she will follow",
        missing_from_prompt=tuple(d.id for d in rubric.PLANNING_DIMENSIONS),
    )
    text = template_floor(request)
    check = validate(
        text,
        level=level,
        category=category,
        protected_judgment=request.protected_judgment,
        missing_from_prompt=request.missing_from_prompt,
    )
    assert check.ok, f"level {level} / {category.value}: {check.reason}"


# --- affect ---------------------------------------------------------------


def test_latency_is_recorded_but_never_read_as_affect():
    reading = affect.read(latency_ms=600_000)
    assert reading.frustration is False
    assert reading.boredom is False
    assert reading.observed_latency_ms == 600_000
    assert "planning" in reading.basis


def test_only_an_explicit_statement_counts_as_frustration():
    reading = affect.read(student_said_stuck=True)
    assert reading.frustration is True
    assert reading.basis == "the student said so"


# --- decomposition --------------------------------------------------------


def test_an_overlong_step_fails_validation():
    steps = [
        decomposition.Step(goal="g", instructions="x" * 300, checkpoint="c"),
        decomposition.Step(goal="g", instructions="short", checkpoint="c"),
        decomposition.Step(goal="g", instructions="short", checkpoint="c"),
    ]
    result = decomposition.validate(steps)
    assert not result
    assert any("characters" in f for f in result.failures)


def test_a_step_without_a_checkpoint_fails():
    steps = [
        decomposition.Step(goal="g", instructions="short", checkpoint=""),
        decomposition.Step(goal="g", instructions="short", checkpoint="c"),
        decomposition.Step(goal="g", instructions="short", checkpoint="c"),
    ]
    result = decomposition.validate(steps)
    assert not result
    assert any("checkpoint" in f for f in result.failures)


def test_too_many_steps_fails():
    steps = [
        decomposition.Step(goal="g", instructions="s", checkpoint="c") for _ in range(9)
    ]
    assert not decomposition.validate(steps)


def test_a_valid_decomposition_passes():
    steps = [
        decomposition.Step(goal="g", instructions="s", checkpoint="c") for _ in range(4)
    ]
    assert decomposition.validate(steps)


# --- the task bank matches the band definitions --------------------------


def test_bands_one_and_two_name_their_dimensions_and_band_three_does_not():
    for task in taskbank.TASKS:
        if task.band in (1, 2):
            assert task.named_dimensions, task.id
            assert len(task.named_dimensions) == task.band, task.id
        if task.band == 3:
            assert not task.named_dimensions, task.id


def test_band_four_supplies_an_output_and_band_five_does_not():
    """That is the entire difference between them - sec:calibrate."""
    for task in taskbank.TASKS:
        if task.band == 4:
            assert task.provided_model_output, task.id
        if task.band == 5:
            assert not task.provided_model_output, task.id


def test_every_band_has_tasks():
    for band in progression.BANDS:
        assert taskbank.in_band(band.number), band.number


def test_every_task_names_a_protected_judgment():
    for task in taskbank.TASKS:
        assert task.protected_judgment.strip(), task.id
