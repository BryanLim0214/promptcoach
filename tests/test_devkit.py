"""The developer kit and the MCP server stay faithful to the framework.

These tests guard the one way a developer release could damage the thesis: by
saying more than the framework does. Grades are never promoted, the audit never
claims quality or learning, and the server only reads the framework package.
"""

from __future__ import annotations

import re
import sys

import anyio
import pytest

pytest.importorskip("mcp")

from promptcoach_ref import devkit, mcp_server  # noqa: E402
from promptcoach_ref.framework import grades  # noqa: E402

pytestmark = pytest.mark.devkit

ARGUED = {c.id for c in grades.GRADED_COMPONENTS if c.grade is grades.Grade.ARGUED}
OVERCLAIM = re.compile(
    r"\b(proven|proves|guarantee[sd]?|effective|improves learning|validated by students|"
    r"the first|novel|state of the art|groundbreaking)\b",
    re.IGNORECASE,
)


def call(name: str, args: dict | None = None) -> dict:
    async def run():
        result = await mcp_server.mcp.call_tool(name, args or {})
        assert not result.is_error, result
        return result.structured_content

    return anyio.run(run)


# -- checklist -------------------------------------------------------------


def test_checklist_covers_every_component_in_thesis_order():
    assert [i.component_id for i in devkit.CHECKLIST] == [
        c.id for c in grades.GRADED_COMPONENTS
    ]
    assert len(devkit.CHECKLIST) == grades.EXPECTED_COMPONENT_COUNT == 24
    assert set(devkit.QUESTION) == set(devkit.LAYER) == set(grades.BY_ID)


def test_checklist_never_promotes_a_grade():
    for item in devkit.CHECKLIST:
        row = item.as_dict()
        assert row["evidence_grade"] == item.component.grade.value
        assert row["thesis_basis"] == item.component.basis
        assert row["thesis_limit"] == item.component.limit


def test_questions_carry_no_numbers_and_no_overclaims():
    for cid, question in devkit.QUESTION.items():
        assert not re.search(r"\d", question), cid
        assert not OVERCLAIM.search(question), cid
        assert question.endswith("?"), cid


def test_original_contributions_are_marked():
    marked = {i.component_id for i in devkit.CHECKLIST if i.as_dict()["not_found_in_reviewed_systems"]}
    assert marked == set(grades.ORIGINAL_CONTRIBUTIONS)


# -- audit -------------------------------------------------------------------


def test_full_adoption_is_coverage_not_quality():
    report = devkit.audit({cid: "yes" for cid in grades.BY_ID})
    assert report["gaps"] == []
    assert set(report["adopted_but_untested"]) == ARGUED
    assert "not a quality or learning score" in report["how_to_read"]
    assert "has not yet been used with students" in report["how_to_read"]


def test_missing_answers_count_as_unknown():
    report = devkit.audit({})
    assert report["summary"]["unknown"] == 24
    assert report["gaps"] == []
    assert len(report["not_answered"]) == 24


def test_gap_reports_the_requirement_it_leaves_unmet():
    report = devkit.audit({"judge_independent_of_generator": "no",
                           "same_task_revision_with_reason": "partly"})
    assert report["gaps"] == ["same_task_revision_with_reason", "judge_independent_of_generator"]
    assert report["summary"]["requirements_not_fully_met"] == ["R3", "R4"]


def test_audit_rejects_unknown_ids_and_answers():
    with pytest.raises(ValueError):
        devkit.audit({"no_such_component": "yes"})
    with pytest.raises(ValueError):
        devkit.audit({"template_floor": "maybe"})


# -- MCP server ----------------------------------------------------------------


def test_every_tool_is_read_only_and_closed_world():
    tools = anyio.run(mcp_server.mcp.list_tools)
    assert len(tools) == 12
    for tool in tools:
        assert tool.annotations.read_only_hint is True, tool.name
        assert tool.annotations.open_world_hint is False, tool.name
        assert tool.annotations.destructive_hint is False, tool.name


def test_tool_descriptions_do_not_overclaim():
    for tool in anyio.run(mcp_server.mcp.list_tools):
        text = (tool.description or "") + (tool.title or "")
        assert not OVERCLAIM.search(text), tool.name


def test_overview_matches_the_pinned_grade_counts():
    overview = call("get_framework_overview")
    assert overview["evidence_grades"] == {"direct": 4, "transferred": 10, "argued": 10}
    assert overview["components"] == 24
    assert len(overview["tutor_layers"]) == 5
    assert overview["evidence_status"] == grades_disclaimer()


def grades_disclaimer() -> str:
    from promptcoach_ref.framework import STANDING_DISCLAIMER

    return STANDING_DISCLAIMER


def test_list_components_filters_by_grade():
    rows = call("list_components", {"grade": "argued"})["result"]
    assert {r["component_id"] for r in rows} == ARGUED


def test_taxonomy_and_ladder_come_from_the_framework():
    tax = call("get_failure_taxonomy")
    assert len(tax["categories"]) == 7
    ladder = call("get_help_ladder")
    assert [lv["level"] for lv in ladder["levels"]] == [1, 2, 3, 4]
    assert "may not close it" in ladder["authorship_boundary"]


def test_coach_attempt_runs_the_worked_example_offline():
    first = call("coach_attempt", {
        "stated_intent": "Okay so I have to explain the sky thing to my cousin, she's "
                         "like seven so it can't be complicated, maybe just a few sentences.",
        "prompt_text": "explain why the sky is blue",
        "predicted_rating": 3,
    })
    assert "stand-in" in first["engine_note"]
    assert first["measure"]["judge_independent_of_generator"] is True
    assert first["diagnose"]["target"] == "intent_drift"
    assert first["respond"]["level"] == 1

    revision = "explain why the sky is blue for a seven year old, keep it to a few sentences"
    unreasoned = call("coach_attempt", {"stated_intent": "same", "prompt_text": revision,
                                        "session_id": first["session_id"],
                                        "revise_previous": True})
    assert unreasoned["stopped_at"] == "elicit"
    assert "why you changed it" in unreasoned["needs_from_student"]

    reasoned = call("coach_attempt", {
        "stated_intent": "same", "prompt_text": revision,
        "session_id": first["session_id"], "revise_previous": True,
        "revision_reason": "I added who it is for and how long it should be",
        "predicted_rating": 3,
    })
    assert reasoned["stopped_at"] == "calibrate"
    assert reasoned["calibrate"]["paired_dimension_change"] > 0


def test_resources_and_prompts_are_listed():
    uris = {str(r.uri) for r in anyio.run(mcp_server.mcp.list_resources)}
    assert uris == {"promptcoach://guide/developers", "promptcoach://framework/traceability"}
    names = {p.name for p in anyio.run(mcp_server.mcp.list_prompts)}
    assert names == {"review_tutor_design", "tutor_turn_rules"}


def test_server_answers_over_real_stdio():
    from mcp import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client

    async def run():
        params = StdioServerParameters(
            command=sys.executable, args=["-m", "promptcoach_ref.mcp_server"]
        )
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
                result = await session.call_tool("get_component",
                                                 {"component_id": "worked_contrast_terminal"})
                return [t.name for t in tools.tools], result.structured_content

    names, component = anyio.run(run)
    assert "audit_tutor_design" in names
    assert component["evidence_grade"] == "argued"
