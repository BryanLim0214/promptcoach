"""The session: one task cycle, composed.

sec:design gives the sequence in a single paragraph, and it is the closest thing
to a state machine the manuscript contains:

    "A student receives a task at her current difficulty band. She speaks what
    she is trying to do, then types a prompt. Layer 1 records both with timing.
    Layer 2 returns six dimension scores with per dimension confidence, marking
    evaluative dimensions lower. Layer 3 compares intent to artifact, consults
    session history, and returns a ranked failure list. Layer 4 selects the top
    ranked failure, checks the escalation state, and issues help at the
    appropriate level, drawing the template floor matched to that failure and
    generating within it. The student revises. Layer 5 records whether the
    dimension paired with that failure improved, updates the difficulty state
    against both rate and streak conditions, updates the sentinel, and surfaces
    both to the student."

The redesigned framework (sec:framework) adds the student's own attempt cycle
around that loop: Plan, Write, Predict (she rates the prompt 1 to 4), See (the
prompt runs and she reads what it produced, before any coaching), Revise (the
same task, with a short stated reason). The session carries the two new pieces
of state that cycle needs: how many reasoned revisions each task has, and the
calibration gap on every scored attempt.

**Help climbs across revisions of one task.** A help cycle is the help given
on one task for one top-ranked category (policy `escalation.cycle`). A revision
is first measured by Layer 5 against its parent. If the same category is still
ranked first, the paired dimension did not improve and level 4 has not been
issued, the cycle stays open and Layer 4 answers the revision, one rung higher
when the escalation rule says so. Otherwise the cycle closes and the revision
ends at Layer 5. The escalation count is consecutive attempts, first attempts
and revisions alike, with the same top-ranked category
(`escalation.consecutive_unresolved`). The two rules that limit it still hold:
for diagnoses paired with an evaluative dimension, help moves up only when she
asks or her text is unchanged (`escalation.evaluative_pairing`); and the
revision hold (component 21) is released by her first reasoned revision, or
after four attempts, whether or not the help cycle is still open. An
unreasoned revision stops at Layer 1, so it neither raises nor resets help.

**Two engines, not one.** `engine` judges (Layers 2 and 3) and composes the
coaching (Layer 4). `generator` answers her prompt. They are configured
separately so the model that writes the answer she reads is not the model that
scores her prompt (component 23). With no generator configured, the offline
scripted responder answers.

**The thesis names no states.** There is no `task-selected`, no
`ready-for-measurement`, no enumeration anywhere in the manuscript; the entire
state vocabulary is the two prose phrases "the escalation state" and "the
difficulty state". Every name in `Stage` below is ours, and `Stage.THESIS_NAMED`
is False to say so.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .engines.base import Engine
from .framework import ladder
from .framework import revision as revision_rule
from .framework.taxonomy import BY_ID as TAXONOMY, Category
from .framework.contracts import (
    CalibrateInput,
    CalibrateOutput,
    DiagnoseInput,
    DiagnoseOutput,
    ElicitInput,
    ElicitOutput,
    MeasureInput,
    MeasureOutput,
    PairedRecord,
    RespondInput,
    RespondOutput,
    Span,
    calibration_gap,
)
from .layers import (
    CalibrateLayer,
    Consent,
    DiagnoseLayer,
    ElicitLayer,
    MeasureLayer,
    RespondLayer,
)
from .layers.measure import ROUTING_SCORE_AVAILABLE
from .policy import calibration as calibration_policy
from .policy import revision as revision_policy
from .policy import taskbank
from .responder import Answer, Responder, build as build_responder, name_of
from .store import Store
from .trace import Trace


class Stage(str, Enum):
    """Where a cycle stopped. Ours, not the thesis's."""

    THESIS_NAMED = "false"

    ELICIT = "elicit"
    MEASURE = "measure"
    DIAGNOSE = "diagnose"
    RESPOND = "respond"
    CALIBRATE = "calibrate"


@dataclass
class CycleResult:
    stopped_at: Stage
    elicit: ElicitOutput
    measure: MeasureOutput | None = None
    diagnose: DiagnoseOutput | None = None
    respond: RespondOutput | None = None
    calibrate: CalibrateOutput | None = None
    #: What her prompt actually produced. The reason she is here.
    answer: "Answer | None" = None
    #: Predicted minus measured for this attempt, recorded whether or not she
    #: is shown it. Student-facing only.
    calibration_gap: float | None = None
    #: Whether the gap may be shown to her (policy, F8). The gap is recorded
    #: either way.
    gap_visible: bool = True
    #: True while this task still needs one reasoned revision before a new task.
    revision_pending: bool = False
    #: What happened to the help cycle on this attempt, in one sentence
    #: (opened, continued, or closed and why). None when no cycle was touched.
    help_cycle: str | None = None
    trace: Trace = field(default_factory=Trace)

    @property
    def clarification(self) -> str | None:
        return self.elicit.clarification_required


@dataclass
class Session:
    """One student, one run of tasks."""

    session_id: str
    consent: Consent
    #: The judge: scores (Layer 2), diagnoses (Layer 3), composes coaching (4).
    engine: Engine
    comparator: Engine | None = None
    #: The generator: answers her prompt. Never the judge.
    generator: Engine | None = None
    selection_mode: str | None = None
    #: The reasoned-revision requirement. None means the policy default; False is
    #: F7's control arm.
    require_reason: bool | None = None
    #: Whether she is shown her calibration gap. None means the policy default;
    #: False is F8's control arm.
    show_gap: bool | None = None

    band: int = taskbank.ENTRY_BAND.value
    task_id: str = taskbank.WORKED_EXAMPLE_ID
    history: list[PairedRecord] = field(default_factory=list)
    outcomes: tuple[bool, ...] = ()
    levels_issued: tuple[int, ...] = ()
    store: Store = field(default_factory=Store)
    #: attempt id -> what that prompt produced, so a revision can be shown
    #: beside the answer it replaced.
    answers: dict[str, Answer] = field(default_factory=dict)
    #: task id -> revisions of that task that carried a stated reason.
    reasoned_revisions: dict[str, int] = field(default_factory=dict)
    #: task id -> submissions on that task, scored or not.
    attempts_on_task: dict[str, int] = field(default_factory=dict)
    #: Tasks left through the policy exit without a reasoned revision. Kept so
    #: an F7 analysis can count them.
    gate_exits: list[str] = field(default_factory=list)
    #: Help cycles closed after level 4 without the paired dimension improving:
    #: (task id, category). policy escalation.after_terminal records them
    #: instead of repeating level 4.
    unresolved: list[tuple[str, str]] = field(default_factory=list)
    #: The category the open help cycle is about, or None when no cycle is open.
    cycle_category: Category | None = None
    #: Her composed text on the last attempt that received help in the current
    #: help cycle. Read only while `levels_issued` is non-empty, so it needs no
    #: reset of its own.
    _cycle_last_text: str | None = field(default=None, init=False, repr=False)
    #: Consecutive scored attempts on this task with the same top-ranked
    #: category, and that category. Unscored attempts neither extend nor break
    #: the run; moving task resets it.
    _same_top_run: int = field(default=0, init=False, repr=False)
    _last_top: Category | None = field(default=None, init=False, repr=False)
    #: attempt id -> id of the help response issued on that attempt.
    _help_on: dict[str, str] = field(default_factory=dict, init=False, repr=False)
    #: task id -> the last attempt recorded on that task.
    _last_attempt_on_task: dict[str, str] = field(
        default_factory=dict, init=False, repr=False
    )

    responder: Responder | None = None

    def __post_init__(self) -> None:
        if self.require_reason is None:
            self.require_reason = bool(revision_policy.REQUIRED.value)
        if self.show_gap is None:
            self.show_gap = bool(calibration_policy.SHOW_GAP_TO_STUDENT.value)
        if self.responder is None:
            self.responder = build_responder(self.generator)
        self._elicit = ElicitLayer(self.consent, require_reason=self.require_reason)
        self._measure = MeasureLayer(
            self.engine, self.comparator, generator_model=name_of(self.responder)
        )
        self._diagnose = DiagnoseLayer(self.engine)
        self._respond = RespondLayer(self.engine, self.selection_mode)
        # Layer 5 calls the judge's own over-reliance detector: the model-based
        # one live, the author-tested keyword stand-in offline.
        self._calibrate = CalibrateLayer(self.engine)

    # -- the reasoned-revision hold ---------------------------------------

    @property
    def revision_pending(self) -> bool:
        return revision_rule.new_task_held(
            reasoned_revisions_on_task=self.reasoned_revisions.get(self.task_id, 0),
            required=bool(self.require_reason),
            exit_applies=revision_policy.exit_applies(
                self.attempts_on_task.get(self.task_id, 0)
            ),
        )

    def move_to(self, task_id: str) -> tuple[bool, str]:
        """Move to another task, unless the current one is held.

        Returns (moved, reason). A held task stays put and the reason is the
        sentence to show her.
        """
        if task_id == self.task_id:
            return True, "already on this task"
        if self.revision_pending:
            return False, revision_rule.HOLD_MESSAGE
        if (
            self.require_reason
            and self.reasoned_revisions.get(self.task_id, 0) < 1
            and self.attempts_on_task.get(self.task_id, 0) > 0
        ):
            self.gate_exits.append(self.task_id)
        self.task_id = task_id
        # sec:respond - the ladder is per task cycle; a new task starts at the
        # bottom, and the same-top count starts again.
        self._close_cycle()
        self._same_top_run = 0
        self._last_top = None
        return True, "moved"

    # -- the cycle -------------------------------------------------------

    def submit(
        self,
        *,
        stated_intent: str,
        prompt_text: str,
        intent_modality: str = "typed",
        transcript_reviewed: bool = True,
        student_ms: int = 0,
        parent_attempt_id: str | None = None,
        asked_for_help: bool = False,
        predicted_rating: int | None = None,
        revision_reason: str | None = None,
        inserted_spans: tuple[Span, ...] = (),
    ) -> CycleResult:
        trace = Trace()
        task = taskbank.BY_ID[self.task_id]
        self.attempts_on_task[self.task_id] = (
            self.attempts_on_task.get(self.task_id, 0) + 1
        )

        # A revision is a revision of *this* task. A parent from another task
        # makes this a fresh attempt, not a revision.
        if parent_attempt_id is not None:
            parent_record = self.store.get(parent_attempt_id)
            if parent_record is None or parent_record.task_id != self.task_id:
                parent_attempt_id = None

        # The help this attempt follows, if any: the response issued on the
        # attempt it revises, or on the last attempt on this task. Layer 3 needs
        # it - blind acceptance is "took the previous output as final after help
        # was offered", which no rule can see unless the help is on the record.
        preceding = parent_attempt_id or self._last_attempt_on_task.get(self.task_id)
        triggering = self._help_on.get(preceding) if preceding else None

        # --- Layer 1 ----------------------------------------------------
        elicited = self._elicit.run(
            ElicitInput(
                session_id=self.session_id,
                task_id=self.task_id,
                stated_intent=stated_intent,
                prompt_text=prompt_text,
                intent_modality=intent_modality,
                transcript_reviewed=transcript_reviewed,
                student_ms=student_ms,
                parent_attempt_id=parent_attempt_id,
                triggering_intervention_id=triggering,
                predicted_rating=predicted_rating,
                revision_reason=revision_reason,
                inserted_spans=tuple(inserted_spans),
            )
        )
        trace.record("elicit", elicited)
        if elicited.record is None:
            return CycleResult(
                stopped_at=Stage.ELICIT,
                elicit=elicited,
                gap_visible=bool(self.show_gap),
                revision_pending=self.revision_pending,
                trace=trace,
            )

        record = elicited.record
        self.store.append(record.attempt_id, record)
        self._last_attempt_on_task[self.task_id] = record.attempt_id
        if record.is_revision and revision_rule.reason_is_stated(
            record.revision_reason, revision_policy.min_chars()
        ):
            self.reasoned_revisions[self.task_id] = (
                self.reasoned_revisions.get(self.task_id, 0) + 1
            )

        # --- Layer 2 ----------------------------------------------------
        measured = self._measure.run(MeasureInput(record=record))
        trace.record("measure", measured)
        # Kept against the attempt id so Layer 5 can compare a child's scores
        # with its parent's. Without this the deltas are all zero and F2 becomes
        # unrunnable - the comparison would have nothing to compare.
        self.store.remember_scores(record.attempt_id, measured.scores)
        gap = calibration_gap(record.predicted_rating, measured.overall)

        # See before coaching (component 20). Her prompt runs whatever the
        # scores turned out to be. A weak prompt earns the answer a weak prompt
        # earns; that is the lesson, and withholding it until she improves
        # would invert the whole design.
        assert self.responder is not None
        answer = self.responder.answer(record.prompt_text, measured.scores)
        self.answers[record.attempt_id] = answer

        common = dict(
            elicit=elicited,
            measure=measured,
            answer=answer,
            calibration_gap=gap,
            gap_visible=bool(self.show_gap),
            trace=trace,
        )

        if measured.routing != ROUTING_SCORE_AVAILABLE:
            self.history.append(record)
            return CycleResult(
                stopped_at=Stage.MEASURE,
                revision_pending=self.revision_pending,
                **common,
            )

        # --- Layer 3 ----------------------------------------------------
        diagnosed = self._diagnose.run(
            DiagnoseInput(
                record=record,
                scores=measured.scores,
                session_history=tuple(self.history),
            )
        )
        trace.record("diagnose", diagnosed)

        parent = self._parent_of(record)
        self.history.append(record)
        target = diagnosed.target

        # The same-top count (escalation.consecutive_unresolved): consecutive
        # scored attempts on this task, first attempts and revisions alike,
        # whose top-ranked category is the same. This attempt counts.
        if target is None:
            self._same_top_run = 0
        elif target is self._last_top:
            self._same_top_run += 1
        else:
            self._same_top_run = 1
        self._last_top = target

        cycle_open = bool(self.levels_issued)
        terminal_issued = cycle_open and ladder.is_terminal(max(self.levels_issued))
        same_category = cycle_open and target is not None and target is self.cycle_category
        calibrated: CalibrateOutput | None = None

        # --- Layer 5 on a revision, before any further help --------------
        # Every revision is measured against its parent: Layer 5 records whether
        # the dimension paired with the category being helped improved. Whether
        # the help cycle stays open is decided from that (policy
        # escalation.cycle), so Calibrate runs first.
        if parent is not None:
            calibrated = self._run_calibrate(record, parent, diagnosed, measured)
            trace.record("calibrate", calibrated)
            improved = self._cycle_improved(parent, record, measured)
            if not cycle_open:
                note = None
            elif terminal_issued:
                if not improved:
                    self.unresolved.append(
                        (self.task_id, self.cycle_category.value)  # type: ignore[union-attr]
                    )
                note = (
                    "closed: level 4 had been issued, and level 4 is not repeated"
                    + ("" if improved else "; recorded as unresolved")
                )
            elif not same_category:
                note = (
                    "closed: nothing was diagnosed on the revision"
                    if target is None
                    else "closed: a different category is ranked first now"
                )
            elif improved and not asked_for_help:
                note = "closed: the paired dimension improved"
            else:
                note = None  # stays open; Layer 4 answers below

            stays_open = cycle_open and note is None
            if not stays_open:
                self._close_cycle()
                # A revision ends here unless she asked for more help, which
                # opens a new cycle at the first rung.
                if target is None or not asked_for_help:
                    return CycleResult(
                        stopped_at=Stage.CALIBRATE,
                        diagnose=diagnosed,
                        calibrate=calibrated,
                        revision_pending=calibrated.revision_pending,
                        help_cycle=note,
                        **common,
                    )
                note = (note + "; " if note else "") + (
                    "she asked for more help, so a new cycle opens"
                )
            else:
                note = (
                    "open: she asked for more help"
                    if asked_for_help and improved
                    else "open: the same category is ranked first and the paired "
                    "dimension did not improve"
                )

        # --- a first attempt -------------------------------------------
        else:
            if target is None:
                # Nothing to respond to closes the cycle; Layer 5 runs as before.
                was_open = cycle_open
                calibrated = self._run_calibrate(record, None, diagnosed, measured)
                trace.record("calibrate", calibrated)
                self._close_cycle()
                return CycleResult(
                    stopped_at=Stage.CALIBRATE,
                    diagnose=diagnosed,
                    calibrate=calibrated,
                    revision_pending=calibrated.revision_pending,
                    help_cycle=(
                        "closed: nothing was diagnosed" if was_open else None
                    ),
                    **common,
                )
            if cycle_open and terminal_issued and same_category:
                self.unresolved.append((self.task_id, target.value))
                self._close_cycle()
                note = (
                    "closed after level 4 and recorded as unresolved; a new cycle "
                    "opens at the first rung"
                )
            elif cycle_open and not same_category:
                self._close_cycle()
                note = "a different category is ranked first; a new cycle opens"
            elif cycle_open:
                note = "open: the same category is ranked first"
            else:
                note = "opened"

        # --- Layer 4 ----------------------------------------------------
        assert target is not None
        responded = self._respond.run(
            RespondInput(
                record=record,
                target=target,
                scores=measured.scores,
                levels_already_issued=self.levels_issued,
                consecutive_same_top=self._same_top_run,
                escalation_signals=("asked_for_help",) if asked_for_help else (),
                previous_composed_text=(
                    self._cycle_last_text if self.levels_issued else None
                ),
            ),
            protected_judgment=task.protected_judgment,
        )
        trace.record("respond", responded)
        self.levels_issued = self.levels_issued + (responded.level,)
        self.cycle_category = target
        self._cycle_last_text = record.composed_text
        self._help_on[record.attempt_id] = (
            f"{record.attempt_id}:help:L{responded.level}"
        )

        return CycleResult(
            stopped_at=Stage.RESPOND,
            diagnose=diagnosed,
            respond=responded,
            calibrate=calibrated,
            revision_pending=(
                calibrated.revision_pending
                if calibrated is not None
                else self.revision_pending
            ),
            help_cycle=note,
            **common,
        )

    # -- helpers ---------------------------------------------------------

    def _cycle_improved(
        self, parent: PairedRecord, record: PairedRecord, measured: MeasureOutput
    ) -> bool:
        """Did a dimension paired with the open cycle's category rise from the
        parent to this revision? The same leniency as Layer 5's paired delta: a
        broad pairing counts if any of its dimensions rose."""
        if self.cycle_category is None:
            return False
        before = self.store.scores_for(parent.attempt_id) or {}
        after = measured.scores
        for dim_id in TAXONOMY[self.cycle_category].paired.dimension_ids:
            b, a = before.get(dim_id), after.get(dim_id)
            if b is None or a is None or b.value is None or a.value is None:
                continue
            if a.value > b.value:
                return True
        return False

    def _close_cycle(self) -> None:
        """End the help cycle: the ladder starts again at the first rung."""
        self.levels_issued = ()
        self.cycle_category = None

    def _parent_of(self, record: PairedRecord) -> PairedRecord | None:
        if record.parent_attempt_id is None:
            return None
        for h in self.history:
            if h.attempt_id == record.parent_attempt_id:
                return h
        return None

    def _run_calibrate(
        self,
        record: PairedRecord,
        parent: PairedRecord | None,
        diagnosed: DiagnoseOutput,
        measured: MeasureOutput,
    ) -> CalibrateOutput:
        # Layer 5's own report is about this attempt's diagnosis, as before.
        # Whether the help cycle's category improved is checked separately
        # (`_cycle_improved`), because that category may differ.
        target = diagnosed.target
        if target is None:
            target = Category.UNDER_SPECIFICATION

        parent_scores = measured.scores
        child_scores: dict | None = None
        if parent is not None:
            child_scores = measured.scores
            parent_scores = self.store.scores_for(parent.attempt_id) or measured.scores

        out = self._calibrate.run(
            CalibrateInput(
                parent=parent or record,
                child=record if parent else None,
                target=target,
                level_issued=self.levels_issued[-1] if self.levels_issued else 0,
                parent_scores=parent_scores,
                child_scores=child_scores,
                band=self.band,
                recent_outcomes=self.outcomes,
                reasoned_revisions_on_task=self.reasoned_revisions.get(self.task_id, 0),
                revision_exit_applies=revision_policy.exit_applies(
                    self.attempts_on_task.get(self.task_id, 0)
                ),
                revision_required=bool(self.require_reason),
                prior_prompts=tuple(
                    h.composed_text
                    for h in self.history
                    if h.attempt_id != record.attempt_id
                ),
            )
        )

        self.band = out.band
        # One outcome each time Layer 5 runs (policy gating.streak_unit), decided
        # by policy gating.success. Calibrate already appended it to the window
        # it evaluated; the session keeps the same tuple. Whether the help cycle
        # closes is decided by the caller (policy escalation.cycle), not here.
        self.outcomes = self.outcomes + (out.attempt_succeeded,)
        # `out.next_task_id` is Calibrate's *recommendation*, not a move. The
        # session stays on the task she just finished until she says go, because
        # switching here re-labels the screen she is still reading: the header
        # would name the next task above a comparison of the previous one.
        return out

    def store_scores(self, attempt_id: str, scores: dict) -> None:
        self.store.remember_scores(attempt_id, scores)
