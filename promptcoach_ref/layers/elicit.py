"""Layer 1 - Elicit.

    "The layer captures two things per attempt: the artifact the student submits,
    and a concurrent account of what she was trying to do."
    - sec:elicit

    "Requirement passed downstream: a paired record of intent and artifact, plus
    timing."
    - sec:elicit

Two rules do the work here.

The first is that the prompt is stored verbatim. A layer that quietly repaired
the artifact would destroy the very comparison Layer 3 depends on, and would also
be doing the student's work.

The second is that declining the microphone degrades the record and never blocks
the loop. sec:elicit - the typed fallback "preserves the paired record at lower
fidelity"; sec:method - "a student who declines the microphone must still be able to
use the system on a typed statement of intent, which degrades the diagnosis
rather than blocking it." The thesis adds "None of that has been implemented."
It is implemented here.

Two typed fields, never one. Without a microphone she types her **plan** before
she writes (`stated_intent`, modality "typed") on every attempt, the first
included, so Layer 3 has a plan to compare with the prompt on attempt 1. On a
revision she also types a **reason** (`revision_reason`) after she has seen the
output. The reason does not replace the plan, and a revision with a reason but
no plan is asked for the plan.

Three things the redesigned framework adds to this layer:

- **A predicted rating.** Before she sees the output she rates how good she
  thinks the prompt is, 1 to 4 (the attempt cycle's Predict step). Optional:
  skipping it never blocks the loop. Calibrate subtracts the measured score.
- **A stated reason on every same-task revision.** Without one the revision is
  not scored; this layer asks for the reason instead (component 21).
- **Inserted spans.** Text the interface put into the prompt (a chip, a
  template) is recorded as inserted, so downstream layers never treat it as
  hers (component 24). The prompt itself is still stored verbatim.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass

from ..framework import revision as revision_rule
from ..framework.contracts import (
    PREDICTED_MAX,
    PREDICTED_MIN,
    ElicitInput,
    ElicitOutput,
    PairedRecord,
)
from ..policy import revision as revision_policy

MIN_PROMPT_CHARACTERS = 8

TRUNCATION = re.compile(r"(\b(and|or|the|a|an|to|of|for|with|about)\s*)$", re.I)


@dataclass(frozen=True)
class Consent:
    """Three decisions, taken separately.

    sec:commitments - "Research consent is distinct from platform consent,
    so a student can use the tool without becoming a subject. Layer 1 extends this
    to the microphone."

    Bundling any two of these into one checkbox would violate the commitment, so
    they are three fields and there is no constructor that sets them together.
    """

    platform_use: bool
    research_participation: bool
    audio_retention: bool

    @property
    def instruction_permitted(self) -> bool:
        """Only platform use gates instruction. Withdrawing research consent or
        refusing the microphone must not close the door."""
        return self.platform_use


class ElicitLayer:
    READS: tuple[str, ...] = ()

    def __init__(
        self,
        consent: Consent,
        *,
        require_reason: bool | None = None,
        min_reason_chars: int | None = None,
    ) -> None:
        self._consent = consent
        #: The reasoned-revision rule (framework/revision.py). Switchable only so
        #: F7's control arm can run; on by default.
        self.require_reason = (
            revision_policy.REQUIRED.value if require_reason is None else require_reason
        )
        self.min_reason_chars = (
            revision_policy.min_chars() if min_reason_chars is None else min_reason_chars
        )

    def run(self, data: ElicitInput) -> ElicitOutput:
        if not self._consent.instruction_permitted:
            return ElicitOutput(
                record=None,
                clarification_required=(
                    "Platform use has not been agreed, so nothing can be captured."
                ),
            )

        modality = data.intent_modality
        transcript_reviewed = data.transcript_reviewed

        # Declining audio retention downgrades the modality. It does not stop the
        # cycle and it does not silently keep the audio.
        if modality == "speech" and not self._consent.audio_retention:
            modality = "typed"
            transcript_reviewed = True

        problem = self._capture_problem(data, modality, transcript_reviewed)
        if problem:
            return ElicitOutput(record=None, clarification_required=problem)

        record = PairedRecord(
            # Unique per attempt. A hash of the text collided when she sent the
            # same prompt twice, and the append-only store rightly refused the
            # second record.
            attempt_id=data.session_id + ":" + uuid.uuid4().hex[:12],
            task_id=data.task_id,
            stated_intent=data.stated_intent,
            # Verbatim. Never repaired, never normalised, never completed.
            prompt_text=data.prompt_text,
            intent_modality=modality,
            transcript_reviewed=transcript_reviewed,
            student_ms=data.student_ms,
            system_ms=0,
            parent_attempt_id=data.parent_attempt_id,
            triggering_intervention_id=data.triggering_intervention_id,
            predicted_rating=data.predicted_rating,
            revision_reason=(data.revision_reason or "").strip() or None,
            inserted_spans=tuple(data.inserted_spans),
        )
        return ElicitOutput(record=record)

    # -- capture checks --------------------------------------------------

    def _capture_problem(
        self, data: ElicitInput, modality: str, transcript_reviewed: bool
    ) -> str | None:
        prompt = data.prompt_text.strip()
        intent = data.stated_intent.strip()

        if not prompt:
            return "There is no prompt yet. Write what you want to ask."
        if not intent:
            return (
                "Say or type what you are trying to do first. Without it there is "
                "nothing to compare your prompt against."
            )
        if len(prompt) < MIN_PROMPT_CHARACTERS:
            return (
                "That prompt is too short to read. Write the whole thing before "
                "sending it."
            )
        if TRUNCATION.search(prompt):
            return "That looks like it got cut off. Finish the sentence and resend."
        if data.predicted_rating is not None and not (
            PREDICTED_MIN <= data.predicted_rating <= PREDICTED_MAX
        ):
            return (
                f"Pick how good you think your prompt is from {PREDICTED_MIN} to "
                f"{PREDICTED_MAX}, or leave it blank."
            )
        for span in data.inserted_spans:
            if span.end > len(data.prompt_text):
                return "Part of the prompt marked as inserted is missing. Send it again."
        if data.inserted_spans and _composed(data).strip() == "":
            return (
                "Everything in that prompt was put there by the tool. Add "
                "something in your own words before it is sent."
            )
        # The reasoned-revision rule. A revision of the same task is not scored
        # until she says why she changed it; the rule is the framework's, the
        # length is policy's.
        if not revision_rule.revision_may_be_scored(
            is_revision=data.parent_attempt_id is not None,
            reason=data.revision_reason,
            required=self.require_reason,
            min_chars=self.min_reason_chars,
        ):
            return revision_rule.ASK_FOR_REASON
        if modality == "speech" and not transcript_reviewed:
            return (
                "Check the transcript of what you said before it is scored. "
                "Speech recognition makes mistakes, and a wrong transcript would "
                "produce a wrong diagnosis."
            )
        return None


def _composed(data: ElicitInput) -> str:
    from ..framework.contracts import composed_text

    return composed_text(data.prompt_text, tuple(data.inserted_spans))


#: sec:elicit. Stated here because the thesis says the layer's
#: classroom feasibility is the least established part of the framework, and a
#: reader of this module should see that where the code is.
UNTESTED_ASSUMPTIONS = (
    "Three assumptions are doing work in this layer and none has been tested with "
    "students: that thirty students can plan aloud in one room, that transcription "
    "is accurate enough on middle school speech - which matters most for the "
    "accented and second language speakers - and that a twelve year old will "
    "narrate her plan candidly with peers within earshot."
)

#: sec:falsify. The condition that would make the framework
#: unbuildable rather than wrong.
UNBUILDABILITY_CONDITION = (
    "If speech capture proves unworkable in a classroom, Layer 1 cannot supply the "
    "paired record, four of the seven categories become undetectable, and the "
    "framework reduces to a scoring and hinting system without a diagnose layer. "
    "The typed intent fallback is what stands between that outcome and total loss."
)
