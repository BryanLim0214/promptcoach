"""The thing she actually came for: an answer to the prompt she wrote.

Every earlier version of this application scored her prompt, diagnosed it, and
coached her, without ever once running it. That is a marking scheme, not a tool,
and no student would use it twice.

It also removes the only lesson the application can honestly teach. The thesis's
whole argument is that a generative model "can answer an incomplete request", and
that the fluent answer conceals the gap between what she meant and what she
asked. She cannot learn that from a score. She learns it by asking badly, reading
what came back, and seeing it change when she asks better.

Two responders. The live one sends her prompt verbatim and returns whatever it
produces. The scripted one runs with no key and no network, and is quality
sensitive rather than canned: it reads the same six dimension scores Layer 2
produced and assembles an answer that is vague exactly where her prompt was
vague. It is authored, and the interface says so.

Neither responder ever improves her prompt before sending it.

**The generator is not the judge** (sec:measure, component 23). The live
responder is built from its own generator engine, configured separately from
the scoring engine (`policy/generator.py`, `PROMPTCOACH_GENERATOR`). The model
that writes the answer she reads is never handed the job of scoring her prompt,
and Layer 2 records both names on every attempt so the separation is checked
rather than assumed. Offline, the scripted responder generates and the rule
engine scores.

The responder sends the full prompt, including anything the interface inserted:
that is what she asked. Only the scoring treats inserted text as not hers.
"""

from __future__ import annotations

import textwrap
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from .framework import rubric
from .framework.contracts import DimensionScore


@dataclass(frozen=True)
class Answer:
    text: str
    source: str
    #: True when the text was assembled locally rather than generated.
    scripted: bool
    latency_ms: int = 0


@runtime_checkable
class Responder(Protocol):
    def answer(self, prompt_text: str, scores: dict[str, DimensionScore]) -> Answer: ...


# ---------------------------------------------------------------------------


class LiveResponder:
    """Sends her prompt as written, to the generator engine."""

    def __init__(self, engine) -> None:
        self._engine = engine
        self.name = engine.name

    def answer(self, prompt_text: str, scores: dict[str, DimensionScore]) -> Answer:
        import time

        started = time.perf_counter()
        try:
            text = self._engine.answer(prompt_text)
        except Exception as exc:  # a failed answer is not a coaching moment
            return Answer(
                text=(
                    "The assistant did not reply. That is a problem with the tool, "
                    "not with your prompt — try sending it again."
                ),
                source=f"{self._engine.name} (failed: {type(exc).__name__})",
                scripted=False,
            )
        return Answer(
            text=text,
            source=self._engine.name,
            scripted=False,
            latency_ms=int((time.perf_counter() - started) * 1000),
        )


# ---------------------------------------------------------------------------


TOPIC_FALLBACK = "the topic you asked about"

#: Assembled from the dimensions her prompt actually supplied. Each fragment is
#: written so that its absence is felt: no audience means a register nobody
#: asked for, no constraint means length nobody asked for.
_OPENERS = {
    "vague": (
        "{topic} is a broad subject with many aspects worth considering. "
        "There are several perspectives to take into account, and the answer "
        "depends somewhat on what exactly you are interested in."
    ),
    "focused": "Here is what you asked for about {topic}.",
}

_BODY_GENERIC = (
    "Broadly speaking, the subject involves a number of interrelated processes "
    "and factors. Researchers have studied it extensively, and there are "
    "introductory treatments as well as more advanced ones. Depending on your "
    "purpose, you might focus on the underlying mechanisms, the historical "
    "development, or the practical applications. Each of these could be "
    "expanded considerably. It is also worth noting that terminology in this "
    "area varies between sources, so definitions are not always consistent."
)

_BODY_TARGETED = (
    "The short version: it happens because of one main mechanism, and the "
    "everyday version of that is easy to picture once you have the right image "
    "for it."
)


class ScriptedResponder:
    """Offline, and sensitive to the prompt's quality rather than canned.

    The mapping from score to answer shape is an implementation choice, not a
    finding. It exists so the application can be demonstrated without a key, and
    the interface labels every answer it produces.
    """

    name = "scripted-responder"

    def answer(self, prompt_text: str, scores: dict[str, DimensionScore]) -> Answer:
        def has(dim_id: str, at_least: int = 2) -> bool:
            score = scores.get(dim_id)
            return bool(score and score.value is not None and score.value >= at_least)

        topic = _topic_of(prompt_text)
        audience = has(rubric.AUDIENCE_AWARENESS.id)
        constrained = has(rubric.CONSTRAINT_SETTING.id)
        specific = has(rubric.SPECIFICITY.id)
        purposeful = has(rubric.CONTEXT_CLARITY.id, 3)

        parts: list[str] = []

        if purposeful or specific:
            parts.append(_OPENERS["focused"].format(topic=topic))
        else:
            parts.append(_OPENERS["vague"].format(topic=topic))

        if audience and constrained:
            parts.append(_BODY_TARGETED)
        elif audience:
            parts.append(
                "Pitched for the reader you named, though you did not say how "
                "long it should be, so here is a fuller treatment. "
                + _BODY_TARGETED
                + " "
                + _BODY_GENERIC
            )
        else:
            parts.append(_BODY_GENERIC)

        if not constrained and not audience:
            parts.append(
                "If you had a particular length or reader in mind, I could not "
                "tell from the question, so this is written for a general adult "
                "reader at moderate length."
            )

        if specific and constrained and audience:
            parts.append("That should fit what you asked for.")

        text = "\n\n".join(textwrap.fill(p, 88) for p in parts)
        return Answer(text=text, source=self.name, scripted=True)


_STOPWORDS = {
    "explain", "write", "tell", "me", "about", "a", "an", "the", "why", "how",
    "what", "is", "are", "was", "were", "do", "does", "did", "please", "can",
    "could", "you", "give", "summarise", "summarize", "describe", "of", "and",
    "or", "it", "its", "something", "help", "with", "my", "i", "need", "want",
    "get", "make", "some", "that", "this", "on", "so", "then",
}

#: Everything from here on is audience or constraint, not subject matter.
#: "explain why the sky is blue for a seven year old, keep it short" is about
#: the sky, and a topic phrase that swallowed "seven year old" would read as
#: gibberish in the answer.
_TOPIC_ENDS = {
    "for", "to", "at", "in", "under", "using", "keep", "keeping", "within",
    "no", "not", "aimed", "pitched", "suitable", "so",
}


def _topic_of(prompt_text: str) -> str:
    head = prompt_text.split(",")[0]
    words: list[str] = []
    for raw in head.split():
        word = raw.strip(".,!?;:\"'").lower()
        if not word:
            continue
        if word in _TOPIC_ENDS and words:
            break
        if word in _STOPWORDS:
            continue
        if word.isdigit():
            continue
        words.append(word)
    if not words:
        return TOPIC_FALLBACK
    return " ".join(words[:4])


def build(generator=None) -> Responder:
    """Live when a generator engine is configured and can answer, scripted
    otherwise.

    Takes the *generator* engine, never the scoring engine. Passing the scorer
    here would make one model both write the answer and judge the prompt, which
    is the configuration component 23 exists to rule out.
    """
    if generator is not None and hasattr(generator, "answer"):
        return LiveResponder(generator)
    return ScriptedResponder()


def name_of(responder: Responder) -> str:
    return getattr(responder, "name", type(responder).__name__)
