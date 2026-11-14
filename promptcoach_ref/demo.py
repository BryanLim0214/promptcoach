"""Replay Chapter 11's worked example in the terminal.

    python -m promptcoach_ref.demo

Runs offline on the deterministic engine. Every value printed is either from the
manuscript or produced by this implementation, and the output says which.
"""

from __future__ import annotations

from .engines import DeterministicEngine
from .framework import ladder, rubric
from .framework.taxonomy import BY_ID as TAXONOMY
from .layers import Consent
from .policy import taskbank
from .session import Session

SPOKEN = (
    "Okay so I have to explain the sky thing to my cousin, she's like seven so it "
    "can't be complicated, maybe just a few sentences."
)
TYPED = "explain why the sky is blue"
REVISION = (
    "explain why the sky is blue for a seven year old, keep it to a few sentences"
)
#: Authored here: the thesis's revision is longer; this shorter one is what the test runs.
REASON = "I added who it is for and how long it should be"
PREDICTED = 3

# tab:worked, sec:design
THESIS_SCORES = {
    "context_clarity": 2,
    "specificity": 1,
    "iteration_awareness": 1,
    "audience_awareness": 1,
    "constraint_setting": 1,
    "reflection": 1,
}

BAR = "─" * 74


def head(text: str) -> None:
    print(f"\n{text}\n{BAR}")


def main() -> None:
    task = taskbank.BY_ID[taskbank.WORKED_EXAMPLE_ID]

    print(BAR)
    print("PromptCoach Reference — Chapter 11 worked example")
    print(BAR)
    print("The thesis constructed this example to show the mechanism, not to")
    print("report a result. No student has used the reference design.")

    head(f"TASK  ·  band {task.band}  ·  {task.id}")
    print(task.scenario)
    print(f"\nhers to decide: {task.protected_judgment}")

    session = Session(
        session_id="demo",
        consent=Consent(
            platform_use=True, research_participation=False, audio_retention=True
        ),
        engine=DeterministicEngine(),
    )
    session.task_id = task.id
    session.band = task.band

    first = session.submit(
        stated_intent=SPOKEN,
        prompt_text=TYPED,
        intent_modality="speech",
        predicted_rating=PREDICTED,
    )

    head("LAYER 1  ELICIT  ·  a paired record of intent and artifact, plus timing")
    record = first.elicit.record
    assert record is not None
    print(f"  spoken : {record.stated_intent}")
    print(f"  typed  : {record.prompt_text}")
    print("  nothing has been judged yet")

    head("LAYER 2  MEASURE  ·  six dimension scores with per dimension confidence")
    print(f"  {'dimension':24s} {'here':>5s} {'thesis':>7s} {'conf':>6s}")
    for dim in rubric.DIMENSIONS:
        score = first.measure.scores[dim.id]
        flag = " evaluative" if dim.is_evaluative else ""
        print(
            f"  {dim.name:24s} {str(score.value):>5s} "
            f"{THESIS_SCORES[dim.id]:>7d} {score.confidence:>6.2f}{flag}"
        )
    print(f"\n  overall {first.measure.overall}; she predicted {PREDICTED}; "
          f"gap {first.calibration_gap:+.2f} (hers only)")
    print(f"  judged by {first.measure.judge_model}; answered by "
          f"{first.measure.generator_model}; independent: "
          f"{first.measure.judge_independent_of_generator}")
    print(f"\n  {rubric.THIRD_BAR_UNCLEARED}")

    head("LAYER 3  DIAGNOSE  ·  a ranked list of failure categories with confidence")
    for a in first.diagnose.assignments:
        marker = "→" if a.category is first.diagnose.target else " "
        print(f"  {marker} {a.rank}. {TAXONOMY[a.category].name:22s} {a.confidence:.2f}")
        print(f"       {a.trigger}")
    print(f"\n  ranked, never a single label — the categories overlap by design")

    head("LAYER 4  RESPOND  ·  the level issued, and whether the next attempt improved")
    level = ladder.BY_NUMBER[first.respond.level]
    print(f"  level {level.number}: {level.gives}")
    print(f"  she still: {level.student_still_does}\n")
    for line in first.respond.text.splitlines():
        print(f"    {line}")
    print(f"\n  {first.respond.expected_action}")

    print("\n  she revises ...")
    print(f"    {REVISION}")

    unreasoned = session.submit(
        stated_intent=SPOKEN,
        prompt_text=REVISION,
        parent_attempt_id=record.attempt_id,
    )
    print(f"\n  sent without a reason, it is not scored:\n    {unreasoned.clarification}")
    print(f"\n  she says why: {REASON}")

    second = session.submit(
        stated_intent=SPOKEN,
        prompt_text=REVISION,
        parent_attempt_id=record.attempt_id,
        revision_reason=REASON,
        predicted_rating=PREDICTED,
    )

    head("LAYER 5  CALIBRATE  ·  no downstream requirement is stated for this layer")
    cal = second.calibrate
    assert cal is not None
    print(f"  paired dimension moved : {cal.paired_delta:+.0f}  ({cal.pairing_strictness})")
    print(f"  unpaired movement      : {cal.unpaired_deltas}")
    print(f"  band                   : {cal.band}  (was {task.band})")
    print(f"  reason                 : {cal.reason}")
    print(f"  calibration gap        : {cal.calibration_gap}  (predicted minus measured; hers only)")
    print(f"  revision still pending : {cal.revision_pending}")
    print("\n  over-reliance signals, to her and to nobody else:")
    for key, value in cal.sentinel.items():
        print(f"    {key:32s} {value:.2f}")

    head("WHAT THIS SHOWED")
    print("  The diagnosis was only possible because two records existed instead")
    print("  of one. The response was selected by the failure category, not by the")
    print("  score. The student was never told what to write.")
    print()
    print("  It showed nothing about whether any of it teaches anyone anything.")
    print(BAR)


if __name__ == "__main__":
    main()
