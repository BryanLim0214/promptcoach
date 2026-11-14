"""Generate TRACEABILITY.md.

    python -m promptcoach_ref.traceability

Maps all thirteen chapters to the module that implements them and the test that
holds them, lists the framework's twenty-four graded components with both grade
columns (mechanism and need basis), enumerates the twenty-four things the thesis
leaves open with what was chosen instead, and names what is not implementable
and why.

It also checks every section label the package cites against `\\label{...}` in
the chapter sources (`thesis/sections_v2/*.tex`) when that folder exists, and
says plainly that the check was skipped when it does not.

This file is generated, never hand-edited. A hand-maintained traceability
document drifts from the code within a week, and a drifted map is worse than
none because it is believed.
"""

from __future__ import annotations

import re
from pathlib import Path

from . import about, policy
from .framework import (
    classroom,
    commitments,
    grades,
    ladder,
    progression,
    revision,
    rubric,
    sentinel,
    taxonomy,
)
from .framework.grades import Grade, NeedBasis
from .policy import escalation

OUT = Path(__file__).resolve().parent.parent / "TRACEABILITY.md"

#: Where the chapter sources live when the thesis sits beside this project.
SECTIONS_V2 = (
    Path(__file__).resolve().parents[2]
    / "UTPB_Thesis_Lim_Final"
    / "thesis"
    / "sections_v2"
)

CHAPTERS: list[tuple[str, str, str, str]] = [
    (
        "1",
        "Introduction - thesis statement, research questions, contributions",
        "`about.py` (THESIS_STATEMENT, RESEARCH_QUESTIONS, SCOPE)",
        "surfaced in the About view",
    ),
    (
        "2",
        "Background - games, calibration, model judges, Flavell and Veenman",
        "`about.py`, `framework/rubric.py` (the planning/evaluative split)",
        "`test_grades.py`",
    ),
    (
        "3",
        "Methods - chronology, inclusion rule, evidence grades, ethics, statistics",
        "`framework/grades.py` (Grade, NeedBasis), `eval/revalidate.py`, "
        "`framework/commitments.py`",
        "`test_grades.py`, `test_statistics.py`",
    ),
    (
        "4",
        "User study one: PicPrompt",
        "`framework/classroom.py` (PicPrompt aggregates, comparability flags)",
        "`test_classroom.py`",
    ),
    (
        "5",
        "User study two: Promptemon and the re-analysis of its survey data",
        "`framework/classroom.py` (RAW aggregates, WITHDRAWN)",
        "`test_classroom.py`, `test_rejection.py` (withdrawn figures absent)",
    ),
    (
        "6",
        "Build one: PromptAloud and Proem - six dimensions, ensemble, sentinel",
        "`framework/rubric.py`, `framework/sentinel.py`, `layers/measure.py`, "
        "`policy/confidence.py`, `layers/calibrate.py` (which detector runs)",
        "`test_worked_example.py`, `test_rejection.py`, `test_review_r3.py`",
    ),
    (
        "7",
        "Build two: MathEduAI - classify before responding, template floor, dual gate",
        "`layers/diagnose.py`, `policy/gating.py`, `policy/affect.py` (removed)",
        "`test_mechanism.py` (the dual condition)",
    ),
    (
        "8",
        "Build three: PyPal - decomposition validator, ladder, escalation, consent",
        "`framework/ladder.py`, `policy/decomposition.py`, `policy/escalation.py`, "
        "`session.py` (help across revisions)",
        "`test_mechanism.py`, `test_review_r3.py` (attempt and three revisions reach level 4)",
    ),
    (
        "9",
        "Synthesis - requirements R1 to R6, what was not adopted",
        "`about.py` (REQUIREMENTS), `framework/grades.py` (REMOVED_COMPONENTS)",
        "`test_grades.py`",
    ),
    (
        "10",
        "The framework - two loops, five layers, 24 components, commitments",
        "`framework/` in full, `layers/` in full, `framework/revision.py`",
        "`test_contracts.py`, `test_rejection.py`, `test_grades.py`",
    ),
    (
        "11",
        "Design and implementation - session walkthrough, worked example, this app",
        "`session.py`, `responder.py`, `api.py`, `policy/taskbank.py`, `web/`",
        "`test_worked_example.py`, `test_api.py`, `test_tour.py`",
    ),
    (
        "12",
        "Evidence, falsification (F1 to F9), threats",
        "`framework/grades.py`, `policy/classifier.py` (both selection modes), "
        "`policy/revision.py` (F7 switch), `policy/calibration.py` (F8 switch), "
        "`layers/measure.py` (F9 provenance)",
        "`test_falsifiability.py`, `test_grades.py`",
    ),
    (
        "13",
        "Remaining work and conclusion",
        "`about.py` (REMAINING, CONCLUSION)",
        "documented, not implemented",
    ),
]

NOT_IMPLEMENTABLE: list[tuple[str, str]] = [
    (
        "Agreement with a human rater - Measure's third bar",
        "sec:measure - \"The third bar is agreement with a human rater, and this "
        "thesis does not clear it.\" It needs teachers scoring the same items. No "
        "amount of software closes it.",
    ),
    (
        "Classroom feasibility of speech capture",
        "sec:elicit - three untested assumptions: thirty students planning aloud in "
        "one room, transcription accuracy on middle school speech, and whether a "
        "twelve year old narrates candidly with peers within earshot.",
    ),
    (
        "Whether the taxonomy covers authentic student prompts",
        "F1. Needs a corpus of real middle school prompts and independent human "
        "annotators. No student data has been classified with it.",
    ),
    (
        "Whether the band ordering holds",
        "F3. Needs student performance across all five bands, and the two scales "
        "are not commensurable across the join between bands 3 and 4.",
    ),
    (
        "Whether the worked contrast holds a student",
        "F5. The framework's most exposed single claim. Needs a controlled "
        "comparison against a plain hint.",
    ),
    (
        "Whether a reasoned revision, or a visible calibration gap, does anything",
        "F7 and F8. The switches for both control arms exist here; the experiments "
        "need students.",
    ),
    (
        "Any instructional effect whatsoever",
        "sec:intro and sec:threats - no student has used the framework. The "
        "reference implementation has not been used with students.",
    ),
]


# ---------------------------------------------------------------------------
# Citation labels against the chapter sources
# ---------------------------------------------------------------------------


def cited_labels() -> set[str]:
    """Every section label the package cites."""
    labels: set[str] = set()
    labels |= {c.cite.label for c in grades.GRADED_COMPONENTS}
    labels |= {cite.label for _, cite in grades.REMOVED_COMPONENTS.values()}
    labels |= {c.cite.label for c in taxonomy.CATEGORIES}
    labels |= {lv.cite.label for lv in ladder.LEVELS}
    labels |= {b.cite.label for b in progression.BANDS}
    labels |= {s.cite.label for s in sentinel.SIGNALS}
    labels |= {c.cite.label for c in commitments.COMMITMENTS}
    labels |= {a.cite.label for a in classroom.AGGREGATES.values()}
    labels |= {p.cite.label for p in classroom.ITEM_PAIRS.values()}
    labels |= {rubric.CITE.label, revision.CITE.label}
    labels |= {p.label for p in (about.THESIS_STATEMENT, about.SCOPE, about.CONCLUSION)}
    labels |= {t.label for t in about.THREATS}
    return labels


def check_labels(folder: Path = SECTIONS_V2) -> tuple[str, list[str]]:
    """("checked" | "skipped", missing labels).

    Skipped, not passed, when the chapter sources are not on disk: a check that
    silently passed with nothing to check against would be believed.
    """
    if not folder.is_dir():
        return "skipped", []
    defined: set[str] = set()
    for tex in folder.glob("*.tex"):
        text = tex.read_text(encoding="utf-8", errors="replace")
        defined |= set(re.findall(r"\\label\{([^}]+)\}", text))
    missing = sorted(cited_labels() - defined)
    return "checked", missing


# ---------------------------------------------------------------------------


def render() -> str:
    lines: list[str] = []
    add = lines.append

    add("# Traceability")
    add("")
    add("Generated by `python -m promptcoach_ref.traceability`. Do not edit by hand.")
    add("")
    add(
        f"Maps *{about.TITLE}* onto this implementation: every chapter to the module "
        "that carries it, every graded component to its evidence and its need "
        "basis, every gap in the thesis to what was chosen instead, and everything "
        "that cannot be implemented to the sentence that says why."
    )
    add("")
    add(
        "**What this is evidence of.** The application shows that the specification "
        "is implementable. It has not been used with students."
    )
    add("")

    # --- chapters ---------------------------------------------------------
    add("## All thirteen chapters")
    add("")
    add("| Ch. | What it supplies | Where it lands | Held by |")
    add("|---|---|---|---|")
    for number, title, module, test in CHAPTERS:
        add(f"| {number} | {title} | {module} | {test} |")
    add("")

    # --- citation check ---------------------------------------------------
    status, missing = check_labels()
    labels = sorted(cited_labels(), key=lambda l: (int(grades.SECTION_LABELS[l]), l))
    add("## Citation labels")
    add("")
    add(
        f"The package cites {len(labels)} section labels, never a file or a line. "
        "Each is one of the chapter map's labels; a `Cite` naming anything else "
        "cannot be constructed."
    )
    add("")
    if status == "skipped":
        add(
            "Check against `thesis/sections_v2/*.tex`: **skipped** - the chapter "
            "sources are not on disk yet. Re-run this generator once they are."
        )
    elif missing:
        add(
            "Check against `thesis/sections_v2/*.tex`: **failed** - not defined "
            "there: " + ", ".join(f"`{m}`" for m in missing)
        )
    else:
        add("Check against `thesis/sections_v2/*.tex`: **passed** - every label is defined.")
    add("")
    add(", ".join(f"`{l}`" for l in labels))
    add("")

    # --- graded components ------------------------------------------------
    counts = grades.counts()
    needs = grades.need_counts()
    add("## Evidence grades")
    add("")
    add(
        f"The framework grades {len(grades.GRADED_COMPONENTS)} components on two "
        f"columns. Mechanism: **{counts[Grade.DIRECT]} Direct, "
        f"{counts[Grade.TRANSFERRED]} Transferred, {counts[Grade.ARGUED]} Argued**. "
        f"Need basis: **{needs[NeedBasis.STUDENTS]} {NeedBasis.STUDENTS.label}, "
        f"{needs[NeedBasis.BUILDS]} {NeedBasis.BUILDS.label}, "
        f"{needs[NeedBasis.ARGUMENT]} {NeedBasis.ARGUMENT.label}**. "
        "`test_grades.py` pins both sets of counts, so the implementation cannot "
        "quietly promote a proposition to a finding."
    )
    add("")
    for n in NeedBasis:
        add(f"- **{n.label}** - {grades.NEED_DEFINITION[n]}")
    add("")
    for grade in (Grade.DIRECT, Grade.TRANSFERRED, Grade.ARGUED):
        add(f"### {grade.value.title()} ({counts[grade]})")
        add("")
        add(f"> {grades.GRADE_DEFINITION[grade]}")
        add("")
        add("| # | Component | Need | Basis | Limit | Cite |")
        add("|---|---|---|---|---|---|")
        for i, c in enumerate(grades.GRADED_COMPONENTS, start=1):
            if c.grade is not grade:
                continue
            star = " (thesis's own)" if c.id in grades.ORIGINAL_CONTRIBUTIONS else ""
            req = f" [{c.requirement}]" if c.requirement else ""
            add(
                f"| {i} | {c.name}{star}{req} | {c.need.label} | {c.basis} | "
                f"{c.limit} | `{c.cite}` |"
            )
        add("")

    add(
        "The four marked *thesis's own* are the seven-category taxonomy, the "
        "five-band progression, the reasoned same-task revision and the calibration "
        "gap. All four are Argued."
    )
    add("")
    add("**Removed after implementation.**")
    add("")
    for key, (why, cite) in grades.REMOVED_COMPONENTS.items():
        add(f"- `{key}` - {why} (`{cite}`)")
    add("")

    # --- the spec ---------------------------------------------------------
    add("## The specification, as implemented")
    add("")
    add(f"**Rubric** - {len(rubric.DIMENSIONS)} dimensions, scale "
        f"{rubric.RUBRIC_MIN}-{rubric.RUBRIC_MAX}, "
        f"{len(rubric.PLANNING_DIMENSIONS)} planning + "
        f"{len(rubric.EVALUATIVE_DIMENSIONS)} evaluative. `framework/rubric.py`")
    add("")
    add("| Dimension | Kind | kappa (Proem pair) | within one |")
    add("|---|---|---|---|")
    for d in rubric.DIMENSIONS:
        add(f"| {d.name} | {d.kind.value} | {d.weighted_kappa} | {d.within_one_pct}% |")
    add("")
    add(f"> {rubric.WEAKEST_DEPENDS_ON_PAIR}")
    add("")
    add(f"Overall ICC(2,2) {rubric.OVERALL_ICC_2_2}. Overall weighted kappa is "
        "`n/a` in the source table, so none is computed here either.")
    add("")

    add(f"**Taxonomy** - {len(taxonomy.CATEGORIES)} categories. "
        f"{len(taxonomy.detectable_from_prompt_alone())} detectable from the prompt "
        f"alone; {len(taxonomy.requires_spoken_record())} needs the paired spoken "
        f"record; {len(taxonomy.requires_session_history())} need session history. "
        "`framework/taxonomy.py`")
    add("")
    add("| Failure | Visible in | Layer 5 checks |")
    add("|---|---|---|")
    for c in taxonomy.CATEGORIES:
        add(f"| {c.name} | {c.detectable_from.value.replace('_', ' ')} | "
            f"{c.paired.description} |")
    add("")

    add(f"**Ladder** - {len(ladder.LEVELS)} levels, terminal at "
        f"{ladder.TERMINAL_LEVEL}. `framework/ladder.py`")
    add("")
    add("| Level | Gives | She still |")
    add("|---|---|---|")
    for lv in ladder.LEVELS:
        add(f"| {lv.number} | {lv.gives} | {lv.student_still_does} |")
    add("")
    add(f"> {ladder.AUTHORSHIP_BOUNDARY}")
    add("")
    add("How help climbs (`policy/escalation.py`, `session.py`): a help cycle is "
        "the help given on one task for one top-ranked category. Help moves up "
        "one rung when the same category is ranked first on "
        f"{escalation.CONSECUTIVE_UNRESOLVED} consecutive attempts (first "
        "attempts and revisions alike) or when she asks; for the three diagnoses "
        "paired with an evaluative dimension, only when she asks or her text is "
        "unchanged. A revision is measured by Layer 5 first; the cycle stays open "
        "while the category persists and the paired dimension has not improved, "
        "and closes once level 4 has been issued. A first attempt and three "
        "revisions reach level 4 end to end in `test_review_r3.py`.")
    add("")

    add(f"**Progression** - {len(progression.BANDS)} bands on two separate scales, "
        f"joined between {progression.AXIS_JOIN[0]} and {progression.AXIS_JOIN[1]} "
        "with no promotion rule across the join. `framework/progression.py`")
    add("")
    add("| Band | Scale | Requires |")
    add("|---|---|---|")
    for b in progression.BANDS:
        add(f"| {b.number} | {b.axis.value.replace('_', ' ')} | {b.requires} |")
    add("")
    add(f"> {progression.AXES_NOT_COMMENSURABLE}")
    add("")

    add(f"**Sentinel** - {len(sentinel.SIGNALS)} signals. `framework/sentinel.py`")
    add("")
    add(f"> {sentinel.AUC_READING}")
    add("")
    add(f"> {sentinel.ROUTING_RULE}")
    add("")
    add("Which detector runs: in a live session Layer 5 calls the judge engine's "
        "model-based detector (`GeminiEngine.sentinel`), the one "
        "`eval/benchmark.py` measured. The keyword rules "
        "(`DeterministicEngine.sentinel`) run only in the offline engine; they "
        "are an author-tested stand-in, and every Layer 5 result names its "
        "detector in `sentinel_source`. Layer 3 does not read the sentinel: it "
        "diagnoses with its own rules over the plan, the prompt and the session "
        "history. `test_review_r3.py`")
    add("")

    add("**Reasoned revision** - `framework/revision.py`, switch in "
        "`policy/revision.py`")
    add("")
    add(f"> {revision.ASK_FOR_REASON}")
    add("")
    add(f"F7: {revision.F7}")
    add("")

    add(f"**Commitments** - {len(commitments.COMMITMENTS)}, each with a rejection "
        "test. `framework/commitments.py`")
    add("")
    for c in commitments.COMMITMENTS:
        add(f"- **{c.name}** - {c.grade.value}")
    add("")
    add(f"> {commitments.CALIBRATION_STAYS_WITH_STUDENT}")
    add("")

    # --- classroom --------------------------------------------------------
    add("## Classroom aggregates")
    add("")
    add(f"`framework/classroom.py`. {classroom.SELF_REPORT_RULE} Promptemon values "
        f"come from {classroom.PROMPTEMON_LABEL}. "
        f"{classroom.PROMPTEMON_STUDENTS_DID_NOT_TYPE}")
    add("")
    add("| Item pair | Before | After | Comparable | Why |")
    add("|---|---|---|---|---|")
    for p in classroom.ITEM_PAIRS.values():
        add(f"| `{p.id}` | {p.pre} | {p.post} | "
            f"{'yes' if p.comparable else '**no** - never shown as change'} | {p.why} |")
    add("")

    # --- the gaps ---------------------------------------------------------
    add("## What the thesis does not specify")
    add("")
    add(
        f"{len(policy.UNSPECIFIED_BY_THESIS)} things an implementation needs and "
        "the manuscript leaves open. Each is enumerated so a gap cannot be closed "
        "by silence."
    )
    add("")
    add("| Gap | Why it is open |")
    add("|---|---|")
    for key, note in policy.UNSPECIFIED_BY_THESIS:
        add(f"| `{key}` | {note} |")
    add("")
    for key, note in policy.base.CLOSED_BY_REMOVAL:
        add(f"Closed by removal: `{key}` - {note}")
    add("")

    choices = policy.all_choices()
    add(f"### What was chosen instead ({len(choices)} choices)")
    add("")
    add("Every value below is this implementation's, not the thesis's.")
    add("")
    add("| Choice | Value | Borrowed from | Caveat |")
    add("|---|---|---|---|")
    for c in choices:
        value = c.value if not isinstance(c.value, (dict, list)) else str(c.value)
        add(f"| `{c.id}` | `{value}` | {c.borrowed_from} | {c.caveat} |")
    add("")
    add(
        "Three are removals or refusals rather than values - "
        "`affect.latency_inference` and `escalation.inactivity` are removed, and "
        "`gating.may_cross_axis_join` is off. Each gives up capability Build 2 or "
        "Build 3 had. Two are switches that exist so the thesis's own refutations "
        "can run: `revision.required` (F7) and `calibration.show_gap_to_student` "
        "(F8)."
    )
    add("")

    # --- deliberate absences ---------------------------------------------
    add("## Deliberately not implemented")
    add("")
    for key, why in commitments.NON_TRANSFERS.items():
        add(f"**{key.replace('_', ' ')}** - {why}")
        add("")

    # --- not implementable ------------------------------------------------
    add("## Not implementable, and why")
    add("")
    add(
        "These are not omissions. Each needs something software cannot supply."
    )
    add("")
    for what, why in NOT_IMPLEMENTABLE:
        add(f"**{what}**")
        add("")
        add(f"> {why}")
        add("")

    add("---")
    add("")
    add(f"**What running this shows.** {about.WHAT_RUNNING_THIS_SHOWS}")
    add("")
    add(f"**What it does not show.** {about.WHAT_IT_DOES_NOT_SHOW}")
    add("")

    return "\n".join(lines) + "\n"


def main() -> None:
    OUT.write_text(render(), encoding="utf-8")
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
