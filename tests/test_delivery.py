"""Real assets plus adversarial mutations of a known-correct miniature figure batch."""
from __future__ import annotations

from copy import deepcopy
import csv
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".agents/skills/cumcm-figure-orchestrator/scripts"))
from qa_evidence import make_evidence
from route_figures import route_manifest
from score_providers import load_scorecard
from validate_manifest import COMMON_FORMAL_CHECKS, validate_manifest
from finalize_manifest import finalize
from verify_numeric import compare_tables
from matplotlib_layout_qa import inspect_figure_layout


def fixture(directory: Path) -> dict:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    (directory/"paper.md").write_text("Synthetic test only. A=2 and B=4 units. No empirical claim.", encoding="utf-8")
    (directory/"raw.csv").write_text("group,value\nA,1\nA,3\nB,2\nB,6\n", encoding="utf-8")
    (directory/"render.py").write_text("# Test renderer: group means from raw.csv\n", encoding="utf-8")
    (directory/"verify.py").write_text("# Independent test reference: A=(1+3)/2; B=(2+6)/2\n", encoding="utf-8")
    (directory/"expected.csv").write_text("group,value\nA,2\nB,4\n", encoding="utf-8")
    fig, ax = plt.subplots(figsize=(120/25.4, 80/25.4), layout="constrained")
    ax.plot([0,1], [2,4], marker="o")
    ax.set_xticks([0,1], ["A", "B"])
    ax.set_ylabel("Mean (units)")
    with (directory/"plotted.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle); writer.writerow(["group","value"])
        writer.writerows(zip(["A","B"], ax.lines[0].get_ydata()))
    fig.savefig(directory/"figure.png", dpi=320)
    fig.savefig(directory/"figure.svg")
    plt.close(fig)
    f = {"figure_id":"f1","status":"formal","task_type":"data_chart",
         "claim":"A=2 and B=4 units", "caption":"Synthetic means", "paper_anchor":"paper.md, sentence 2",
         "sources":["paper.md","raw.csv"],"data_source":"raw.csv","code_path":"render.py",
         "final_width_mm":120,"constraints":{"exact_numeric":True,"exact_text":True,
         "vector_required":True,"reproducible_required":True,"contains_text":True},
         "data_contract":{"input_files":["raw.csv"],"fields":[{"name":"value","unit":"units","source":"raw.csv/value"}],
          "observation_unit":"one observation", "keys":["group"],"time_scope":"not temporal",
          "missing_policy":"reject", "duplicate_policy":"group repeated observations by mean",
          "transformations":["arithmetic group mean"],"verification_method":"independent two-value arithmetic",
          "reference_data":"expected.csv","plotted_data":"plotted.csv","verification_code":"verify.py",
          "numeric_columns":["value"],"atol":1e-9,"rtol":1e-7,"tolerance_reason":"floating point mean"}}
    m = route_manifest({"schema_version":2,"batch_id":"unit-fixture","competition_profile":"cumcm",
        "paper":{"title":"Synthetic fixture","source_path":"paper.md"},"figures":[f],
        "target_figure_ids":["f1"],"layout":{"page_width_mm":210,"margin_left_mm":25,"margin_right_mm":25,"min_dpi":300}}, load_scorecard())
    m["delivery_status"]="ready"
    f=m["figures"][0]; f["pipeline_state"]="verified"
    f["outputs"]={"png":"figure.png","svg":"figure.svg","source":"render.py"}
    f["provenance"]={"renderer_version":matplotlib.__version__,"actual_provider":f["route"]["provider"],
      "render_command":"unit fixture in tests/test_delivery.py", "ai_assisted":False,
      "verification_method":"known-answer automated fixture, not a human-reviewed scientific deliverable"}
    f["qa"]={}
    for key in (*COMMON_FORMAL_CHECKS, "numeric_check", "ocr_check"):
        result={"status":"pass","method":"Synthetic acceptance fixture; not a production review"}
        record=make_evidence(f,m["paper"],m["layout"],key,result,directory,"unittest fixture 2", "synthetic-test")
        path=f"{key}.json"
        (directory/path).write_text(json.dumps(record),encoding="utf-8")
        f["qa"][key]={"status":"pass","method":result["method"],"evidence":path}
    return m


class DeliveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.seed=tempfile.TemporaryDirectory()
        cls.manifest=fixture(Path(cls.seed.name))
        cls.scorecard=load_scorecard()

    @classmethod
    def tearDownClass(cls):
        cls.seed.cleanup()

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name)
        shutil.copytree(self.seed.name,self.base,dirs_exist_ok=True)
        self.m=deepcopy(self.manifest)
        self.f=self.m["figures"][0]

    def errors(self):
        return validate_manifest(self.m,self.scorecard,strict=True,base_dir=self.base)[0]

    def test_real_png_svg_and_numeric_reference_pass(self):
        self.assertEqual(self.errors(),[])

    def test_missing_source_rejected(self):
        (self.base/"raw.csv").unlink()
        self.assertTrue(any("raw.csv" in e for e in self.errors()))

    def test_markdown_as_png_and_svg_rejected(self):
        self.f["outputs"].update(png="paper.md",svg="paper.md")
        errors=self.errors()
        self.assertTrue(any("invalid PNG" in e for e in errors))
        self.assertTrue(any("invalid SVG" in e for e in errors))

    def test_strict_cannot_disable_file_checks(self):
        (self.base/"figure.png").unlink()
        errors,_=validate_manifest(self.m,self.scorecard,strict=True,check_files=False,base_dir=self.base)
        self.assertTrue(any("invalid PNG" in e for e in errors))

    def test_numeric_flag_cannot_remove_data_check(self):
        self.f["constraints"]["exact_numeric"]=False
        del self.f["qa"]["numeric_check"]
        self.assertTrue(any("numeric_check" in e for e in self.errors()))

    def test_failed_evidence_cannot_be_promoted_by_pass_text(self):
        path=self.base/"collision_check.json"
        record=json.loads(path.read_text()); record["result"]["status"]="fail"
        path.write_text(json.dumps(record))
        self.assertTrue(any("evidence result is not pass" in e for e in self.errors()))

    def test_source_mutation_invalidates_old_qa(self):
        (self.base/"raw.csv").write_text("group,value\nA,999\n")
        self.assertTrue(any("stale evidence: raw.csv" in e for e in self.errors()))

    def test_output_mutation_invalidates_old_qa(self):
        path=self.base/"figure.png"
        path.write_bytes(path.read_bytes()+b"changed")
        self.assertTrue(any("stale evidence: figure.png" in e for e in self.errors()))

    def test_caption_mutation_invalidates_old_qa(self):
        self.f["caption"]="Changed claim"
        self.assertTrue(any("specification changed" in e for e in self.errors()))

    def test_wrong_plotted_numbers_fail_independent_recheck(self):
        (self.base/"plotted.csv").write_text("group,value\nA,200\nB,4\n")
        self.assertTrue(any("recomputation failed" in e for e in self.errors()))

    def test_same_reference_and_plotted_file_rejected(self):
        self.f["data_contract"]["reference_data"]="plotted.csv"
        self.assertTrue(any("separate reference" in e for e in self.errors()))

    def test_failed_solver_cannot_be_passed_by_qa(self):
        self.f["data_contract"]["model"]={"parameters":"test", "seed":None,
            "solver_status":"infeasible", "reproduction_status":"blocked"}
        self.assertTrue(any("model/solver" in e for e in self.errors()))

    def test_raster_embedded_svg_rejected(self):
        (self.base/"figure.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 80"><rect width="120" height="80"/><image href="figure.png"/></svg>')
        self.assertTrue(any("embeds raster" in e for e in self.errors()))

    def test_low_resolution_png_rejected(self):
        from PIL import Image
        Image.new("RGB",(120,80),"white").save(self.base/"figure.png")
        self.assertTrue(any("min_dpi" in e for e in self.errors()))

    def test_malformed_evidence_fails_closed(self):
        (self.base/"visual_review.json").write_text('[]')
        self.assertTrue(any("invalid evidence" in e for e in self.errors()))

    def test_missing_visual_reviewer_rejected(self):
        path=self.base/"visual_review.json"
        record=json.loads(path.read_text()); record["reviewer"]=None
        path.write_text(json.dumps(record))
        self.assertTrue(any("reviewer identity" in e for e in self.errors()))

    def test_duplicate_or_nonfinite_numeric_rows_rejected(self):
        for content in ("group,value\nA,2\nA,4\n", "group,value\nA,nan\nB,4\n"):
            (self.base/"plotted.csv").write_text(content)
            with self.assertRaises(ValueError):
                compare_tables(self.base/"expected.csv",self.base/"plotted.csv",["group"],["value"])

    def test_zero_formal_and_missing_target_rejected(self):
        self.f.update(status="excluded",exclusion_reason="test")
        errors=self.errors()
        self.assertTrue(any("no formal figures" in e for e in errors))
        self.assertTrue(any("undelivered target" in e for e in errors))

    def test_schema_types_and_identifiers_rejected(self):
        self.f.update(figure_id="BAD ID!",final_width_mm=True)
        self.assertTrue(any("schema" in e for e in self.errors()))

    def test_null_width_returns_error_not_exception(self):
        self.f["final_width_mm"]=None
        self.assertTrue(self.errors())

    def test_oversized_figure_rejected(self):
        self.f["final_width_mm"]=180
        self.assertTrue(any("content width" in e for e in self.errors()))

    def test_composite_requires_panels(self):
        self.f["task_type"]="composite"
        self.assertTrue(any("panels" in e for e in self.errors()))

    def test_blocked_panel_prevents_delivery(self):
        panel=deepcopy(self.f); panel.update(figure_id="panel1",pipeline_state="blocked")
        self.f.update(task_type="composite",panels=[panel])
        self.assertTrue(any("panel1.pipeline_state" in e for e in self.errors()))

    def test_finalize_preserves_failed_check_and_original(self):
        self.f["qa"]["collision_check"]["status"]="fail"
        before=deepcopy(self.m)
        candidate,errors,_=finalize(self.m,self.base)
        self.assertIsNone(candidate)
        self.assertTrue(errors)
        self.assertEqual(self.m,before)

    def test_finalize_valid_evidence_succeeds(self):
        self.f["pipeline_state"]="rendered"
        self.m["delivery_status"]="partial"
        candidate,errors,_=finalize(self.m,self.base)
        self.assertEqual(errors,[])
        self.assertEqual(candidate["delivery_status"],"ready")

    def test_runtime_fallback_keeps_numeric_constraints(self):
        environment=[{"id":"ggplot2-ggrepel","status":"available"}]
        result=route_manifest(self.m,self.scorecard,environment)
        self.assertEqual(result["figures"][0]["route"]["provider"],"ggplot2-ggrepel")
        result=route_manifest(self.m,self.scorecard,[])
        self.assertEqual(result["figures"][0]["pipeline_state"],"blocked")

    def test_ignored_text_still_checked_for_clipping(self):
        import matplotlib.pyplot as plt
        figure=plt.figure(figsize=(3,2))
        text=figure.text(1.5,0.5,"outside")
        result=inspect_figure_layout(figure,ignored_artists=[text])
        plt.close(figure)
        self.assertEqual(result["status"],"fail")
        self.assertTrue(result["clipped"])

    def test_style_profile_requires_six_bound_checks(self):
        self.f['style_policy']={'profile_id':'developer-v02-style-v2','baseline_id':'personal-cumcm-v02',
                                'input_files':['render.py']}
        errors=self.errors()
        for name in ('panel_size_uniformity','text_solid_stroke_clearance','legend_data_region_clearance',
                     'axes_frame_closed','panel_aspect_whitelist','curve_smoothing'):
            self.assertTrue(any(name in e and 'missing' in e for e in errors), name)

    def test_style_config_mutation_invalidates_evidence(self):
        (self.base/'style.json').write_text('{"padding":4}')
        self.f['style_policy']={'profile_id':'test','baseline_id':'test','input_files':['style.json']}
        result={'status':'pass','method':'Synthetic binding fixture, not a visual review'}
        evidence=make_evidence(self.f,self.m['paper'],self.m['layout'],'panel_size_uniformity',result,self.base,'unittest')
        from qa_evidence import validate_evidence
        self.assertEqual(validate_evidence(evidence,self.f,self.m['paper'],self.m['layout'],'panel_size_uniformity',self.base),[])
        (self.base/'style.json').write_text('{"padding":0}')
        self.assertTrue(any('stale evidence: style.json' in e for e in validate_evidence(
            evidence,self.f,self.m['paper'],self.m['layout'],'panel_size_uniformity',self.base)))


if __name__ == "__main__":
    unittest.main()
