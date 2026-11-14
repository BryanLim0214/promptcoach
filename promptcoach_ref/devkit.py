"""The developer kit: the framework turned into a checklist a builder can answer.

This module is for people building AI tutors that teach prompt writing. It turns
the 24 graded components into one yes/no question each and reports, for a
design, which components it adopts, which it leaves out, and how strong the
evidence is for each.

Two rules keep it honest, and the tests in ``tests/test_devkit.py`` hold them:

* The question wording is ours. It paraphrases each component so a developer
  can answer it; the thesis's own statement of the component (name, basis,
  limit, section) is attached unchanged from ``framework.grades``. A question
  never carries a number the component does not.
* The audit reports coverage and evidence, never quality or learning. A design
  that answers "yes" to all 24 is a design that follows the framework, not one
  shown to teach. Argued components are flagged as the parts a pilot can still
  remove (Chapter 12's falsification tests).

Nothing here imports ``policy``: the checklist is about what the framework
states, not about the values the reference implementation chose.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .framework import grades
from .framework.grades import GradedComponent, Grade

Answer = Literal["yes", "partly", "no", "unknown"]
ANSWERS: tuple[str, ...] = ("yes", "partly", "no", "unknown")

#: Where each component sits, for grouping the checklist. This grouping is ours,
#: based on tab:framework; "Student cycle" marks steps the student takes, and
#: "All layers" marks the commitments that apply to every layer.
LAYER: dict[str, str] = {
    "six_dimension_rubric": "Measure",
    "lower_confidence_on_evaluative": "Measure",
    "content_over_fluency": "All layers",
    "over_reliance_separable": "Calibrate",
    "intent_artifact_gap_diagnostic": "Elicit",
    "classify_before_responding": "Diagnose",
    "ranked_multiple_assignment": "Diagnose",
    "template_floor": "Respond",
    "graduated_ladder": "Respond",
    "dual_condition_gating": "Calibrate",
    "seven_category_taxonomy": "Diagnose",
    "five_band_progression": "Calibrate",
    "diagnostics_belong_to_student": "All layers",
    "validated_decomposition": "Elicit",
    "single_target_response": "Respond",
    "escalation_on_observable_conditions": "Respond",
    "worked_contrast_terminal": "Respond",
    "accessibility_in_default_path": "All layers",
    "consent_separable_from_use": "All layers",
    "visible_consequence_before_coaching": "Student cycle",
    "same_task_revision_with_reason": "Calibrate",
    "predicted_rating_beside_score": "Calibrate",
    "judge_independent_of_generator": "Measure",
    "selecting_is_not_composing": "Measure",
}

#: One plain question per component. Developer-facing paraphrase, not thesis text.
QUESTION: dict[str, str] = {
    "six_dimension_rubric": (
        "Do you score the student's prompt itself on a fixed rubric (the framework "
        "uses six dimensions), instead of relying on her self-rating?"
    ),
    "lower_confidence_on_evaluative": (
        "Do you report lower confidence for the evaluative dimensions (Iteration "
        "Awareness, Reflection) than for the planning dimensions?"
    ),
    "content_over_fluency": (
        "Does your scoring reward what the prompt asks for, not grammar or polish, "
        "so students writing in a second language are not marked down?"
    ),
    "over_reliance_separable": (
        "Do you watch for signs that the student is handing her judgment to the "
        "AI, and keep that signal separate from her prompt score?"
    ),
    "intent_artifact_gap_diagnostic": (
        "Do you capture the student's plan (what she means to ask) separately "
        "from the prompt she writes, so the gap between them can be diagnosed?"
    ),
    "classify_before_responding": (
        "Does the tutor name the kind of error before it chooses a response?"
    ),
    "ranked_multiple_assignment": (
        "When an error fits more than one category, does the diagnosis keep a "
        "ranked list instead of forcing a single label?"
    ),
    "template_floor": (
        "Is there a prepared response, checked against the authorship rule, under "
        "every generated one, so the tutor has a safe fallback when generation fails "
        "or is blocked?"
    ),
    "graduated_ladder": (
        "Does help come in levels that start with a question and give more only "
        "when needed, without ever writing the missing part of her prompt?"
    ),
    "dual_condition_gating": (
        "Does difficulty change only when two conditions both hold (for example a "
        "success rate and a streak), not on a single good attempt?"
    ),
    "seven_category_taxonomy": (
        "Do you diagnose prompt failures with categories built for learners "
        "(the framework's seven), each tied to the dimension it should improve?"
    ),
    "five_band_progression": (
        "Are tasks ordered on two separate scales, planning (bands one to three) and "
        "judging an answer (bands four and five), with no automatic move between them?"
    ),
    "diagnostics_belong_to_student": (
        "Does what the system infers about the student go to her first, with "
        "teacher views kept aggregate unless she chooses to share, and does the "
        "tutor tell her why when it changes what it asks of her?"
    ),
    "validated_decomposition": (
        "When a task is broken into steps for her, is the breakdown checked "
        "before it is shown?"
    ),
    "single_target_response": (
        "Does each response address one failure at a time?"
    ),
    "escalation_on_observable_conditions": (
        "Does help move up only on things you can observe (repeated failed "
        "attempts, an explicit request), never on pauses or guessed mood?"
    ),
    "worked_contrast_terminal": (
        "At the top of the help ladder, do you show a worked contrast (two prompts "
        "that differ only on the diagnosed dimension, with both outputs, and she says "
        "which is better and why) instead of a finished prompt to copy?"
    ),
    "accessibility_in_default_path": (
        "Are accessibility supports available by default, without the student "
        "having to request or earn them?"
    ),
    "consent_separable_from_use": (
        "Can a student use the tool without becoming a research participant, and "
        "keep a usable path if she declines the microphone?"
    ),
    "visible_consequence_before_coaching": (
        "Does the student see what her own prompt produced before any coaching?"
    ),
    "same_task_revision_with_reason": (
        "Does she revise the same prompt on the same task, and say why, before "
        "moving to a new task?"
    ),
    "predicted_rating_beside_score": (
        "Does she predict her score before she runs the prompt, with the prediction recorded "
        "beside the measured score?"
    ),
    "judge_independent_of_generator": (
        "Is the model that scores her prompt a different model from the one that "
        "answers it?"
    ),
    "selecting_is_not_composing": (
        "Is only text she wrote herself scored as hers (chosen, pasted, or "
        "inserted text excluded)?"
    ),
}

GRADE_NOTE: dict[Grade, str] = {
    Grade.DIRECT: "Measured in this domain on the thesis's benchmarks (Build 1).",
    Grade.TRANSFERRED: "Shown in another setting; assumed to carry to prompt writing.",
    Grade.ARGUED: "Follows from the evidence but has not been tested; a pilot can remove it.",
}


@dataclass(frozen=True)
class CheckItem:
    component_id: str
    number: int
    layer: str
    question: str
    component: GradedComponent

    def as_dict(self) -> dict:
        c = self.component
        return {
            "component_id": c.id,
            "number": self.number,
            "layer": self.layer,
            "question": self.question,
            "component_name": c.name,
            "evidence_grade": c.grade.value,
            "evidence_grade_meaning": GRADE_NOTE[c.grade],
            "need_basis": c.need.label,
            "requirement": c.requirement or None,
            "thesis_basis": c.basis,
            "thesis_limit": c.limit,
            "thesis_section": str(c.cite),
            "not_found_in_reviewed_systems": c.id in grades.ORIGINAL_CONTRIBUTIONS,
        }


CHECKLIST: tuple[CheckItem, ...] = tuple(
    CheckItem(c.id, i, LAYER[c.id], QUESTION[c.id], c)
    for i, c in enumerate(grades.GRADED_COMPONENTS, start=1)
)
BY_ID: dict[str, CheckItem] = {item.component_id: item for item in CHECKLIST}


def audit(answers: dict[str, str]) -> dict:
    """Report how a tutor design lines up with the framework.

    ``answers`` maps a component id to "yes", "partly", "no" or "unknown".
    Components left out count as "unknown". Unknown ids raise ``ValueError``,
    so a typo cannot silently drop a check.
    """
    unknown_ids = sorted(set(answers) - set(BY_ID))
    if unknown_ids:
        raise ValueError(
            f"Unknown component ids: {unknown_ids}. Call get_design_checklist for "
            "the 24 valid ids."
        )
    bad = {k: v for k, v in answers.items() if str(v).lower() not in ANSWERS}
    if bad:
        raise ValueError(f"Answers must be one of {ANSWERS}; got {bad}.")

    rows = []
    tally = {a: 0 for a in ANSWERS}
    adopted_untested = []
    gaps = []
    not_answered = []
    for item in CHECKLIST:
        answer = str(answers.get(item.component_id, "unknown")).lower()
        tally[answer] += 1
        row = item.as_dict() | {"answer": answer}
        if answer in ("no", "partly"):
            row["what_to_do"] = (
                f"Consider adding: {item.component.name}. Thesis basis: "
                f"{item.component.basis}"
            )
            gaps.append(item.component_id)
        if answer == "unknown":
            not_answered.append(item.component_id)
        if answer in ("yes", "partly") and item.component.grade is Grade.ARGUED:
            adopted_untested.append(item.component_id)
        rows.append(row)

    by_layer: dict[str, dict[str, int]] = {}
    for row in rows:
        layer = by_layer.setdefault(row["layer"], {a: 0 for a in ANSWERS})
        layer[row["answer"]] += 1

    requirement_gaps = sorted(
        {BY_ID[g].component.requirement for g in gaps if BY_ID[g].component.requirement}
    )
    return {
        "summary": {
            "components": len(CHECKLIST),
            **tally,
            "requirements_not_fully_met": requirement_gaps,
        },
        "by_layer": by_layer,
        "gaps": gaps,
        "not_answered": not_answered,
        "adopted_but_untested": adopted_untested,
        "rows": rows,
        "how_to_read": (
            "This is a coverage report against the framework, not a quality or "
            "learning score. 'gaps' lists components answered no or partly; "
            "'not_answered' lists the ones the design does not say, which are not "
            "counted as gaps. 'adopted_but_untested' lists Argued components you "
            "use: they follow from the thesis's evidence but have not been tested "
            "with students, so plan to measure them. The framework itself has not "
            "yet been used with students."
        ),
    }
