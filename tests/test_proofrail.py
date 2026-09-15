import unittest
import json
from pathlib import Path

from proofrail.checks import cosine_similarity, normalize_run_text, score_output, validate_runs, validate_spec
from proofrail.engine import run_review
from proofrail.preflight import SURFACE_NAMES, run_preflight


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
