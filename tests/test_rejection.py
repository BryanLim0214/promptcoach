"""Tier 2 - the normative prohibitions.

Each of these is something the thesis forbids and a plausible implementation
would do by default. A teacher dashboard is the obvious thing to build. Bundled
consent is the easy thing to ship. Keeping the audio is the cheap thing to do.
Filling in the missing element is the helpful-feeling thing to do.

These tests fail loudly when any of that creeps back in.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from promptcoach_ref.engines import DeterministicEngine
from promptcoach_ref.framework import commitments, ladder, rubric
from promptcoach_ref.framework.taxonomy import Category
from promptcoach_ref.layers import Consent, validate
from promptcoach_ref.layers.measure import ROUTING_HUMAN_REVIEW
from promptcoach_ref.policy import taskbank
from promptcoach_ref.session import Session
from promptcoach_ref.store import OverwriteRejected, Store

from conftest import WORKED_SPOKEN, WORKED_TYPED, FailingEngine, OverreachingEngine

pytestmark = pytest.mark.rejection


# --- Layer 1 --------------------------------------------------------------


def test_the_prompt_is_stored_verbatim_and_never_repaired(session):
    raw = "explain  WHY the sky   is blue plz"
    r = session.submit(stated_intent="I want to know about the sky", prompt_text=raw)
    assert r.elicit.record is not None
    assert r.elicit.record.prompt_text == raw


def test_declining_the_microphone_still_completes_the_loop(engine):
    """sec:commitments - "a student who declines audio capture must retain a usable path
    through the system". sec:method adds that it degrades the diagnosis rather than
    blocking it. The thesis then says none of that was implemented."""
    s = Session(
        session_id="no-mic",
        consent=Consent(
            platform_use=True, research_participation=False, audio_retention=False
        ),
        engine=engine,
    )
    s.task_id = taskbank.WORKED_EXAMPLE_ID
    r = s.submit(
        stated_intent=WORKED_SPOKEN,
        prompt_text=WORKED_TYPED,
        intent_modality="speech",
    )
    assert r.elicit.record is not None
    # Downgraded, not blocked.
    assert r.elicit.record.intent_modality == "typed"
    assert r.elicit.record.intent_is_degraded
    assert r.stopped_at.value != "elicit"
    assert r.diagnose is not None


def test_withdrawing_research_consent_does_not_close_the_door(engine):
    """Platform use and research participation are separate decisions."""
    s = Session(
        session_id="no-research",
        consent=Consent(
            platform_use=True, research_participation=False, audio_retention=False
        ),
        engine=engine,
    )
    assert s.consent.instruction_permitted is True


def test_consent_has_three_separate_decisions():
    """Bundling any two into one control would violate sec:commitments."""
    fields = Consent.__dataclass_fields__
    assert {"platform_use", "research_participation", "audio_retention"} <= set(fields)


def test_an_unreviewed_transcript_is_not_scored(session):
    r = session.submit(
        stated_intent=WORKED_SPOKEN,
        prompt_text=WORKED_TYPED,
        intent_modality="speech",
        transcript_reviewed=False,
    )
    assert r.stopped_at.value == "elicit"
    assert "transcript" in (r.clarification or "").lower()


def test_no_audio_is_ever_stored(session, worked):
    """The transcript is the artifact. There is no audio field to leak."""
    record = worked.elicit.record
    assert record is not None
    assert not hasattr(record, "audio")
    assert not hasattr(record, "audio_blob")
    assert not hasattr(record, "recording")


# --- Layer 2 --------------------------------------------------------------


def test_a_scoring_failure_is_not_a_score_of_zero(consent):
    s = Session(session_id="fail", consent=consent, engine=FailingEngine())
    s.task_id = taskbank.WORKED_EXAMPLE_ID
    r = s.submit(stated_intent=WORKED_SPOKEN, prompt_text=WORKED_TYPED)
    assert r.measure is not None
    assert r.measure.overall is None
    assert r.measure.routing == ROUTING_HUMAN_REVIEW
    assert "timed out" in (r.measure.failure_reason or "")
    assert r.diagnose is None


def test_an_evidence_span_absent_from_the_artifact_is_dropped(session):
    """A span the model invented would show her a quotation she never wrote."""
    from promptcoach_ref.engines.base import DimensionSample, ScoringSample

    class Fabricating(DeterministicEngine):
        def sample_scores(self, request, temperature):
            return ScoringSample(
                judge="fabricating",
                temperature=temperature,
                dimensions=tuple(
                    DimensionSample(
                        dimension_id=d.id,
                        value=3,
                        evidence_span="a phrase she never typed",
                    )
                    for d in rubric.DIMENSIONS
                ),
            )

    session._measure.engine = Fabricating()
    r = session.submit(stated_intent="something", prompt_text="explain the sky please")
    assert r.measure is not None
    for score in r.measure.scores.values():
        assert score.evidence_span is None
        assert score.span_verified is False


def test_a_value_outside_the_rubric_is_discarded_not_clamped(session):
    from promptcoach_ref.engines.base import DimensionSample, ScoringSample

    class OutOfRange(DeterministicEngine):
        def sample_scores(self, request, temperature):
            return ScoringSample(
                judge="oor",
                temperature=temperature,
                dimensions=tuple(
                    DimensionSample(dimension_id=d.id, value=9)
                    for d in rubric.DIMENSIONS
                ),
            )

    session._measure.engine = OutOfRange()
    r = session.submit(stated_intent="something", prompt_text="explain the sky please")
    assert r.measure is not None
    assert r.measure.overall is None
    assert all(s.unable_to_score for s in r.measure.scores.values())


def test_model_agreement_is_never_called_teacher_calibration():
    from promptcoach_ref.layers.measure import PROVENANCE

    assert PROVENANCE["teacher_calibrated"] is False


# --- Layer 3 --------------------------------------------------------------


def test_diagnosis_never_returns_a_bare_single_label(worked):
    """sec:diagnose requires "several categories in rank order and never a single
    label", because the categories overlap constantly."""
    assert worked.diagnose is not None
    assert len(worked.diagnose.assignments) >= 2
    ranks = [a.rank for a in worked.diagnose.assignments]
    assert ranks == sorted(ranks)


def test_every_assignment_carries_the_evidence_that_fired_it(worked):
    assert worked.diagnose is not None
    for a in worked.diagnose.assignments:
        assert a.trigger.strip()


def test_no_diagnosis_records_a_trait_label(worked):
    """The framework diagnoses a prompt, not a student."""
    blob = json.dumps(
        [a.trigger for a in worked.diagnose.assignments]
        + list(worked.diagnose.reason_trace)
    ).lower()
    for word in ("lazy", "unmotivated", "careless", "weak student", "dependent"):
        assert word not in blob


def test_insufficient_evidence_is_distinct_from_no_failure(session):
    """"The system could not tell" is not "she did not fail"."""
    from promptcoach_ref.engines.base import RawAssignment

    class Unsure(DeterministicEngine):
        def diagnose(self, request):
            return [
                RawAssignment(
                    category=Category.SOCIAL_FRAMING,
                    confidence=0.2,
                    trigger="a faint hint",
                )
            ]

    session._diagnose.engine = Unsure()
    r = session.submit(stated_intent="something", prompt_text="explain the sky please")
    assert r.diagnose is not None
    assert r.diagnose.target is None
    assert r.diagnose.insufficient_evidence is True
    assert any("insufficient evidence" in t for t in r.diagnose.reason_trace)


# --- Layer 4 --------------------------------------------------------------


def test_no_level_supplies_a_missing_element(session, worked):
    """sec:respond - "Guidance may narrow the search space and may not close it." """
    assert worked.respond is not None
    missing = tuple(
        d.id
        for d in rubric.PLANNING_DIMENSIONS
        if d.id not in ("context_clarity",)
    )
    check = validate(
        "You should ask for it for a seven year old in three sentences.",
        level=1,
        category=Category.UNDER_SPECIFICATION,
        protected_judgment="what counts as an explanation she will follow",
        missing_from_prompt=missing,
    )
    assert check.ok is False
    assert "may not close it" in check.reason


def test_replaying_what_she_said_aloud_is_not_supplying_it(session, worked):
    """The other side of sec:respond - "on her behalf".

    The same sentence that must be refused when she never said it has to be
    allowed when she did, or intent-drift coaching is impossible: sec:design's own
    model response names the threads she dropped. Getting this wrong is not
    hypothetical - it rejected every generated response on the worked example
    and served the template floor in place of all of them.

    The exemption is per dimension, not per phrase, because she says "she's
    like seven" and a model says "a seven-year-old".
    """
    missing = tuple(d.id for d in rubric.PLANNING_DIMENSIONS)
    said_aloud = ("audience_awareness", "specificity")
    # Close to what the live model actually writes on the worked example: it
    # names the reader and the length, both of which she supplied herself.
    text = (
        "You told me it was for a seven year old cousin and that it should be "
        "a few sentences, and neither made it into what you typed. Which of "
        "those matters most?"
    )

    refused = validate(
        text,
        level=1,
        category=Category.INTENT_DRIFT,
        protected_judgment="",
        missing_from_prompt=missing,
    )
    assert refused.ok is False, "with nothing stated aloud this is a supply"

    allowed = validate(
        text,
        level=1,
        category=Category.INTENT_DRIFT,
        protected_judgment="",
        missing_from_prompt=missing,
        stated_by_student=said_aloud,
    )
    assert allowed.ok is True, allowed.reason


def test_a_dimension_she_never_raised_is_still_closed():
    """The exemption covers what she said, and nothing beyond it."""
    check = validate(
        "Try asking for it as bullet points.",
        level=1,
        category=Category.INTENT_DRIFT,
        protected_judgment="",
        missing_from_prompt=("specificity", "audience_awareness"),
        # She mentioned the reader, never the length.
        stated_by_student=("audience_awareness",),
    )
    assert check.ok is False
    assert "Specificity" in check.reason


def test_a_response_that_hands_over_a_prompt_is_rejected():
    check = validate(
        "Here's a better prompt: explain the sky for a seven year old.",
        level=1,
        category=Category.INTENT_DRIFT,
        protected_judgment="",
        missing_from_prompt=(),
    )
    assert check.ok is False
    assert "prohibited disclosure" in check.reason


def test_an_overreaching_generation_falls_back_to_the_template_floor(consent):
    """sec:respond - the floor "is served whenever the model call fails or its output
    violates the constraints"."""
    s = Session(session_id="over", consent=consent, engine=OverreachingEngine())
    s.task_id = taskbank.WORKED_EXAMPLE_ID
    r = s.submit(
        stated_intent=WORKED_SPOKEN,
        prompt_text=WORKED_TYPED,
        intent_modality="speech",
    )
    assert r.respond is not None
    assert r.respond.used_template_floor is True
    assert "Here's a better prompt" not in r.respond.text
    assert "rejected" in r.respond.selection_reason


def test_respond_cannot_reclassify(worked):
    assert worked.respond is not None
    assert worked.diagnose is not None
    assert worked.respond.target is worked.diagnose.target


def test_first_help_is_always_the_lowest_level(worked):
    assert worked.respond is not None
    assert worked.respond.level == ladder.FIRST_LEVEL


def test_the_terminal_level_still_requires_student_authorship():
    check = validate(
        "A. one prompt B. another prompt. That is the answer.",
        level=ladder.TERMINAL_LEVEL,
        category=Category.UNDER_SPECIFICATION,
        protected_judgment="",
        missing_from_prompt=(),
    )
    assert check.ok is False


# --- Cross-cutting --------------------------------------------------------


def test_the_teacher_view_is_aggregate_and_carries_no_sentinel():
    """sec:method - "The framework forbids it, requiring aggregate teacher views
    unless a student chooses to share her own." """
    from promptcoach_ref.api import teacher_view

    payload = teacher_view()
    assert payload["aggregate_only"] is True
    assert payload["named_detail_included"] is False
    assert payload["sentinel_included"] is False
    blob = json.dumps(payload).lower()
    for signal in ("transcript_prompt_disconnect", "excessive_deference"):
        assert signal not in blob


def test_the_teacher_route_takes_no_student_parameter():
    """There is no argument that would make it return one student's record."""
    import inspect

    from promptcoach_ref.api import teacher_view

    assert inspect.signature(teacher_view).parameters == {}


def _code_only(path: pathlib.Path) -> str:
    """Source with comments and string literals removed.

    Prose is not an implementation. The word "badges" in a sentence about how the
    interface badges a citation is not a gamification badge, so the scan looks at
    executable tokens only.
    """
    import io
    import tokenize

    kept: list[str] = []
    with path.open("rb") as fh:
        for tok in tokenize.tokenize(fh.readline):
            if tok.type in (tokenize.COMMENT, tokenize.STRING):
                continue
            kept.append(tok.string)
    return " ".join(kept)


def test_gamification_is_absent():
    """sec:build2 records it as a deliberate non transfer, not an omission."""
    root = pathlib.Path(__file__).resolve().parent.parent / "promptcoach_ref"
    blob = "\n".join(
        _code_only(p)
        for p in root.rglob("*.py")
        # commitments.py is where the tokens are declared in order to forbid
        # them, so it is the one file allowed to name them.
        if p.name != "commitments.py"
    )
    for token in commitments.FORBIDDEN_TOKENS:
        assert token not in blob, f"{token} would reintroduce the gamification layer"


def test_the_six_mathematics_error_types_are_absent():
    """sec:build2 - "These are domain knowledge and do not transfer; the practice of
    classifying before responding does." The seven categories are the taxonomy;
    there is no second, mathematics-shaped one hiding anywhere."""
    from promptcoach_ref.framework.taxonomy import CATEGORIES

    assert len(CATEGORIES) == 7
    names = {c.id.value for c in CATEGORIES}
    for maths in (
        "arithmetic_slip",
        "conceptual_inversion",
        "magnitude_error",
        "reciprocal_error",
    ):
        assert maths not in names


def test_the_store_refuses_to_reuse_an_identifier():
    store = Store()
    store.append("a", {"v": 1})
    with pytest.raises(OverwriteRejected):
        store.append("a", {"v": 2})


def test_audit_events_carry_no_prompt_content():
    store = Store()
    store.append("a", {"prompt_text": "zzqq-secret-goal"})
    blob = " ".join(str(e) for e in store.audit)
    assert "zzqq" not in blob


# --- the redesigned framework's prohibitions --------------------------------


def test_calibration_data_never_reaches_the_teacher_view():
    """Her predicted rating and the gap are diagnostics about her. The teacher
    route carries neither, aggregate or otherwise, however many students have
    rated their prompts."""
    import inspect

    from fastapi.testclient import TestClient

    from promptcoach_ref.api import app, teacher_view

    client = TestClient(app)
    for rating in (1, 2, 3, 4, 4, 3):
        sid = client.post(
            "/api/session", json={"platform_use": True, "task_id": "b3-babysitting"}
        ).json()["session_id"]
        out = client.post(
            f"/api/session/{sid}/submit",
            json={
                "stated_intent": WORKED_SPOKEN,
                "prompt_text": WORKED_TYPED,
                "predicted_rating": rating,
            },
        ).json()
        assert out["calibration"]["gap"] is not None  # she gets it

    payload = teacher_view()
    assert payload["calibration_included"] is False
    blob = json.dumps(payload).lower()
    for token in ("predicted", "calibration_gap", "measured_overall", "\"gap\""):
        assert token not in blob
    # And no parameter could ask for it.
    assert inspect.signature(teacher_view).parameters == {}


def test_a_revision_without_a_reason_is_not_scored(session):
    """framework/revision.py, rule 1: a revision of the same task needs a
    non-empty stated reason before it is scored."""
    from conftest import WORKED_REVISION

    first = session.submit(stated_intent=WORKED_SPOKEN, prompt_text=WORKED_TYPED)
    parent = first.elicit.record.attempt_id
    for missing in (None, "", "   "):
        r = session.submit(
            stated_intent=WORKED_SPOKEN,
            prompt_text=WORKED_REVISION,
            parent_attempt_id=parent,
            revision_reason=missing,
        )
        assert r.stopped_at.value == "elicit"
        assert r.elicit.record is None
        assert r.measure is None
        assert r.answer is None
        assert "why you changed it" in (r.clarification or "")
    # A first attempt needs no reason.
    assert first.measure is not None


def test_a_perfunctory_reason_below_the_policy_minimum_is_not_scored(session):
    from conftest import WORKED_REVISION

    first = session.submit(stated_intent=WORKED_SPOKEN, prompt_text=WORKED_TYPED)
    r = session.submit(
        stated_intent=WORKED_SPOKEN,
        prompt_text=WORKED_REVISION,
        parent_attempt_id=first.elicit.record.attempt_id,
        revision_reason="idk",
    )
    assert r.measure is None


def test_inserted_text_is_not_scored_as_hers(session):
    """Selecting is not composing. A chip that supplies the audience does not
    earn her the Audience Awareness score."""
    from promptcoach_ref.framework.contracts import Span

    prompt = "explain why the sky is blue for a seven year old"
    start = prompt.index("for a seven year old")
    inserted = (Span(start, len(prompt)),)

    with_chip = session.submit(
        stated_intent="I want to know about the sky",
        prompt_text=prompt,
        inserted_spans=inserted,
    )
    assert with_chip.elicit.record.prompt_text == prompt  # stored verbatim
    assert with_chip.measure.scores["audience_awareness"].value == 1
    assert with_chip.measure.excluded_inserted_chars > 0
    for s in with_chip.measure.scores.values():
        if s.evidence_span:
            assert "seven year old" not in s.evidence_span

    # The same words typed by her do earn it.
    typed = Session(
        session_id="typed-herself",
        consent=Consent(
            platform_use=True, research_participation=False, audio_retention=False
        ),
        engine=DeterministicEngine(),
    ).submit(stated_intent="I want to know about the sky", prompt_text=prompt)
    assert typed.measure.scores["audience_awareness"].value >= 3


def test_respond_treats_inserted_text_as_not_hers(engine):
    """The coaching still treats the audience as missing from what she wrote,
    and the prompt it shows back is her own words only."""
    from promptcoach_ref.framework.contracts import (
        MeasureInput,
        PairedRecord,
        RespondInput,
        Span,
    )
    from promptcoach_ref.layers import MeasureLayer, RespondLayer

    prompt = "explain why the sky is blue for a seven year old"
    record = PairedRecord(
        attempt_id="x",
        task_id=taskbank.WORKED_EXAMPLE_ID,
        stated_intent="I want to know about the sky",
        prompt_text=prompt,
        intent_modality="typed",
        transcript_reviewed=True,
        student_ms=0,
        system_ms=0,
        inserted_spans=(Span(prompt.index("for a seven"), len(prompt)),),
    )
    scores = MeasureLayer(engine).run(MeasureInput(record=record)).scores
    seen = {}

    class Spy(DeterministicEngine):
        def compose(self, request):
            seen["request"] = request
            return super().compose(request)

    RespondLayer(Spy()).run(
        RespondInput(record=record, target=Category.UNDER_SPECIFICATION, scores=scores),
        protected_judgment="",
    )
    request = seen["request"]
    assert "audience_awareness" in request.missing_from_prompt
    assert "seven year old" not in request.prompt_text


def test_an_all_inserted_prompt_is_not_sent_as_hers(session):
    from promptcoach_ref.framework.contracts import Span

    prompt = "act as a scientist and make a list for a 5th grader"
    r = session.submit(
        stated_intent="I picked some chips",
        prompt_text=prompt,
        inserted_spans=(Span(0, len(prompt)),),
    )
    assert r.stopped_at.value == "elicit"
    assert "own words" in (r.clarification or "")


def test_generator_and_judge_differ_in_the_live_configuration(monkeypatch):
    """Component 23. With a key present, the engine that answers her prompt is
    built from its own setting and is not the engine that scores it. No network
    call is made: building an engine does not contact the provider."""
    from promptcoach_ref import api
    from promptcoach_ref.engines import gemini
    from promptcoach_ref.policy import generator as generator_policy

    monkeypatch.setattr(gemini, "load_env", lambda *a, **k: None)
    for var in (
        "PROMPTCOACH_OFFLINE",
        "PROMPTCOACH_SCORER",
        "PROMPTCOACH_GENERATOR",
        "PROMPTCOACH_CROSS_MODEL",
        "OPENROUTER_API_KEY",
    ):
        monkeypatch.delenv(var, raising=False)

    monkeypatch.setenv("GEMINI_API_KEY", "test-key-not-real")
    judge, comparator, gen = api._engines()
    assert gen is not None and comparator is None
    assert judge.name != gen.name
    assert judge.model == gemini.SCORER
    assert gen.model == generator_policy.DEFAULTS["gemini"]
    assert generator_policy.independent((judge.name,), gen.name)

    live = Session(
        session_id="live-config",
        consent=Consent(
            platform_use=True, research_participation=False, audio_retention=False
        ),
        engine=judge,
        generator=gen,
    )
    assert live._measure.generator_model == gen.name
    assert live._measure.engine.name != live._measure.generator_model

    monkeypatch.delenv("GEMINI_API_KEY")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key-not-real")
    judge, comparator, gen = api._engines()
    assert judge.slug != gen.slug
    assert generator_policy.independent((judge.name,), gen.name)


def test_independence_is_flagged_when_the_generator_is_a_judge():
    from promptcoach_ref.policy import generator as generator_policy

    assert not generator_policy.independent(
        ("gemini:gemini-3.8-flash",), "openrouter:google/gemini-3.8-flash"
    )
    assert generator_policy.independent(("deterministic-1.0.0",), "scripted-responder")


def _withdrawn_scan_roots():
    root = pathlib.Path(__file__).resolve().parent.parent
    yield from (root / "promptcoach_ref").rglob("*.py")
    for pattern in ("*.ts", "*.tsx"):
        yield from (root / "web" / "src").rglob(pattern)


def test_withdrawn_figures_appear_nowhere_in_the_package_source():
    """NUMBERS.md section 10: withdrawn figures are never printed. They are
    declared once, in classroom.WITHDRAWN, so this test knows what to look for;
    every other line of the package and the frontend must be free of them."""
    from promptcoach_ref.framework import classroom

    declaration = pathlib.Path(classroom.__file__).read_text(encoding="utf-8")
    start = declaration.index("WITHDRAWN: tuple[str, ...] = (")
    end = declaration.index(")", start) + 1
    without_declaration = declaration[:start] + declaration[end:]

    scanned = 0
    for path in _withdrawn_scan_roots():
        scanned += 1
        text = path.read_text(encoding="utf-8")
        if path.name == "classroom.py" and path.parent.name == "framework":
            text = without_declaration
        for figure in classroom.WITHDRAWN:
            assert figure not in text, f"withdrawn figure {figure!r} in {path.name}"
    assert scanned > 30


def test_no_student_names_in_the_classroom_module():
    """Aggregates only. Promptemon pairs were linked by name in the re-analysis;
    no name, and no per-student row, reaches this package."""
    from promptcoach_ref.framework import classroom

    for a in classroom.AGGREGATES.values():
        values = a.value.values() if isinstance(a.value, dict) else [a.value]
        assert all(isinstance(v, (int, float)) for v in values), a.id
    for p in classroom.ITEM_PAIRS.values():
        for side in (p.pre, p.post):
            assert all(isinstance(v, (int, float)) for v in side.values()), p.id


def _live_env(monkeypatch, provider: str, cross: bool, generator: str | None = None):
    from promptcoach_ref.engines import gemini

    monkeypatch.setattr(gemini, "load_env", lambda *a, **k: None)
    for var in (
        "PROMPTCOACH_OFFLINE",
        "PROMPTCOACH_SCORER",
        "PROMPTCOACH_GENERATOR",
        "PROMPTCOACH_CROSS_MODEL",
        "GEMINI_API_KEY",
        "OPENROUTER_API_KEY",
    ):
        monkeypatch.delenv(var, raising=False)
    key = "GEMINI_API_KEY" if provider == "gemini" else "OPENROUTER_API_KEY"
    monkeypatch.setenv(key, "test-key-not-real")
    if cross:
        monkeypatch.setenv("PROMPTCOACH_CROSS_MODEL", "1")
    if generator:
        monkeypatch.setenv("PROMPTCOACH_GENERATOR", generator)


@pytest.mark.parametrize("provider", ["gemini", "openrouter"])
@pytest.mark.parametrize("cross", [False, True])
def test_every_shipped_default_config_has_judge_not_generator(monkeypatch, provider, cross):
    """Judge independence: in every shipped live configuration - each provider,
    with and without the cross-model comparator - the generator is neither the
    scorer nor the comparator. Building engines makes no network call."""
    from promptcoach_ref import api
    from promptcoach_ref.policy import generator as generator_policy

    _live_env(monkeypatch, provider, cross)
    judge, comparator, gen = api._engines()
    assert gen is not None
    assert (comparator is not None) is cross
    judges = (judge.name,) + ((comparator.name,) if comparator else ())
    assert generator_policy.independent(judges, gen.name), (judges, gen.name)
    for j in judges:
        assert generator_policy._model_id(j) != generator_policy._model_id(gen.name)


def test_the_shipped_judge_table_matches_the_engines():
    """SHIPPED_JUDGES is what the independence test trusts; it must be what the
    engines actually build."""
    from promptcoach_ref.engines import gemini, openrouter
    from promptcoach_ref.policy import generator as generator_policy

    assert generator_policy.SHIPPED_JUDGES["gemini"] == (gemini.SCORER, gemini.COMPARATOR)
    assert generator_policy.SHIPPED_JUDGES["openrouter"] == (
        openrouter.MODELS["primary"],
        openrouter.MODELS["comparator"],
    )
    for provider, judges in generator_policy.SHIPPED_JUDGES.items():
        assert generator_policy.DEFAULTS[provider] not in judges


@pytest.mark.parametrize(
    "provider,cross,collision",
    [
        ("gemini", False, "gemini-3.1-flash-lite"),
        ("gemini", True, "gemini-3.8-flash"),
        ("openrouter", False, "anthropic/claude-opus-5"),
        ("openrouter", True, "google/gemini-3.8-flash"),
    ],
)
def test_a_live_config_whose_generator_is_a_judge_refuses_to_start(
    monkeypatch, provider, cross, collision
):
    from fastapi.testclient import TestClient

    from promptcoach_ref import api
    from promptcoach_ref.policy.generator import NonIndependentConfiguration

    _live_env(monkeypatch, provider, cross, generator=collision)
    with pytest.raises(NonIndependentConfiguration) as exc:
        api._engines()
    assert "Refusing to start" in str(exc.value)
    assert "PROMPTCOACH_GENERATOR" in str(exc.value)
    # And the application itself will not start.
    with pytest.raises(NonIndependentConfiguration):
        with TestClient(api.app):
            pass


def test_the_offline_path_is_unaffected_by_the_refusal(monkeypatch):
    from promptcoach_ref import api

    monkeypatch.setenv("PROMPTCOACH_OFFLINE", "1")
    monkeypatch.setenv("PROMPTCOACH_GENERATOR", "deterministic-1.0.0")
    judge, comparator, gen = api._engines()
    assert judge.name == "deterministic-1.0.0" and gen is None
