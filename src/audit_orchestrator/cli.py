"""Command-line entry point for running an engagement.

    audit-orchestrator run \
        --program sample/northwind/program.yaml \
        --evidence sample/northwind/evidence \
        --out viewer/data/workpaper.json \
        --markdown out/workpaper.md

With no arguments, `run` uses the bundled Northwind sample.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

from .engine import run_program
from .gateway import GatewayError
from .models import ControlAssessment
from .program import load_evidence, load_program
from .workpaper import to_markdown

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROGRAM = REPO_ROOT / "sample/northwind/program.yaml"
DEFAULT_EVIDENCE = REPO_ROOT / "sample/northwind/evidence"
DEFAULT_OUT = REPO_ROOT / "viewer/data/workpaper.json"

_SYMBOLS = {"documented": "✓", "partially_documented": "~", "not_found": "✗"}


def _progress(i: int, total: int, a: ControlAssessment) -> None:
    if a.error:
        print(f"  [{i}/{total}] ! {a.control_id} ERRORED — {a.error}")
        return
    print(
        f"  [{i}/{total}] {_SYMBOLS[a.verdict]} {a.control_id} "
        f"{a.verdict} (conf {a.confidence}, coverage "
        f"{a.coverage_matched}/{a.coverage_total})"
    )


def _run(args: argparse.Namespace) -> int:
    load_dotenv()
    controls = load_program(args.program)
    docs = load_evidence(args.evidence)
    engagement = args.engagement or Path(args.evidence).name

    print(f"Running {len(controls)} controls against {len(docs)} documents...\n")
    try:
        wp = run_program(engagement, controls, docs, on_control=_progress)
    except GatewayError as e:
        print(f"\nGateway not configured: {e}", file=sys.stderr)
        print("Copy .env.example to .env and set one provider key.", file=sys.stderr)
        return 1

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(wp.model_dump_json(indent=2))
    print(f"\nWorkpaper JSON -> {out}")

    if args.markdown:
        md = Path(args.markdown)
        md.parent.mkdir(parents=True, exist_ok=True)
        md.write_text(to_markdown(wp))
        print(f"Workpaper Markdown -> {md}")

    s = wp.summary
    print(
        f"\nSummary: {s['documented']} documented · "
        f"{s['partially_documented']} partial · {s['not_found']} not found"
    )
    if s.get("errored"):
        print(
            f"\n{s['errored']} control(s) failed to run (rate limit/timeout/etc) "
            "and were NOT assessed — see the ERRORED lines above. The workpaper "
            "was still written with the controls that did complete; rerun to "
            "retry the failed ones.",
            file=sys.stderr,
        )
        return 2
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="audit-orchestrator")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Run an engagement and emit a workpaper.")
    run.add_argument("--program", default=str(DEFAULT_PROGRAM))
    run.add_argument("--evidence", default=str(DEFAULT_EVIDENCE))
    run.add_argument("--out", default=str(DEFAULT_OUT))
    run.add_argument("--markdown", default=None)
    run.add_argument("--engagement", default=None)
    run.set_defaults(func=_run)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
