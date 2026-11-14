"""The chapters that are not the framework.

Chapters 10 to 12 become code (framework/, policy/, layers/, tests/). Chapters 1,
2, 3, 9, 12 and 13 become this: the thesis statement, the research questions,
the scope, the threats, and the remaining work, in the thesis's words, so the
running app can state its own limits. Chapters 4 and 5 (the user studies)
become `framework/classroom.py`; Chapters 6 to 8 (the builds) become the
mechanisms in `framework/` and `policy/`.

User-study numbers below are self-report unless stated, and none of them is
evidence that a student learned anything.
"""

from __future__ import annotations

from dataclasses import dataclass

from .framework.grades import SECTION_LABELS


@dataclass(frozen=True)
class Passage:
    #: Section label in the thesis.
    label: str
    heading: str
    text: str

    def __post_init__(self) -> None:
        if self.label not in SECTION_LABELS:
            raise ValueError(f"{self.label} is not a section label")

    @property
    def chapter(self) -> str:
        return SECTION_LABELS[self.label]


TITLE = "Learning to Prompt: A Design Framework for Middle School AI Literacy"

# --- Chapter 1 --------------------------------------------------------------

THESIS_STATEMENT = Passage(
    label="sec:intro",
    heading="Thesis statement",
    text=(
        # Verbatim from 1_introduction.tex (Thesis Statement), revised after the
        # second review round (D01, M1).
        "Two exploratory user studies showed that short game sessions are "
        "workable. One used an image-prompt game with 22 students in grades 2 to "
        "9 (4 in grades 6 to 8), and the other a prompt-selection game with 60 "
        "students in grades 6 to 8. In the one study that measured confidence "
        "before and after, more students rated it higher than lower right after "
        "playing. The studies also showed what the games could not do. Neither "
        "game measured the quality of a student's prompt, and neither asked a "
        "student to revise her own prompt. Building on those findings and on "
        "three coaching systems we built, this thesis assembles a five-layer "
        "design framework for teaching prompt writing. Each part of the framework "
        "is traced to a named study or source, graded by the strength of its "
        "evidence, and stated precisely enough to be built and tested."
    ),
)

RESEARCH_QUESTIONS: tuple[str, ...] = (
    "RQ1 (PicPrompt, Ch 4). What changed for students after a short image-prompt "
    "game, and which of those changes can the survey actually support?",
    "RQ2 (Promptemon, Ch 5). Does students' self-rated confidence rise after a "
    "short prompt game, and does a comparable item about how to write a prompt "
    "move with it?",
    "RQ3 (PromptAloud and Proem, Ch 6). Can prompt quality be scored in a way that "
    "does not depend on one AI model or on surface wording?",
    "RQ4 (MathEduAI, Ch 7). Which ways of responding to errors and adjusting "
    "difficulty carry over from a subject with right answers?",
    "RQ5 (PyPal, Ch 8). What carries over from a tutor built for learners that "
    "default designs leave out, and where does it stop working when no single "
    "right answer exists?",
    "RQ6 (Synthesis, Ch 9 to 12). What requirements follow from the pattern across "
    "the five studies, does a design built to meet them hold together when "
    "implemented, and what result would show it is wrong?",
)

SCOPE = Passage(
    label="sec:intro",
    heading="Scope and what is not claimed",
    text=(
        "No student has used the framework. The two user studies used games "
        "built before it, and their outcomes are self-report from one-group, "
        "pre/post designs with no comparison group. The three builds involved no "
        "students at all: their numbers come from hand-built benchmark items, "
        "automated harnesses, and simulated learner profiles, and their reliability "
        "evidence is agreement between AI graders, not with a teacher. The thesis "
        "therefore makes no claim that the framework improves learning. It claims "
        "that each component is traced to a named study and graded, that the "
        "components compose, that the composition is specified precisely enough to "
        "build, and that it states what result would show it wrong."
    ),
)

WHY_THE_BOUNDARY = Passage(
    label="sec:intro",
    heading="Why confidence is not the outcome",
    text=(
        "In the Promptemon re-analysis, 26 of 53 matched students rated their "
        "confidence higher after a short station visit, 8 lower and 19 the same, "
        "while on the one identical item about how to write a prompt, 31 of 52 "
        "chose the structured option before and 27 after: no improvement. "
        "Self-rated confidence and careful practice are "
        "different things, and a tool that raises the first without the second is "
        "not the tool this thesis is after. That is why the framework scores the "
        "prompt rather than the student's rating of it, and records the gap between "
        "the two."
    ),
)

# --- Chapter 2 --------------------------------------------------------------

WHY_INPUT_SIDE = Passage(
    label="sec:background",
    heading="The neglected input side",
    text=(
        "The instructional response to generative AI has concentrated on the output "
        "side, teaching students to evaluate what a model returns. The input side, "
        "what the student hands the model in the first place, has no instructional "
        "framework, no error taxonomy, and until recently no objective measure."
    ),
)

WHERE_THE_RUBRIC_COMES_FROM = Passage(
    label="sec:background",
    heading="Where the six dimensions come from",
    text=(
        "The dimensions derive from Flavell's decomposition of metacognition. Two of "
        "them, Iteration Awareness and Reflection, sit at the evaluative end. In "
        "both grader pairs the two evaluative "
        "dimensions had the lowest agreement, though which of the two was lowest "
        "depended on the pair, which is why the framework attaches lower confidence "
        "to them rather than discarding them."
    ),
)

# --- Chapter 9 --------------------------------------------------------------

REQUIREMENTS: tuple[tuple[str, str, str], ...] = (
    ("R1", "The student sees what her own words produced, quickly, at no cost "
     "for failing.",
     "Self-report acceptance only; the order was never varied, so the "
     "mechanism is untested (Argued)"),
    ("R2", "Skill is measured from the prompt, not from self-rating.",
     "Descriptive pattern; confidence and the strategy item are different "
     "constructs"),
    ("R3", "Revision of her own prompt is built into the task.",
     "Design inspection: neither game allowed it"),
    ("R4", "The judge that scores her work is not the model that produced the "
     "output.", "Literature (Transferred)"),
    ("R5", "Choosing parts from a menu is not composing a prompt.",
     "Design inspection: Promptemon students picked from prepared choices"),
    ("R6", "Watch for handing judgment to the AI.",
     "Build 1's over-reliance detector and the literature on cognitive "
     "offloading"),
)

# --- Chapter 12: threats ----------------------------------------------------

THREATS: tuple[Passage, ...] = (
    Passage(
        label="sec:threats",
        heading="No student has used the framework",
        text=(
            "The reference implementation exists and has not been used with "
            "students, so nothing here speaks to student behavior. What would "
            "resolve it: a classroom evaluation under ethics review."
        ),
    ),
    Passage(
        label="sec:threats",
        heading="The user-study numbers are self-report",
        text=(
            "Both user studies were one-group pre/post designs with no "
            "comparison group. The Promptemon analysis is a post hoc secondary "
            "analysis by a member of the original team and was not pre-registered; "
            "groups shared stations, so its p-values are likely too small. "
            "PicPrompt's one performance measure was lost to survey fatigue."
        ),
    ),
    Passage(
        label="sec:threats",
        heading="Two models can be wrong together",
        text=(
            "Cross model agreement does not establish independence of priors. Both "
            "graders were pretrained on overlapping public text, so both could "
            "diverge from a teacher in the same direction and still agree with each "
            "other closely. Every claim that rests on the rubric inherits that "
            "limit, and so does the calibration gap, because its 'measured' side is "
            "a model score."
        ),
    ),
    Passage(
        label="sec:threats",
        heading="Reliability expires",
        text=(
            "A reliability coefficient tied to two specific model versions expires "
            "when either is retired, so a system built to this framework needs a "
            "revalidation procedure rather than a one time certificate."
        ),
    ),
    Passage(
        label="sec:threats",
        heading="Latency may exceed patience",
        text=(
            "In the Proem evaluation configuration the full pipeline took 5.7 "
            "seconds on average and 8.6 at the 95th percentile. That cost is paid "
            "on every attempt and may exceed middle school patience."
        ),
    ),
    Passage(
        label="sec:threats",
        heading="Building it shows it composes, not that it teaches",
        text=(
            "This application shows that the specification is implementable and "
            "that the layers compose. It is not evidence that the framework helps a "
            "student write better prompts."
        ),
    ),
)

# --- Chapter 13: what is left -----------------------------------------------

REMAINING: tuple[str, ...] = (
    "Score the same items against teacher judgment. Cross model agreement is a "
    "necessary and not sufficient gate.",
    "Classify a corpus of authentic middle school prompts with the taxonomy, "
    "independently annotated, and measure coverage and agreement.",
    "Author a task bank ordered by the five bands, with a placement pretest so band "
    "1 rests on data rather than argument.",
    "Run the cheapest experiment first: does diagnosis-selected help produce better "
    "revision than weakest-dimension-selected help?",
    "Run F7: does requiring a reasoned revision change first-to-revised scores "
    "more than not requiring it?",
    "Run F8: does showing the calibration gap narrow it over a session, and does it "
    "change how often students revise?",
    "Run F9: do an independent judge and a self-judging generator differ by more "
    "than paraphrase noise on student prompts?",
    "Test whether the worked contrast at level 4 holds a student the way a worked "
    "solution does.",
)

CONCLUSION = Passage(
    label="sec:conclusion",
    heading="What this is",
    text=(
        "The framework is traced, graded, specified and falsifiable. It is not "
        "validated. Its four original components - the taxonomy, the progression, "
        "the reasoned same-task revision, and the calibration gap - are all Argued, "
        "and a reader who wants to attack this thesis should start there."
    ),
)

# --- What this application does and does not show ---------------------------

WHAT_RUNNING_THIS_SHOWS = (
    "That the specification is implementable: each layer's output is sufficient "
    "for the next layer's input, and the constraints the thesis states - including "
    "the reasoned revision, the calibration gap, a judge that is a different "
    "model from the generator, and scoring only what she composed - can be "
    "enforced in code rather than in prose."
)

WHAT_IT_DOES_NOT_SHOW = (
    "Anything about students. It has not been used with students. The rules in "
    "policy/ are implementation choices, not findings, and some of them are "
    "refusals to act on signals the thesis says may be backwards."
)


def payload() -> dict:
    def p(passage: Passage) -> dict:
        return {
            "chapter": passage.chapter,
            "label": passage.label,
            "heading": passage.heading,
            "text": passage.text,
        }

    return {
        "title": TITLE,
        "thesis_statement": p(THESIS_STATEMENT),
        "research_questions": list(RESEARCH_QUESTIONS),
        "requirements": [
            {"id": r, "requirement": text, "strength": strength}
            for r, text, strength in REQUIREMENTS
        ],
        "scope": p(SCOPE),
        "why_the_boundary": p(WHY_THE_BOUNDARY),
        "why_input_side": p(WHY_INPUT_SIDE),
        "where_the_rubric_comes_from": p(WHERE_THE_RUBRIC_COMES_FROM),
        "threats": [p(t) for t in THREATS],
        "remaining": list(REMAINING),
        "conclusion": p(CONCLUSION),
        "shows": WHAT_RUNNING_THIS_SHOWS,
        "does_not_show": WHAT_IT_DOES_NOT_SHOW,
    }
