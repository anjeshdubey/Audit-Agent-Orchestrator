# audit-orchestrator

A grounded, human-in-the-loop agent for **compliance evidence review**. Give it
a list of controls (a SOC 2-style checklist) and a set of policy documents, and
it answers each control with a **verdict, a confidence score, and a citation to
the exact source passage** it relied on — routing anything uncertain to a human
to sign off. Nothing is ever concluded without a person, and no answer is
trusted unless its supporting quote can be verified against the source.

I built this because the interesting engineering problem in applied AI isn't
getting a model to produce an answer — it's making that answer **traceable and
trustworthy** enough that a domain expert would stake their name on it. Compliance
review is a clean forcing function for that: the answer is worthless without a
verifiable citation, and a wrong "pass" is worse than no answer at all.

## Design principles

- **The human always concludes.** The agent proposes; a person disposes. No
  control is marked passed or failed without explicit sign-off.
- **Verification before confidence.** The primary guardrail is deterministic:
  a cited passage must literally exist in the source, checked in code — not by
  asking the model how sure it is. A confident but fabricated citation is
  caught by the quote check, not the score.
- **Confidence is derived, not self-reported.** The score comes from signals
  the code owns (did verification pass, how much of the requirement the
  evidence covers), so it means something.
- **Predictable over clever.** In this domain a repeatable correct answer beats
  an impressive-looking wrong one.

## Scope

This does **design/documentation testing** — "is this control adequately
documented, and where's the proof?" It deliberately does *not* do sample-based
operating-effectiveness testing. Design testing maps cleanly onto grounded
document extraction, which is the capability this project is about.

## How it works

Per control, the agent:

1. **Extracts evidence** — for each part of the requirement it believes is met,
   the model returns a *verbatim* citation (source · section · exact quote).
2. **Verifies** — code checks each quoted passage literally exists in the named
   source. An unverifiable quote is rejected and cannot count.
3. **Scores in code** — the verdict (`documented` / `partially_documented` /
   `not_found`) and a confidence score are derived from verification + how many
   requirement parts are backed by verified evidence. The model never reports
   its own verdict or confidence.

Verification proves a citation is *authentic*, not that it's *relevant* — the
semantic-sufficiency judgment is surfaced for a human reviewer (the
human-in-the-loop phase), which is the whole point: the agent does the tedious
first pass, a person signs off.

## Quickstart

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e '.[anthropic]'     # or .[groq] / .[gemini] / .[together] / .[all]
cp .env.example .env              # set at least one provider key

# Run the bundled Northwind sample engagement (12 controls, 5 policy docs)
audit-orchestrator run --markdown out/workpaper.md

# View the workpaper (served, not file://, so the browser can fetch the JSON)
python -m http.server -d viewer 8000   # then open http://localhost:8000
```

Run the deterministic-core tests with `pip install -e '.[dev]' && pytest`.

## Status

Testing-agent core is working end-to-end: a CLI runs a full control program
against an evidence set and emits a workpaper (JSON + Markdown) with verified
citations, plus a read-only viewer that highlights each cited passage inside
its source document. The earlier `spike/phase_0_5.py` remains as the original
proof of the core loop.

All sample data is synthetic and clearly fictional — never real client data.
