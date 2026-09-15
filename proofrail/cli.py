from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from typing import Any

from .engine import run_review
from .report import markdown_report


def load_json(path: str | Path) -> Any:
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_evaluators(path: str | None) -> dict[str, Any]:
    if not path:
        return {}
    module_path = Path(path).resolve()
    module_spec = importlib.util.spec_from_file_location("proofrail_user_evaluators", module_path)
    if module_spec is None or module_spec.loader is None:
        raise ValueError(f"could not load evaluator module: {module_path}")
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    evaluators = getattr(module, "EVALUATORS", None)
    if not isinstance(evaluators, dict) or not all(callable(value) for value in evaluators.values()):
        raise ValueError("custom evaluator module must expose an EVALUATORS dictionary of callables")
    return evaluators


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="proofrail", description="Review model outputs against an auditable release gate")
    subparsers = parser.add_subparsers(dest="command", required=True)
    review = subparsers.add_parser("review", help="run a Proofrail evaluation review")
    review.add_argument("--spec", required=True, help="path to the evaluation specification JSON")
    review.add_argument("--runs", required=True, help="path to model run JSON")
    review.add_argument("--corpus", help="optional comparison corpus JSON")
    review.add_argument("--out", default="artifacts", help="output directory")
    review.add_argument("--evaluators", help="optional trusted Python module exposing an EVALUATORS dictionary")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    spec = load_json(args.spec)
    runs = load_json(args.runs)
    corpus = load_json(args.corpus) if args.corpus else []
    result = run_review(spec, runs, corpus, load_evaluators(args.evaluators))

    output_directory = Path(args.out)
    output_directory.mkdir(parents=True, exist_ok=True)
    (output_directory / "proofrail-results.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    (output_directory / "proofrail-report.md").write_text(markdown_report(result), encoding="utf-8")

    print(f"Proofrail decision: {result['decision']}")
    print(f"Report: {output_directory / 'proofrail-report.md'}")
    return 0 if result["decision"] == "RELEASE" else 1
