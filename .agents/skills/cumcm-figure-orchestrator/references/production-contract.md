# Production contract (v2)

Use this for actual figure production, numerical reconciliation or migration of an old batch. The JSON Schema is the structural authority; strict validation adds file, evidence, numerical and delivery checks.

## Inputs and scientific decisions

Read one complete manuscript and inventory its exact data/code. Sources are local files; put section/page/cell anchors in `paper_anchor`, `fields[].source` or `semantic_contract`, not as fake file paths. Resolve all relative paths against the manifest directory. Downloaded inputs, when needed and authorized, become frozen local files with their origin recorded.

Before rendering, record:

- `fields`: source sheet/column, variable name and unit; explicitly say dimensionless where appropriate.
- `observation_unit`, output `keys`, `time_scope`, `missing_policy`, `duplicate_policy` and `transformations`: filters, groupings, weights, denominators, normalization, unit conversion, interpolation and ordering. `input_files` lists all raw/processed inputs actually used, including helper code/config that changes results.
- `reference_data`, `plotted_data`, `verification_code`, `numeric_columns`, `atol`, `rtol`, `tolerance_reason`, `verification_method`: independently computed reference versus values extracted from the actual plot. Do not write both CSVs from the same intermediate array. The independent code must differ from plotting code; that separation helps review but alone is not proof of independence.
- `model`, when this is a model-result figure: actual parameters, seed (null only for deterministic/nonrandom work), solver status and `reproduction_status`. `supplied_only` must be stated in the claim/caption; `blocked` cannot support a reproduced numerical conclusion.

Missing formulas or model outputs do not prevent valid descriptive figures. Reconstruct a method only when fully specified and within the request. Compare manuscript claims, code and recomputation; document the conflicting values, their provenance and the unresolved reason. Never choose whichever source produces the nicest graph. Continue unaffected figures while the affected figure stays blocked.

## Task-specific checks

| Task | Required semantic evidence |
| --- | --- |
| Statistical chart | Observational unit, units, group/time alignment, denominator/weights, missingness; actual plotted values and transformations |
| Intervals/model comparison | What interval means, sample size, train/test separation and paired comparison if applicable; do not invent uncertainty |
| Optimization | Decision-variable mapping, objective recomputation, feasibility residuals and solver termination; distinguish feasible from proven optimal |
| Network/flowchart | `semantic_contract.source_mapping` and `invariants`: node IDs, edges, direction, labels and conditional branches; topology must match source. Check numeric weights if used |
| Map | CRS/projection, coordinate units/order, source geometry version, join keys and unmatched records; quantitative layers require numeric checks |
| Composite | Full formal records in `panels`, unique IDs throughout the batch; panel checks plus parent assembly checks. Rescaling/assembly invalidates the relevant layout evidence |

For marker area, use an explicitly documented mapping. An offset/square-root transform or per-panel normalization must not be presented as a common proportional frequency scale. Check log-domain validity and data clipping separately from text clipping.

## Batch and delivery states

- `schema_version: 2`; `status` is the publication role (`formal`, `alternative`, `draft`, `excluded`). It is not QA state.
- `pipeline_state`: `planned`, `rendered`, `verified`, `blocked`; keep a concrete `blocked_reason`. Every excluded figure needs `exclusion_reason`.
- `target_figure_ids`: the actual agreed/selected formal figure scope. Do not remove targets merely to obtain a green batch.
- `delivery_status`: `planned`, `partial`, `ready`, `no_figures`. Strict delivery requires at least one formal figure and all targets delivered. A legitimate no-figure analysis is a planning conclusion, not strict image delivery.
- `layout`: page width and left/right margins in mm, and minimum PNG dpi (at least 300). Use the actual target document; after embedding, inspect its page render for scale, caption/numbering and cropping.

Six to twelve formal figures remains an evidence-dependent planning preference, not a reason to invent figures. Alternative exploration is optional in production when it adds no value.

## Execution and evidence

Use the same interpreter for dependency probing and rendering. The route command probes by default. If unavailable routes remain, select an eligible available fallback and update the recorded route before rendering. A found executable/module is only a preflight check; a successful decoded export and retained `provenance.actual_provider`, `renderer_version`, `render_command` establish the execution record. Do not equate a Skill file on disk with an available session tool.

Use this sequence with batch paths:

```powershell
python scripts/route_figures.py plan.json --out routed.json
# Produce code, outputs and independent reference/plotted CSVs first.
python scripts/verify_numeric.py reference.csv plotted.csv --keys series key --columns value --out numeric-result.json
python scripts/qa_evidence.py candidate.json fig_01 numeric_check numeric-result.json --checker "verify_numeric.py v2" --out qa/numeric-evidence.json
python scripts/finalize_manifest.py candidate.json --out verified.json
python scripts/validate_manifest.py verified.json --strict
```

Replace `python` with the concrete interpreter path and `scripts/` with the installed Skill script directory. `verify_numeric` checks unique keys, matching row sets, finite values and `abs(actual-reference) <= atol + rtol*abs(reference)`. Choose tolerances from precision and domain needs before comparing; no arbitrary tolerance inflation to pass.

Each manifest QA entry is `{status, method, evidence}`; `evidence` is a local JSON record created by `qa_evidence`. Run that recorder after the outputs, specification, contract and provenance are complete. It preserves the real check result, checker/version, timestamp and file hashes. Changes to the current specification, inputs, source code or images invalidate old records. Record failure as failure; finalization does not overwrite the candidate or existing output.

Checks are `numeric_check`, `ocr_check`, `collision_check`, `clipping_check`, `grayscale_check`, `export_check`, `claim_caption_check`, `visual_review`, and `structure_check` for flow/network/maps. All applicable checks need current evidence. A hash protects against stale evidence; it does not authenticate scientific truth or prove that a person inspected an image.

For visual review, inspect the actual final-size PNG and grayscale (and final embedded page when integrating). Put the actual reviewer identity in `--reviewer` (e.g. the reviewing Agent, or a human who actually reviewed it). Record observations in the result JSON: label accuracy, data/annotation occlusion, arrows/branches, scale/legend/units, final-size readability. Agent review is allowed; never describe it as human review. Human competition-use review remains separate under the applicable contest rules.

`matplotlib_layout_qa` screens text boxes, font size, missing glyphs, equal peer-panel plotting areas, text-to-solid-stroke clearance, legend-to-data clearance, closed four-sided axes frames, composite panel aspect ratios and declared line continuity. See `personal-figure-style.md` for parameters, structural exemptions and limitations. Ignoring a deliberate text collision does not exempt that label from clipping, small-font or stroke checks. OCR or XML text matching does not establish edge correctness or mathematical semantics. Export validation decodes PNG, parses SVG/PDF and rejects raster-only vector substitutes; in this v2 gate, vector-required assets must not embed raster images. For a legitimate raster/map layer, explicitly choose a raster deliverable and retain reproducible source rather than claiming vector output.

New profile-based production records include `style_policy` with `profile_id`, `baseline_id`, and `input_files` binding the palette, profile and helper/QA code. Retain object mapping, overrides, panel/layout justifications, `frame_exemptions`, `tick_side_justifications` and `continuity_declarations` there. The six added `panel_size_uniformity`, `text_solid_stroke_clearance`, `legend_data_region_clearance`, `axes_frame_closed`, `panel_aspect_whitelist` and `curve_smoothing` QA entries use the existing `{status,method,evidence}` format and real `qa_evidence` bindings. Strict validation requires all six when style_policy is present; old v2 batches without it remain compatible but have not passed the new profile checks. Vector-to-PNG final-size rasterization and actual visual review are required in addition to automated screening.

## Legacy migration and recovery

Legacy manifests remain readable for planning, but old `pass` strings do not migrate into production evidence. Keep old assets and logs. Create a new batch/candidate, validate its input mapping, rerender at the correct width, run the real checks and record current evidence. Historical hand-review timestamps must never be regenerated by a script.

If a check fails, repair the smallest responsible input/plot/layout and rerun all checks whose bound assets changed. If two attempts expose the same unresolved scientific ambiguity, record the exact missing fact and ask a focused clarification while continuing independent figures. Rendering or formatting failures can be repaired autonomously within scope; lack of evidence is not an aesthetic issue.
