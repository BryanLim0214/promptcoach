"""How Layer 3 turns evidence into a ranked list.

sec:design names this the largest gap in the reference
design: "The classifier itself, and the category to dimension pairing in
operation. Nothing existing does this."

The thesis specifies the *shape* of the output - ranked, never a single label,
with confidence - and nothing about how to get there. Everything in this module
is therefore an implementation choice, including the priority order, which is the
part most likely to be wrong.
"""

from __future__ import annotations

from ..framework.taxonomy import Category
from .base import Choice, register

#: When several categories fire at similar confidence, something has to break the
#: tie. This order puts the failures that remove the student's own judgment above
#: the failures that merely leave the prompt thin.
PRIORITY: tuple[Category, ...] = (
    Category.DELEGATED_JUDGMENT,
    Category.INTENT_DRIFT,
    Category.BLIND_ACCEPTANCE,
    Category.UNDIAGNOSED_RETRY,
    Category.UNDER_SPECIFICATION,
    Category.BORROWED_PHRASING,
    Category.SOCIAL_FRAMING,
)

PRIORITY_CHOICE = register(
    Choice(
        id="classifier.priority_order",
        value=[c.value for c in PRIORITY],
        thesis_says=(
            "The thesis specifies ranked multiple assignment and no ranking rule. "
            "sec:design lists the classifier as unbuilt."
        ),
        borrowed_from="none",
        caveat=(
            "This ordering encodes a pedagogical judgment the thesis does not make: "
            "that delegating the decision is a worse failure than omitting a "
            "constraint. F1 and F4 both bear on whether it is right, and neither has "
            "been run."
        ),
    )
)

MIN_CONFIDENCE = 0.50

MIN_CONFIDENCE_CHOICE = register(
    Choice(
        id="classifier.min_confidence",
        value=MIN_CONFIDENCE,
        thesis_says="No confidence scale or threshold is specified for Layer 3.",
        borrowed_from="none",
        caveat=(
            "Below this an observation is recorded as insufficient evidence rather "
            "than as a category. That distinction matters: 'the system could not "
            "tell' is not 'the student did not fail'."
        ),
    )
)

MAX_RANKED = 3

MAX_RANKED_CHOICE = register(
    Choice(
        id="classifier.max_ranked",
        value=MAX_RANKED,
        thesis_says=(
            "The thesis does not say how many categories the ranked list should "
            "contain, only that it must be more than one label."
        ),
        borrowed_from="none",
        caveat=(
            "Three keeps the overlap visible - sec:diagnose says under specification and "
            "social framing 'co occur constantly' - without turning the diagnosis "
            "into the report card sec:respond warns against. Respond still acts on the top "
            "one only."
        ),
    )
)


def rank(
    scored: dict[Category, tuple[float, str]],
) -> list[tuple[Category, float, str]]:
    """Order by confidence, breaking ties on PRIORITY. Drop below threshold.

    Returns at most MAX_RANKED. The caller keeps everything that was dropped for
    the reason trace, so a below-threshold observation is still visible to the
    student as "seen but not acted on" rather than vanishing.
    """
    kept = [
        (cat, conf, trigger)
        for cat, (conf, trigger) in scored.items()
        if conf >= MIN_CONFIDENCE
    ]
    kept.sort(key=lambda row: (-row[1], PRIORITY.index(row[0])))
    return kept[:MAX_RANKED]


def below_threshold(
    scored: dict[Category, tuple[float, str]],
) -> list[tuple[Category, float, str]]:
    out = [
        (cat, conf, trigger)
        for cat, (conf, trigger) in scored.items()
        if 0.0 < conf < MIN_CONFIDENCE
    ]
    out.sort(key=lambda row: -row[1])
    return out


# ---------------------------------------------------------------------------
# F4: the cheapest experiment in Chapter 12, and it needs two modes
# ---------------------------------------------------------------------------

SELECTION_MODES: tuple[str, ...] = ("diagnosis", "weakest_dimension")

SELECTION_MODE = register(
    Choice(
        id="classifier.selection_mode",
        value="diagnosis",
        thesis_says=(
            "sec:falsify - Layer 3 fails as specified 'if diagnosis "
            "adds nothing over score alone, that is, if responses selected by "
            "diagnosis produce no better revision than responses selected by the "
            "weakest dimension. This is the cheapest experiment in the list and "
            "should be run first.'"
        ),
        borrowed_from="none",
        caveat=(
            "Both modes are implemented so that experiment can actually be run. A "
            "system that only supported diagnosis-selected responses would make its "
            "own falsification impossible, which is why this is a switch and not a "
            "constant."
        ),
    )
)
