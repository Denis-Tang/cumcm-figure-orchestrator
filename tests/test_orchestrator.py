from __future__ import annotations

import json
import sys
import unittest
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / ".agents" / "skills" / "cumcm-figure-orchestrator"
SCRIPTS = SKILL / "scripts"
sys.path.insert(0, str(SCRIPTS))

from matplotlib_layout_qa import inspect_figure_layout  # noqa: E402
from route_figures import route_manifest  # noqa: E402
from score_providers import load_scorecard, rank_providers  # noqa: E402
from validate_manifest import validate_manifest  # noqa: E402


class OrchestratorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.scorecard = load_scorecard()
        cls.plan = json.loads((ROOT / "examples" / "paper-plan.json").read_text(encoding="utf-8"))

    def test_exact_data_chart_rejects_image_generators(self) -> None:
        ranked, rejected = rank_providers(
            self.scorecard,
            "data_chart",
            {
                "exact_numeric": True,
                "exact_text": True,
                "vector_required": True,
                "reproducible_required": True,
                "formal_final": True,
            },
        )
        self.assertEqual(ranked[0]["id"], "matplotlib-seaborn")
        rejected_ids = {item["id"] for item in rejected}
        self.assertIn("openai-imagegen", rejected_ids)
        self.assertIn("engineering-figure-agent", rejected_ids)

    def test_example_plan_matches_json_schema(self) -> None:
        try:
            import jsonschema
        except ImportError:
            self.skipTest("jsonschema is not installed")
        schema = json.loads((SKILL / "assets" / "figure-manifest.schema.json").read_text(encoding="utf-8"))
        jsonschema.validate(self.plan, schema)

    def test_routes_formal_flowchart_to_d2(self) -> None:
        routed = route_manifest(self.plan, self.scorecard)
        by_id = {item["figure_id"]: item for item in routed["figures"]}
        self.assertEqual(by_id["fig_01_solution_overview"]["route"]["provider"], "d2-elk")
        self.assertEqual(by_id["fig_01_solution_overview"]["route"]["skill"], "cumcm-figure-orchestrator")
        self.assertEqual(by_id["fig_02_model_error"]["route"]["provider"], "matplotlib-seaborn")
        self.assertEqual(by_id["fig_02_model_error"]["route"]["skill"], "data-analytics:visualize-data")
        self.assertEqual(by_id["alt_01_delivery_scene"]["route"]["provider"], "engineering-figure-agent")

    def test_self_reported_legacy_pass_is_rejected(self) -> None:
        completed = route_manifest(deepcopy(self.plan), self.scorecard)
        completed.pop("schema_version", None)
        for figure in completed["figures"]:
            if figure["status"] != "formal":
                continue
            figure["outputs"] = {
                "png": f"figures/{figure['figure_id']}.png",
                "svg": f"figures/{figure['figure_id']}.svg",
                "pdf": None,
                "source": f"src/{figure['figure_id']}.txt",
            }
            figure["provenance"] = {
                "renderer_version": "test-renderer 1.0",
                "ai_assisted": False,
                "ai_tool_and_version": None,
                "prompt_summary": None,
                "ai_output_adopted": "none",
                "human_edits": None,
                "verification_method": "Compared against frozen example sources.",
            }
            method = "Automated test fixture check."
            figure["qa"] = {
                key: {"status": "pass", "method": method}
                for key in (
                    "numeric_check",
                    "ocr_check",
                    "collision_check",
                    "clipping_check",
                    "grayscale_check",
                    "export_check",
                    "claim_caption_check",
                )
            }
        errors, warnings = validate_manifest(completed, self.scorecard, strict=True)
        self.assertTrue(any("schema_version" in error for error in errors))
        self.assertTrue(any("missing evidence" in error for error in errors))
        self.assertTrue(any("6-12" in warning for warning in warnings))

    def test_strict_gate_rejects_ai_renderer_and_missing_qa(self) -> None:
        invalid = route_manifest(deepcopy(self.plan), self.scorecard)
        figure = invalid["figures"][1]
        figure["route"]["provider"] = "openai-imagegen"
        errors, _ = validate_manifest(invalid, self.scorecard, strict=True)
        self.assertTrue(any("missing capability: exact_numeric" in error for error in errors))
        self.assertTrue(any("qa" in error for error in errors))

    def test_matplotlib_overlap_screen_detects_collision(self) -> None:
        try:
            import matplotlib.pyplot as plt
        except ImportError:
            self.skipTest("matplotlib is not installed")
        figure = plt.figure(figsize=(3, 2), dpi=100)
        figure.text(0.5, 0.5, "overlap", ha="center")
        figure.text(0.5, 0.5, "overlap", ha="center")
        result = inspect_figure_layout(figure)
        plt.close(figure)
        self.assertEqual(result["status"], "fail")
        self.assertGreaterEqual(len(result["collisions"]), 1)


if __name__ == "__main__":
    unittest.main()
