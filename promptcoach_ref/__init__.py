"""PromptCoach Reference.

A runnable instantiation of the five-layer, evidence-graded design framework
specified in *Learning to Prompt: A Design Framework for Middle School AI
Literacy* (Lim, UT Permian Basin).

The thesis says the framework "has not been built as a composed system" and that
"the reference design is unbuilt, so composition is argued on paper". This is
that composed system.

What running it shows: that the specification is complete enough to implement,
that each layer's output is sufficient for the next layer's input, and that the
constraints the thesis states can be enforced in code rather than in prose.

What it does not show: anything about students. No middle school student has used
this, or any of the three systems the framework was extracted from. The taxonomy
and the difficulty progression are the thesis's own contributions and the two
components with the least evidence behind them.
"""

__version__ = "1.0.0"

from . import framework, policy

__all__ = ["framework", "policy", "__version__"]
