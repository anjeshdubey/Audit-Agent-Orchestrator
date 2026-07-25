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

## Status

Early. The first spike (`spike/phase_0_5.py`) proves the core loop:
structured extraction → citation → **deterministic quote-verification** →
code-derived verdict and confidence, against a small synthetic sample set.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e '.[groq]'          # or .[gemini] / .[together] / .[anthropic] / .[all]
cp .env.example .env              # set at least one provider key
python spike/phase_0_5.py
```

All sample data is synthetic and clearly fictional — never real client data.
