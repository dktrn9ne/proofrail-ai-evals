import unittest
import json
import copy
from pathlib import Path

from proofrail.checks import cosine_similarity, normalize_run_text, score_output, validate_runs, validate_spec
from proofrail.engine import run_review
from proofrail.preflight import SURFACE_NAMES, run_preflight
from proofrail.report import markdown_report
from proofrail.cli import main
import tempfile


def sample_spec():
    return {
        "id": "sample",
        "name": "Sample evaluation",
        "objective": "Require a safe answer",
        "rubric": [
            {"id": "safe", "description": "safe", "weight": 1.0, "evaluator": "contains_all", "params": {"terms": ["safe"]}}
        ],
        "controls": {"oracle": "safe", "negative": ""},
        "gate": {"min_score": 1.0, "min_pass_rate": 0.5, "max_overlap": 0.9},
    }


class ProofrailTests(unittest.TestCase):
    def example_inputs(self):
        root = Path(__file__).resolve().parents[1] / "examples"
        return tuple(json.loads((root / path).read_text(encoding="utf-8")) for path in (
            "ledgerkit/spec.json", "ledgerkit/runs.json", "regression-corpus/corpus.json"))

    def test_review_enforces_trial_coverage(self):
        spec, runs, corpus = self.example_inputs()
        required = spec["gate"]["min_trials"]
        for count in (1, required - 1, required):
            with self.subTest(count=count):
                result = run_review(spec, runs[:count], corpus)
                self.assertEqual(result["decision"], "RELEASE" if count >= required else "BLOCK")
                self.assertEqual(result["stages"]["trial_scoring"]["coverage_passed"], count >= required)
                coverage = next(s for s in run_preflight(spec, runs[:count], corpus)["surfaces"] if s["name"] == "trial_coverage")
                self.assertEqual(coverage["passed"], count >= required)
                self.assertIn(f"required trials {required}", markdown_report(result))

    def test_invalid_min_trials_blocks_both_paths(self):
        spec, runs, corpus = self.example_inputs()
        for value in (0, -1, True, 1.5, "3", None):
            with self.subTest(value=value):
                spec["gate"]["min_trials"] = value
                self.assertEqual(run_review(spec, runs, corpus)["decision"], "BLOCK")
                self.assertEqual(run_preflight(spec, runs, corpus)["decision"], "BLOCK")

    def test_malformed_rubric_blocks_without_exception(self):
        spec, runs, corpus = self.example_inputs()
        for value in (None, "criterion", 7, [], True):
            for rubric in ([value], [copy.deepcopy(spec["rubric"][0]), value]):
                with self.subTest(value=value, mixed=len(rubric) > 1):
                    bad = copy.deepcopy(spec)
                    bad["rubric"] = rubric
                    review = run_review(bad, runs, corpus)
                    self.assertEqual(review["decision"], "BLOCK")
                    self.assertTrue(any("must be an object" in e for e in review["stages"]["intake_scan"]["errors"]))
                    preflight = run_preflight(bad, runs, corpus)
                    self.assertEqual(preflight["decision"], "BLOCK")
                    self.assertEqual(preflight["total_count"], 21)

    def test_nonfinite_and_boolean_telemetry_blocks_both_paths(self):
        spec, runs, corpus = self.example_inputs()
        for field in ("cost_usd", "latency_ms"):
            for value in (float("inf"), float("-inf"), float("nan"), True):
                with self.subTest(field=field, value=value):
                    bad = copy.deepcopy(runs)
                    bad[0][field] = value
                    self.assertTrue(validate_runs(bad))
                    self.assertEqual(run_review(spec, bad, corpus)["decision"], "BLOCK")
                    result = run_preflight(spec, bad, corpus)
                    self.assertFalse(next(s for s in result["surfaces"] if s["name"] == "trial_integrity")["passed"])

    def test_finite_zero_telemetry_is_valid(self):
        self.assertEqual(validate_runs([{"id": "zero", "output": "safe", "cost_usd": 0, "latency_ms": 0.0}]), [])

    def test_duplicate_ids_cannot_inflate_coverage(self):
        spec, runs, corpus = self.example_inputs()
        duplicates = [copy.deepcopy(runs[0]) for _ in range(spec["gate"]["min_trials"])]
        self.assertEqual(run_review(spec, duplicates, corpus)["decision"], "BLOCK")
        self.assertEqual(run_preflight(spec, duplicates, corpus)["decision"], "BLOCK")

    def test_cli_blocks_and_writes_reports_for_invalid_inputs(self):
        spec, runs, corpus = self.example_inputs()
        cases = [(spec, runs[:1]), ({**spec, "rubric": [None]}, runs),
                 (spec, [{**runs[0], "cost_usd": float("inf")}, *runs[1:]])]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for command in ("review", "preflight"):
                for bad_spec, bad_runs in cases:
                    for name, value in (("spec", bad_spec), ("runs", bad_runs), ("corpus", corpus)):
                        (root / f"{name}.json").write_text(json.dumps(value), encoding="utf-8")
                    self.assertEqual(main([command, "--spec", str(root / "spec.json"), "--runs", str(root / "runs.json"),
                                           "--corpus", str(root / "corpus.json"), "--out", str(root / "out")]), 1)
                    report = "proofrail-results.json" if command == "review" else "proofrail-preflight.json"
                    self.assertEqual(json.loads((root / "out" / report).read_text())["decision"], "BLOCK")

    def test_valid_spec(self):
        self.assertEqual(validate_spec(sample_spec()), [])

    def test_run_envelope_validation(self):
        self.assertEqual(validate_runs([{"id": "one", "output": "hello"}]), [])
        self.assertTrue(validate_runs([{"id": "one", "latency_ms": -1}]))

    def test_invalid_weights(self):
        spec = sample_spec()
        spec["rubric"][0]["weight"] = 0.5
        self.assertTrue(any("sum to 1.0" in error for error in validate_spec(spec)))

    def test_controls_discriminate(self):
        result = run_review(sample_spec(), [{"id": "one", "output": "safe"}])
        self.assertTrue(result["stages"]["anchor_controls"]["passed"])
        self.assertEqual(result["decision"], "RELEASE")

    def test_forbidden_pattern_zeros_score(self):
        spec = sample_spec()
        spec["forbidden_patterns"] = ["bypass"]
        result = score_output(spec, {"id": "bad", "output": "safe bypass"})
        self.assertEqual(result["score"], 0.0)
        self.assertFalse(result["passed"])

    def test_similarity_bounds(self):
        self.assertAlmostEqual(cosine_similarity("same words", "same words"), 1.0)
        self.assertEqual(cosine_similarity("alpha", "zebra"), 0.0)

    def test_structured_output_is_supported(self):
        result = score_output(sample_spec(), {"id": "json", "output": {"status": "safe"}})
        self.assertTrue(result["passed"])

    def test_agent_trace_and_tools_are_normalized(self):
        run = {
            "output": {"decision": "reject"},
            "tool_calls": [{"name": "verify", "status": "success"}],
            "trace": [{"event": "completed"}],
        }
        text = normalize_run_text(run)
        self.assertIn("verify", text)
        self.assertIn("completed", text)

    def test_tool_evaluators(self):
        spec = sample_spec()
        spec["rubric"] = [
            {"id": "tool", "description": "tool", "weight": 0.5, "evaluator": "tool_called", "params": {"names": ["verify"]}},
            {"id": "success", "description": "success", "weight": 0.5, "evaluator": "tool_success_rate", "params": {"minimum": 1.0}},
        ]
        run = {"id": "agent", "output": "done", "tool_calls": [{"name": "verify", "status": "success"}]}
        self.assertTrue(score_output(spec, run)["passed"])

    def test_agent_envelope_controls(self):
        spec = sample_spec()
        spec["rubric"] = [
            {"id": "tool", "description": "tool", "weight": 1.0, "evaluator": "tool_called", "params": {"names": ["verify"]}}
        ]
        spec["controls"] = {
            "oracle": {"output": "done", "tool_calls": [{"name": "verify", "status": "success"}]},
            "negative": {"output": "done", "tool_calls": []},
        }
        result = run_review(spec, [{"id": "one", "output": "done", "tool_calls": [{"name": "verify", "status": "success"}]}])
        self.assertTrue(result["stages"]["anchor_controls"]["passed"])

    def test_custom_evaluator_is_accepted(self):
        spec = sample_spec()
        spec["rubric"][0]["evaluator"] = "always_one"
        evaluators = {"always_one": lambda criterion, run, text: (1.0, "custom pass")}
        result = run_review(spec, [{"id": "one", "output": "anything"}], custom_evaluators=evaluators)
        self.assertTrue(result["stages"]["trial_scoring"]["runs"][0]["passed"])

    def test_preflight_has_exactly_21_named_surfaces(self):
        self.assertEqual(len(SURFACE_NAMES), 21)
        self.assertEqual(len(set(SURFACE_NAMES)), 21)

    def test_example_preflight_passes_all_surfaces(self):
        root = Path(__file__).resolve().parents[1]
        spec = json.loads((root / "examples" / "ledgerkit" / "spec.json").read_text(encoding="utf-8"))
        runs = json.loads((root / "examples" / "ledgerkit" / "runs.json").read_text(encoding="utf-8"))
        corpus = json.loads((root / "examples" / "regression-corpus" / "corpus.json").read_text(encoding="utf-8"))
        result = run_preflight(spec, runs, corpus)
        self.assertEqual(result["total_count"], 21)
        self.assertEqual(result["decision"], "PASS", [surface for surface in result["surfaces"] if not surface["passed"]])


if __name__ == "__main__":
    unittest.main()
