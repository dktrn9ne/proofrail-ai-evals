from __future__ import annotations

from typing import Any


def _mark(passed: bool) -> str:
    return "PASS" if passed else "FAIL"


def markdown_report(result: dict[str, Any]) -> str:
    stages = result.get("stages", {})
    lines = [
        "# Proofrail Model Evaluation Review",
        "",
        f"**Evaluation:** {result.get('spec_name', result.get('spec_id', 'Unknown'))}",
        f"**Decision:** {result.get('decision', 'BLOCK')}",
        "",
        "## Gate summary",
        "",
        "| Stage | Result | Evidence |",
        "|---|---:|---|",
    ]

    intake = stages.get("intake_scan", {})
    lines.append(f"| Intake scan | {_mark(bool(intake.get('passed')))} | {len(intake.get('errors', []))} specification errors |")
    if not intake.get("passed"):
        lines.extend(["", "## Specification errors", ""])
        lines.extend(f"- {error}" for error in intake.get("errors", []))
        return "\n".join(lines) + "\n"

    overlap = stages["overlap_scan"]
    controls = stages["anchor_controls"]
    trials = stages["trial_scoring"]
    lines.extend([
        f"| Overlap scan | {_mark(overlap['passed'])} | Maximum similarity {overlap['maximum']:.3f} |",
        f"| Anchor controls | {_mark(controls['passed'])} | Oracle {controls['oracle']['score']:.3f}; negative {controls['negative']['score']:.3f} |",
        f"| Trial scoring | {_mark(trials['passed'])} | {trials['passed_count']}/{trials['total_count']} passed; mean {trials['mean_score']:.3f} |",
        f"| Release gate | {_mark(stages['release_gate']['passed'])} | {result['decision']} |",
        "",
        "## Trial evidence",
        "",
        "| Run | Score | Result | Failed criteria |",
        "|---|---:|---:|---|",
    ])
    for run in trials["runs"]:
        failed = [criterion["id"] for criterion in run["criteria"] if not criterion["passed"]]
        failed.extend(f"forbidden:{pattern}" for pattern in run["forbidden_hits"])
        lines.append(f"| {run['id']} | {run['score']:.3f} | {_mark(run['passed'])} | {', '.join(failed) or 'None'} |")

    lines.extend(["", "## Failure patterns", ""])
    failures = stages["evidence_audit"]["failure_classes"]
    if failures:
        lines.extend(f"- **{failure}:** {count} occurrence(s)" for failure, count in failures.items())
    else:
        lines.append("No recurring failure classes were observed.")

    spend = stages["spend_summary"]
    lines.extend([
        "",
        "## Performance and spend",
        "",
        f"- Total recorded cost: ${spend['total_cost_usd']:.6f}",
        f"- Average recorded cost: {('$' + format(spend['average_cost_usd'], '.6f')) if spend['average_cost_usd'] is not None else 'Not supplied'}",
        f"- Average latency: {(format(spend['average_latency_ms'], '.2f') + ' ms') if spend['average_latency_ms'] is not None else 'Not supplied'}",
        "",
        "## Interpretation",
        "",
        "A release decision requires a valid specification, acceptable task originality, discriminating anchor controls, and the configured pass rate across repeated trials. Criterion-level failures remain visible even when the aggregate gate passes.",
    ])
    return "\n".join(lines) + "\n"
