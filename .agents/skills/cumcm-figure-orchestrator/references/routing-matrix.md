# Routing matrix

## Formal routes

| Task type | Primary route | Fallback | Hard requirements |
| --- | --- | --- | --- |
| `data_chart` | `data-analytics:visualize-data` → Matplotlib/Seaborn | R ggplot2/ggrepel; Plotly/Kaleido | deterministic data geometry, numeric check, vector export |
| `flowchart` | D2 + ELK | Mermaid + ELK; Graphviz | exact text, vector output, automatic layout, source retained |
| `network` | NetworkX + Graphviz | D2 + ELK | nodes/edges traceable to source, deterministic layout seed/config |
| `map` | GeoPandas/Cartopy + Matplotlib | Plotly geospatial only with frozen export | CRS/projection recorded, source and units retained |
| `conceptual_schematic` | deterministic SVG/D2 when possible | engineering-figure-agent or imagegen as candidate | no numeric claim; exact labels reconstructed; human verification |
| `composite` | render quantitative panels deterministically, assemble as SVG/PDF | deterministic raster composition | every panel keeps its own provenance and QA |

## Selection logic

1. Exclude providers that fail a requested hard capability.
2. Exclude `candidate_only` providers for `status: formal`. After deterministic reconstruction, route the formal asset to the actual deterministic renderer and retain the candidate's provenance separately.
3. Score remaining providers using scenario fit plus accuracy, text, collision, vector, reproducibility, speed, auditability, and aesthetics.
4. Production CLI filters candidates using the current interpreter's dependency probe, then preserves up to three available eligible alternatives. `--planning-only` gives recommendations without execution readiness. Re-record the actual route/provenance after any fallback; no eligible available renderer means blocked, not weaker constraints.

## Skill invocation notes

- Use `data-analytics:visualize-data` for chart choice and visual QA, but retain executable plotting code and frozen data as the formal renderer evidence.
- The installed `engineering-figure-agent` already separates `plot`, `image`, and `mixed` modes. Reuse its plot renderer for exact charts and its image mode only for conceptual candidates.
- Use `imagegen` only where the result is truly illustrative. Do not ask it to spell long Chinese labels, place exact equations, or reproduce benchmark values.
- Use document/PDF Skills only after assets pass strict manifest validation; document integration is not evidence that the figures themselves are correct.

## Anti-overlap policy

- Matplotlib: enable `layout="constrained"`, render at final physical size, place legends/colorbars within the constraint system, run `matplotlib_layout_qa.py`, and use adjustText for dense direct labels.
- D2/Mermaid: use ELK, keep node labels short, group phases explicitly, and render SVG at final width. Visually review arrows and containers after export.
- Any renderer: reject text outside canvas, text-text overlap that harms readability, edge-label collisions, clipped legends/colorbars, and labels below the minimum readable size.
- Automated checks are screening, not proof. A final human rendered-image review remains required for CUMCM submission.
