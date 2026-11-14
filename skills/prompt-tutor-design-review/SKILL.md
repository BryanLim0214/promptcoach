---
name: prompt-tutor-design-review
description: Review or design an AI tutor that teaches middle school students to write prompts, using the evidence-graded Learning to Prompt framework (five layers, 24 components, seven failure categories, a help ladder that never writes the student's prompt). Use when someone is building, reviewing, or prompting a prompt-writing coach, an AI literacy tutor, or a rubric for scoring student prompts.
compatibility: Works on its own. If the promptcoach MCP server is connected, call its tools for exact component text, grades, and thesis sections.
metadata:
  source: "Lim, P. (2026), Learning to Prompt: A Design Framework for Middle School AI Literacy, UTPB thesis"
  version: "1.1.0"
---

# Reviewing a prompt-writing tutor design

## When the MCP server is connected

1. Call `get_framework_overview`.
2. Call `get_design_checklist` and answer each of the 24 questions for the design
   with yes, partly, no, or unknown. Use unknown when the design does not say.
3. Call `audit_tutor_design` with the answers.
4. Report gaps by layer, the requirements R1 to R6 not fully met, and the adopted
   components that are still untested (Argued). Cite the thesis section each tool
   returns, and suggest the smallest change that closes each gap.

## Without the server

Check the design against these rules. The grade in brackets is the thesis's
evidence grade: Direct (measured on the thesis's benchmarks), Transferred (shown
in another setting), Argued (follows from the evidence, untested).

**The student's cycle.** She states a plan, writes the prompt herself, predicts
its 1 to 4 score before running it, sees what it produced before any coaching, then
revises the same prompt with a one-sentence reason [all Argued].

**Elicit.** Keep the plan and the prompt as separate records, and record her
predicted score, her revision reason, and which text was inserted [Argued]. Check
any task breakdown before showing it [Transferred].

**Measure.** Score the prompt on six dimensions: Context Clarity, Specificity,
Audience Awareness, Constraint Setting (planning) and Iteration Awareness,
Reflection (evaluative) [Direct]. Lower the confidence on the two evaluative ones
[Direct]. Reward content, not polish [Direct]. The judge model must differ from the
model that answers her [Transferred]. Score only text she wrote [Argued].

**Diagnose.** Name the failure before responding [Transferred], keep a ranked list
when categories overlap [Argued], using seven learner categories: under
specification, social framing, intent drift, blind acceptance, undiagnosed retry,
delegated judgment, borrowed phrasing [Argued].

**Respond.** One failure at a time [Transferred]. A four-level ladder: a question;
name the weak dimension; show her own prompt with the weak part marked; two sample
prompts that differ only on the diagnosed dimension, with both outputs, where she
says which is better and why [Transferred; level 4 is Argued]. Move up only when
she asks or the same failure stays on top, never because she paused
[Transferred]. For blind acceptance, undiagnosed retry, and delegated judgment,
move up only when she asks or sends her prompt unchanged. Keep a
prepared response under every generated one [Transferred]. **No level may write the
missing part of her prompt.** Enforce that in code.

**Calibrate.** Hold the task until one reasoned revision [Argued]. Change
difficulty only when a success rate and a streak both hold [Transferred]. Five
bands on two scales, with no promotion across the join between bands 3 and 4
[Argued]. Whether to show her the predicted-versus-measured gap is the builder's
choice; the thesis leaves it open and states a test for it. Watch for
over-reliance [Direct], as a prompt for a question, not a verdict.

**Every layer.** Content over fluency [Direct]. Diagnostics belong to the student;
teachers see class summaries unless she shares, and the tutor tells her why when
it changes what it asks [Argued]. Accessibility by default [Transferred]. Consent to
research is separate from use [Transferred].

## How to report

- Say what each grade means. Never call an Argued part proven.
- Never say the framework improves learning. It has not yet been used with
  students; it is a design specification that runs in code, and the thesis states
  nine tests that could remove parts of it.
- Do not ask for or process real student data. Point builders to COPPA, FERPA, and
  their own ethics review before any use with children.
