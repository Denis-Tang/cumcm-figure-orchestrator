---
name: cumcm-figure-orchestrator
description: Analyze one complete CUMCM mathematical-modeling paper, decide which formal figures are justified, score and route each data chart, flowchart, network, map, or conceptual schematic to the safest available Skill and renderer, and enforce numerical, text, collision, grayscale, export, provenance, and AI-disclosure quality gates. Use when planning, producing, revising, or auditing a CUMCM paper's complete figure set rather than drawing one isolated image.
---

# CUMCM Figure Orchestrator

Process one complete paper per batch. Own figure necessity, data semantics, chart selection, rendering, and QA. When asked to draw, deliver the actual figures and reproducible sources, not only a plan. Use planning-only mode only when requested. Ask the user mainly to review residual aesthetic defects; missing scientific information is a separate blocking issue.

## Workflow

Before styling figures, read `references/personal-color-baseline.md` and load `assets/personal-color-baseline.json`. The active user-approved palette in that JSON is the default for every renderer, including delegated/routed chart and flowchart work. Pass its colors, fill roles and object-to-color mapping to the renderer explicitly; do not fall back to a renderer's default palette. A user's task-specific color instructions override this baseline. Scientific color semantics and required readability still apply.

1. Read the complete manuscript and its data/code. For PDF or Word input, use the available PDF or document Skill to extract the paper without losing captions, tables, formulas, and section anchors. Inventory exact input files, sheet/column mappings, units, and formulas. Separate supplied results from independently reproduced results. Do not infer model outputs from a complete-looking manuscript.
2. Build a figure plan with 6–12 formal figures when the evidence supports them. Put 2–4 experimental alternatives in `status: alternative`; never mix them into the formal set.
3. Use the version 2 manifest at `assets/figure-manifest.schema.json`: record the batch's `target_figure_ids`, final document `layout`, and each figure's claim, anchor, sources, caption, constraints, and `pipeline_state`. For data/model results read `references/production-contract.md` and fill the data contract before calculation. For composite figures define full per-panel records.
4. Run `scripts/route_figures.py` with the actual plotting interpreter. It filters dependency availability before selecting an eligible route; `--planning-only` disables that filtering and is not execution evidence. A blocked route must not weaken the numerical/text constraints. Continue independent figures while recording the affected figure's `blocked_reason`.
5. Invoke the routed Skill/renderer using `references/routing-matrix.md`. If its dependencies are unavailable, use the next eligible route reported by the router rather than silently changing figure semantics.
6. Keep image-generated diagrams as candidates unless manually or deterministically reconstructed. Never use image generation for axes, numerical geometry, benchmark values, formulas, or exact labels in a formal figure.
7. Render within the document's actual content width (A4 with 25 mm margins gives 160 mm). Independently recompute reference values and read the values actually plotted from artists/export geometry; compare them with `scripts/verify_numeric.py`. Check labels, layout, grayscale, export and claim/caption; review the rendered PNG at final size, including labels over data and edge directions that bounding-box screening cannot prove.
8. Record checks using `scripts/qa_evidence.py` only after performing them. Each check binds current inputs, code, outputs and specification. Use `scripts/finalize_manifest.py candidate.json --out verified.json` in the same batch directory; it validates before promotion and never fabricates pass statuses. `scripts/validate_manifest.py verified.json --strict` always validates real files, evidence and numerical comparison. A plan, a blocked batch or an all-excluded batch is not a completed figure delivery.
9. Update the AI-use fields and produce the disclosure detail from `assets/ai-usage-detail-template.md` when AI assisted any figure.

## Routing Defaults

- Exact data/statistical plots: `data-analytics:visualize-data` for design/QA, rendered with Matplotlib + Seaborn + constrained layout; add SciencePlots and adjustText when available.
- Exact formal flowcharts or model architecture: D2 + ELK, exported to SVG/PDF and PNG.
- Fast editable draft flowcharts: Mermaid + ELK; promote to formal only after exact-text and collision QA.
- Network figures: NetworkX + Graphviz.
- Maps/spatial figures: GeoPandas/Cartopy + Matplotlib.
- R-native data work: ggplot2 + ggrepel.
- Non-numeric conceptual candidates: installed `engineering-figure-agent` or `imagegen`; reconstruct and verify before formal use.
- Word/PDF integration: available document/PDF Skills after assets pass manifest validation.

## Quality Contract

- Do not invent measurements, mappings, labels, equations, causal claims, or chart geometry.
- Do not accept a figure merely because it looks polished.
- Use final-width layout and Chinese-capable fonts. Prefer short labels, stable reading order, and external legends only when they fit without shrinking the data region.
- A formal data chart/map requires numeric evidence even if its `exact_numeric` flag is false. Exact numeric geometry in other task types also requires it. Networks/flowcharts/maps require a semantic contract and structure check; composites require verified panels plus assembly QA.
- Every formal figure requires collision, clipping, grayscale, export, claim/caption and current rendered-image review evidence; text requires exact-label/OCR review. `pass` text alone is insufficient. Source/figure edits invalidate old evidence; re-run the affected checks.
- If automated collision evidence is unavailable, record a manual review method. Never record `pass` without performing the check.
- Preserve original files, transformed tables, independent reference calculation, plotted-value tables, executable code, interpreter/dependency versions, actual renderer and command, prompts and edits. Version new batches rather than overwrite frozen snapshots or previous figures. Do not run unreviewed supplied notebooks/scripts that can modify source data or external state.
- Resolve manuscript/data/code discrepancies explicitly. Do not silently replace the manuscript's conclusion with a new computation or treat a described algorithm as a reproduced result. Block only the affected claim when the evidence cannot resolve it.
- Model estimates need method, parameters, seed and solver/reproduction status. Do not claim causal effects, statistical significance, confidence intervals or optimization success unless the corresponding evidence exists. Keep units, normalization, area/length encoding and any clipping explicit in the caption or legend.
- Follow `references/cumcm-compliance.md` for paper limits and AI-use disclosure.

## Resources

- `references/scorecard.md`: scoring meaning, evidence confidence, and current benchmark interpretation.
- `references/skill-scorecard.md`: separate scores for installed/session and notable external Skills.
- `references/routing-matrix.md`: task-type routing and fallback order.
- `references/cumcm-compliance.md`: official CUMCM output and AI-use rules.
- `assets/provider-scorecard.json`: machine-readable provider and renderer scores.
- `assets/skill-scorecard.json`: machine-readable Skill-layer scores; advisory capability is not confused with final rendering.
- `assets/figure-manifest.schema.json`: manifest contract.
- `scripts/score_providers.py`: rank capabilities for a scenario.
- `scripts/route_figures.py`: apply hard gates and choose primary/fallback routes.
- `scripts/check_environment.py`: report locally available renderer dependencies.
- `scripts/bootstrap_d2.ps1`: install a pinned, checksum-verified D2 binary inside this project without changing global PATH.
- `scripts/render_d2.ps1`: render D2+ELK to SVG and a faithful high-resolution PNG through the system Edge engine.
- `scripts/validate_manifest.py`: fail-closed batch QA.
- `scripts/matplotlib_layout_qa.py`: reusable text overlap and clipping check for Matplotlib figures.
- `references/production-contract.md`: data/semantic contracts, evidence recording, failure recovery and migration.
- `scripts/verify_numeric.py`: key-aligned reference/artist numeric comparison.
- `scripts/qa_evidence.py`: evidence recorder and hash binding; does not perform the review itself.
- `scripts/finalize_manifest.py`: validated promotion to a new manifest; no forced passes.
- `scripts/demo_batch.py`: synthetic executable example of raw data, independent calculation, rendering and pending visual review.
