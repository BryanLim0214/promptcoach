"""The two user studies, as aggregates.

Every number here is transcribed, never computed. Promptemon values come only
from the post hoc paired re-analysis of its survey data
(`analysis/promptemon_aggregates.json`, cited RAW), which supersedes both drafts
wherever they differ. PicPrompt values come only from the published article as
recorded in `evidence/NUMBERS.md` (cited CoED). Each aggregate carries the
section label of the chapter that reports it, the NUMBERS id, and the caveat
NUMBERS attaches to it.

Three rules shape the module.

1. **Aggregates only.** There is no per-student row, no name, no identifier.
   Promptemon pairs were linked by name in the re-analysis; nothing of that
   linkage reaches this package.
2. **Comparability is a flag, not a footnote.** A pre/post item pair whose two
   items were worded differently cannot be presented as change.
   `present_change()` refuses it; `present_separately()` is the only way to show
   both values, and it returns them without a difference.
3. **Self-report is not skill.** Every classroom outcome here is self-report
   unless stated. Nothing in this module is evidence that any student learned
   or improved anything.

The withdrawn figures are listed once, at the bottom, so a test can prove they
appear nowhere else in the package.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .grades import Cite

PROMPTEMON_LABEL = (
    "a post hoc paired re-analysis of the Promptemon survey data, conducted by a "
    "member of the original team and not pre-registered"
)

SELF_REPORT_RULE = (
    "User-study numbers are self-report unless stated. They are never evidence that "
    "a student learned, improved a skill, or was taught."
)

#: sec:promptemon - the fact that matters everywhere.
PROMPTEMON_STUDENTS_DID_NOT_TYPE = (
    "Promptemon students did not type free text: they picked a prepared base "
    "instruction and added up to one chip each for persona, style and audience."
)


@dataclass(frozen=True)
class Aggregate:
    id: str
    study: str
    value: Any
    meaning: str
    cite: Cite
    #: NUMBERS.md row id.
    numbers_id: str
    #: Where the value was transcribed from: a RAW key path, or a CoED page.
    source: str
    caveat: str
    #: For RAW values: the key path into promptemon_aggregates.json, so a test
    #: can pin the transcription against the file.
    raw_key: tuple[str, ...] = ()
    self_report: bool = True


@dataclass(frozen=True)
class ItemPair:
    """A pre item and a post item that someone might want to subtract."""

    id: str
    study: str
    pre: Any
    post: Any
    meaning: str
    comparable: bool
    why: str
    cite: Cite
    numbers_id: str
    raw_keys: tuple[tuple[str, ...], ...] = ()
    test: dict[str, Any] = field(default_factory=dict)


class NotComparable(ValueError):
    """Raised when a non-comparable pair is asked for as a change."""


_PM = Cite("sec:promptemon-reanalysis", "paired re-analysis (RAW)")
_PM_SETTING = Cite("sec:promptemon", "sample and setting")
_PP = Cite("sec:picprompt", "kumar2026picprompt")


# ---------------------------------------------------------------------------
# Promptemon (RAW)
# ---------------------------------------------------------------------------

_PROMPTEMON: tuple[Aggregate, ...] = (
    Aggregate(
        id="promptemon.n_pre", study="promptemon", value=60,
        meaning="Pre-survey rows", cite=_PM_SETTING, numbers_id="PM-01",
        source="RAW n_pre", caveat="Grades 6 to 8, one school expo station.",
        raw_key=("n_pre",), self_report=False,
    ),
    Aggregate(
        id="promptemon.n_post", study="promptemon", value=60,
        meaning="Post-survey rows", cite=_PM_SETTING, numbers_id="PM-01",
        source="RAW n_post", caveat="", raw_key=("n_post",), self_report=False,
    ),
    Aggregate(
        id="promptemon.matched_pairs", study="promptemon", value=53,
        meaning="Pre and post records linked by name", cite=_PM, numbers_id="PM-02",
        source="RAW paired_n", caveat="Matching on name only.",
        raw_key=("paired_n",), self_report=False,
    ),
    Aggregate(
        id="promptemon.attrition", study="promptemon",
        value={"pre_only": 6, "post_only": 5, "duplicate_name_keys": 1},
        meaning="Records without a match, and one duplicate name excluded",
        cite=_PM, numbers_id="PM-03", source="RAW attrition",
        caveat="Supersedes the earlier seven-on-each-side figure.",
        raw_key=("attrition",), self_report=False,
    ),
    Aggregate(
        id="promptemon.grade_agree", study="promptemon", value=53,
        meaning="Matched pairs reporting the same grade before and after",
        cite=_PM, numbers_id="PM-04", source="RAW matched_pairs_grade_agree",
        caveat="", raw_key=("matched_pairs_grade_agree",), self_report=False,
    ),
    Aggregate(
        id="promptemon.confidence_direction", study="promptemon",
        value={"up": 26, "down": 8, "same": 19},
        meaning="Within-student change in self-rated confidence (n = 53)",
        cite=_PM, numbers_id="PM-10", source="RAW confidence_paired",
        caveat=(
            "Self-report, not skill. The post item names the game, so treat it as "
            "an upper bound. Groups shared stations, so p-values are "
            "anti-conservative."
        ),
        raw_key=("confidence_paired",),
    ),
    Aggregate(
        id="promptemon.confidence_sign_test", study="promptemon",
        value={"p": 0.0029, "holm": 0.0058},
        meaning="Sign test of the confidence change", cite=_PM, numbers_id="PM-11",
        source="RAW confidence_paired.sign_test_p; holm_adjusted",
        caveat="Exploratory; Holm family of two chosen after seeing the data.",
        raw_key=("confidence_paired", "sign_test_p"),
    ),
    Aggregate(
        id="promptemon.feedback_helped", study="promptemon",
        value={"agreed": 44, "of": 60},
        meaning=(
            "Agreed the feedback helped them understand how to make their prompts "
            "better (post only)"
        ),
        cite=_PM, numbers_id="PM-40", source="RAW feedback_helped (4 + 5)",
        caveat=(
            "Post only. Perceived understanding, not use. Bundles the visible "
            "consequence with the coaching tip."
        ),
        raw_key=("feedback_helped",),
    ),
    Aggregate(
        id="promptemon.combo_motivation", study="promptemon",
        value={"agreed": 28, "of": 60},
        meaning="Agreed the game made them want to try other chip combinations",
        cite=_PM, numbers_id="PM-41", source="RAW combo_motivation (4 + 5)",
        caveat="Post only; fewer than half.",
        raw_key=("combo_motivation",),
    ),
)

_PROMPTEMON_PAIRS: tuple[ItemPair, ...] = (
    ItemPair(
        id="promptemon.confidence", study="promptemon",
        pre={"mean": 3.58}, post={"mean": 4.13},
        meaning="Self-rated confidence getting a useful response from an AI, 1-5",
        comparable=True,
        why=(
            "Same question and scale; the post wording adds 'After playing "
            "Promptemon', so the change is an upper bound."
        ),
        cite=_PM, numbers_id="PM-13",
        raw_keys=(("confidence_paired", "mean_pre"), ("confidence_paired", "mean_post")),
        test={"name": "sign test", "p": 0.0029},
    ),
    ItemPair(
        id="promptemon.best_way", study="promptemon",
        pre={"structured": 31, "of": 52}, post={"structured": 27, "of": 52},
        meaning="Chose the structured option on the best-way-to-prompt item",
        comparable=True,
        why="The only identical pre/post item. Blank answers excluded.",
        cite=_PM, numbers_id="PM-18",
        raw_keys=(("best_way_paired", "structured_pre"), ("best_way_paired", "structured_post")),
        test={"name": "McNemar exact", "p": 0.2188},
    ),
    ItemPair(
        id="promptemon.let_ai_decide", study="promptemon",
        pre={"chose": 12, "of": 52}, post={"chose": 18, "of": 52},
        meaning="Chose the option that leaves the decisions to the AI",
        comparable=True,
        why="Same item as best_way. Not tested; descriptive only.",
        cite=_PM, numbers_id="PM-20",
        raw_keys=(("best_way_paired", "let_ai_decide_pre"), ("best_way_paired", "let_ai_decide_post")),
    ),
    ItemPair(
        id="promptemon.persona", study="promptemon",
        pre={"mean": 3.66}, post={"mean": 4.0},
        meaning="Persona, style and audience items",
        comparable=False,
        why="The pre item asks belief; the post item asks gained understanding.",
        cite=_PM, numbers_id="PM-21",
        raw_keys=(("persona_paired_descriptive", "mean_pre"), ("persona_paired_descriptive", "mean_post")),
    ),
)


# ---------------------------------------------------------------------------
# PicPrompt (CoED 2026, via NUMBERS.md)
# ---------------------------------------------------------------------------

_PICPROMPT: tuple[Aggregate, ...] = (
    Aggregate(
        id="picprompt.n", study="picprompt", value=22,
        meaning="Students, grades 2 through 9, at one informal site", cite=_PP,
        numbers_id="PP-01", source="CoED p. 113",
        caveat="Not a middle-school sample: only 4 of the 22 were in grades 6 to 8.",
        self_report=False,
    ),
    Aggregate(
        id="picprompt.in_target_band", study="picprompt", value={"n": 4, "of": 22},
        meaning="Students in grades 6 to 8", cite=_PP, numbers_id="PP-02",
        source="CoED Table 1 p. 113", caveat="No eighth graders.", self_report=False,
    ),
    Aggregate(
        id="picprompt.post_confidence", study="picprompt", value={"mean": 2.91, "of": 4},
        meaning="Post-only confidence", cite=_PP, numbers_id="PP-11",
        source="CoED p. 120", caveat="Post only; no baseline was collected.",
    ),
    Aggregate(
        id="picprompt.fun", study="picprompt", value={"mean": 3.95, "of": 5, "lowest_rating": 3},
        meaning="Rated fun; 3 of 22 gave the lowest rating", cite=_PP,
        numbers_id="PP-13", source="CoED p. 121", caveat="Post only; wide spread.",
    ),
    Aggregate(
        id="picprompt.recommend", study="picprompt", value={"n": 17, "of": 22},
        meaning="Would recommend the game", cite=_PP, numbers_id="PP-14",
        source="CoED p. 121", caveat="Post only.",
    ),
    Aggregate(
        id="picprompt.helped_most_theme", study="picprompt", value={"n": 6, "of_usable": 12},
        meaning=(
            "Most common theme among usable answers to what helped most: writing "
            "and testing prompts"
        ),
        cite=_PP, numbers_id="PP-16", source="CoED pp. 123, 125",
        caveat="Descriptive; no coding reliability; 10 of 22 answers unusable.",
    ),
    Aggregate(
        id="picprompt.skill_task_lost", study="picprompt", value={"n": 14, "of": 22},
        meaning="Post answers to the one performance task that were empty or off-topic",
        cite=_PP, numbers_id="PP-17", source="CoED p. 124",
        caveat="The one performance measure was lost to survey fatigue.",
        self_report=False,
    ),
)

_PICPROMPT_PAIRS: tuple[ItemPair, ...] = (
    ItemPair(
        id="picprompt.prompt_knowledge", study="picprompt",
        pre={"mean": 2.23, "of": 4}, post={"mean": 2.73, "of": 4},
        meaning="Self-rated prompt-writing knowledge",
        comparable=False,
        why=(
            "The pre and post anchors were worded differently ('know' against "
            "'learned'). Not significant (p = .12, d = 0.35)."
        ),
        cite=_PP, numbers_id="PP-06",
    ),
    ItemPair(
        id="picprompt.lowest_anchor", study="picprompt",
        pre={"n": 8, "of": 22}, post={"n": 1, "of": 22},
        meaning="Chose the lowest anchor on each form",
        comparable=False,
        why=(
            "The post form has no 'never done this' option and every player writes "
            "a prompt, so the drop is guaranteed by taking part."
        ),
        cite=_PP, numbers_id="PP-07",
    ),
    ItemPair(
        id="picprompt.ai_knowledge", study="picprompt",
        pre={"mean": 3.77, "of": 5}, post={"mean": 3.27, "of": 5},
        meaning="Self-rated AI knowledge",
        comparable=False,
        why="The authors call the two items not comparable.",
        cite=_PP, numbers_id="PP-08",
    ),
    ItemPair(
        id="picprompt.specificity_strategy", study="picprompt",
        pre={"n": 13, "of": 22}, post={"n": 12, "of": 22},
        meaning="Chose 'specific and detailed' as a good-prompt strategy",
        comparable=False,
        why="The items differ (belief against observation). McNemar p = 1.0.",
        cite=_PP, numbers_id="PP-09",
    ),
    ItemPair(
        id="picprompt.wrong_image_response", study="picprompt",
        pre={"n": 19, "of": 22}, post={"n": 13, "of": 22},
        meaning="Chose 'add details' or 'change a few words' after a wrong image",
        comparable=False,
        why=(
            "Hypothetical 'would do' against recalled 'worked best'; possible "
            "survey fatigue. McNemar p = .11."
        ),
        cite=_PP, numbers_id="PP-10",
    ),
    ItemPair(
        id="picprompt.bedroom_prompt", study="picprompt",
        pre={"mean": 6.68, "of": 12}, post={"mean": 3.55, "of": 12},
        meaning="Rated quality of the one written prompt task",
        comparable=False,
        why=(
            "Invalid as a skill measure: 14 of 22 post answers were empty or "
            "off-topic, and there was no inter-rater reliability."
        ),
        cite=_PP, numbers_id="PP-17",
    ),
)


AGGREGATES: dict[str, Aggregate] = {a.id: a for a in _PROMPTEMON + _PICPROMPT}
ITEM_PAIRS: dict[str, ItemPair] = {p.id: p for p in _PROMPTEMON_PAIRS + _PICPROMPT_PAIRS}

#: One flag per pre/post item pair. A test pins it.
COMPARABLE: dict[str, bool] = {k: p.comparable for k, p in ITEM_PAIRS.items()}

#: The thesis statement's "82 students in total": 60 Promptemon respondents per
#: form plus 22 PicPrompt players.
STUDENTS_ACROSS_BOTH_STUDIES = 60 + 22


def present_change(pair_id: str) -> dict[str, Any]:
    """Pre, post and the difference, for a comparable pair only."""
    pair = ITEM_PAIRS[pair_id]
    if not pair.comparable:
        raise NotComparable(
            f"{pair_id} cannot be presented as change: {pair.why}"
        )
    out: dict[str, Any] = {
        "id": pair.id,
        "pre": pair.pre,
        "post": pair.post,
        "meaning": pair.meaning,
        "note": pair.why,
        "cite": str(pair.cite),
    }
    if pair.test:
        out["test"] = pair.test
    return out


def present_separately(pair_id: str) -> dict[str, Any]:
    """Both values, side by side, with no difference and the reason why."""
    pair = ITEM_PAIRS[pair_id]
    return {
        "id": pair.id,
        "before_item": pair.pre,
        "after_item": pair.post,
        "meaning": pair.meaning,
        "comparable": pair.comparable,
        "note": pair.why,
        "cite": str(pair.cite),
    }


def present(pair_id: str) -> dict[str, Any]:
    """Change when the pair allows it, separate values otherwise."""
    pair = ITEM_PAIRS[pair_id]
    return present_change(pair_id) if pair.comparable else present_separately(pair_id)


# ---------------------------------------------------------------------------
# WITHDRAWN. Never printed. Declared here, once, so a test can prove the package
# contains them nowhere else.
# ---------------------------------------------------------------------------

WITHDRAWN: tuple[str, ...] = (
    "40 of 51",
    "78% of newcomers",
    "31.7",
    "46.7",
    "5 to 52",
)
