#!/usr/bin/env python3
"""Build a synthetic v2 batch; visual/caption/grayscale review stays pending."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

from qa_evidence import make_evidence
from route_figures import route_manifest
from score_providers import load_scorecard
from validate_manifest import inspect_outputs
from verify_numeric import compare_tables
from figure_style import load_style, select_colors

RENDER = '''from pathlib import Path
import csv, json, sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from PIL import Image
from matplotlib_layout_qa import inspect_figure_layout
from figure_style import matplotlib_style, select_colors, declare_continuity, apply_closed_cartesian_style
root=Path(__file__).resolve().parent
groups={}
with (root/"raw.csv").open() as handle:
    for row in csv.DictReader(handle):
        groups.setdefault(row["group"],[]).append(float(row["value"]))
labels=sorted(groups)
values=[sum(groups[key])/len(groups[key]) for key in labels]
plt.rcParams.update({"font.sans-serif":["Microsoft YaHei","DejaVu Sans"], "svg.fonttype":"none"})
plt.rcParams.update(matplotlib_style())
fig,axes=plt.subplots(1,2,figsize=(160/25.4,80/25.4),layout="constrained")
mapping=select_colors(labels)
declarations={}
for ax in axes:
    apply_closed_cartesian_style(ax)   # four visible spines, ticks only on the left and bottom
    ax.set_box_aspect(3/4)          # set_box_aspect takes height/width: 3/4 gives a 4:3 plotting area
    ax.set_ylim(0,9)
    ax.set_xticks(range(len(labels)),labels)
    ax.set_xlabel("分组")
    ax.set_ylabel("数值（单位）")
    ax.grid(axis="y",alpha=.2)
    ax.set_axisbelow(True)
mean_ax,span_ax=axes
mean_ax.set_title("(a) 分组均值")
span_ax.set_title("(b) 分组观测区间")
points=mean_ax.scatter(range(len(labels)),values,s=55,color=[mapping[k]['colors'] for k in labels])
spans=[]
for index,key in enumerate(labels):
    samples=groups[key]
    line,=span_ax.plot([index-0.16,index+0.16],[min(samples),max(samples)],
                       color=mapping[key]['colors'],marker="o",markersize=4)
    declarations.update(declare_continuity(line,"discrete",name="span_"+key,sample_count=2))
    spans.extend([(key+"_min",float(min(samples))),(key+"_max",float(max(samples)))])
layout=inspect_figure_layout(fig,continuity_declarations=declarations)
with (root/"plotted.csv").open("w",newline="",encoding="utf-8") as handle:
    writer=csv.writer(handle); writer.writerow(["group","value"])
    writer.writerows((labels[int(x)],float(y)) for x,y in points.get_offsets())
with (root/"plotted_span.csv").open("w",newline="",encoding="utf-8") as handle:
    writer=csv.writer(handle); writer.writerow(["group","value"])
    writer.writerows(spans)
fig.savefig(root/"figure.png",dpi=320)
fig.savefig(root/"figure.svg")
fig.savefig(root/"figure.pdf")  # Retained for final-vector raster review; SVG remains strict vector output.
Image.open(root/"figure.png").convert("L").save(root/"grayscale.png")
expected={"A","B","C","分组","数值（单位）","(a) 分组均值","(b) 分组观测区间"}
from matplotlib.text import Text
actual={item.get_text() for item in fig.findobj(match=Text)}
(root/"render-result.json").write_text(json.dumps({"layout":layout,"declarations":declarations,
  "missing_labels":sorted(expected-actual),"renderer_version":matplotlib.__version__},ensure_ascii=False,indent=2),encoding="utf-8")
plt.close(fig)
'''

REFERENCE = '''# Independent reference computation: streaming sum, count, min and max per key.
from pathlib import Path
import csv, math
root=Path(__file__).resolve().parent
with (root/"raw.csv").open() as handle:
    rows=list(csv.DictReader(handle))
keys=sorted({r["group"] for r in rows})
with (root/"reference.csv").open("w",newline="",encoding="utf-8") as handle:
    out=csv.writer(handle); out.writerow(["group","value"])
    for key in keys:
        samples=[float(r["value"]) for r in rows if r["group"]==key]
        out.writerow([key,math.fsum(samples)/len(samples)])
with (root/"reference_span.csv").open("w",newline="",encoding="utf-8") as handle:
    out=csv.writer(handle); out.writerow(["group","value"])
    for key in keys:
        samples=[float(r["value"]) for r in rows if r["group"]==key]
        out.writerow([key+"_min",min(samples)]); out.writerow([key+"_max",max(samples)])
'''

PROFILE_CHECKS = ('panel_size_uniformity','text_solid_stroke_clearance','legend_data_region_clearance',
                  'axes_frame_closed','panel_aspect_whitelist','curve_smoothing')


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out",type=Path,required=True,help="New directory; existing batches are never overwritten")
    args=parser.parse_args()
    root=args.out.resolve()
    root.mkdir(parents=True,exist_ok=False)
    scripts=Path(__file__).resolve().parent
    (root/"paper.md").write_text("# 合成验收材料\n仅用于软件验证，不是实测论文。\nA、B、C 的均值分别为 2、4、6 单位，组内观测区间分别为 1–3、2–6、4–8。\n图只展示三组均值与组内观测区间，不主张因果、趋势或显著性。\n",encoding="utf-8")
    (root/"raw.csv").write_text("group,value\nA,1\nA,3\nB,2\nB,6\nC,4\nC,8\n",encoding="utf-8")
    # Explicit script path enables the shared QA import without changing global environment.
    (root/"render.py").write_text("import sys\nsys.path.insert(0,"+repr(str(scripts))+")\n"+RENDER,encoding="utf-8")
    (root/"verify.py").write_text(REFERENCE,encoding="utf-8")
    subprocess.run([sys.executable,"-B",str(root/"render.py")],check=True)
    subprocess.run([sys.executable,"-B",str(root/"verify.py")],check=True)
    rendered=json.loads((root/"render-result.json").read_text(encoding="utf-8"))
    figure={"figure_id":"f01_means","status":"formal","task_type":"data_chart",
      "claim":"合成数据中 A、B、C 均值分别为 2、4、6 单位，组内观测区间分别为 1–3、2–6、4–8。",
      "caption":"三组合成数据的均值（a）与组内观测区间（b）（软件验收示例）。",
      "paper_anchor":"paper.md 第 3 行", "sources":["paper.md","raw.csv"],
      "data_source":"raw.csv","code_path":"render.py","final_width_mm":160,
      "constraints":{"exact_numeric":True,"exact_text":True,"contains_text":True,"vector_required":True,"reproducible_required":True},
      "data_contract":{"input_files":["raw.csv","grayscale.png","plotted_span.csv","reference_span.csv",str(scripts/"matplotlib_layout_qa.py")],
        "fields":[{"name":"value","unit":"单位","source":"raw.csv/value"}],
        "observation_unit":"one synthetic observation","keys":["group"],"time_scope":"not temporal",
        "missing_policy":"none in synthetic fixture; reject invalid numeric input",
        "duplicate_policy":"two distinct observations per group; aggregate by arithmetic mean, min and max",
        "transformations":["group arithmetic mean, group minimum, group maximum; no scaling"],
        "reference_data":"reference.csv","plotted_data":"plotted.csv","verification_code":"verify.py",
        "verification_method":"independent raw CSV reread, fsum/count and min/max; compare to scatter offsets and span-line vertices",
        "numeric_columns":["value"],"atol":1e-9,"rtol":1e-7,"tolerance_reason":"floating-point mean precision"}}
    from check_environment import provider_status
    score=load_scorecard()
    # This example explicitly requires its implemented renderer; do not route to an unimplemented demo backend.
    environment=[provider_status(next(p for p in score["providers"] if p["id"]=="matplotlib-seaborn"))]
    manifest=route_manifest({"schema_version":2,"batch_id":"synthetic-v2-smoke","competition_profile":"cumcm",
      "paper":{"title":"合成验收材料","source_path":"paper.md"},"target_figure_ids":["f01_means"],
      "layout":{"page_width_mm":210,"margin_left_mm":25,"margin_right_mm":25,"min_dpi":300},"figures":[figure]},score,environment)
    figure=manifest["figures"][0]
    figure["pipeline_state"]="rendered"
    profile, palette = load_style()
    figure['style_policy']={'profile_id':profile['profile_id'], 'baseline_id':palette['baseline_id'],
      'object_mapping':select_colors(['A','B','C'],profile=profile,palette=palette),
      'continuity_declarations':rendered["declarations"],
      'input_files':['figure.pdf',str(scripts/'figure_style.py'),str(scripts.parent/'assets/personal-figure-style.json'),
                     str(scripts.parent/'assets/personal-color-baseline.json')]}
    figure["outputs"]={"png":"figure.png","svg":"figure.svg","source":"render.py"}
    figure["provenance"]={"actual_provider":"matplotlib-seaborn","renderer_version":rendered["renderer_version"],
      "render_command":f'"{sys.executable}" -B render.py',"ai_assisted":True,
      "ai_tool_and_version":"Codex session; model version not supplied", "prompt_summary":"Optimize and verify the CUMCM figure skill using a synthetic batch",
      "ai_output_adopted":"partial","human_edits":"none; current visual review recorded separately",
      "verification_method":"independent arithmetic, plotted-offset and span-vertex reread, file decoding and current image review"}
    layout=rendered["layout"]
    means=compare_tables(root/"reference.csv",root/"plotted.csv",["group"],["value"])
    spans=compare_tables(root/"reference_span.csv",root/"plotted_span.csv",["group"],["value"])
    numeric={"status":"fail" if "fail" in (means["status"],spans["status"]) else "pass",
      "method":"Independent reference reread versus plotted artist values (group means and per-group observed range)",
      "max_absolute_error":max(means["max_absolute_error"],spans["max_absolute_error"]),
      "mean_check":means,"span_check":spans}
    exports=inspect_outputs(figure,root,manifest["layout"])
    results={"numeric_check":numeric,
      "collision_check":{"status":"fail" if layout["collisions"] else "pass","method":layout["method"],"collisions":layout["collisions"]},
      "clipping_check":{"status":"fail" if layout["clipped"] or layout["small_text"] else "pass","method":layout["method"],"clipped":layout["clipped"],"small_text":layout["small_text"]},
      "ocr_check":{"status":"fail" if rendered["missing_labels"] or layout["glyph_warnings"] else "pass","method":"Exact Matplotlib artist text and missing-glyph scan; PNG reviewed separately","missing_labels":rendered["missing_labels"],"glyph_warnings":layout["glyph_warnings"]},
      "export_check":{"status":"fail" if exports else "pass","method":"PNG decode, SVG vector/size/aspect and final effective DPI check","errors":exports}}
    figure["qa"]={}
    for key in PROFILE_CHECKS:
        results[key]=layout[key]
    (root/"qa").mkdir()
    for key,result in results.items():
        evidence=make_evidence(figure,manifest["paper"],manifest["layout"],key,result,root,"demo_batch v2")
        path=f"qa/{key}.json"
        (root/path).write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding="utf-8")
        figure["qa"][key]={"status":result["status"],"method":result["method"],"evidence":path}
    for key in ("visual_review","grayscale_check","claim_caption_check"):
        figure["qa"][key]={"status":"pending","method":"Review the actual current figure and paper before recording evidence"}
    manifest["delivery_status"]="partial"
    (root/"candidate.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(f"Rendered synthetic example: {root}; visual/caption/grayscale review remains pending")
    return 1 if any(r["status"]!="pass" for r in results.values()) else 0


if __name__ == "__main__":
    raise SystemExit(main())
