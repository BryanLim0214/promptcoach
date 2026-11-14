"""An engine with no network and no key.

This is not a mock. sec:respond requires a template floor that "is
served whenever the model call fails or its output violates the constraints", and
"the constraint lives in code, not in the model's instructions". The compose half
of this module *is* that floor - the specified safe path, which the live engine
falls back to.

The scoring and diagnosis halves are a rule engine, which lets the whole loop run
offline: hermetic tests, and a committee that can execute the artifact without an
API key.

Every rule here is a heuristic over surface features. That is a much weaker
instrument than the rubric Chapter 6 evaluated, and nothing about ICC 0.976
transfers to it.
"""

from __future__ import annotations

import re

from ..framework import ladder, rubric
from ..framework.taxonomy import Category
from .base import (
    ComposeRequest,
    DiagnosisRequest,
    DimensionSample,
    Engine,
    RawAssignment,
    ScoringRequest,
    ScoringSample,
)

# ---------------------------------------------------------------------------
# Surface signals
# ---------------------------------------------------------------------------

AUDIENCE = re.compile(
    r"\b(for (my|a|an|the)\s+\w+|audience|reader|classmate|teacher|parent|"
    r"kid|child|cousin|sister|brother|year[- ]old|grader|beginner|someone who)\b",
    re.I,
)
CONSTRAINT = re.compile(
    r"\b(no more than|at most|under \d+|within \d+|\d+\s*(word|sentence|paragraph|"
    r"bullet|line)s?|reading level|grade level|simple words|short|brief|"
    r"don'?t use|avoid|without|"
    # A ceiling stated in a child's own words is still a ceiling. The Chapter 11
    # spoken record carries "it can't be complicated", which tab:worked reads as
    # Constraint Setting.
    r"can'?t be|cannot be|not too|nothing too|keep it \w+|complicated|"
    r"easy enough|simple enough)\b",
    re.I,
)
FORMAT = re.compile(
    r"\b(bullet|list|table|paragraph|sentence|steps|outline|summary|essay|email|"
    r"script|format|in the form of|"
    # "maybe just a few sentences" is a length request without a numeral;
    # tab:worked reads it as Specificity.
    r"a few|a couple of|just a bit)\b",
    re.I,
)
PURPOSE = re.compile(
    r"\b(so that|because|so i can|to help|in order to|for (a|an|my) \w+ (assignment|"
    r"project|presentation|class))\b",
    re.I,
)
ITERATION = re.compile(
    r"\b(then i|after that|follow up|if it|come back|revise|first .* then|"
    r"i'?ll ask|next i)\b",
    re.I,
)
STANDARD = re.compile(
    r"\b(a good (one|answer|response) would|it should|make sure it|i'?m looking for|"
    r"i'?ll know it'?s good|the standard|check that|must include)\b",
    re.I,
)
DELEGATION = re.compile(
    r"\b(just make it (good|better|nice)|whatever you think|you decide|"
    r"make it the best|do it however|is this good|tell me if (it'?s|this is) good|"
    r"what should i think|decide for me)\b",
    re.I,
)
SOCIAL = re.compile(
    r"\b(please|thank you|thanks|sorry|hi|hello|hey|could you be so|"
    r"i really need|i'?m struggling|you'?re (so |really )?(good|smart|great))\b",
    re.I,
)
OPERATIONAL = re.compile(
    r"\b(write|explain|summar|list|compare|describe|outline|draft|rewrite|"
    r"give me|make me)\b",
    re.I,
)
MODEL_VOICE = re.compile(
    r"\b(delve|multifaceted|it'?s important to note|in conclusion|furthermore|"
    r"moreover|tapestry|underscore|fundamental force|governs)\b",
    re.I,
)


def _has(pattern: re.Pattern[str], text: str) -> bool:
    return bool(pattern.search(text))


def _span(pattern: re.Pattern[str], text: str) -> str | None:
    m = pattern.search(text)
    return m.group(0) if m else None


def _dimension_evidence(dimension_id: str, text: str) -> tuple[bool, str | None]:
    """Does the artifact show this dimension, and where?"""
    if dimension_id == rubric.CONTEXT_CLARITY.id:
        if _has(PURPOSE, text):
            return True, _span(PURPOSE, text)
        return False, None
    if dimension_id == rubric.SPECIFICITY.id:
        if _has(FORMAT, text):
            return True, _span(FORMAT, text)
        return False, None
    if dimension_id == rubric.AUDIENCE_AWARENESS.id:
        if _has(AUDIENCE, text):
            return True, _span(AUDIENCE, text)
        return False, None
    if dimension_id == rubric.CONSTRAINT_SETTING.id:
        if _has(CONSTRAINT, text):
            return True, _span(CONSTRAINT, text)
        return False, None
    if dimension_id == rubric.ITERATION_AWARENESS.id:
        if _has(ITERATION, text):
            return True, _span(ITERATION, text)
        return False, None
    if dimension_id == rubric.REFLECTION.id:
        if _has(STANDARD, text):
            return True, _span(STANDARD, text)
        return False, None
    return False, None


def dimensions_present(text: str) -> set[str]:
    return {d.id for d in rubric.DIMENSIONS if _dimension_evidence(d.id, text)[0]}


class DeterministicEngine:
    """Rules for scoring and diagnosis; the specified template floor for compose."""

    name = "deterministic-1.0.0"
    organisation = "none"

    # -- scoring ---------------------------------------------------------

    def sample_scores(
        self, request: ScoringRequest, temperature: float
    ) -> ScoringSample:
        text = request.prompt_text
        samples: list[DimensionSample] = []

        for dim in rubric.DIMENSIONS:
            present, span = _dimension_evidence(dim.id, text)
            value = rubric.RUBRIC_MIN

            if dim.id == rubric.CONTEXT_CLARITY.id:
                # A bare topic word scores 1; naming an operation lifts it to 2;
                # stating why lifts it further.
                if _has(OPERATIONAL, text):
                    value = 2
                if present:
                    value = 4
            elif present:
                value = 3
                # A second piece of evidence for the same dimension earns the top.
                if dim.id == rubric.CONSTRAINT_SETTING.id and len(
                    CONSTRAINT.findall(text)
                ) > 1:
                    value = 4
                if dim.id == rubric.SPECIFICITY.id and _has(CONSTRAINT, text):
                    value = 4

            samples.append(
                DimensionSample(dimension_id=dim.id, value=value, evidence_span=span)
            )

        return ScoringSample(
            judge=self.name,
            temperature=temperature,
            dimensions=tuple(samples),
            latency_ms=0,
        )

    # -- diagnosis -------------------------------------------------------

    def diagnose(self, request: DiagnosisRequest) -> list[RawAssignment]:
        out: list[RawAssignment] = []
        prompt = request.prompt_text
        intent = request.stated_intent

        in_prompt = dimensions_present(prompt)
        in_intent = dimensions_present(intent)
        dropped = sorted(in_intent - in_prompt)

        # 1. Intent drift - needs the paired record, and nothing else can see it.
        if dropped:
            names = ", ".join(rubric.BY_ID[d].name for d in dropped)
            confidence = min(0.95, 0.55 + 0.15 * len(dropped))
            out.append(
                RawAssignment(
                    category=Category.INTENT_DRIFT,
                    confidence=round(confidence, 2),
                    trigger=(
                        f"{names} present in what she said, absent from what she typed"
                    ),
                )
            )

        # 2. Under specification - the planning dimensions the prompt omits.
        missing_planning = [
            d.id for d in rubric.PLANNING_DIMENSIONS if d.id not in in_prompt
        ]
        if missing_planning:
            confidence = min(0.9, 0.4 + 0.12 * len(missing_planning))
            names = ", ".join(rubric.BY_ID[d].name for d in missing_planning)
            out.append(
                RawAssignment(
                    category=Category.UNDER_SPECIFICATION,
                    confidence=round(confidence, 2),
                    trigger=f"no evidence of {names} in the prompt",
                )
            )

        # 3. Delegated judgment - she asked it to decide what good means.
        if _has(DELEGATION, prompt):
            out.append(
                RawAssignment(
                    category=Category.DELEGATED_JUDGMENT,
                    confidence=0.85,
                    trigger=f"asked the model to judge: {_span(DELEGATION, prompt)!r}",
                )
            )

        # 4. Social framing - only when social language *substitutes* for an
        #    instruction. Politeness beside a complete request is just politeness.
        if _has(SOCIAL, prompt) and not _has(OPERATIONAL, prompt):
            out.append(
                RawAssignment(
                    category=Category.SOCIAL_FRAMING,
                    confidence=0.7,
                    trigger=(
                        f"social language {_span(SOCIAL, prompt)!r} with no "
                        "operational instruction"
                    ),
                )
            )

        # 5. Undiagnosed retry - history only.
        if request.history:
            previous = request.history[-1]
            if _normalise(previous) == _normalise(prompt):
                out.append(
                    RawAssignment(
                        category=Category.UNDIAGNOSED_RETRY,
                        confidence=0.9,
                        trigger="resubmitted the previous prompt unchanged",
                    )
                )

        # 6. Blind acceptance - history only.
        if (
            request.history_had_intervention
            and request.history
            and not _has(ITERATION, prompt)
            and _normalise(request.history[-1]) == _normalise(prompt)
        ):
            out.append(
                RawAssignment(
                    category=Category.BLIND_ACCEPTANCE,
                    confidence=0.6,
                    trigger="took the previous output as final after help was offered",
                )
            )

        # 7. Borrowed phrasing - history only.
        if _has(MODEL_VOICE, prompt):
            out.append(
                RawAssignment(
                    category=Category.BORROWED_PHRASING,
                    confidence=0.65,
                    trigger=f"phrasing reads as model output: {_span(MODEL_VOICE, prompt)!r}",
                )
            )

        return out

    # -- over-reliance: an UNBENCHMARKED OFFLINE STAND-IN ---------------

    #: What `sentinel` below is. Shown wherever its numbers are shown.
    SENTINEL_SOURCE = (
        "offline keyword rules: an author-tested stand-in for the model-based "
        "detector, used only when no model is configured"
    )

    def sentinel(
        self, stated_intent: str, prompt_text: str, history: tuple[str, ...]
    ) -> dict[str, float]:
        """An author-tested offline stand-in: four fixed text-matching rules, so
        the offline loop has values to show.

        **Not the detector the thesis reports.** The AUC figures (0.81 in Proem,
        0.882 pooled in the replication) belong to the model-based detector,
        `GeminiEngine.sentinel`, which `eval/benchmark.py` scores. These rules
        were benchmarked once, offline, on the 30 replication items by the same
        authors (eval/offline_sentinel.py: AUC 0.847). A live session
        calls the live engine's detector instead; these run only when the
        offline engine is the judge.

        The rules: 0.25 per dimension present in the plan and missing from the
        prompt (capped at 1); 0.8 if a delegation phrase matches; 0.9 if the
        prompt equals the previous prompt (whitespace at the ends ignored); 0.7
        if a "model voice" phrase matches.
        """
        dropped = dimensions_present(stated_intent) - dimensions_present(prompt_text)
        previous = history[-1] if history else None
        return {
            "transcript_prompt_disconnect": round(min(1.0, 0.25 * len(dropped)), 2),
            "excessive_deference": 0.8 if _has(DELEGATION, prompt_text) else 0.0,
            "mindless_retry": (
                0.9
                if previous is not None and previous.strip() == prompt_text.strip()
                else 0.0
            ),
            "copied_ai_content": 0.7 if _has(MODEL_VOICE, prompt_text) else 0.0,
        }

    # -- compose: the template floor ------------------------------------

    def compose(self, request: ComposeRequest) -> str | None:
        return template_floor(request)


def _normalise(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


# ---------------------------------------------------------------------------
# The template floor
# ---------------------------------------------------------------------------

#: How each dimension sounds when spoken to a twelve year old. The rubric's own
#: names ("Constraint Setting") are the instrument's vocabulary, not hers, and a
#: coaching question that used them would be teaching her the rubric instead of
#: pointing at her own words.
_IN_HER_WORDS: dict[str, str] = {
    rubric.AUDIENCE_AWARENESS.id: "who it was for",
    rubric.SPECIFICITY.id: "how long it should be",
    rubric.CONSTRAINT_SETTING.id: "how simple it had to be",
    rubric.CONTEXT_CLARITY.id: "why you wanted it",
    rubric.ITERATION_AWARENESS.id: "that you would ask again after",
    rubric.REFLECTION.id: "what would make it good",
}


def _list_in_words(dimension_ids: tuple[str, ...]) -> str:
    """"who it was for and how long it should be" - the thesis's own phrasing."""
    parts = [_IN_HER_WORDS[d] for d in dimension_ids if d in _IN_HER_WORDS]
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    if len(parts) == 2:
        return f"{parts[0]} and {parts[1]}"
    return ", ".join(parts[:-1]) + f", and {parts[-1]}"


def _question(request: ComposeRequest) -> str:
    """One question, naming what she actually did.

    The first version of this was a fixed sentence per category, and it showed:
    intent drift asked "you said something out loud that did not make it into
    what you typed", where the thesis's own response names the specific threads.
    A question that says "something" is a question she cannot act on.
    """
    category = request.category
    dropped = _list_in_words(request.dropped_from_intent)
    missing = _list_in_words(request.missing_from_prompt)

    if category is Category.INTENT_DRIFT and dropped:
        count = len(request.dropped_from_intent)
        # One sentence, then one question - the level 1 budget is two moves, and
        # sec:design's own model response is built the same way: the threads named, the
        # loss stated, in a single breath.
        tail = {1: "and it did not make it", 2: "and neither made it"}.get(
            count, "and none of it made it"
        )
        return (
            f"You said out loud {dropped} — {tail} into what you typed. "
            f"{'Would that' if count == 1 else 'Which of those would'} change the "
            "answer most?"
        )
    if category is Category.INTENT_DRIFT:
        return (
            "You knew more about what you wanted than your prompt says. What did "
            "you leave out?"
        )
    if category is Category.UNDER_SPECIFICATION and missing:
        one = len(request.missing_from_prompt) == 1
        return (
            f"Your prompt does not say {missing}. "
            f"{'Would that' if one else 'Which one of those would'} change the "
            "answer most?"
        )
    if category is Category.UNDER_SPECIFICATION:
        return "Which one missing piece would change the answer the most?"

    return {
        Category.SOCIAL_FRAMING: (
            "If you took out the polite parts, what instruction would be left?"
        ),
        Category.BLIND_ACCEPTANCE: (
            "If you could ask once more, what would you want changed about that "
            "answer?"
        ),
        Category.UNDIAGNOSED_RETRY: (
            "Before you send that again — what was actually wrong with the last "
            "answer?"
        ),
        Category.DELEGATED_JUDGMENT: (
            "You asked it to decide what good means. What would a good answer "
            "have to do?"
        ),
        Category.BORROWED_PHRASING: (
            "Which part of that did you write yourself, and what is it doing "
            "there?"
        ),
    }[category]


def template_floor(request: ComposeRequest) -> str:
    """The response served when generation fails or overreaches.

    Every level is written to what the student must still supply. None supplies a
    missing element on her behalf - sec:respond, "Guidance may narrow the search space
    and may not close it."
    """
    level = request.level
    question = _question(request)
    dim = rubric.BY_ID.get(request.weakest_dimension_id)
    plain = _IN_HER_WORDS.get(request.weakest_dimension_id, "one part of it")

    if level == 1:
        return question

    if level == 2:
        # Names the dimension at fault without saying what to add. The name is
        # the rubric's, so she learns the word; the gloss is hers, so the word
        # means something. Level 1's question is not repeated here - repeating
        # it would spend a rung of the ladder without narrowing anything.
        name = dim.name if dim else "one part of your prompt"
        pointer = (
            "You said that part out loud and then left it out."
            if request.weakest_dimension_id in request.dropped_from_intent
            else "Your prompt never says it."
        )
        return (
            f"Of everything in your prompt, the part doing the least work is "
            f"{name} — {plain}. {pointer} Where would it go?"
        )

    if level == 3:
        return (
            "This is your own prompt back, with the gap marked where it falls:\n\n"
            f"{_mark_prompt(request)}\n\n"
            "Put that in your own words and send the whole thing again."
        )

    if level == ladder.TERMINAL_LEVEL:
        return (
            f"Two prompts. They differ in one way only — {plain}:\n\n"
            f"  A. {request.prompt_text}\n"
            f"  B. {request.prompt_text}, ‹{plain}: ____›\n\n"
            "Picture what each one hands back. Say which is better and why, then "
            "write a new prompt of your own.\n\n"
            f"Filling B in does not settle {request.protected_judgment}. That call "
            "stays yours."
        )

    raise ValueError(f"no template for level {level}")


def _mark_prompt(request: ComposeRequest) -> str:
    """The slot carries her words for the dimension, not the rubric's.

    Level 3 is the rung where she has to write something into the gap. A slot
    labelled "Constraint Setting" asks her to recall a definition first; one
    labelled "how simple it had to be" asks her only the thing being asked.
    """
    plain = _IN_HER_WORDS.get(request.weakest_dimension_id, "the missing part")
    return f"    {request.prompt_text}  ‹{plain}: ____›"
