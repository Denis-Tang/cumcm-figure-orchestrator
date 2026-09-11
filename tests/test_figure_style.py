import json
import sys
import unittest
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / '.agents/skills/cumcm-figure-orchestrator'
sys.path.insert(0, str(SKILL / 'scripts'))
from figure_style import load_style, select_colors, matplotlib_style, declare_continuity, apply_closed_cartesian_style
from matplotlib_layout_qa import inspect_figure_layout


class StyleTests(unittest.TestCase):
    def tearDown(self):
        plt.close('all')

    def test_categorical_counts_and_artist_colors(self):
        for n in range(1, 6):
            keys = list('ABCDE')[:n]
            mapping = select_colors(keys)
            self.assertEqual([v['role'] for v in mapping.values()], ['blue','coral','amber','violet','teal'][:n])
            with plt.rc_context(matplotlib_style()):
                fig, ax = plt.subplots()
                for key in keys:
                    line, = ax.plot([0,1], [0,1], color=mapping[key]['colors'])
                    self.assertEqual(line.get_color(), mapping[key]['colors'])
        with self.assertRaises(ValueError): select_colors(list('ABCDEF'))

    def test_semantic_override_and_stable_mapping(self):
        mapping = select_colors(['vegetation','other'], overrides={'vegetation': {'role':'teal','reason':'vegetation convention'}})
        self.assertEqual(mapping['vegetation']['role'], 'teal')
        self.assertEqual(select_colors(['other','vegetation'], existing=mapping), {'other':mapping['other'],'vegetation':mapping['vegetation']})
        with self.assertRaises(ValueError): select_colors(['A'], overrides={'A':{'role':'teal'}})

    def test_v02_is_the_single_immutable_baseline(self):
        _, palette = load_style()
        self.assertEqual(palette['colors'], dict(blue='#2389DA',coral='#D95B52',amber='#E5A33D',teal='#49A88D',violet='#8876AF',slate='#687D91'))
        self.assertEqual(palette, json.loads((SKILL/'assets/personal-color-baseline-v02.json').read_text()))
        self.assertEqual(palette['baseline_id'], 'personal-cumcm-v02')
        self.assertFalse((SKILL/'assets/personal-color-baseline-v03.json').exists())
        self.assertFalse((SKILL/'assets/personal-color-baseline-v03.png').exists())
        for path in SKILL.rglob('*'):
            if path.is_file() and path.suffix in {'.md','.json','.py','.yaml','.ps1'}:
                self.assertNotIn('v03', path.read_text(encoding='utf-8',errors='ignore').lower(), path)
        self.assertEqual(json.loads((SKILL/'assets/personal-figure-style.json').read_text())['profile_id'], 'developer-v02-style-v2')

    def test_closed_frame_is_required(self):
        with plt.rc_context(matplotlib_style()):
            fig, ax = plt.subplots()
            result = inspect_figure_layout(fig)['axes_frame_closed']
            self.assertEqual(result['status'], 'pass')
            self.assertEqual(result['panels'][0]['hidden_spines'], [])
            self.assertEqual(result['panels'][0]['tick_sides'], ['bottom', 'left'])
            ax.spines[['right','top']].set_visible(False)
            result = inspect_figure_layout(fig)['axes_frame_closed']
            self.assertEqual(result['status'], 'fail')
            self.assertEqual(result['panels'][0]['hidden_spines'], ['right','top'])
            result = inspect_figure_layout(fig, frame_exemptions={'axes[0]':'shared edge with the adjacent panel'})['axes_frame_closed']
            self.assertEqual(result['status'], 'pass')
            self.assertTrue(result['panels'][0]['exception_applied'])

    def test_non_cartesian_axes_are_skipped_not_failed(self):
        fig = plt.figure()
        fig.add_subplot(projection='polar')
        result = inspect_figure_layout(fig)['axes_frame_closed']
        self.assertEqual(result['status'], 'pass')
        self.assertTrue(any('polar' in item['reason'] for item in result['skipped']))

    def test_apply_closed_cartesian_style_restores_the_frame(self):
        fig, ax = plt.subplots()
        ax.spines[['right','top']].set_visible(False)
        ax.tick_params(bottom=False, labelbottom=False, left=False, labelleft=False)
        self.assertEqual(inspect_figure_layout(fig)['axes_frame_closed']['status'], 'fail')
        apply_closed_cartesian_style(ax)
        result = inspect_figure_layout(fig)['axes_frame_closed']
        self.assertEqual(result['status'], 'pass')
        self.assertEqual(result['panels'][0]['hidden_spines'], [])
        self.assertEqual(result['panels'][0]['tick_sides'], ['bottom', 'left'])
        ax.tick_params(bottom=False, labelbottom=False)
        apply_closed_cartesian_style(ax, labels=False)
        result = inspect_figure_layout(fig)['axes_frame_closed']
        self.assertEqual(result['panels'][0]['tick_sides'], ['bottom', 'left'])
        self.assertTrue(any(t.tick1line.get_visible() for t in ax.xaxis.get_major_ticks()))
        self.assertFalse(any(t.label1.get_visible() for t in ax.xaxis.get_major_ticks()))

    def test_top_ticks_need_a_recorded_reason(self):
        with plt.rc_context(matplotlib_style()):
            fig, ax = plt.subplots()
            ax.tick_params(top=True, labeltop=True)
            result = inspect_figure_layout(fig)['axes_frame_closed']
            self.assertEqual(result['status'], 'fail')
            self.assertEqual(result['panels'][0]['non_default_tick_sides'], ['top'])
            self.assertTrue(any(v.get('kind') == 'undeclared_tick_side' for v in result['violations']))
            result = inspect_figure_layout(fig, tick_side_justifications={'axes[0]':'wide time series read against both edges'})['axes_frame_closed']
            self.assertEqual(result['status'], 'pass')
            self.assertTrue(result['panels'][0]['tick_side_justification'])

    def test_composite_panel_aspect_whitelist(self):
        with plt.rc_context(matplotlib_style()):
            fig, axes = plt.subplots(1,2,figsize=(6.3,3.2),layout='constrained')
            for ax in axes: ax.set_box_aspect(3/4)
            result = inspect_figure_layout(fig)['panel_aspect_whitelist']
            self.assertEqual(result['status'], 'pass')
            self.assertTrue(result['applies'])
            self.assertEqual({p['nearest_allowed'] for p in result['panels']}, {'4:3'})
            self.assertLess(max(p['deviation'] for p in result['panels']), 1e-6)
        fig, axes = plt.subplots(1,2,figsize=(6.3,3.2),layout='constrained')
        for ax in axes: ax.set_box_aspect(1/3)
        result = inspect_figure_layout(fig)['panel_aspect_whitelist']
        self.assertEqual(result['status'], 'fail')
        self.assertEqual(len(result['violations']), 2)
        result = inspect_figure_layout(fig, layout_justifications={'axes[0]':'map overview strip','axes[1]':'map overview strip'})['panel_aspect_whitelist']
        self.assertEqual(result['status'], 'pass')

    def test_single_panel_aspect_is_out_of_scope(self):
        fig, ax = plt.subplots()
        result = inspect_figure_layout(fig)['panel_aspect_whitelist']
        self.assertEqual(result['status'], 'pass')
        self.assertFalse(result['applies'])

    def curve_fixture(self, x, y, declaration, **kwargs):
        import numpy as np
        fig, ax = plt.subplots(figsize=(5,3),dpi=100)
        line, = ax.plot(np.asarray(x,float), np.asarray(y,float))
        line.set_gid('target')
        return inspect_figure_layout(fig, continuity_declarations={'target': declaration}, **kwargs)['curve_smoothing']

    def test_continuous_curve_must_be_smooth(self):
        import numpy as np
        x = np.linspace(0,1,200)
        result = self.curve_fixture(x, np.sin(2*np.pi*x), {'kind':'continuous','y_range':[-1,1]})
        self.assertEqual(result['status'], 'pass')
        self.assertEqual(result['lines'][0]['declared'], 'continuous')
        result = self.curve_fixture([0,1,2,3,4,5],[0,3,1,4,2,5], {'kind':'continuous','y_range':[0,5]})
        self.assertEqual(result['status'], 'fail')
        self.assertTrue(any(v['kind'] in ('coarse_corner','sparse_sampling') for v in result['violations']))

    def test_continuous_curve_needs_a_data_envelope(self):
        import numpy as np
        x = np.linspace(0,1,200)
        result = self.curve_fixture(x, np.sin(2*np.pi*x), 'continuous')
        self.assertTrue(any(v['kind'] == 'missing_data_envelope' for v in result['violations']))

    def test_envelope_overshoot_and_invented_turning_points_rejected(self):
        import numpy as np
        x = np.linspace(0,1,200)
        result = self.curve_fixture(x, 1.4+np.sin(2*np.pi*x), {'kind':'continuous','y_range':[0.4,1.0]})
        self.assertTrue(any(v['kind'] == 'envelope_overshoot' for v in result['violations']))
        result = self.curve_fixture(x, np.sin(6*np.pi*x), {'kind':'continuous','y_range':[-1,1],'turning_points':2})
        self.assertTrue(any(v['kind'] == 'fabricated_extremum' for v in result['violations']))

    def test_discrete_line_must_keep_its_samples(self):
        import numpy as np
        result = self.curve_fixture([0,1,2,3],[1,2,1,2], {'kind':'discrete','sample_count':4})
        self.assertEqual(result['status'], 'pass')
        self.assertEqual(result['lines'][0]['max_off_path_pt'], 0.0)
        result = self.curve_fixture(np.linspace(0,3,120), np.tile([1,2,1,2],30), {'kind':'discrete','sample_count':4})
        self.assertTrue(any(v['kind'] == 'interpolated_samples' for v in result['violations']))
        result = self.curve_fixture([0,1,2,3],[1,2,1,2], 'discrete')
        self.assertTrue(any(v['kind'] == 'missing_sample_count' for v in result['violations']))

    def test_step_line_needs_a_steps_drawstyle(self):
        result = self.curve_fixture([0,1,2,3],[1,2,1,2], 'step')
        self.assertTrue(any(v['kind'] == 'step_drawstyle' for v in result['violations']))

    def test_undeclared_data_line_is_rejected(self):
        fig, ax = plt.subplots()
        line, = ax.plot([0,1,2,3],[1,2,1,2])
        line.set_gid('orphan')
        result = inspect_figure_layout(fig, continuity_declarations={})['curve_smoothing']
        self.assertTrue(any(v['kind'] == 'missing_declaration' and v['line'] == 'orphan' for v in result['violations']))

    def test_axis_aligned_reference_line_is_skipped(self):
        fig, ax = plt.subplots()
        ax.axhline(0.5)
        result = inspect_figure_layout(fig, continuity_declarations={})['curve_smoothing']
        self.assertEqual(result['status'], 'pass')
        self.assertTrue(result['skipped'])

    def test_declare_continuity_helper(self):
        import numpy as np
        fig, ax = plt.subplots()
        line, = ax.plot(np.linspace(0,1,64), np.linspace(0,1,64))
        record = declare_continuity(line, 'continuous', name='ramp', y_range=[0,1])
        self.assertEqual(record, {'ramp': {'kind':'continuous','y_range':[0,1]}})
        self.assertEqual(line.get_gid(), 'ramp')
        with self.assertRaises(ValueError): declare_continuity(line, 'continuous', name='ramp')
        with self.assertRaises(ValueError): declare_continuity(line, 'wobbly', name='ramp')
        step, = ax.plot([0,1,2],[0,1,0])
        self.assertEqual(declare_continuity(step, 'step', name='latch'), {'latch':'step'})
        self.assertTrue(step.get_drawstyle().startswith('steps'))

    def test_uniform_grids(self):
        for rows, cols in [(3,1),(2,2)]:
            with plt.rc_context(matplotlib_style()):
                fig, axes = plt.subplots(rows,cols,figsize=(6.3,7),layout='constrained')
                result = inspect_figure_layout(fig)
                self.assertEqual(result['panel_size_uniformity']['status'],'pass')

    def test_mosaic_fail_and_justified_exception(self):
        fig, axes = plt.subplot_mosaic([['a','a'],['b','c']],figsize=(6,5))
        result = inspect_figure_layout(fig)
        self.assertEqual(result['panel_size_uniformity']['status'],'fail')
        result = inspect_figure_layout(fig,layout_justifications={'peers':'Full map with two local zooms'})
        self.assertEqual(result['panel_size_uniformity']['status'],'pass')
        self.assertTrue(result['panel_size_uniformity']['groups'][0]['exception_applied'])

    def annotation_fixture(self, gap_pt, linewidth=1, dpi=100):
        fig, ax = plt.subplots(figsize=(5,3),dpi=dpi)
        ax.set(xlim=(0,1),ylim=(0,1))
        ax.plot([0,1],[0.5,0.5],lw=linewidth,gid='target-line')
        ax.annotate('target text',(.4,.5),xytext=(0,gap_pt),textcoords='offset points',va='bottom')
        return inspect_figure_layout(fig)['text_solid_stroke_clearance']

    def test_contact_and_near_miss_across_dpi(self):
        for dpi in (100,300):
            for gap in (0,2):
                result=self.annotation_fixture(gap,dpi=dpi)
                self.assertTrue(any(v['text']=='target text' and v['stroke']=='target-line' for v in result['violations']))
            result=self.annotation_fixture(8,dpi=dpi)
            self.assertFalse(any(v['text']=='target text' and v['stroke']=='target-line' for v in result['violations']))

    def test_linewidth_is_part_of_clearance(self):
        result=self.annotation_fixture(6,linewidth=8)
        self.assertTrue(any(v['text']=='target text' and v['distance_pt']<4 for v in result['violations']))

    def test_dashed_and_dotted_grid_are_not_solid(self):
        for linestyle in (':','--'):
            fig,ax=plt.subplots()
            ax.set(ylim=(0,1),yticks=[.5])
            ax.grid(linestyle=linestyle)
            ax.text(.5,.5,'grid text')
            result=inspect_figure_layout(fig)['text_solid_stroke_clearance']
            self.assertFalse(any(v['text']=='grid text' for v in result['violations']))

    def test_diagonal_bbox_is_not_collision(self):
        fig,ax=plt.subplots()
        ax.plot([0,1],[0,1])
        ax.text(.1,.8,'safe')
        result=inspect_figure_layout(fig)['text_solid_stroke_clearance']
        self.assertFalse(any(v['text']=='safe' for v in result['violations']))

    def test_legend_data_region_and_line_collection(self):
        fig,ax=plt.subplots()
        ax.set(xlim=(0,1),ylim=(0,1))
        ax.hlines(.5,0,1,label='reference')
        ax.legend(loc='center')
        result=inspect_figure_layout(fig)
        self.assertEqual(result['legend_data_region_clearance']['status'],'fail')

    def test_own_annotation_leader_is_exempt(self):
        fig,ax=plt.subplots()
        ax.annotate('own arrow',(.3,.3),xytext=(.5,.7),arrowprops={'arrowstyle':'->'})
        result=inspect_figure_layout(fig)['text_solid_stroke_clearance']
        self.assertFalse(any(v['text']=='own arrow' for v in result['violations']))

    def test_ignored_text_cannot_hide_stroke_contact(self):
        fig,ax=plt.subplots()
        line,=ax.plot([0,1],[.5,.5])
        text=ax.text(.5,.5,'contact')
        result=inspect_figure_layout(fig,ignored_artists=[text],stroke_exemptions=[(text,line,'test')])
        self.assertTrue(any(v['text']=='contact' for v in result['text_solid_stroke_clearance']['violations']))

    def test_out_of_view_ticks_are_not_clipped_text(self):
        fig,ax=plt.subplots()
        ax.set(ylim=(0,4.3),yticks=[0,1,2,3,4,5])
        ax.set_ylim(0,4.3)
        result=inspect_figure_layout(fig)
        self.assertFalse(any(v['text']=='5' for v in result['clipped']))


if __name__ == '__main__': unittest.main()
