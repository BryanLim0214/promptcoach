"""The four cross-cutting commitments that constrain all five layers.

sec:commitments - "Four commitments constrain all five layers."

These are not preferences. Each one has a rejection test, because each one is a
constraint a plausible implementation would violate by default: a teacher
dashboard is the obvious thing to build, bundled consent is the easy thing to
ship, and keeping the audio is the cheap thing to do.
"""

from __future__ import annotations

from dataclasses import dataclass

from .grades import (
    ACCESSIBILITY_IN_DEFAULT_PATH,
    CONSENT_SEPARABLE_FROM_USE,
    CONTENT_OVER_FLUENCY,
    Cite,
    DIAGNOSTICS_BELONG_TO_STUDENT,
    Grade,
    GradedComponent,
)


@dataclass(frozen=True)
class Commitment:
    id: str
    name: str
    text: str
    component: GradedComponent
    cite: Cite

    @property
    def grade(self) -> Grade:
        return self.component.grade



CONTENT_OVER_FLUENCY_COMMITMENT = Commitment(
    id="content_over_fluency",
    name="Content over fluency",
    text=(
        "Scoring tracks metacognitive content, not grammatical polish. Build 1 "
        "found that the rubric does this on its own benchmark: the three ESL "
        "items averaged 3.59 against 2.48 for the 15 clean items, on items written "
        "with rich content to test exactly that. In any "
        "classroom where students are writing in a second language, an instrument "
        "that did the opposite would be actively harmful. The commitment also "
        "reaches upstream into Layer 1: if the speech recognition degrades on "
        "accented speech, content over fluency in the rubric will not rescue a "
        "transcript that has already lost the content."
    ),
    component=CONTENT_OVER_FLUENCY,
    cite=Cite("sec:commitments", "content over fluency"),
)

OWNERSHIP_AND_LEGIBILITY = Commitment(
    id="ownership_and_legibility",
    name="Diagnostics belong to the student, and adaptation is visible to her",
    text=(
        "This commitment has two halves. The first is ownership: everything the "
        "system infers surfaces to the student by default, and teacher facing views "
        "are aggregate unless a student chooses to share. This constrains the "
        "product, making the system less immediately attractive to some adopters, "
        "which is the correct trade. The second is legibility: when the system "
        "changes what it asks of her, it tells her why it changed, making the "
        "adaptation something she can inspect rather than something that happens to "
        "her. A system that showed a student her own diagnostics while keeping the "
        "adaptation logic opaque would satisfy the first half and not the second."
    ),
    component=DIAGNOSTICS_BELONG_TO_STUDENT,
    cite=Cite("sec:commitments", "ownership and legibility"),
)

ACCESSIBILITY_DEFAULT = Commitment(
    id="accessibility_default",
    name="Accessibility in the default path",
    text=(
        "From Build 3. Supports are available without being requested or earned, "
        "following Universal Design for Learning's finding that accommodations "
        "designed for disabled students improve outcomes across the class."
    ),
    component=ACCESSIBILITY_IN_DEFAULT_PATH,
    cite=Cite("sec:commitments", "accessibility in the default path"),
)

CONSENT_SEPARABLE = Commitment(
    id="consent_separable",
    name="Consent separate from use",
    text=(
        "From Build 3. Research consent is distinct from platform consent, so a "
        "student can use the tool without becoming a subject. Layer 1 extends this "
        "to the microphone: a student who declines audio capture must retain a "
        "usable path through the system."
    ),
    component=CONSENT_SEPARABLE_FROM_USE,
    cite=Cite("sec:commitments", "consent separable from use"),
)


COMMITMENTS: tuple[Commitment, ...] = (
    CONTENT_OVER_FLUENCY_COMMITMENT,
    OWNERSHIP_AND_LEGIBILITY,
    ACCESSIBILITY_DEFAULT,
    CONSENT_SEPARABLE,
)

BY_ID: dict[str, Commitment] = {c.id: c for c in COMMITMENTS}


# ---------------------------------------------------------------------------
# The two prohibitions that follow from the commitments
# ---------------------------------------------------------------------------

#: sec:method. Stated as a framework prohibition, not
#: a recommendation.
TEACHER_VIEW_PROHIBITION = (
    "Layers 3 and 5 generate diagnostic information about an individual: which "
    "failure she committed, and whether she is over relying on the tool. The obvious "
    "implementation surfaces that to a teacher. The framework forbids it, requiring "
    "aggregate teacher views unless a student chooses to share her own. A diagnostic "
    "layer that reports a named student's failures and her over reliance score to an "
    "adult is a monitoring system whatever the intent behind it."
)

#: sec:calibrate with sec:commitments. The calibration gap is a diagnostic about
#: an individual - how far her own judgment of her prompt sits from its score -
#: so the ownership commitment covers it exactly as it covers the sentinel.
CALIBRATION_STAYS_WITH_STUDENT = (
    "Her predicted rating and the gap between it and the measured score belong to "
    "her. They never appear in a teacher view, aggregate or otherwise."
)

#: sec:method.
AUDIO_HANDLING_RULE = (
    "The transcript and not the audio is the artifact, audio should be discarded "
    "once transcribed, and a student who declines the microphone must still be able "
    "to use the system on a typed statement of intent, which degrades the diagnosis "
    "rather than blocking it."
)

#: The same passage ends: "None of that has been implemented." It is implemented
#: here; that is part of what this reference implementation is for.
AUDIO_RULE_WAS_UNIMPLEMENTED_IN_THESIS = True


# ---------------------------------------------------------------------------
# Deliberate non-transfers. Absence is a design decision, not an omission.
# ---------------------------------------------------------------------------

#: sec:build2
NON_TRANSFERS: dict[str, str] = {
    "gamification": (
        "Narrative game worlds depend on a wrong answer having a physical analogue, "
        "and it is not obvious what the physical consequence of an under specified "
        "prompt would be, so the framework does not adopt the gamification layer. "
        "Chapter 9 records that as a deliberate non transfer rather than an omission."
    ),
    "mathematics_error_types": (
        "The six mathematics error types are worthless outside mathematics. These "
        "are domain knowledge and do not transfer; the practice of classifying "
        "before responding does."
    ),
}

#: Tokens a rejection test greps for across the whole package, to prove the
#: non-transfers really are absent rather than merely undocumented.
FORBIDDEN_TOKENS: tuple[str, ...] = (
    "xp_award",
    "experience_points",
    "badge",
    "streak_bonus",
    "leaderboard",
    "avatar",
    "world_unlock",
)
