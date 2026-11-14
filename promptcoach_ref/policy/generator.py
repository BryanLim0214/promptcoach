"""Which model answers her prompt.

sec:measure (the judge-independence component, R4): the judge that scores her
work is not the model that produced the output. Promptemon used one model to
generate and to judge; self-preference in model judges is the reason not to
(Panickssery et al. 2024). The framework states the separation. It does not say
which model generates, so the choice is here.

The generator is configured separately from the scoring engines: the scorer is
`PROMPTCOACH_SCORER` (or the provider default), the optional cross-model
comparator is the provider's comparator, and the generator is
`PROMPTCOACH_GENERATOR` (or the default below). Every shipped default generator
differs from **both** scoring models on its provider, so the cross-model path is
independent too. A live configuration whose generator equals any judge is
refused at start-up rather than run (`check_independent`). With no key, the
offline scripted responder generates and the rule engine scores, which are
different components by construction.
"""

from __future__ import annotations

import os

from .base import Choice, register

ENV_VAR = "PROMPTCOACH_GENERATOR"

#: Provider -> scoring models shipped by default: (scorer, cross-model
#: comparator). Kept here so the independence test can see every judge.
SHIPPED_JUDGES: dict[str, tuple[str, str]] = {
    "gemini": ("gemini-3.1-flash-lite", "gemini-3.8-flash"),
    "openrouter": ("anthropic/claude-opus-5", "google/gemini-3.8-flash"),
}

#: Provider -> default generator model. Neither scorer nor comparator.
DEFAULTS: dict[str, str] = {
    "gemini": "gemini-3.1-pro-preview",
    "openrouter": "openai/gpt-5.4-mini",
}

GENERATOR = register(
    Choice(
        id="generator.model",
        value=dict(DEFAULTS),
        thesis_says=(
            "sec:measure requires a judge independent of the generating model and "
            "names no generator."
        ),
        borrowed_from=(
            "none. On each provider, a third model that is neither the scorer nor "
            f"the cross-model comparator; override with {ENV_VAR}."
        ),
        caveat=(
            "Independence here means a different model, which rules out a model "
            "scoring prompts for its own outputs. It does not rule out shared "
            "priors between models of one vendor (all three Gemini defaults are "
            "Google models). On Gemini the generator is the Pro preview, which was "
            "slow in informal testing (three calls, not benchmarked); it answers "
            "once per attempt and is off the scoring path. The component has never "
            "been measured on student prompts."
        ),
    )
)

ON_SAME_MODEL = register(
    Choice(
        id="generator.on_same_model",
        value="refuse",
        thesis_says="The framework does not say what to do when the two coincide.",
        borrowed_from="none",
        caveat=(
            "A live configuration that points the generator at a judge (the scorer "
            "or, with PROMPTCOACH_CROSS_MODEL=1, the comparator) refuses to start "
            "with a message naming the collision, rather than run non-independent. "
            "The offline rule engine is unaffected. Every Measure output still "
            "records judge_independent_of_generator, so the check is visible per "
            "attempt as well."
        ),
    )
)


class NonIndependentConfiguration(RuntimeError):
    """The configured generator is one of the judges."""


def model_for(provider: str) -> str:
    return os.environ.get(ENV_VAR) or DEFAULTS[provider]


def independent(judges: tuple[str, ...], generator: str) -> bool:
    """True when no judge is the generator. Compared by model id."""
    gen = _model_id(generator)
    return bool(gen) and all(_model_id(j) != gen for j in judges if j)


def check_independent(judges: tuple[str, ...], generator: str) -> None:
    """Refuse a live configuration whose generator is a judge."""
    if not independent(judges, generator):
        raise NonIndependentConfiguration(
            f"Refusing to start: the generator ({generator}) is the same model as "
            f"a judge ({', '.join(j for j in judges if j)}). The framework requires "
            "the judge to be independent of the generating model. Set "
            f"{ENV_VAR} to a third model that is neither the scorer nor the "
            "comparator, or run offline (no API key) with the rule engine."
        )


def _model_id(name: str) -> str:
    """'gemini:gemini-3.8-flash' and 'openrouter:google/gemini-3.8-flash' both
    name the model 'gemini-3.8-flash'."""
    tail = name.split(":", 1)[-1]
    return tail.split("/", 1)[-1].strip().lower()
