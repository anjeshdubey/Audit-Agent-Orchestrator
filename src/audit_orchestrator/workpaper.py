"""Render a Workpaper as human-readable Markdown.

The JSON form is the Workpaper model's own `model_dump_json`; this module is
the reviewer-facing document version (no embedded evidence blobs).
"""

from __future__ import annotations

from .models import Workpaper

_SYMBOLS = {"documented": "✓", "partially_documented": "~", "not_found": "✗"}
_LABELS = {
    "documented": "Documented",
    "partially_documented": "Partially documented",
    "not_found": "Not found",
}


def to_markdown(wp: Workpaper) -> str:
    s = wp.summary
    lines = [
        f"# Workpaper — {wp.engagement}",
        "",
        f"_Generated {wp.generated_at} · {wp.provider}/{wp.model}_",
        "",
        f"> {wp.scope_note}",
        "",
        f"**Summary:** {s['documented']} documented · "
        f"{s['partially_documented']} partial · {s['not_found']} not found "
        f"({s['total']} controls)",
        "",
    ]
    for a in wp.assessments:
        lines.append(f"## {_SYMBOLS[a.verdict]} {a.control_id} — {a.title}")
        lines.append("")
        lines.append(f"- **Verdict:** {_LABELS[a.verdict]} (confidence {a.confidence})")
        lines.append(
            f"- **Coverage:** {a.coverage_matched}/{a.coverage_total} requirement parts"
        )
        lines.append(f"- **Rationale:** {a.rationale}")
        if a.evidence:
            lines.append("- **Evidence:**")
            for item in a.evidence:
                c = item.citation
                lines.append(f"  - _{item.requirement_part}_ — `{c.source}` {c.anchor}")
                lines.append(f"    > {c.exact_quote}")
        else:
            lines.append("- **Evidence:** _none_")
        if a.rejected_citations:
            lines.append(
                f"- **Rejected citations:** {a.rejected_citations} "
                "(quote not found in source — fabrication caught)"
            )
        lines.append("")
    return "\n".join(lines)
