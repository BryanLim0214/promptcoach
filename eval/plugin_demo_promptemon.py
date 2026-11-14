"""Real plug-in run for the defense: audit Promptemon's design through a real MCP client.

    .venv/Scripts/python -m eval.plugin_demo_promptemon

Starts the plug-in as a subprocess over stdio (exactly as an AI assistant would),
calls audit_tutor_design, and saves the request and the full response to
eval/results/plugin_demo_promptemon.json.

Every answer below describes Promptemon's design as the thesis states it
(Chapter 5 and Section 9.4); anything the thesis does not state is left out and
so counts as "unknown". Sources, by component:
  visible_consequence_before_coaching  yes      each battle showed the result at once (5.9, R1)
  six_dimension_rubric                 no       the game judged the AI's response, not the prompt (5.9, R2)
  same_task_revision_with_reason       no       could change chips, never asked to revise and explain (5.9, R3)
  judge_independent_of_generator       no       one Gemini model both generated and judged (5.9, R4)
  selecting_is_not_composing           no       students picked a base instruction and chips, typed nothing (5.9, R5)
  predicted_rating_beside_score        no       no score prediction in the game (Chapter 5)
  intent_artifact_gap_diagnostic       no       no plan was recorded (Chapter 5)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import anyio
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

ANSWERS = {
    "visible_consequence_before_coaching": "yes",
    "six_dimension_rubric": "no",
    "same_task_revision_with_reason": "no",
    "judge_independent_of_generator": "no",
    "selecting_is_not_composing": "no",
    "predicted_rating_beside_score": "no",
    "intent_artifact_gap_diagnostic": "no",
}
OUT = Path(__file__).resolve().parent / "results" / "plugin_demo_promptemon.json"


async def main() -> dict:
    params = StdioServerParameters(command=sys.executable, args=["-m", "promptcoach_ref.mcp_server"])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = [t.name for t in (await session.list_tools()).tools]
            result = await session.call_tool("audit_tutor_design", {"answers": ANSWERS})
            return {"tools_listed": tools, "request": {"answers": ANSWERS},
                    "response": result.structured_content}


if __name__ == "__main__":
    data = anyio.run(main)
    OUT.write_text(json.dumps(data, indent=2), encoding="utf-8")
    r = data["response"]
    print("gaps:", r["gaps"])
    print("requirements not fully met:", r["summary"]["requirements_not_fully_met"])
    print("adopted but untested:", r["adopted_but_untested"])
    print("summary:", {k: r["summary"][k] for k in ("yes", "partly", "no", "unknown")})
    print("saved", OUT)
