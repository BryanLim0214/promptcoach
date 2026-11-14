"""HTTP surface.

Two kinds of endpoint. `/api/framework` and `/api/policy` are static: they serve
the thesis-as-code and the implementation choices, so the frontend can label
every number it renders with a citation and a grade, or with the passage proving
the thesis left it open. `/api/session/*` runs the loop.

`/api/teacher` returns aggregates only, and there is no parameter that would make
it return anything else. Neither the sentinel nor any calibration data (her
predicted rating, the measured score beside it, the gap) is in its payload.

The application shows that the specification is implementable. It has not been
used with students.
"""

from __future__ import annotations

import os
import uuid
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import about, telemetry
from .engines import DeterministicEngine
from .engines.base import Engine
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
from .framework.contracts import Span
from .layers import Consent
from .policy import all_choices, taskbank, UNSPECIFIED_BY_THESIS
from .policy import calibration as calibration_policy
from .policy import generator as generator_policy
from .policy.base import CLOSED_BY_REMOVAL
from .responder import name_of
from .session import Session

app = FastAPI(title="PromptCoach Reference", version="1.0.0")

WEB_DIST = Path(__file__).parent.parent / "web" / "dist"

_SESSIONS: dict[str, Session] = {}


def _engines() -> tuple[Engine, Engine | None, Engine | None]:
    """(judge, comparator, generator).

    Live engines when a key is present, the offline set otherwise. The judge
    scores, diagnoses and composes coaching; the generator answers her prompt.
    They come from separate settings - the scorer from PROMPTCOACH_SCORER or the
    provider default, the generator from PROMPTCOACH_GENERATOR or the policy
    default - so the model that writes the answer she reads is not the model
    that scores her prompt (component 23).

    Gemini first, because that is the provider the replication benchmark was run
    against and the scorer reproduces Build 1's grader A configuration.
    OpenRouter is kept as the route to a genuinely different vendor, which is
    what Layer 2's first bar actually requires.

    The cross-model comparator is off unless asked for: it doubles the cost of
    every attempt, and two Gemini versions do not satisfy the bar anyway.

    Offline, the judge is the rule engine and the generator is None, which the
    session turns into the scripted responder: two different components by
    construction.
    """
    # An explicit escape hatch, because a key on the machine must never make a
    # test suite reach the network. Without this the API tests silently started
    # calling Gemini: they still passed, slowly, and were no longer testing the
    # thing they claimed to test.
    if os.environ.get("PROMPTCOACH_OFFLINE") == "1":
        return DeterministicEngine(), None, None

    from .engines import gemini

    gemini.load_env()
    cross = os.environ.get("PROMPTCOACH_CROSS_MODEL") == "1"

    if os.environ.get("GEMINI_API_KEY"):
        try:
            primary = gemini.build("scorer")
            comparator = gemini.build("comparator") if cross else None
            generator = gemini.build("generator")
        except Exception:
            # A bad key must not take the whole application down; the offline
            # engines run the same loop.
            return DeterministicEngine(), None, None
        # Outside the try: a non-independent configuration is not a bad key,
        # and falling back offline would hide it.
        _require_independent(primary, comparator, generator)
        return primary, comparator, generator

    if os.environ.get("OPENROUTER_API_KEY"):
        from .engines import openrouter

        primary = openrouter.build("primary")
        comparator = openrouter.build("comparator") if cross else None
        generator = openrouter.build("generator")
        _require_independent(primary, comparator, generator)
        return primary, comparator, generator

    return DeterministicEngine(), None, None


def _require_independent(
    primary: Engine, comparator: Engine | None, generator: Engine
) -> None:
    """The judge-independence component: the generator may be neither the
    scorer nor the comparator. Raises NonIndependentConfiguration."""
    judges = (primary.name,) + ((comparator.name,) if comparator else ())
    generator_policy.check_independent(judges, generator.name)


@app.on_event("startup")
def _refuse_non_independent_live_config() -> None:
    """Refuse to start, with the reason, rather than run non-independent."""
    _engines()


def _j(obj: Any) -> Any:
    if is_dataclass(obj) and not isinstance(obj, type):
        return {k: _j(v) for k, v in asdict(obj).items()}
    if isinstance(obj, dict):
        return {str(k): _j(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_j(v) for v in obj]
    if hasattr(obj, "value") and hasattr(obj, "name"):
        return obj.value
    return obj


# ---------------------------------------------------------------------------
# The spec
# ---------------------------------------------------------------------------


@app.get("/api/framework")
def framework() -> dict:
    return {
        "dimensions": [
            {
                "id": d.id,
                "name": d.name,
                "measures": d.measures,
                "one_against_four": d.one_against_four,
                "kind": d.kind.value,
                "weighted_kappa": d.weighted_kappa,
                "within_one_pct": d.within_one_pct,
                "cite": str(rubric.CITE),
            }
            for d in rubric.DIMENSIONS
        ],
        "scale": {"min": rubric.RUBRIC_MIN, "max": rubric.RUBRIC_MAX,
                  "span": rubric.RUBRIC_SPAN},
        "reliability": {
            "overall_icc": rubric.OVERALL_ICC_2_2,
            "overall_weighted_kappa": rubric.OVERALL_WEIGHTED_KAPPA,
            "paraphrase_shift": rubric.PARAPHRASE_MEAN_ABSOLUTE_SHIFT,
            "mean_grader_gap": rubric.MEAN_GRADER_GAP_POINTS,
            "latency_mean_s": rubric.LATENCY_MEAN_SECONDS,
            "latency_p95_s": rubric.LATENCY_P95_SECONDS,
            "caveat": rubric.RELIABILITY_CAVEAT,
            "third_bar": rubric.THIRD_BAR_UNCLEARED,
            "shared_prior": rubric.SHARED_PRIOR_THREAT,
            "expires": rubric.RELIABILITY_EXPIRY,
        },
        "taxonomy": [
            {
                "id": c.id.value,
                "name": c.name,
                "student_did": c.student_did,
                "derived_from": c.derived_from,
                "response_implied": c.response_implied,
                "detectable_from": c.detectable_from.value,
                "paired_dimension": c.paired.description,
                "grade": c.grade.value,
                "cite": str(c.cite),
            }
            for c in taxonomy.CATEGORIES
        ],
        "taxonomy_notes": {
            "overlap": taxonomy.OVERLAP_IS_MANDATORY,
            "circularity": taxonomy.CIRCULARITY_WARNING,
            "strictness": taxonomy.STRICTNESS_WARNING,
            "prior_work": taxonomy.CONTRAST_WITH_PRIOR_WORK,
        },
        "ladder": [
            {
                "level": lv.number,
                "gives": lv.gives,
                "student_still_does": lv.student_still_does,
                "grade": lv.grade.value,
                "cite": str(lv.cite),
            }
            for lv in ladder.LEVELS
        ],
        "ladder_notes": {
            "boundary": ladder.AUTHORSHIP_BOUNDARY,
            "level_4_exposure": ladder.LEVEL_4_EXPOSURE,
            "template_floor": ladder.TEMPLATE_FLOOR_RULE,
            "single_target": ladder.SINGLE_TARGET_RULE,
        },
        "bands": [
            {
                "band": b.number,
                "axis": b.axis.value,
                "requires": b.requires,
                "example": b.example,
                "dimensions_named_in_task": b.dimensions_named_in_task,
                "grade": b.grade.value,
                "cite": str(b.cite),
            }
            for b in progression.BANDS
        ],
        "band_notes": {
            "axis_join": list(progression.AXIS_JOIN),
            "not_commensurable": progression.AXES_NOT_COMMENSURABLE,
            "band_1_argument": progression.BAND_1_RESTS_ON_ARGUMENT,
            "why_4_and_5": progression.WHY_4_AND_5_SPLIT,
        },
        "sentinel": {
            "signals": [
                {
                    "id": s.id,
                    "name": s.name,
                    "detects": s.detects,
                    "derives_category": s.derives_category.value,
                }
                for s in sentinel.SIGNALS
            ],
            "auc": sentinel.AUC,
            "cross_model_agreement": sentinel.CROSS_MODEL_PEARSON,
            "one_signal": sentinel.ONE_SIGNAL_CARRIES_IT,
            "thin_basis": sentinel.THIN_BASIS,
            "routing_rule": sentinel.ROUTING_RULE,
            "replication_auc_pooled": sentinel.REPLICATION_AUC_POOLED,
            "replication_auc_run_range": list(sentinel.REPLICATION_AUC_RUN_RANGE),
            "auc_reading": sentinel.AUC_READING,
        },
        "commitments": [
            {
                "id": c.id,
                "name": c.name,
                "text": c.text,
                "grade": c.grade.value,
                "cite": str(c.cite),
            }
            for c in commitments.COMMITMENTS
        ],
        "prohibitions": {
            "teacher_view": commitments.TEACHER_VIEW_PROHIBITION,
            "calibration": commitments.CALIBRATION_STAYS_WITH_STUDENT,
            "audio": commitments.AUDIO_HANDLING_RULE,
        },
        "revision": {
            "rule": revision.ASK_FOR_REASON,
            "hold": revision.HOLD_MESSAGE,
            "f7": revision.F7,
            "grade": revision.COMPONENT.grade.value,
            "cite": str(revision.CITE),
        },
        "classroom": {
            "self_report_rule": classroom.SELF_REPORT_RULE,
            "promptemon_label": classroom.PROMPTEMON_LABEL,
            "promptemon_students_did_not_type": classroom.PROMPTEMON_STUDENTS_DID_NOT_TYPE,
            "aggregates": [
                {
                    "id": a.id,
                    "study": a.study,
                    "value": a.value,
                    "meaning": a.meaning,
                    "caveat": a.caveat,
                    "self_report": a.self_report,
                    "cite": str(a.cite),
                }
                for a in classroom.AGGREGATES.values()
            ],
            # Each pair goes through present(): change only where the two items
            # are comparable, side by side with no difference otherwise.
            "item_pairs": [classroom.present(k) for k in classroom.ITEM_PAIRS],
        },
        "non_transfers": commitments.NON_TRANSFERS,
        "grades": {
            "definitions": {g.value: t for g, t in grades.GRADE_DEFINITION.items()},
            "need_definitions": {
                n.value: t for n, t in grades.NEED_DEFINITION.items()
            },
            # Display text. The keys stay stable; the labels are what a reader
            # sees ("User studies", never "Students").
            "need_labels": {n.value: t for n, t in grades.NEED_LABEL.items()},
            "counts": {g.value: n for g, n in grades.counts().items()},
            "need_counts": {n.value: k for n, k in grades.need_counts().items()},
            "components": [
                {
                    "id": c.id,
                    "name": c.name,
                    "grade": c.grade.value,
                    "need": c.need.value,
                    "need_label": c.need.label,
                    "requirement": c.requirement,
                    "basis": c.basis,
                    "limit": c.limit,
                    "cite": str(c.cite),
                }
                for c in grades.GRADED_COMPONENTS
            ],
            "originals": list(grades.ORIGINAL_CONTRIBUTIONS),
            "removed": {
                k: {"why": why, "cite": str(cite)}
                for k, (why, cite) in grades.REMOVED_COMPONENTS.items()
            },
        },
    }


@app.get("/api/policy")
def policy_payload() -> dict:
    return {
        "choices": [
            {
                "id": c.id,
                "value": c.value,
                "thesis_says": c.thesis_says,
                "borrowed_from": c.borrowed_from,
                "caveat": c.caveat,
            }
            for c in all_choices()
        ],
        "unspecified": [{"id": k, "note": v} for k, v in UNSPECIFIED_BY_THESIS],
        "closed_by_removal": [{"id": k, "note": v} for k, v in CLOSED_BY_REMOVAL],
    }


@app.get("/api/about")
def about_payload() -> dict:
    return about.payload()


#: One engine kept for the life of the process, so live telemetry accumulates
#: across requests instead of resetting on every call.
_LIVE_ENGINE: Engine | None = None


@app.get("/api/telemetry")
def telemetry_payload() -> dict:
    global _LIVE_ENGINE
    if _LIVE_ENGINE is None:
        _LIVE_ENGINE, _, _ = _engines()
    return telemetry.payload(_LIVE_ENGINE)


@app.get("/api/tasks")
def tasks() -> list[dict]:
    return [
        {
            "id": t.id,
            "band": t.band,
            "topic": t.topic,
            "scenario": t.scenario,
            "protected_judgment": t.protected_judgment,
            "named_dimensions": list(t.named_dimensions),
            "provided_model_output": t.provided_model_output,
            "reading_load": t.reading_load,
            "from_thesis": t.from_thesis,
        }
        for t in taskbank.TASKS
    ]


@app.get("/api/health")
def health() -> dict:
    primary, comparator, generator = _engines()
    generator_name = generator.name if generator else "scripted-responder"
    judges = (primary.name,) + ((comparator.name,) if comparator else ())
    return {
        "engine": primary.name,
        "organisation": primary.organisation,
        "comparator": comparator.name if comparator else None,
        "generator": generator_name,
        "judge_independent_of_generator": generator_policy.independent(
            judges, generator_name
        ),
        "cross_model": comparator is not None
        and comparator.organisation != primary.organisation,
        "offline": primary.organisation == "none",
        "no_students": (
            "No middle school student has used this. It shows the specification "
            "is implementable, not that it teaches."
        ),
    }


# ---------------------------------------------------------------------------
# The loop
# ---------------------------------------------------------------------------


class NewSession(BaseModel):
    platform_use: bool = True
    research_participation: bool = False
    audio_retention: bool = False
    task_id: str | None = None
    selection_mode: str | None = None
    #: F7's control arm switches this off. None is the policy default.
    require_reason: bool | None = None
    #: F8's control arm switches this off. None is the policy default.
    show_gap: bool | None = None


class InsertedSpan(BaseModel):
    start: int = Field(ge=0)
    end: int = Field(ge=0)


class Submission(BaseModel):
    stated_intent: str = Field(default="")
    prompt_text: str = Field(default="")
    intent_modality: str = "typed"
    transcript_reviewed: bool = True
    student_ms: int = 0
    parent_attempt_id: str | None = None
    asked_for_help: bool = False
    #: Her prediction, 1 to 4, before she sees the output. Optional; an
    #: out-of-range value is asked about by Layer 1 rather than rejected here.
    predicted_rating: int | None = None
    #: Why she changed the prompt, on a revision of the same task.
    revision_reason: str | None = None
    #: Character ranges of prompt_text the interface inserted.
    inserted_spans: list[InsertedSpan] = Field(default_factory=list)


@app.post("/api/session")
def create_session(body: NewSession) -> dict:
    global _LIVE_ENGINE
    primary, comparator, generator = _engines()
    # Sessions share one engine instance so live telemetry accumulates across
    # them. A per-session engine would reset the latency distribution every
    # time someone started a task, and the resulting chart would always show
    # one or two points.
    if _LIVE_ENGINE is None:
        _LIVE_ENGINE = primary
    else:
        primary = _LIVE_ENGINE
    sid = uuid.uuid4().hex[:12]
    session = Session(
        session_id=sid,
        consent=Consent(
            platform_use=body.platform_use,
            research_participation=body.research_participation,
            audio_retention=body.audio_retention,
        ),
        engine=primary,
        comparator=comparator,
        generator=generator,
        selection_mode=body.selection_mode,
        require_reason=body.require_reason,
        show_gap=body.show_gap,
    )
    if body.task_id:
        if body.task_id not in taskbank.BY_ID:
            raise HTTPException(404, f"no task {body.task_id}")
        session.task_id = body.task_id
        session.band = taskbank.BY_ID[body.task_id].band
    _SESSIONS[sid] = session
    return _state(session)


@app.get("/api/session/{sid}")
def get_session(sid: str) -> dict:
    return _state(_require(sid))


@app.post("/api/session/{sid}/task/{task_id}")
def set_task(sid: str, task_id: str) -> dict:
    """Move to a task, keeping the session's history and band.

    Calibrate recommends the next task; this is where the move actually
    happens, when the student asks for it. The band is not reset from the
    task's own band here, because the difficulty state belongs to the session
    and Calibrate has already decided it.
    """
    session = _require(sid)
    if task_id not in taskbank.BY_ID:
        raise HTTPException(404, f"no task {task_id}")
    moved, why = session.move_to(task_id)
    if not moved:
        # The reasoned-revision hold (component 21). Not an error in her work:
        # the task asks for one revision with a reason before the next one.
        raise HTTPException(409, why)
    return _state(session)


@app.post("/api/session/{sid}/submit")
def submit(sid: str, body: Submission) -> dict:
    session = _require(sid)
    result = session.submit(
        stated_intent=body.stated_intent,
        prompt_text=body.prompt_text,
        intent_modality=body.intent_modality,
        transcript_reviewed=body.transcript_reviewed,
        student_ms=body.student_ms,
        parent_attempt_id=body.parent_attempt_id,
        asked_for_help=body.asked_for_help,
        predicted_rating=body.predicted_rating,
        revision_reason=body.revision_reason,
        inserted_spans=_spans(body.inserted_spans),
    )
    if result.measure and result.elicit.record:
        session.store_scores(result.elicit.record.attempt_id, result.measure.scores)

    parent_answer = None
    if body.parent_attempt_id:
        prior = session.answers.get(body.parent_attempt_id)
        parent_answer = _j(prior) if prior else None

    calibrate = _j(result.calibrate)
    if calibrate is not None and not result.gap_visible:
        # F8's control arm: recorded, not shown.
        calibrate["calibration_gap"] = None
        calibrate["measured_overall"] = None

    return {
        "stopped_at": result.stopped_at.value,
        "clarification": result.clarification,
        "elicit": _j(result.elicit),
        "measure": _j(result.measure),
        "diagnose": _j(result.diagnose),
        "respond": _j(result.respond),
        "calibrate": calibrate,
        # Hers only. The teacher route never carries any of this.
        "calibration": {
            "predicted_rating": (
                result.elicit.record.predicted_rating if result.elicit.record else None
            ),
            "measured_overall": (
                result.measure.overall
                if result.measure and result.gap_visible
                else None
            ),
            "gap": result.calibration_gap if result.gap_visible else None,
            "visible": result.gap_visible,
        },
        "revision_pending": result.revision_pending,
        # What happened to the help cycle on this attempt (opened, still open,
        # closed and why). Policy escalation.cycle.
        "help_cycle": result.help_cycle,
        # What her prompt produced, and what the prompt before it produced, so
        # a revision can be read against the answer it replaced.
        "answer": _j(result.answer),
        "previous_answer": parent_answer,
        "previous_prompt": (
            session.store.get(body.parent_attempt_id).prompt_text
            if body.parent_attempt_id and session.store.get(body.parent_attempt_id)
            else None
        ),
        "trace": result.trace.to_json(),
        "state": _state(session),
    }


@app.get("/api/teacher")
def teacher_view() -> dict:
    """Aggregate only.

    There is no `student_id` parameter, no per-student route, and neither the
    sentinel nor any calibration data (predicted rating, measured score, gap)
    appears in this payload, aggregate or otherwise. That is the commitment,
    not a default.
    """
    counts: dict[str, int] = {}
    for session in _SESSIONS.values():
        counts[str(session.band)] = counts.get(str(session.band), 0) + 1

    MIN_CELL = 5
    suppressed = {
        band: (n if n >= MIN_CELL else "suppressed") for band, n in counts.items()
    }
    return {
        "aggregate_only": True,
        "named_detail_included": False,
        "sentinel_included": False,
        "calibration_included": False,
        "min_cell_size": MIN_CELL,
        "band_distribution": suppressed,
        "why": commitments.TEACHER_VIEW_PROHIBITION,
        "calibration_policy": calibration_policy.TEACHER_VIEW.value,
    }


def _spans(raw: list[InsertedSpan]) -> tuple[Span, ...]:
    try:
        return tuple(Span(s.start, s.end) for s in raw)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


def _require(sid: str) -> Session:
    session = _SESSIONS.get(sid)
    if session is None:
        raise HTTPException(404, f"no session {sid}")
    return session


def _state(session: Session) -> dict:
    task = taskbank.BY_ID[session.task_id]
    return {
        "session_id": session.session_id,
        "band": session.band,
        "task_id": session.task_id,
        "task": {
            "id": task.id,
            "band": task.band,
            "scenario": task.scenario,
            "protected_judgment": task.protected_judgment,
            "named_dimensions": list(task.named_dimensions),
            "provided_model_output": task.provided_model_output,
            "from_thesis": task.from_thesis,
        },
        "levels_issued": list(session.levels_issued),
        "attempts": len(session.history),
        "revision_pending": session.revision_pending,
        "require_reason": bool(session.require_reason),
        "show_gap": bool(session.show_gap),
        "generator": name_of(session.responder) if session.responder else None,
        "consent": {
            "platform_use": session.consent.platform_use,
            "research_participation": session.consent.research_participation,
            "audio_retention": session.consent.audio_retention,
        },
    }


# ---------------------------------------------------------------------------
# Static frontend
# ---------------------------------------------------------------------------

if WEB_DIST.exists():
    app.mount("/assets", StaticFiles(directory=WEB_DIST / "assets"), name="assets")

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(WEB_DIST / "index.html")

    @app.get("/{path:path}")
    def spa(path: str) -> FileResponse:
        """Serve the app for any non-API path.

        The student app is at `/` and the researcher view at `/inspect`. The
        second is deliberately not linked from the first: a citation is no use
        to a twelve year old and every reason to distract her. It is reachable
        by typing the URL, which is the right amount of friction for something
        only a committee needs.
        """
        if path.startswith("api/"):
            raise HTTPException(404, "no such endpoint")
        return FileResponse(WEB_DIST / "index.html")

else:

    @app.get("/")
    def index_missing() -> JSONResponse:
        return JSONResponse(
            {
                "detail": "The frontend has not been built.",
                "run": "cd web && npm install && npm run build",
            },
            status_code=503,
        )
