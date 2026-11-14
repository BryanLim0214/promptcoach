"""The golden transcript: Chapter 11's worked example, replayed.

sec:design traces one hypothetical interaction through all
five layers and states what each one produces. Every assertion below is the
thesis's own, and this test is the closest thing to a specification conformance
check the manuscript makes possible.

The thesis is explicit that the values are illustrative: "The scores below
illustrate how the layers hand work to each other. They are not measurements. No
student has used the reference design; I constructed this example to show the
mechanism, not to report a result." That is exactly why it is a good conformance
target - it fixes the mechanism without claiming anything empirical.
"""

from __future__ import annotations

import pytest

from promptcoach_ref.framework import ladder, rubric
from promptcoach_ref.framework.taxonomy import Category
from promptcoach_ref.policy import taskbank

from conftest import WORKED_REASON, WORKED_SPOKEN, WORKED_TYPED

# tab:worked, sec:design.
THESIS_SCORES = {
    "context_clarity": 2,
    "specificity": 1,
    "iteration_awareness": 1,
    "audience_awareness": 1,
    "constraint_setting": 1,
    "reflection": 1,
}


def test_the_task_is_the_thesis_own_and_sits_at_band_three():
    task = taskbank.BY_ID[taskbank.WORKED_EXAMPLE_ID]
    assert task.from_thesis is True
    assert task.band == 3
    assert "babysitting" in task.scenario
    assert "why the sky is blue" in task.scenario


def test_layer_one_stores_both_records_and_judges_nothing(worked):
    """sec:design - "stores both, with the timing. Nothing has been judged yet." """
    record = worked.elicit.record
    assert record is not None
    assert record.stated_intent == WORKED_SPOKEN
    assert record.prompt_text == WORKED_TYPED
    assert record.intent_modality == "speech"


@pytest.mark.parametrize("dimension_id,expected", sorted(THESIS_SCORES.items()))
def test_layer_two_reproduces_tab_worked(worked, dimension_id, expected):
    score = worked.measure.scores[dimension_id]
    assert score.value == expected, (
        f"{rubric.BY_ID[dimension_id].name}: got {score.value}, "
        f"tab:worked gives {expected}"
    )


def test_the_two_evaluative_dimensions_carry_lower_confidence(worked):
    scores = worked.measure.scores
    evaluative = [scores[d.id].confidence for d in rubric.EVALUATIVE_DIMENSIONS]
    planning = [scores[d.id].confidence for d in rubric.PLANNING_DIMENSIONS]
    assert max(evaluative) < max(planning)


def test_layer_three_ranks_intent_drift_above_under_specification(worked):
    """sec:design - the pattern "matches intent drift... and it matches it more
    strongly than under specification, because the student is not missing the
    knowledge, she is failing to transfer it. The diagnosis returns intent drift
    first and under specification second."
    """
    assert worked.diagnose is not None
    categories = [a.category for a in worked.diagnose.assignments]
    assert worked.diagnose.target is Category.INTENT_DRIFT
    assert Category.UNDER_SPECIFICATION in categories
    assert categories.index(Category.INTENT_DRIFT) < categories.index(
        Category.UNDER_SPECIFICATION
    )


def test_the_diagnosis_names_the_three_threads_the_thesis_names(worked):
    """sec:design - "three pieces of relevant thinking, the reader, the length, and
    the complexity ceiling, are present in the spoken account and absent from
    the prompt." """
    drift = next(
        a for a in worked.diagnose.assignments if a.category is Category.INTENT_DRIFT
    )
    trigger = drift.trigger
    assert rubric.AUDIENCE_AWARENESS.name in trigger  # the reader
    assert rubric.SPECIFICITY.name in trigger  # the length
    assert rubric.CONSTRAINT_SETTING.name in trigger  # the complexity ceiling


def test_layer_four_issues_the_lowest_level(worked):
    """sec:design - "issues help at the lowest ladder level, since this is a first
    attempt with no escalation triggered"."""
    assert worked.respond is not None
    assert worked.respond.level == ladder.FIRST_LEVEL


def test_the_response_is_a_question_not_a_rewrite(worked):
    """sec:design - "It does not supply a corrected prompt... It does not list all five
    weak dimensions... It does not report anything to a teacher." """
    text = worked.respond.text
    assert text.strip().endswith("?")
    # Not a rewritten prompt.
    assert "for a seven year old" not in text.lower()
    # Not a report card: it names one failure, not five dimensions.
    named = [d.name for d in rubric.DIMENSIONS if d.name.lower() in text.lower()]
    assert len(named) <= 1


def test_the_response_replays_her_own_intent(worked):
    """sec:design gives the response as: "you said out loud who this was for and how
    long it should be, and neither made it into what you typed. Which of those
    would change the answer most?" """
    text = worked.respond.text.lower()
    assert "said" in text
    assert "typed" in text


def test_the_band_holds_at_three_after_one_success(session):
    """sec:design - "The band holds at 3 either way, because a single success does not
    satisfy both the rate and the streak condition." """
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
    assert revision.calibrate.band == 3
    assert revision.calibrate.band_changed is False
    assert "single condition" in revision.calibrate.reason


def test_the_sentinel_stays_quiet_on_a_genuine_revision(session):
    """sec:design - "The over reliance signals stay quiet: she revised instead of
    resubmitting unchanged, and she did not ask the tool to decide what a good
    answer would be." """
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
    signals = revision.calibrate.sentinel
    assert signals["mindless_retry"] == 0.0
    assert signals["excessive_deference"] == 0.0


def test_the_three_properties_the_example_demonstrates(worked):
    """sec:design - "The diagnosis was only possible because two records existed
    instead of one. The response was selected by the failure category, not by the
    score. And the student was never told what to write." """
    # Two records, not one.
    assert worked.elicit.record.stated_intent != worked.elicit.record.prompt_text
    # Selected by category.
    assert worked.respond.target is worked.diagnose.target
    # Never told what to write - checked by the validator on the way out.
    assert worked.respond.used_template_floor in (True, False)
    assert "sky is blue for" not in worked.respond.text.lower()
