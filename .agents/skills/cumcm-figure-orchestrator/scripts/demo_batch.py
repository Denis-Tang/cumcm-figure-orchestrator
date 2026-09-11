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

RENDER = '''from pathlib import Path
import csv, json, sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from PIL import Image
from matplotlib_layout_qa import inspect_figure_layout
root=Path(__file__).resolve().parent
groups={}
with (root/"raw.csv").open() as handle:
    for row in csv.DictReader(handle):
        groups.setdefault(row["group"],[]).append(float(row["value"]))
labels=sorted(groups)
values=[sum(groups[key])/len(groups[key]) for key in labels]
plt.rcParams.update({"font.sans-serif":["Microsoft YaHei","DejaVu Sans"], "svg.fonttype":"none"})
fig,ax=plt.subplots(figsize=(140/25.4,95/25.4),layout="constrained")
points=ax.scatter(range(len(labels)),values,s=55,color="#265B7A")
ax.set_xticks(range(len(labels)),labels)
ax.set_ylim(0,7)
ax.set_ylabel("分组均值（单位）")
ax.set_title("合成数据验收示例")
ax.spines[["right","top"]].set_visible(False)
ax.grid(axis="y",alpha=.2)
ax.set_axisbelow(True)
layout=inspect_figure_layout(fig)
with (root/"plotted.csv").open("w",newline="",encoding="utf-8") as handle:
    writer=csv.writer(handle); writer.writerow(["group","value"])
    writer.writerows((labels[int(x)],float(y)) for x,y in points.get_offsets())
fig.savefig(root/"figure.png",dpi=320)
fig.savefig(root/"figure.svg")
Image.open(root/"figure.png").convert("L").save(root/"grayscale.png")
expected={"A","B","C","分组均值（单位）","合成数据验收示例"}
from matplotlib.text import Text
actual={item.get_text() for item in fig.findobj(match=Text)}
(root/"render-result.json").write_text(json.dumps({"layout":layout,
  "missing_labels":sorted(expected-actual),"renderer_version":matplotlib.__version__},ensure_ascii=False,indent=2),encoding="utf-8")
plt.close(fig)
'''

REFERENCE = '''# Independent reference computation: streaming sum and count per key.
from pathlib import Path
import csv, math
root=Path(__file__).resolve().parent
with (root/"raw.csv").open() as handle:
    rows=list(csv.DictReader(handle))
with (root/"reference.csv").open("w",newline="",encoding="utf-8") as handle:
    out=csv.writer(handle); out.writerow(["group","value"])
    for key in sorted({r["group"] for r in rows}):
        samples=[float(r["value"]) for r in rows if r["group"]==key]
        out.writerow([key,math.fsum(samples)/len(samples)])
'''


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out",type=Path,required=True,help="New directory; existing batches are never overwritten")
    args=parser.parse_args()
    root=args.out.resolve()
    root.mkdir(parents=True,exist_ok=False)
    scripts=Path(__file__).resolve().parent
    (root/"paper.md").write_text("# 合成验收材料\n仅用于软件验证，不是实测论文。\nA、B、C 的均值分别为 2、4、6 单位。\n图只展示三组均值，不主张因果、趋势或显著性。\n",encoding="utf-8")
    (root/"raw.csv").write_text("group,value\nA,1\nA,3\nB,2\nB,6\nC,4\nC,8\n",encoding="utf-8")
    # Explicit script path enables the shared QA import without changing global environment.
    (root/"render.py").write_text("import sys\nsys.path.insert(0,"+repr(str(scripts))+")\n"+RENDER,encoding="utf-8")
    (root/"verify.py").write_text(REFERENCE,encoding="utf-8")
    subprocess.run([sys.executable,"-B",str(root/"render.py")],check=True)
    subprocess.run([sys.executable,"-B",str(root/"verify.py")],check=True)
    rendered=json.loads((root/"render-result.json").read_text(encoding="utf-8"))
    figure={"figure_id":"f01_means","status":"formal","task_type":"data_chart",
      "claim":"合成数据中 A、B、C 均值分别为 2、4、6 单位。", "caption":"三组合成数据的均值（软件验收示例）。",
      "paper_anchor":"paper.md 第 3 行", "sources":["paper.md","raw.csv"],
      "data_source":"raw.csv","code_path":"render.py","final_width_mm":140,
      "constraints":{"exact_numeric":True,"exact_text":True,"contains_text":True,"vector_required":True,"reproducible_required":True},
      "data_contract":{"input_files":["raw.csv","grayscale.png",str(scripts/"matplotlib_layout_qa.py")],
        "fields":[{"name":"value","unit":"单位","source":"raw.csv/value"}],
        "observation_unit":"one synthetic observation","keys":["group"],"time_scope":"not temporal",
        "missing_policy":"none in synthetic fixture; reject invalid numeric input",
        "duplicate_policy":"two distinct observations per group; aggregate by arithmetic mean",
        "transformations":["group arithmetic mean; no scaling"],
        "reference_data":"reference.csv","plotted_data":"plotted.csv","verification_code":"verify.py",
        "verification_method":"independent raw CSV reread, fsum/count; compare to scatter offsets",
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
    figure["outputs"]={"png":"figure.png","svg":"figure.svg","source":"render.py"}
    figure["provenance"]={"actual_provider":"matplotlib-seaborn","renderer_version":rendered["renderer_version"],
      "render_command":f'"{sys.executable}" -B render.py',"ai_assisted":True,
      "ai_tool_and_version":"Codex session; model version not supplied", "prompt_summary":"Optimize and verify the CUMCM figure skill using a synthetic batch",
      "ai_output_adopted":"partial","human_edits":"none; current visual review recorded separately",
      "verification_method":"independent arithmetic, plotted-offset reread, file decoding and current image review"}
    layout=rendered["layout"]
    numeric=compare_tables(root/"reference.csv",root/"plotted.csv",["group"],["value"])
    exports=inspect_outputs(figure,root,manifest["layout"])
    results={"numeric_check":numeric,
      "collision_check":{"status":"fail" if layout["collisions"] else "pass","method":layout["method"],"collisions":layout["collisions"]},
      "clipping_check":{"status":"fail" if layout["clipped"] or layout["small_text"] else "pass","method":layout["method"],"clipped":layout["clipped"],"small_text":layout["small_text"]},
      "ocr_check":{"status":"fail" if rendered["missing_labels"] or layout["glyph_warnings"] else "pass","method":"Exact Matplotlib artist text and missing-glyph scan; PNG reviewed separately","missing_labels":rendered["missing_labels"],"glyph_warnings":layout["glyph_warnings"]},
      "export_check":{"status":"fail" if exports else "pass","method":"PNG decode, SVG vector/size/aspect and final effective DPI check","errors":exports}}
    figure["qa"]={}
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
