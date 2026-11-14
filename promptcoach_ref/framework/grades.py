"""Evidence grading, on two axes.

The framework chapter (sec:framework) grades every component twice.

The **mechanism grade** records the route from evidence to the claim that the
mechanism works. Its meaning is unchanged from the earlier draft (sec:grades):

    Direct means a completed evaluation in the target domain supports the
    mechanism. Direct does not mean strong. Transferred means it was shown
    elsewhere and is assumed to carry, which is a real assumption with a named
    way of failing. Argued means it follows from evidence without having been
    tested at all.

The **need basis** is new. It records where the *need* for the component was
observed: in a user study with students, through its design or its
self-report data (User studies), in one of the three builds (Builds), or in the
literature or an ethical argument (Argument). The enum member is still
`STUDENTS` with value "students" so stored payloads stay readable; every
human-facing label comes from `NEED_LABEL` and says "User studies". A component
can rest on user-study data for its need and on nothing at all for its
mechanism; the two columns exist so that difference cannot be blurred.

Every constant in `promptcoach_ref.framework` carries a Cite, and every graded
component carries both grades. Every constant in `promptcoach_ref.policy`
carries an ImplementationChoice instead, because the thesis does not specify it.
Tests enforce both.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Grade(str, Enum):
    """The three mechanism grades. There is no fourth."""

    DIRECT = "direct"
    TRANSFERRED = "transferred"
    ARGUED = "argued"


class NeedBasis(str, Enum):
    """Where the need for a component was observed.

    The identifiers are stable API values. Display text is `label`, never the
    value: the first basis is shown as "User studies", because the need
    was observed in a study's design or its self-report data, not in students'
    prompts.
    """

    #: User studies (PicPrompt, Promptemon): their design or self-report.
    STUDENTS = "students"
    #: One of the three builds (PromptAloud and Proem, MathEduAI, PyPal).
    BUILDS = "builds"
    #: The literature, or an ethical argument.
    ARGUMENT = "argument"

    @property
    def label(self) -> str:
        return NEED_LABEL[self]


GRADE_DEFINITION: dict[Grade, str] = {
    Grade.DIRECT: (
        "A completed evaluation in the target domain supports the mechanism. "
        "Direct does not mean strong: the four Direct rows are Build 1 "
        "measurement results, resting on benchmarks of 30 items or fewer, "
        "written by the authors and scored by models."
    ),
    Grade.TRANSFERRED: (
        "The mechanism was shown somewhere else and is assumed to carry, which is "
        "a real assumption with a named way of failing."
    ),
    Grade.ARGUED: (
        "The mechanism follows from evidence without having been tested at all, "
        "and a reader who rejects the argument has nothing else to fall back on."
    ),
}

#: Human-facing names for the need basis. Every label shown in the app or
#: written into TRACEABILITY.md comes from here.
NEED_LABEL: dict[NeedBasis, str] = {
    NeedBasis.STUDENTS: "User studies",
    NeedBasis.BUILDS: "Builds",
    NeedBasis.ARGUMENT: "Argument",
}

NEED_DEFINITION: dict[NeedBasis, str] = {
    NeedBasis.STUDENTS: (
        "Need observed in a user study with students, through its design or "
        "its self-report data."
    ),
    NeedBasis.BUILDS: "The need was observed in one of the three builds.",
    NeedBasis.ARGUMENT: "The need rests on the literature or an ethical argument.",
}

#: sec:framework - "Mechanism: 4 Direct, 10 Transferred, 10 Argued." A test pins
#: these counts; if the implementation ever disagrees with the manuscript, that
#: test fails. (Was 5/10/9 until component 20 was regraded Argued, M7.)
EXPECTED_GRADE_COUNTS: dict[Grade, int] = {
    Grade.DIRECT: 4,
    Grade.TRANSFERRED: 10,
    Grade.ARGUED: 10,
}

#: sec:evidence - "By need basis, 4 rest on the user studies, 18 on the
#: builds, and 2 on argument."
EXPECTED_NEED_COUNTS: dict[NeedBasis, int] = {
    NeedBasis.STUDENTS: 4,
    NeedBasis.BUILDS: 18,
    NeedBasis.ARGUMENT: 2,
}

EXPECTED_COMPONENT_COUNT = 24


# ---------------------------------------------------------------------------
# Citations point at section labels of the thesis, never at file:line
# ---------------------------------------------------------------------------

#: Every section label the chapter map fixes (FRAMEWORK_SPEC section 2). A Cite
#: may only name one of these, so a citation cannot point at a section that the
#: thesis does not have. The traceability generator additionally checks each
#: label against `\label{...}` in the chapter sources when they are on disk.
SECTION_LABELS: dict[str, str] = {
    # Ch 1
    "sec:intro": "1",
    "sec:rqs": "1",
    "sec:contributions": "1",
    "sec:organization": "1",
    # Ch 2
    "sec:background": "2",
    "sec:bg-games": "2",
    "sec:bg-calibration": "2",
    "sec:bg-judges": "2",
    # Ch 3
    "sec:method": "3",
    "sec:chronology": "3",
    "sec:inclusion-rule": "3",
    "sec:grades": "3",
    "sec:ethics": "3",
    "sec:stats": "3",
    # Ch 4
    "sec:picprompt": "4",
    "sec:picprompt-carry": "4",
    # Ch 5
    "sec:promptemon": "5",
    "sec:promptemon-reanalysis": "5",
    "sec:promptemon-errata": "5",
    "sec:promptemon-carry": "5",
    # Ch 6 to 8
    "sec:build1": "6",
    "sec:carry1": "6",
    "sec:build2": "7",
    "sec:carry2": "7",
    "sec:build3": "8",
    "sec:carry3": "8",
    # Ch 9
    "sec:synthesis": "9",
    "sec:requirements": "9",
    "sec:not-adopted": "9",
    # Ch 10
    "sec:framework": "10",
    "sec:elicit": "10",
    "sec:measure": "10",
    "sec:diagnose": "10",
    "sec:respond": "10",
    "sec:calibrate": "10",
    "sec:commitments": "10",
    # Ch 11
    "sec:design": "11",
    "sec:implementation": "11",
    # Ch 12
    "sec:evidence": "12",
    "sec:falsify": "12",
    "sec:threats": "12",
    # Ch 13
    "sec:remaining": "13",
    "sec:conclusion": "13",
}


@dataclass(frozen=True)
class Cite:
    """A pointer into the thesis by section label.

    `label` must be one of SECTION_LABELS. `detail` names a table or row inside
    that section ("tab:ladder row 1") and is free text, because table labels are
    not fixed by the chapter map. Line numbers are not used: they rot the moment
    a paragraph moves.
    """

    label: str
    detail: str = ""
    quote: str = ""

    def __post_init__(self) -> None:
        if self.label not in SECTION_LABELS:
            raise ValueError(
                f"{self.label!r} is not a section label of the thesis. Cite a "
                "label from the chapter map, not a file or a line."
            )

    @property
    def chapter(self) -> str:
        return SECTION_LABELS[self.label]

    def __str__(self) -> str:
        return f"{self.label} ({self.detail})" if self.detail else self.label


@dataclass(frozen=True)
class GradedComponent:
    """One row of the framework's component table."""

    id: str
    name: str
    grade: Grade
    need: NeedBasis
    basis: str
    limit: str
    cite: Cite
    #: The classroom-derived requirement (R1 to R6, sec:requirements) the row
    #: answers, where it answers one.
    requirement: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.need, NeedBasis):
            raise TypeError(f"{self.id}: need basis must be a NeedBasis")
        if not self.basis.strip():
            raise ValueError(f"{self.id}: a graded component must state its basis")
        if not self.limit.strip():
            raise ValueError(
                f"{self.id}: a graded component must state its limit. The "
                "framework gives a limit for every row, including the direct ones."
            )


# ---------------------------------------------------------------------------
# The twenty-four graded components (sec:framework, renumbered 1 to 24)
# ---------------------------------------------------------------------------

SIX_DIMENSION_RUBRIC = GradedComponent(
    id="six_dimension_rubric",
    name="Six-dimension rubric",
    grade=Grade.DIRECT,
    need=NeedBasis.BUILDS,
    # Basis and limit follow tab:evidence (sec:evidence) row 1. "Different
    # vendors" is correct here: the Proem grader pair is Google and OpenAI.
    basis=(
        "Two AI graders from different vendors agreed at ICC 0.976 on 30 items, "
        "and paraphrase moved scores by 0.134 points on average (Proem); nine "
        "prompts from an LLM-simulated student kept the tier order. On 30 new "
        "items, Gemini against GPT-5.4 mini agreed at ICC 0.965 (95% CI 0.938 to "
        "0.980), and two Google model versions at 0.973 (0.936 to 0.990)."
    ),
    limit=(
        "Author-written items; no teacher scores; graders may share priors; "
        "largest paraphrase shift 0.50 in Proem and 0.833 in the replication."
    ),
    cite=Cite("sec:measure", "component 1"),
)

LOWER_CONFIDENCE_ON_EVALUATIVE = GradedComponent(
    id="lower_confidence_on_evaluative",
    name="Lower confidence on the evaluative dimensions",
    grade=Grade.DIRECT,
    need=NeedBasis.BUILDS,
    basis=(
        "The two evaluative dimensions were lower on average in every grader "
        "pair, but which one is lowest depends on the grader pair: Reflection "
        "(quadratic kappa 0.645) in Proem, Iteration Awareness (linear 0.404) "
        "between two Gemini versions, Context Clarity (linear 0.504) against "
        "GPT-5.4 mini."
    ),
    limit="A statistic about AI graders on author-written items, not about students.",
    cite=Cite("sec:measure", "component 2"),
)

CONTENT_OVER_FLUENCY = GradedComponent(
    id="content_over_fluency",
    name="Content over fluency",
    grade=Grade.DIRECT,
    need=NeedBasis.BUILDS,
    basis=(
        "On 12 matched pairs that held content fixed, rough English cost 0.139 "
        "points (95% bootstrap interval 0.046 to 0.245), within the limit set "
        "in advance (mean at most 0.25, upper bound below 0.5)."
    ),
    limit=(
        "Pairs written by one author imitating learner English; the cost grew "
        "with content quality (strong +0.250); no real multilingual student "
        "prompts."
    ),
    cite=Cite("sec:commitments", "component 3"),
)

OVER_RELIANCE_SEPARABLE = GradedComponent(
    id="over_reliance_separable",
    name="Over-reliance detector",
    grade=Grade.DIRECT,
    need=NeedBasis.BUILDS,
    basis=(
        "The sentinel separated the researchers' risk labels in both studies: "
        "AUC 0.81 in Proem (one run, 9 high-risk items) and 0.882 pooled over "
        "five runs in the replication, where single runs ranged from 0.825 to "
        "0.929. Not an improvement: the run-to-run range is larger than the gap "
        "between the two. Beyond the prompt score: item-level AUC 0.720 with "
        "the rubric alone, 0.905 with the detector added (likelihood-ratio "
        "p = .0045)."
    ),
    limit=(
        "Author labels; 9 high-risk items; unstable across runs (range 0.103); "
        "low-risk items averaged 0.412; the carrying signal changed between "
        "studies; the offline keyword rules were tested only on the authors' items."
    ),
    cite=Cite("sec:calibrate", "component 4"),
)

INTENT_ARTIFACT_GAP_DIAGNOSTIC = GradedComponent(
    id="intent_artifact_gap_diagnostic",
    name="Gap between plan and prompt is diagnostic",
    grade=Grade.ARGUED,
    need=NeedBasis.BUILDS,
    basis="Build 1 captures the spoken plan, and the gap signal fires.",
    limit=(
        "That the gap improves the help is untested, as is classroom speech "
        "capture."
    ),
    cite=Cite("sec:elicit", "component 5"),
)

CLASSIFY_BEFORE_RESPONDING = GradedComponent(
    id="classify_before_responding",
    name="Classify before responding",
    grade=Grade.TRANSFERRED,
    need=NeedBasis.BUILDS,
    basis="MathEduAI (Build 2), tested on constructed cases and simulated learners.",
    limit="Prompting has no correct answer, which weakens the analogy.",
    cite=Cite("sec:diagnose", "component 6"),
)

RANKED_MULTIPLE_ASSIGNMENT = GradedComponent(
    id="ranked_multiple_assignment",
    name="Ranked multiple assignment",
    grade=Grade.ARGUED,
    need=NeedBasis.BUILDS,
    basis=(
        "Follows from MathEduAI's one classifier failure, a constructed case "
        "where two error types overlapped."
    ),
    limit="Untested in prompting.",
    cite=Cite("sec:diagnose", "component 7"),
)

TEMPLATE_FLOOR = GradedComponent(
    id="template_floor",
    name="Template floor under generation",
    grade=Grade.TRANSFERRED,
    need=NeedBasis.BUILDS,
    basis=(
        "MathEduAI and PyPal; consistent with work on constrained tutoring "
        "dialogue."
    ),
    limit="The fixed responses for prompting are new and untested.",
    cite=Cite("sec:respond", "component 8"),
)

GRADUATED_LADDER = GradedComponent(
    id="graduated_ladder",
    name="Graduated ladder",
    grade=Grade.TRANSFERRED,
    need=NeedBasis.BUILDS,
    basis="PyPal (Build 3), where a correct solution exists to reveal.",
    limit="Not tested with students; the top level is replaced by component 17.",
    cite=Cite("sec:respond", "component 9"),
)

DUAL_CONDITION_GATING = GradedComponent(
    id="dual_condition_gating",
    name="Dual-condition difficulty gating",
    grade=Grade.TRANSFERRED,
    need=NeedBasis.BUILDS,
    basis="MathEduAI (Build 2), with simulated learners.",
    limit=(
        "Needs a task order that prompting lacks; its values are mathematics "
        "settings."
    ),
    cite=Cite("sec:calibrate", "component 10"),
)

SEVEN_CATEGORY_TAXONOMY = GradedComponent(
    id="seven_category_taxonomy",
    name="Seven-category taxonomy, with its pairing to dimensions",
    grade=Grade.ARGUED,
    need=NeedBasis.BUILDS,
    basis="Derived from rubric dimensions, detector signals, and published work.",
    limit=(
        "No student prompt classified with it; the derivation is close to "
        "circular, so the pairing Layer 5 tests against needs an outside test."
    ),
    cite=Cite("sec:diagnose", "component 11"),
)

FIVE_BAND_PROGRESSION = GradedComponent(
    id="five_band_progression",
    name="Five-band progression on two scales",
    grade=Grade.ARGUED,
    need=NeedBasis.BUILDS,
    basis=(
        "Two separate scales: bands 1 to 3 by planning dimension count, bands 4 "
        "and 5 by whether an output is visible during evaluation. No promotion "
        "rule crosses the join."
    ),
    limit=(
        "Never tested; no promotion rule between the scales; band 1 has no base "
        "rate."
    ),
    cite=Cite("sec:calibrate", "component 12"),
)

DIAGNOSTICS_BELONG_TO_STUDENT = GradedComponent(
    id="diagnostics_belong_to_student",
    name="Diagnostics belong to the student, and adaptation is visible to her",
    grade=Grade.ARGUED,
    need=NeedBasis.ARGUMENT,
    basis="An ethical position on the first half, defended not measured.",
    limit="The second half was built in MathEduAI but not evaluated.",
    cite=Cite("sec:commitments", "component 13"),
)

VALIDATED_DECOMPOSITION = GradedComponent(
    id="validated_decomposition",
    name="Validated task breakdown",
    grade=Grade.TRANSFERRED,
    need=NeedBasis.BUILDS,
    # M16: the earlier text said an unvalidated decomposition "recreated" the
    # overload; that is not in the PyPal source (FACTS P2). tab:evidence row 14.
    basis=(
        "PyPal (Build 3), where an unchecked breakdown would recreate the "
        "overload it was meant to remove."
    ),
    limit="Prompting tasks may break down differently.",
    cite=Cite("sec:elicit", "component 14"),
)

SINGLE_TARGET_RESPONSE = GradedComponent(
    id="single_target_response",
    name="Single target response",
    grade=Grade.TRANSFERRED,
    need=NeedBasis.BUILDS,
    # Corrected citation: the earlier draft cited Demszky and Liu, which does not
    # support this. Task-level, specific feedback is Hattie and Timperley (2007)
    # and Shute (2008); Build 1 implements it.
    basis=(
        "Reviews favor specific feedback about the task (Hattie and Timperley "
        "2007; Shute 2008); Build 1 gives one question per attempt."
    ),
    limit="That one target beats two is untested.",
    cite=Cite("sec:respond", "component 15"),
)

ESCALATION_ON_OBSERVABLE_CONDITIONS = GradedComponent(
    id="escalation_on_observable_conditions",
    name="Escalation on observable conditions",
    grade=Grade.TRANSFERRED,
    need=NeedBasis.BUILDS,
    basis=(
        "PyPal (Build 3): escalation on repeated failed attempts and on explicit "
        "requests for help ('I'm stuck'). Inactivity is dropped as a trigger, "
        "because a long pause before a prompt may be planning rather than "
        "struggle."
    ),
    limit="The thresholds were set for a task with a correct answer.",
    cite=Cite("sec:respond", "component 16"),
)

WORKED_CONTRAST_TERMINAL = GradedComponent(
    id="worked_contrast_terminal",
    name="Worked contrast at the top level",
    grade=Grade.ARGUED,
    need=NeedBasis.BUILDS,
    basis="Replaces showing a correct answer, which prompting lacks.",
    limit="The least supported claim; untested with students.",
    cite=Cite("sec:respond", "component 17"),
)

ACCESSIBILITY_IN_DEFAULT_PATH = GradedComponent(
    id="accessibility_in_default_path",
    name="Accessibility in the default path",
    grade=Grade.TRANSFERRED,
    need=NeedBasis.BUILDS,
    basis="PyPal (Build 3) and Universal Design for Learning.",
    limit="Not tested in a prompting task; not built in the reference implementation beyond the reduced-motion setting.",
    cite=Cite("sec:commitments", "component 18"),
)

CONSENT_SEPARABLE_FROM_USE = GradedComponent(
    id="consent_separable_from_use",
    name="Consent separate from use",
    grade=Grade.TRANSFERRED,
    need=NeedBasis.BUILDS,
    # Corrected citation: the disability-access source is not a source for
    # consent and is not cited for it.
    basis=(
        "PyPal (Build 3), implemented; the reference implementation keeps a "
        "typed path for students who decline the microphone."
    ),
    limit="Not a claim about outcomes; audio consent untried in a school.",
    cite=Cite("sec:commitments", "component 19"),
)

# --- the five new rows, from the classroom-derived requirements -------------

VISIBLE_CONSEQUENCE_BEFORE_COACHING = GradedComponent(
    id="visible_consequence_before_coaching",
    name="Visible consequence before coaching",
    # Regraded Direct -> Argued after the second review (R2_COMMITTEE M7): no
    # evaluation of the mechanism took place, because the order was never varied.
    grade=Grade.ARGUED,
    need=NeedBasis.STUDENTS,
    basis=(
        "Both games showed students the output first, and most players said "
        "the feedback helped or would recommend the game (self-report); the order was never varied, so the mechanism is "
        "untested."
    ),
    limit=(
        "Self-report; no comparison group; split fun ratings (3 of 22 PicPrompt "
        "students gave the lowest); Promptemon's feedback came from the "
        "generating model; the order was never varied."
    ),
    cite=Cite("sec:framework", "component 20"),
    requirement="R1",
)

SAME_TASK_REVISION_WITH_REASON = GradedComponent(
    id="same_task_revision_with_reason",
    name="Same-task revision with a stated reason, before a new task",
    grade=Grade.ARGUED,
    need=NeedBasis.STUDENTS,
    # D02: the non-significant PicPrompt decline is reported in Ch 4 and is
    # not a basis for this need. tab:evidence row 21.
    basis="R3. Neither game let a student revise her own prompt.",
    limit=(
        "Never tested; the hold could lower engagement; the reason may be "
        "perfunctory."
    ),
    cite=Cite("sec:calibrate", "component 21"),
    requirement="R3",
)

PREDICTED_RATING_BESIDE_SCORE = GradedComponent(
    id="predicted_rating_beside_score",
    name="Predicted rating recorded beside the measured score",
    grade=Grade.ARGUED,
    need=NeedBasis.STUDENTS,
    basis=(
        "R2. In Promptemon, 26 of 53 matched students rated their confidence "
        "higher, 8 lower and 19 the same, while the comparable method item did "
        "not improve (31 then 27 of 52). Whether to show the gap is a policy "
        "setting tested by F8."
    ),
    limit=(
        "The measured score comes from model graders, so shared priors apply; "
        "confidence and prompt quality are different constructs."
    ),
    cite=Cite("sec:calibrate", "component 22"),
    requirement="R2",
)

JUDGE_INDEPENDENT_OF_GENERATOR = GradedComponent(
    id="judge_independent_of_generator",
    name="Judge independent of the generating model",
    grade=Grade.TRANSFERRED,
    need=NeedBasis.ARGUMENT,
    basis=(
        "R4. In summarization tasks, model judges recognized and favored their own "
        "outputs (Panickssery et al. 2024); earlier work raised the possibility (Zheng et al. 2023). "
        "Promptemon used one model to generate and to judge."
    ),
    limit="Never measured on student prompts.",
    cite=Cite("sec:measure", "component 23"),
    requirement="R4",
)

SELECTING_IS_NOT_COMPOSING = GradedComponent(
    id="selecting_is_not_composing",
    name="Selecting is not composing: only text she wrote is scored as hers",
    grade=Grade.ARGUED,
    need=NeedBasis.STUDENTS,
    basis=(
        "R5. Promptemon students assembled prompts from prepared choices and "
        "typed no text. A measurement rule, not a finding."
    ),
    # Matches the Ch 12 evidence table row 24: the need rests on design
    # inspection alone. The untested 12-to-18 shift is not used as its basis.
    limit="Rests on design inspection alone; never tested.",
    cite=Cite("sec:measure", "component 24"),
    requirement="R5",
)


GRADED_COMPONENTS: tuple[GradedComponent, ...] = (
    SIX_DIMENSION_RUBRIC,
    LOWER_CONFIDENCE_ON_EVALUATIVE,
    CONTENT_OVER_FLUENCY,
    OVER_RELIANCE_SEPARABLE,
    INTENT_ARTIFACT_GAP_DIAGNOSTIC,
    CLASSIFY_BEFORE_RESPONDING,
    RANKED_MULTIPLE_ASSIGNMENT,
    TEMPLATE_FLOOR,
    GRADUATED_LADDER,
    DUAL_CONDITION_GATING,
    SEVEN_CATEGORY_TAXONOMY,
    FIVE_BAND_PROGRESSION,
    DIAGNOSTICS_BELONG_TO_STUDENT,
    VALIDATED_DECOMPOSITION,
    SINGLE_TARGET_RESPONSE,
    ESCALATION_ON_OBSERVABLE_CONDITIONS,
    WORKED_CONTRAST_TERMINAL,
    ACCESSIBILITY_IN_DEFAULT_PATH,
    CONSENT_SEPARABLE_FROM_USE,
    VISIBLE_CONSEQUENCE_BEFORE_COACHING,
    SAME_TASK_REVISION_WITH_REASON,
    PREDICTED_RATING_BESIDE_SCORE,
    JUDGE_INDEPENDENT_OF_GENERATOR,
    SELECTING_IS_NOT_COMPOSING,
)

BY_ID: dict[str, GradedComponent] = {c.id: c for c in GRADED_COMPONENTS}


def grade_of(component_id: str) -> Grade:
    return BY_ID[component_id].grade


def counts() -> dict[Grade, int]:
    out = {g: 0 for g in Grade}
    for c in GRADED_COMPONENTS:
        out[c.grade] += 1
    return out


def need_counts() -> dict[NeedBasis, int]:
    out = {n: 0 for n in NeedBasis}
    for c in GRADED_COMPONENTS:
        out[c.need] += 1
    return out


#: sec:framework - "Original to this thesis: taxonomy, progression, 22, 23 (all
#: Argued)." Row 22 and 23 of the spec's numbering are the reasoned revision
#: and the calibration gap.
ORIGINAL_CONTRIBUTIONS: tuple[str, ...] = (
    "seven_category_taxonomy",
    "five_band_progression",
    "same_task_revision_with_reason",
    "predicted_rating_beside_score",
)


# ---------------------------------------------------------------------------
# Removed after implementation (sec:not-adopted, "tried and not carried over")
# ---------------------------------------------------------------------------

#: Kept as data so the removal stays visible. It is not a graded component and
#: nothing in the framework implements it.
REMOVED_COMPONENTS: dict[str, tuple[str, Cite]] = {
    "affective_state_inference": (
        "Affective state inference (frustration from errors with long latency) "
        "was removed from the framework. The reference implementation had to "
        "switch it off, because a long pause before a prompt may be planning, not "
        "struggle.",
        Cite("sec:not-adopted", "tried and not carried over"),
    ),
}
