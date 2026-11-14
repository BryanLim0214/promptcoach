"""An MCP server that gives AI agents and developers the framework.

    promptcoach-mcp                    # after: pip install -e ".[mcp]"
    python -m promptcoach_ref.mcp_server

It speaks the Model Context Protocol over stdio, so any MCP client (Claude Code,
Claude Desktop, VS Code, Gemini CLI, Antigravity, Cursor) can call it. It runs
offline, needs no API key, makes no network calls, and writes nothing to disk.

What it offers:

* **Reference tools** that return the framework exactly as the thesis states it:
  the five layers, the 24 graded components with their evidence grade, basis,
  limit, and thesis section; the six-dimension rubric; the seven failure
  categories; the help ladder; the five difficulty bands; the four commitments;
  and the requirements R1 to R6. These read ``promptcoach_ref.framework``, the
  same package the test suite checks against the thesis. The demo tools also use
  the policy package and the offline rule engine.
* **A design audit** (``audit_tutor_design``) that tells a developer which of
  the 24 components a tutor design adopts or leaves out, and which adopted ones
  are untested. It reports coverage and evidence, never quality or learning.
* **An offline coaching demo** (``coach_attempt``) that runs one attempt through
  all five layers on the reference implementation's rule engine. The rule
  engine is a stand-in for the evaluated rubric; its scores are not the
  thesis's measurements, and every result says so.

What it does not do: it is not a tutor for children, it has not been used with
students, and nothing it returns is evidence that a design teaches. Do not send
real student data to it; see ``DEVELOPER_GUIDE.md``.
"""

from __future__ import annotations

import itertools
from collections import OrderedDict
from pathlib import Path
from typing import Any, Literal

from mcp.server import MCPServer
from mcp.types import ToolAnnotations

from . import about, devkit
from .engines import DeterministicEngine
from .framework import STANDING_DISCLAIMER, commitments, grades, ladder, progression
from .framework import rubric, taxonomy
from .layers import Consent
from .policy import taskbank
from .session import Session

VERSION = "1.1.0"
ROOT = Path(__file__).resolve().parent.parent
GUIDE = ROOT / "DEVELOPER_GUIDE.md"
TRACEABILITY = ROOT / "TRACEABILITY.md"

THESIS = (
    "Lim, P. (2026). Learning to Prompt: A Design Framework for Middle School AI "
    "Literacy. Thesis, The University of Texas Permian Basin."
)

#: tab:framework, sec:framework. Layer, what it does, where it came from.
LAYERS: tuple[dict[str, str], ...] = (
    {"layer": "1. Elicit", "does": "Records her prompt, stated plan, predicted rating, and reason for each revision",
     "from": "Build 1 (speech and prompt capture); Build 3 (checked task breakdown); user studies (rating and reason)"},
    {"layer": "2. Measure", "does": "Scores the prompt on six dimensions, with a judge that is not the generating model",
     "from": "Build 1 (rubric checked across two models and under rewording); published work on model judges"},
    {"layer": "3. Diagnose", "does": "Names the kind of failure, alongside the score",
     "from": "Build 2 (classify before responding); the taxonomy is new"},
    {"layer": "4. Respond", "does": "Gives one piece of help, from a ladder of levels, checked in code before she sees it",
     "from": "Build 1 (one target); Build 2 (prepared fallback); Build 3 (ladder); the code check on each reply is new"},
    {"layer": "5. Calibrate", "does": "Holds the task until one reasoned revision, adjusts difficulty, watches for over-reliance, and compares her predicted rating with her measured score",
     "from": "Build 2 (rate and streak); Build 1 (over-reliance detector); user studies (rating gap); the task progression is new"},
)

#: sec:framework. The student's side of the two loops.
ATTEMPT_CYCLE: tuple[str, ...] = (
    "She plans what she wants, aloud or in writing.",
    "She writes the prompt herself.",
    "She predicts how good it is, on the rubric's 1 to 4 scale.",
    "She runs it and sees the output before any coaching.",
    "She revises the same prompt and says, in a sentence, why she changed it.",
)

OFFLINE_NOTE = (
    "Computed by the reference implementation's offline rule engine "
    "(deterministic-1.0.0). Its rules are surface heuristics, a stand-in for the "
    "evaluated rubric: the thesis's agreement results (Chapters 6 and 11) do not "
    "transfer to these scores. Use it to see how the five layers hand work to "
    "each other, not to grade a student."
)

READ_ONLY = ToolAnnotations(
    read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False
)
#: coach_attempt keeps an in-memory session so a revision can follow an attempt.
#: Nothing is written to disk, and nothing leaves the process.
SESSION_TOOL = ToolAnnotations(
    read_only_hint=True, destructive_hint=False, idempotent_hint=False, open_world_hint=False
)

GradeName = Literal["direct", "transferred", "argued"]
NeedName = Literal["students", "builds", "argument"]
LayerName = Literal["Student cycle", "Elicit", "Measure", "Diagnose", "Respond", "Calibrate", "All layers"]

mcp = MCPServer(
    name="promptcoach",
    title="Learning to Prompt framework",
    version=VERSION,
    instructions=(
        "Design reference for AI tutors that teach middle school students to write "
        "prompts. Start with get_framework_overview. Use get_design_checklist and "
        "audit_tutor_design to review a tutor design, and cite the thesis section "
        "each tool returns. Every component carries an evidence grade: Direct "
        "(measured on the thesis's benchmarks), Transferred (shown elsewhere), or "
        "Argued (untested). Never describe an Argued component as proven, and never "
        "describe the framework as tested with students. Never write a student's "
        "prompt for her: help may narrow what she should add, not supply it. Do not "
        "send real student data to this server."
    ),
)


# ---------------------------------------------------------------------------
# Serializers. Every field below is read from promptcoach_ref.framework.
# ---------------------------------------------------------------------------


def _component(c: grades.GradedComponent) -> dict[str, Any]:
    return devkit.BY_ID[c.id].as_dict()


def _dimension(d: rubric.Dimension) -> dict[str, Any]:
    return {
        "id": d.id,
        "name": d.name,
        "measures": d.measures,
        "kind": d.kind.value,
        "score_1_vs_4": d.one_against_four,
        "build1_weighted_kappa": d.weighted_kappa,
        "build1_exact_agreement_pct": d.exact_pct,
        "build1_within_one_pct": d.within_one_pct,
    }


def _category(c: taxonomy.FailureCategory) -> dict[str, Any]:
    return {
        "id": c.id.value,
        "name": c.name,
        "what_the_student_did": c.student_did,
        "derived_from": c.derived_from,
        "response_it_implies": c.response_implied,
        "detectable_from": c.detectable_from.value,
        "dimension_checked_next": c.paired.description,
        "thesis_section": str(c.cite),
    }


# ---------------------------------------------------------------------------
# Reference tools
# ---------------------------------------------------------------------------


@mcp.tool(title="Framework overview", annotations=READ_ONLY)
def get_framework_overview() -> dict[str, Any]:
    """The framework in one call: the student's attempt cycle, the tutor's five
    layers, the evidence-grade counts, the four parts not found in the systems
    and sources the thesis reviewed,
    and what the evidence does and does not show."""
    return {
        "title": about.TITLE,
        "cite_as": THESIS,
        "student_attempt_cycle": list(ATTEMPT_CYCLE),
        "tutor_layers": list(LAYERS),
        "loops": (
            "Elicit, Measure, Diagnose and Respond act on each attempt (inner loop); "
            "Calibrate chooses the next task (outer loop), following VanLehn's account "
            "of tutoring systems."
        ),
        "components": grades.EXPECTED_COMPONENT_COUNT,
        "evidence_grades": {g.value: n for g, n in grades.counts().items()},
        "grade_meaning": {g.value: text for g, text in grades.GRADE_DEFINITION.items()},
        "not_found_in_reviewed_systems": [grades.BY_ID[i].name for i in grades.ORIGINAL_CONTRIBUTIONS],
        "requirements_from_user_studies": [
            {"id": r, "requirement": text, "evidence": strength}
            for r, text, strength in about.REQUIREMENTS
        ],
        "evidence_status": STANDING_DISCLAIMER,
        "next_tools": [
            "list_components", "get_rubric", "get_failure_taxonomy", "get_help_ladder",
            "get_difficulty_bands", "get_commitments", "get_design_checklist",
            "audit_tutor_design", "coach_attempt",
        ],
    }


@mcp.tool(title="List the 24 components", annotations=READ_ONLY)
def list_components(
    grade: GradeName | None = None,
    need: NeedName | None = None,
    layer: LayerName | None = None,
) -> list[dict[str, Any]]:
    """The framework's 24 graded components, optionally filtered by evidence
    grade (direct, transferred, argued), by where the need was observed
    (students = the user studies, builds, argument), or by layer. Each row gives
    the thesis's basis, its limit, and its section."""
    rows = []
    for c in grades.GRADED_COMPONENTS:
        if grade and c.grade.value != grade:
            continue
        if need and c.need.value != need:
            continue
        if layer and devkit.LAYER[c.id] != layer:
            continue
        rows.append(_component(c))
    return rows


@mcp.tool(title="One component", annotations=READ_ONLY)
def get_component(component_id: str) -> dict[str, Any]:
    """One component by id (for example 'judge_independent_of_generator').
    Use list_components to see the ids."""
    if component_id not in grades.BY_ID:
        raise ValueError(
            f"Unknown component {component_id!r}. Valid ids: {sorted(grades.BY_ID)}"
        )
    return _component(grades.BY_ID[component_id])


@mcp.tool(title="Scoring rubric", annotations=READ_ONLY)
def get_rubric() -> dict[str, Any]:
    """The six-dimension prompt rubric (1 to 4 per dimension): four planning
    dimensions and two evaluative ones, with Build 1's agreement figures and the
    caveats that come with them."""
    return {
        "scale": {"min": rubric.RUBRIC_MIN, "max": rubric.RUBRIC_MAX},
        "dimensions": [_dimension(d) for d in rubric.DIMENSIONS],
        "planning_dimensions": [d.id for d in rubric.PLANNING_DIMENSIONS],
        "evaluative_dimensions": [d.id for d in rubric.EVALUATIVE_DIMENSIONS],
        "build1_overall": {
            "pearson_r": rubric.OVERALL_PEARSON_R,
            "spearman_rho": rubric.OVERALL_SPEARMAN_RHO,
            "mean_grader_gap_points": rubric.MEAN_GRADER_GAP_POINTS,
            "paraphrase_mean_absolute_shift": rubric.PARAPHRASE_MEAN_ABSOLUTE_SHIFT,
        },
        "caveats": [
            rubric.RELIABILITY_CAVEAT,
            rubric.WEAKEST_DEPENDS_ON_PAIR,
            rubric.SHARED_PRIOR_THREAT,
            rubric.THIRD_BAR_UNCLEARED,
        ],
        "thesis_section": str(rubric.CITE),
    }


@mcp.tool(title="Failure categories", annotations=READ_ONLY)
def get_failure_taxonomy() -> dict[str, Any]:
    """The seven prompt-failure categories built for learners, what each implies
    for the response, which dimension to check on the next attempt, and what a
    system must record to detect it (four of seven need more than the prompt)."""
    return {
        "categories": [_category(c) for c in taxonomy.CATEGORIES],
        "evidence_grade": grades.SEVEN_CATEGORY_TAXONOMY.grade.value,
        "notes": [
            taxonomy.OVERLAP_IS_MANDATORY,
            taxonomy.STRICTNESS_WARNING,
            taxonomy.CIRCULARITY_WARNING,
        ],
    }


@mcp.tool(title="Help ladder", annotations=READ_ONLY)
def get_help_ladder() -> dict[str, Any]:
    """The four levels of help, what the student still does at each level, and
    the authorship rule every level must obey."""
    return {
        "levels": [
            {
                "level": lv.number,
                "gives": lv.gives,
                "student_still_does": lv.student_still_does,
                "evidence_grade": lv.grade.value,
                "thesis_section": str(lv.cite),
            }
            for lv in ladder.LEVELS
        ],
        "authorship_boundary": ladder.AUTHORSHIP_BOUNDARY,
        "template_floor": ladder.TEMPLATE_FLOOR_RULE,
        "one_target": ladder.SINGLE_TARGET_RULE,
    }


@mcp.tool(title="Difficulty bands", annotations=READ_ONLY)
def get_difficulty_bands() -> dict[str, Any]:
    """The five proposed task bands, on two scales that must not be joined by a
    promotion rule (bands 1 to 3 count planning dimensions; bands 4 and 5 are
    about judging output)."""
    return {
        "bands": [
            {
                "band": b.number,
                "scale": b.axis.value,
                "requires": b.requires,
                "example": b.example,
                "evidence_grade": b.grade.value,
                "thesis_section": str(b.cite),
            }
            for b in progression.BANDS
        ],
        "scales_not_comparable": progression.AXES_NOT_COMMENSURABLE,
    }


@mcp.tool(title="Commitments", annotations=READ_ONLY)
def get_commitments() -> dict[str, Any]:
    """The four commitments that apply to every layer (content over fluency;
    diagnostics belong to the student; accessibility by default; consent
    separate from use), plus the teacher-view rule."""
    return {
        "commitments": [
            {
                "id": c.id,
                "name": c.name,
                "text": c.text,
                "evidence_grade": c.grade.value,
                "thesis_section": str(c.cite),
            }
            for c in commitments.COMMITMENTS
        ],
        "teacher_view_rule": commitments.TEACHER_VIEW_PROHIBITION,
    }


# ---------------------------------------------------------------------------
# Design audit
# ---------------------------------------------------------------------------


@mcp.tool(title="Design checklist", annotations=READ_ONLY)
def get_design_checklist() -> list[dict[str, Any]]:
    """One yes/no question per component, in the thesis's order, for reviewing a
    tutor design. Answer them (yes, partly, no, unknown) and pass the answers to
    audit_tutor_design."""
    return [item.as_dict() for item in devkit.CHECKLIST]


@mcp.tool(title="Audit a tutor design", annotations=READ_ONLY)
def audit_tutor_design(
    answers: dict[str, Literal["yes", "partly", "no", "unknown"]],
) -> dict[str, Any]:
    """Compare a tutor design with the framework. `answers` maps component ids
    from get_design_checklist to yes, partly, no, or unknown; ids left out count
    as unknown. Returns the gaps (answered no or partly), the requirements R1 to R6
    those gaps leave unmet, the items the design does not say, and the adopted
    components that are still untested. This is a coverage report, not
    a quality or learning score."""
    return devkit.audit(dict(answers))


# ---------------------------------------------------------------------------
# Offline coaching demo
# ---------------------------------------------------------------------------

_MAX_SESSIONS = 32
_SESSIONS: "OrderedDict[str, Session]" = OrderedDict()
_COUNTER = itertools.count(1)


def _new_session(task_id: str) -> Session:
    task = taskbank.BY_ID[task_id]
    session = Session(
        session_id=f"mcp-{next(_COUNTER)}",
        # Platform use only. Research participation and audio are both off:
        # this demo never collects anything.
        consent=Consent(platform_use=True, research_participation=False, audio_retention=False),
        engine=DeterministicEngine(),
    )
    session.task_id = task.id
    session.band = task.band
    _SESSIONS[session.session_id] = session
    while len(_SESSIONS) > _MAX_SESSIONS:
        _SESSIONS.popitem(last=False)
    return session


@mcp.tool(title="Practice tasks", annotations=READ_ONLY)
def list_practice_tasks() -> list[dict[str, Any]]:
    """The reference implementation's ten placeholder tasks (two per band), for
    use with coach_attempt. They are illustrative, not a validated task bank."""
    return [
        {
            "task_id": t.id,
            "band": t.band,
            "topic": t.topic,
            "scenario": t.scenario,
            "her_decision_to_make": t.protected_judgment,
            "from_thesis": t.from_thesis,
        }
        for t in taskbank.TASKS
    ]


@mcp.tool(title="Run one attempt (offline demo)", annotations=SESSION_TOOL)
def coach_attempt(
    stated_intent: str,
    prompt_text: str,
    predicted_rating: int | None = None,
    task_id: str | None = None,
    session_id: str | None = None,
    revise_previous: bool = False,
    revision_reason: str | None = None,
    asked_for_help: bool = False,
) -> dict[str, Any]:
    """Run one attempt through all five layers on the offline rule engine and
    return what each layer produced. `stated_intent` is the student's plan,
    `prompt_text` the prompt she wrote, `predicted_rating` her 1 to 4 guess.
    To revise, pass the returned session_id with revise_previous=true and a
    one-sentence revision_reason (a revision without a reason is not scored).
    For trying the design only: do not send real student text."""
    if predicted_rating is not None and not (
        rubric.RUBRIC_MIN <= predicted_rating <= rubric.RUBRIC_MAX
    ):
        raise ValueError("predicted_rating must be 1 to 4")
    if task_id is not None and task_id not in taskbank.BY_ID:
        raise ValueError(f"Unknown task {task_id!r}. Call list_practice_tasks.")

    notes: list[str] = []
    session = _SESSIONS.get(session_id) if session_id else None
    if session_id and session is None:
        notes.append(f"Session {session_id!r} not found (sessions are in memory only); started a new one.")
    if session is None:
        session = _new_session(task_id or taskbank.WORKED_EXAMPLE_ID)
    elif task_id and task_id != session.task_id:
        moved, why = session.move_to(task_id)
        if moved:
            session.band = taskbank.BY_ID[task_id].band
        else:
            notes.append(why)

    parent = None
    if revise_previous:
        if session.history:
            parent = session.history[-1].attempt_id
        else:
            notes.append("No earlier attempt in this session, so this is a first attempt.")

    result = session.submit(
        stated_intent=stated_intent,
        prompt_text=prompt_text,
        parent_attempt_id=parent,
        predicted_rating=predicted_rating,
        revision_reason=revision_reason,
        asked_for_help=asked_for_help,
    )

    out: dict[str, Any] = {
        "session_id": session.session_id,
        "task_id": session.task_id,
        "stopped_at": result.stopped_at.value,
        "engine_note": OFFLINE_NOTE,
        "notes": notes,
    }
    if result.clarification:
        out["needs_from_student"] = result.clarification
    if result.answer is not None:
        out["output_she_sees_first"] = {
            "text": result.answer.text,
            "scripted_offline": result.answer.scripted,
        }
    if result.measure is not None:
        out["measure"] = {
            "scores": {
                k: {"value": s.value, "confidence": round(s.confidence, 2),
                    "evidence": s.evidence_span}
                for k, s in result.measure.scores.items()
            },
            "overall": result.measure.overall,
            "judge_model": result.measure.judge_model,
            "generator_model": result.measure.generator_model,
            "judge_independent_of_generator": result.measure.judge_independent_of_generator,
        }
    if result.calibration_gap is not None:
        out["calibration_gap_for_student_only"] = (
            round(result.calibration_gap, 2) if result.gap_visible else "recorded, hidden"
        )
    if result.diagnose is not None:
        out["diagnose"] = {
            "ranked": [
                {"rank": a.rank, "category": a.category.value,
                 "confidence": round(a.confidence, 2), "trigger": a.trigger}
                for a in result.diagnose.assignments
            ],
            "target": result.diagnose.target.value if result.diagnose.target else None,
        }
    if result.respond is not None:
        out["respond"] = {
            "level": result.respond.level,
            "text": result.respond.text,
            "she_still_does": result.respond.expected_action,
            "used_prepared_response": result.respond.used_template_floor,
        }
    if result.calibrate is not None:
        cal = result.calibrate
        out["calibrate"] = {
            "band": cal.band,
            "band_changed": cal.band_changed,
            "reason": cal.reason,
            "paired_dimension_change": cal.paired_delta,
            "over_reliance_signals_for_student_only": {
                k: round(v, 2) for k, v in cal.sentinel.items()
            },
        }
    out["revision_pending"] = result.revision_pending
    if result.help_cycle:
        out["help_cycle"] = result.help_cycle
    return out


# ---------------------------------------------------------------------------
# Resources and prompts
# ---------------------------------------------------------------------------


@mcp.resource(
    "promptcoach://guide/developers",
    name="developer_guide",
    title="Developer guide",
    description="How to build a prompt-writing tutor on the framework, with do and do-not rules.",
    mime_type="text/markdown",
)
def developer_guide() -> str:
    return GUIDE.read_text(encoding="utf-8")


@mcp.resource(
    "promptcoach://framework/traceability",
    name="traceability",
    title="Traceability matrix",
    description="Every framework constant and policy choice, traced to its thesis section.",
    mime_type="text/markdown",
)
def traceability_matrix() -> str:
    return TRACEABILITY.read_text(encoding="utf-8")


@mcp.prompt(title="Review a tutor design")
def review_tutor_design(design_description: str) -> str:
    """Review an AI prompt-writing tutor design against the framework."""
    return (
        "Review the tutor design below against the Learning to Prompt framework.\n"
        "1. Call get_framework_overview, then get_design_checklist.\n"
        "2. Answer each of the 24 checklist questions for this design with yes, partly, "
        "no, or unknown. Use unknown when the description does not say; do not guess.\n"
        "3. Call audit_tutor_design with those answers.\n"
        "4. Report the gaps by layer, the requirements R1 to R6 not fully met, and the "
        "adopted components that are still untested. For each gap, cite the thesis "
        "section the tool returns and suggest the smallest change that would close it.\n"
        "Say what the evidence grade means for each item. Do not call any part proven "
        "or say the framework improves learning; it has not been tested with students.\n\n"
        f"DESIGN:\n{design_description}"
    )


@mcp.prompt(title="Tutor turn rules")
def tutor_turn_rules() -> str:
    """Rules for an AI agent acting as a prompt-writing coach, from the framework."""
    rules = [
        "Ask her plan before she writes the prompt, and keep the two separately.",
        "Ask her to predict her score (1 to 4) before she runs the prompt.",
        "Show her what her own prompt produced before you coach.",
        "Score only text she wrote. Text she chose, pasted, or that you inserted is not hers.",
        "The model that scores her prompt must not be the model that answered it.",
        "Name the kind of failure (get_failure_taxonomy) before you choose a response.",
        "Address one failure at a time, starting at help level 1 (a single question).",
        "Move up the help ladder only when she asks or repeats the same failure; never because she paused. "
        "For blind acceptance, undiagnosed retry, and delegated judgment, move up only when she asks "
        "or sends her prompt unchanged.",
        ladder.AUTHORSHIP_BOUNDARY,
        "At the top level, show a worked contrast, never a model answer to copy.",
        "Ask her to revise the same prompt and say why before she moves on.",
        "Diagnoses and over-reliance signals are hers. Do not report them about a named student to anyone else.",
        "When you change what you ask of her, tell her why.",
    ]
    return "Follow these rules on every turn:\n" + "\n".join(f"- {r}" for r in rules)


def main() -> None:
    mcp.run("stdio")


if __name__ == "__main__":
    main()
