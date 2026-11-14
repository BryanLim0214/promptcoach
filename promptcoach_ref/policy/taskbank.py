"""Tasks, ordered by the five band progression.

sec:design lists "A task bank ordered by the five band
progression" as new work, and sec:remaining adds that authoring one
"Needs a placement pretest to set band 1 by data rather than argument."

So every task here is authored for this implementation. Only one is the thesis's:
`BABYSITTING` is the band 3 worked example from sec:design,
reproduced verbatim so the golden-transcript test replays the manuscript's own
example rather than a paraphrase of it.

Band assignment follows tab:progression's rule literally:

  bands 1-2  N planning dimensions, *named in the task*
  band 3     three or more, *implied by a scenario and not named*
  band 4     an evaluative dimension, with an output in front of her
  band 5     an evaluative dimension, with no output to look at

`named_dimensions` is therefore non-empty exactly for bands 1 and 2, and
`provided_model_output` is non-empty exactly for band 4. Both are asserted.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..framework import rubric
from ..framework.progression import BY_NUMBER as BANDS
from .base import Choice, register

BANK = register(
    Choice(
        id="taskbank.authored",
        value="10 tasks, two per band",
        thesis_says=(
            "sec:design lists a task bank ordered by the five "
            "bands as new work; the thesis contains one worked example and two "
            "illustrative phrases per band."
        ),
        borrowed_from=(
            "The band 3 task is sec:design verbatim. The other "
            "nine are authored here."
        ),
        caveat=(
            "sec:remaining - setting band 1 properly 'needs a placement "
            "pretest' for how many middle schoolers already supply one named "
            "dimension unprompted. No such pretest exists, so band 1 rests on "
            "argument, and the whole progression is graded Argued and never tested."
        ),
    )
)


@dataclass(frozen=True)
class Task:
    id: str
    band: int
    topic: str
    scenario: str
    #: The decision the task exists to make the student practise. No response at
    #: any ladder level may make this decision for her.
    protected_judgment: str
    #: Bands 1-2 only: the planning dimensions the task names outright.
    named_dimensions: tuple[str, ...] = ()
    #: Band 4 only: the output she evaluates.
    provided_model_output: str = ""
    reading_load: str = "standard"
    from_thesis: bool = False

    def __post_init__(self) -> None:
        band = BANDS[self.band]
        if band.dimensions_named_in_task is True and not self.named_dimensions:
            raise ValueError(
                f"{self.id}: band {self.band} names its dimensions in the task"
            )
        if band.dimensions_named_in_task is False and self.named_dimensions:
            raise ValueError(
                f"{self.id}: band 3 implies its dimensions through a scenario and "
                "does not name them"
            )
        if self.band == 4 and not self.provided_model_output:
            raise ValueError(
                f"{self.id}: band 4 requires an output in front of her"
            )
        if self.band == 5 and self.provided_model_output:
            raise ValueError(
                f"{self.id}: band 5 has no output to look at - that is what "
                "separates it from band 4"
            )
        for d in self.named_dimensions:
            if d not in rubric.BY_ID:
                raise ValueError(f"{self.id}: {d} is not a rubric dimension")


# --- Band 1: one planning dimension, named ---------------------------------

B1_READING_LEVEL = Task(
    id="b1-reading-level",
    band=1,
    topic="civics",
    scenario=(
        "Get an AI to explain how a law gets made. Your prompt has to say what "
        "reading level you want it written at."
    ),
    protected_judgment="what reading level actually suits your reader",
    named_dimensions=(rubric.CONSTRAINT_SETTING.id,),
)

B1_AUDIENCE = Task(
    id="b1-audience",
    band=1,
    topic="science",
    scenario=(
        "Get an AI to describe what a volcano does. Your prompt has to say who is "
        "going to read it."
    ),
    protected_judgment="who the explanation is for",
    named_dimensions=(rubric.AUDIENCE_AWARENESS.id,),
    reading_load="reduced",
)

# --- Band 2: two planning dimensions, named --------------------------------

B2_LEVEL_AND_LENGTH = Task(
    id="b2-level-and-length",
    band=2,
    topic="literature",
    scenario=(
        "Get an AI to summarise a book you have read. Your prompt has to say both "
        "the reading level and how long the summary should be."
    ),
    protected_judgment="which parts of the book matter enough to keep",
    named_dimensions=(rubric.CONSTRAINT_SETTING.id, rubric.SPECIFICITY.id),
)

B2_AUDIENCE_AND_FORMAT = Task(
    id="b2-audience-and-format",
    band=2,
    topic="school-life",
    scenario=(
        "Get an AI to help you tell people about a club you want to start. Your "
        "prompt has to say who will read it and what form it should take."
    ),
    protected_judgment="what the club is actually for",
    named_dimensions=(rubric.AUDIENCE_AWARENESS.id, rubric.SPECIFICITY.id),
)

# --- Band 3: three or more, implied by a scenario, not named ---------------

BABYSITTING = Task(
    id="b3-babysitting",
    band=3,
    topic="science",
    scenario=(
        "You are babysitting tonight, and the child you are watching keeps asking "
        "why the sky is blue. Get an AI to give you something you can say to her."
    ),
    protected_judgment="what counts as an explanation she will actually follow",
    from_thesis=True,
)

B3_COACH = Task(
    id="b3-coach",
    band=3,
    topic="school-life",
    scenario=(
        "Your team lost badly and your coach asked you to say something to the "
        "group before practice tomorrow. Get an AI to help you work out what to say."
    ),
    protected_judgment="what your team actually needs to hear from you",
)

# --- Band 4: an evaluative dimension, with an output in front of her -------

B4_REPAIR_EXPLANATION = Task(
    id="b4-repair-explanation",
    band=4,
    topic="science",
    scenario=(
        "Below is what an AI produced when someone asked it to explain gravity to a "
        "younger student. Read it, decide what is wrong with it, and write a follow "
        "up prompt that fixes that one thing."
    ),
    protected_judgment="which weakness is the one worth fixing",
    provided_model_output=(
        "Gravity is a fundamental force of attraction between masses, described by "
        "Newton's law of universal gravitation, whereby every particle attracts "
        "every other particle with a force proportional to the product of their "
        "masses and inversely proportional to the square of the distance between "
        "their centres. This force governs planetary motion, tidal phenomena, and "
        "the structure of galaxies."
    ),
)

B4_REPAIR_SUMMARY = Task(
    id="b4-repair-summary",
    band=4,
    topic="history",
    scenario=(
        "Below is an AI's summary of why people moved west in the 1800s. Read it, "
        "work out what it left out, and write a follow up prompt that gets that back."
    ),
    protected_judgment="what the summary owes the people it leaves out",
    provided_model_output=(
        "In the 1800s many Americans moved west in search of land, opportunity, and "
        "a fresh start. The journey was difficult but pioneers were rewarded with "
        "fertile farmland and the chance to build new communities on the frontier."
    ),
    reading_load="reduced",
)

# --- Band 5: an evaluative dimension, with no output to look at ------------

B5_STANDARD_FIRST = Task(
    id="b5-standard-first",
    band=5,
    topic="literature",
    scenario=(
        "You are going to ask an AI to help you plan an essay. Before you ask it "
        "anything, write down what a good answer would have to do. Then write the "
        "prompt."
    ),
    protected_judgment="what makes an essay plan good, decided before you see one",
)

B5_STANDARD_SCIENCE = Task(
    id="b5-standard-science",
    band=5,
    topic="science",
    scenario=(
        "You want an AI to help you design an experiment. Say first how you would "
        "know whether its suggestion was any good, then ask."
    ),
    protected_judgment="the standard the suggestion has to meet",
)


TASKS: tuple[Task, ...] = (
    B1_READING_LEVEL,
    B1_AUDIENCE,
    B2_LEVEL_AND_LENGTH,
    B2_AUDIENCE_AND_FORMAT,
    BABYSITTING,
    B3_COACH,
    B4_REPAIR_EXPLANATION,
    B4_REPAIR_SUMMARY,
    B5_STANDARD_FIRST,
    B5_STANDARD_SCIENCE,
)

BY_ID: dict[str, Task] = {t.id: t for t in TASKS}

#: The task the golden-transcript test replays.
WORKED_EXAMPLE_ID = BABYSITTING.id


def in_band(band: int) -> tuple[Task, ...]:
    return tuple(t for t in TASKS if t.band == band)


ENTRY_BAND = register(
    Choice(
        id="taskbank.entry_band",
        value=1,
        thesis_says=(
            "The thesis specifies no band placement rule. sec:remaining "
            "says band 1 needs a placement pretest."
        ),
        borrowed_from="none",
        caveat=(
            "Everyone starts at band 1. Without the pretest there is no basis for "
            "placing a student anywhere else, and guessing higher would be a claim "
            "about a base rate the thesis says nobody has."
        ),
    )
)


def next_task(band: int, exclude: frozenset[str] = frozenset()) -> Task | None:
    """Prefer an unseen task in the band, and prefer a new topic.

    Topic variation matters because a band change justified by two attempts at
    the same topic is a claim about one topic, not about the band.
    """
    candidates = [t for t in in_band(band) if t.id not in exclude]
    if not candidates:
        candidates = list(in_band(band))
    return candidates[0] if candidates else None
