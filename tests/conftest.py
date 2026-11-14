"""Fixtures. Everything here is offline; no test touches the network."""

from __future__ import annotations

import os

import pytest

# Set before promptcoach_ref.api is imported anywhere. A GEMINI_API_KEY on the
# machine would otherwise make the API tests call a real model: they would still
# pass, take a minute, cost money, and stop testing the deterministic behaviour
# they are written to assert.
os.environ["PROMPTCOACH_OFFLINE"] = "1"

from promptcoach_ref.engines import DeterministicEngine
from promptcoach_ref.engines.base import (
    ComposeRequest,
    DiagnosisRequest,
    EngineError,
    RawAssignment,
    ScoringRequest,
    ScoringSample,
)
from promptcoach_ref.layers import Consent
from promptcoach_ref.policy import taskbank
from promptcoach_ref.session import Session

# The Chapter 11 worked example, verbatim from sec:design.
WORKED_SPOKEN = (
    "Okay so I have to explain the sky thing to my cousin, she's like seven so it "
    "can't be complicated, maybe just a few sentences."
)
WORKED_TYPED = "explain why the sky is blue"
WORKED_REVISION = (
    "explain why the sky is blue for a seven year old, keep it to a few sentences"
)
#: The revision's stated reason. The thesis's revision is longer; this shorter
#: version is the one the test runs (sec:worked says so). The reason restates
#: what she changed, which is all the rule asks.
WORKED_REASON = "I added who it is for and how long it should be"


class FailingEngine(DeterministicEngine):
    """Fails on every scoring call, to prove a failure stays a failure."""

    name = "failing-engine"

    def sample_scores(self, request: ScoringRequest, temperature: float) -> ScoringSample:
        raise EngineError("upstream scoring timed out")


class OverreachingEngine(DeterministicEngine):
    """Returns help that hands over the missing element.

    Used to prove the validator catches it and the template floor takes over.
    A model that ignores its instructions is the case sec:respond designs for.
    """

    name = "overreaching-engine"

    def compose(self, request: ComposeRequest) -> str | None:
        return (
            "Here's a better prompt: explain why the sky is blue for a seven year "
            "old in three short sentences."
        )


class SameOrgEngine(DeterministicEngine):
    """A second scorer from the same organisation as the first."""

    name = "same-org-engine"
    organisation = "none"


class OtherOrgEngine(DeterministicEngine):
    name = "other-org-engine"
    organisation = "another-vendor"

    def sample_scores(self, request: ScoringRequest, temperature: float) -> ScoringSample:
        sample = super().sample_scores(request, temperature)
        # Disagree by one point on the first dimension, so the divergence is
        # non-zero and the agreement payload has something to report.
        dims = list(sample.dimensions)
        first = dims[0]
        if first.value is not None and first.value < 4:
            dims[0] = type(first)(
                dimension_id=first.dimension_id,
                value=first.value + 1,
                evidence_span=first.evidence_span,
            )
        return ScoringSample(
            judge=self.name,
            temperature=temperature,
            dimensions=tuple(dims),
        )


@pytest.fixture
def consent() -> Consent:
    return Consent(
        platform_use=True, research_participation=False, audio_retention=True
    )


@pytest.fixture
def engine() -> DeterministicEngine:
    return DeterministicEngine()


@pytest.fixture
def session(consent: Consent, engine: DeterministicEngine) -> Session:
    s = Session(session_id="test", consent=consent, engine=engine)
    s.task_id = taskbank.WORKED_EXAMPLE_ID
    s.band = taskbank.BY_ID[taskbank.WORKED_EXAMPLE_ID].band
    return s


@pytest.fixture
def worked(session: Session):
    """The Chapter 11 example, run once."""
    return session.submit(
        stated_intent=WORKED_SPOKEN,
        prompt_text=WORKED_TYPED,
        intent_modality="speech",
    )
