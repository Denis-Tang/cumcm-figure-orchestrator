import importlib.util
from pathlib import Path
import unittest
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / ".agents/skills/cumcm-figure-orchestrator/scripts/matplotlib_style_qa.py"
spec = importlib.util.spec_from_file_location("matplotlib_style_qa", MODULE)
qa = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = qa
spec.loader.exec_module(qa)


class MatplotlibStyleQATest(unittest.TestCase):
    def tearDown(self):
        plt.close("all")

    def test_closed_frame_helper_passes(self):
        fig, ax = plt.subplots(figsize=(4, 3))
        qa.apply_closed_cartesian_style(ax)
        result = qa.run_style_qa(fig)
        codes = {item["code"] for item in result["issues"]}
        self.assertNotIn("open_cartesian_frame", codes)
        self.assertNotIn("unexpected_top_ticks", codes)
        self.assertNotIn("unexpected_right_ticks", codes)

    def test_open_frame_is_rejected(self):
        fig, ax = plt.subplots(figsize=(4, 3))
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        issues = qa.check_closed_frame(fig)
        self.assertTrue(any(item.code == "open_cartesian_frame" for item in issues))

    def test_top_and_right_ticks_need_explicit_exception(self):
        fig, ax = plt.subplots(figsize=(4, 3))
        qa.apply_closed_cartesian_style(ax, right_ticks=True, top_ticks=True)
        issues = qa.check_default_tick_sides(fig)
        codes = {item.code for item in issues}
        self.assertIn("unexpected_top_ticks", codes)
        self.assertIn("unexpected_right_ticks", codes)
        self.assertEqual(qa.check_default_tick_sides(fig, allow_axes=[0]), [])

    def test_extreme_flat_panel_is_rejected(self):
        fig, ax = plt.subplots(figsize=(10, 1.3))
        qa.apply_closed_cartesian_style(ax)
        issues = qa.check_panel_aspect_ratios(fig)
        self.assertTrue(any(item.code == "extreme_panel_aspect" for item in issues))

    def test_peer_panel_imbalance_is_rejected(self):
        fig = plt.figure(figsize=(8, 4))
        gs = fig.add_gridspec(1, 3)
        a = fig.add_subplot(gs[0, :2])
        b = fig.add_subplot(gs[0, 2])
        qa.apply_closed_cartesian_style(a)
        qa.apply_closed_cartesian_style(b)
        issues = qa.check_peer_panel_area_balance(fig, [a, b])
        self.assertTrue(any(item.code == "peer_panel_area_imbalance" for item in issues))

    def test_text_on_solid_line_is_rejected(self):
        fig, ax = plt.subplots(figsize=(4, 3))
        qa.apply_closed_cartesian_style(ax)
        ax.plot([0, 1], [0.5, 0.5], color="black")
        ax.text(0.5, 0.5, "label", ha="center", va="center")
        issues = qa.check_text_line_clearance(fig, clearance_px=4)
        self.assertTrue(any(item.code == "text_line_clearance" and item.severity == "error" for item in issues))



class StyleEdgeCaseTests(unittest.TestCase):
    def tearDown(self):
        plt.close('all')

    def test_long_segment_crossing_small_text(self):
        fig, ax = plt.subplots(figsize=(12, 3))
        ax.plot([0, 100], [.5, .5])
        ax.text(3.1, .5, '.', fontsize=7)
        self.assertTrue(qa.check_text_line_clearance(fig, clearance_px=1))

    def test_gap_is_not_a_line(self):
        fig, ax = plt.subplots(figsize=(4, 3))
        ax.plot([0, .2, float('nan'), .8, 1], [.5]*5)
        ax.text(.5, .5, 'x', ha='center')
        self.assertEqual(qa.check_text_line_clearance(fig), [])

    def test_minor_ticks_are_checked(self):
        fig, ax = plt.subplots()
        ax.minorticks_on()
        ax.tick_params(which='minor', top=True)
        self.assertTrue(qa.check_default_tick_sides(fig))
        qa.apply_closed_cartesian_style(ax)
        self.assertEqual(qa.check_default_tick_sides(fig), [])

    def test_non_data_axes_are_excluded(self):
        fig, ax = plt.subplots(figsize=(4, 3))
        im=ax.imshow([[1,2],[3,4]])
        fig.colorbar(im, ax=ax)
        flow=fig.add_axes([.1,.1,.01,.01])
        qa.set_style_role(flow, 'flowchart', reason='node diagram')
        flow.spines['top'].set_visible(False)
        polar=fig.add_axes([.1,.1,.2,.2], projection='polar')
        self.assertEqual(qa.check_closed_frame(fig), [])
        self.assertEqual(qa.check_panel_aspect_ratios(fig), [])

    def test_twin_uses_single_frame(self):
        fig, ax = plt.subplots(figsize=(4,3))
        twin=ax.twinx()
        qa.apply_closed_cartesian_style(twin, right_ticks=True, frame_owner=ax)
        self.assertEqual(qa.check_closed_frame(fig), [])
        self.assertEqual(qa.check_default_tick_sides(fig, allow_axes=[1]), [])
        self.assertTrue(all(s.get_visible() for s in ax.spines.values()))
        self.assertTrue(all(not s.get_visible() for s in twin.spines.values()))

    def test_annotation_arrow_is_not_text_bbox(self):
        fig, ax = plt.subplots(figsize=(4,3))
        ax.plot([0,1],[.3,.3])
        ax.set_ylim(0,1)
        ax.annotate('label',xy=(.5,.3),xytext=(.5,.8),arrowprops={'arrowstyle':'->'})
        self.assertEqual(qa.check_text_line_clearance(fig), [])


if __name__ == "__main__":
    unittest.main()
