#!/usr/bin/env python3
"""Reusable post-render text overlap and clipping checks for Matplotlib figures."""

from __future__ import annotations

from typing import Any, Iterable
import warnings


def _intersection_ratio(a: Any, b: Any) -> float:
    width = max(0.0, min(a.x1, b.x1) - max(a.x0, b.x0))
    height = max(0.0, min(a.y1, b.y1) - max(a.y0, b.y0))
    intersection = width * height
    smaller = min(max(a.width * a.height, 1e-9), max(b.width * b.height, 1e-9))
    return intersection / smaller


def inspect_figure_layout(
    figure: Any,
    *,
    overlap_ratio: float = 0.10,
    canvas_margin_px: float = 1.0,
    ignored_artists: Iterable[Any] = (),
    minimum_font_pt: float = 6.0,
    panel_groups: dict | None = None,
    layout_justifications: dict | None = None,
    stroke_exemptions: Iterable[tuple[Any, Any, str]] = (),
    panel_tolerance: float | None = None,
    text_stroke_clearance_pt: float | None = None,
    legend_data_clearance_pt: float | None = None,
    frame_exemptions: dict | None = None,
    tick_side_justifications: dict | None = None,
    continuity_declarations: dict | None = None,
    panel_aspect_tolerance: float | None = None,
) -> dict[str, Any]:
    """Render a figure and report harmful text-text intersections and clipping.

    This is a screening gate. Call it after setting the final physical figure size.
    Deliberate overlaps can be passed in ``ignored_artists`` and must be documented.
    The profile gate additionally closes every rectangular axes frame, keeps composite
    panels inside the allowed aspect whitelist and checks each declared line's continuity.
    """

    from matplotlib.text import Text

    ignored = {id(artist) for artist in ignored_artists}
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        figure.canvas.draw()
    glyph_warnings = [str(item.message) for item in caught if "Glyph" in str(item.message) and "missing" in str(item.message)]
    renderer = figure.canvas.get_renderer()
    canvas = figure.bbox
    text_items: list[tuple[Any, Any, str]] = []
    clipped: list[dict[str, Any]] = []
    small_text: list[dict[str, Any]] = []
    for artist in _drawn_text(figure):
        label = artist.get_text().strip()
        if not label or not artist.get_visible():
            continue
        bbox = artist.get_window_extent(renderer=renderer)
        if id(artist) not in ignored:
            text_items.append((artist, bbox, label))
        if artist.get_fontsize() < minimum_font_pt:
            small_text.append({"text": label, "font_pt": artist.get_fontsize()})
        if (
            bbox.x0 < canvas.x0 - canvas_margin_px
            or bbox.y0 < canvas.y0 - canvas_margin_px
            or bbox.x1 > canvas.x1 + canvas_margin_px
            or bbox.y1 > canvas.y1 + canvas_margin_px
        ):
            clipped.append({"text": label, "bbox_px": [bbox.x0, bbox.y0, bbox.x1, bbox.y1]})

    collisions: list[dict[str, Any]] = []
    for index, (_, bbox_a, label_a) in enumerate(text_items):
        for _, bbox_b, label_b in text_items[index + 1 :]:
            ratio = _intersection_ratio(bbox_a, bbox_b)
            if ratio >= overlap_ratio:
                collisions.append({"text_a": label_a, "text_b": label_b, "intersection_ratio": round(ratio, 4)})

    from figure_style import load_style
    profile, _ = load_style()
    layout_policy = profile.get("layout", {})
    curve_policy = profile.get("curve", {})
    frame_policy = profile.get("axes_frame", {})
    panels = inspect_panel_sizes(figure, panel_groups, layout_justifications,
                                 layout_policy.get('equal_panel_tolerance', 0.02) if panel_tolerance is None else panel_tolerance)
    strokes, legends = inspect_stroke_clearance(
        figure, renderer,
        profile['qa']['text_stroke_clearance_pt'] if text_stroke_clearance_pt is None else text_stroke_clearance_pt,
        profile['qa']['legend_data_clearance_pt'] if legend_data_clearance_pt is None else legend_data_clearance_pt,
        stroke_exemptions)
    frame = inspect_axes_frame(figure, exemptions=frame_exemptions,
                               required_sides=tuple(frame_policy.get("required_sides", ("left", "right", "top", "bottom"))),
                               default_tick_sides=tuple(frame_policy.get("default_tick_sides", ("left", "bottom"))),
                               skip_projections=tuple(frame_policy.get("skip_projections", ())),
                               tick_side_justifications=tick_side_justifications,
                               require_tick_side_justification=bool(frame_policy.get("require_tick_side_justification", True)))
    aspects = inspect_panel_aspects(
        figure, whitelist=tuple(tuple(pair) for pair in layout_policy.get("panel_aspect_whitelist", ((1, 1), (4, 3), (16, 9)))),
        tolerance=layout_policy.get('panel_aspect_tolerance', 0.02) if panel_aspect_tolerance is None else panel_aspect_tolerance,
        allow_reciprocal=bool(layout_policy.get('panel_aspect_allow_reciprocal', True)),
        min_data_axes=int(layout_policy.get('panel_aspect_min_data_axes', 2)),
        justifications=layout_justifications, groups=panel_groups)
    curves = inspect_curve_smoothing(
        figure, declarations=continuity_declarations,
        kinds=tuple(curve_policy.get('kinds', ("continuous", "discrete", "step", "piecewise_linear"))),
        min_dense_samples=int(curve_policy.get('min_dense_samples', 24)),
        max_turn_deg=float(curve_policy.get('max_turn_deg', 12.0)),
        max_segment_fraction=float(curve_policy.get('max_segment_fraction', 0.06)),
        overshoot_fraction=float(curve_policy.get('overshoot_fraction', 0.01)))
    gates = (panels, strokes, legends, frame, aspects, curves)
    return {
        "status": "pass" if not collisions and not clipped and not glyph_warnings and not small_text and all(x['status'] == 'pass' for x in gates) else "fail",
        "method": "Matplotlib rendered artist bounding-box screening at final figure size",
        "collisions": collisions,
        "clipped": clipped,
        "glyph_warnings": glyph_warnings,
        "text_count": len(text_items),
        "small_text": small_text,
        "ignored_collision_artists": len(ignored),
        "final_size_inches": list(map(float, figure.get_size_inches())),
        "dpi": float(figure.dpi),
        "panel_size_uniformity": panels,
        "text_solid_stroke_clearance": strokes,
        "legend_data_region_clearance": legends,
        "axes_frame_closed": frame,
        "panel_aspect_whitelist": aspects,
        "curve_smoothing": curves,
    }


def inspect_panel_sizes(figure, groups=None, justifications=None, tolerance=0.02):
    """Measure drawn plotting areas, excluding automatic colorbar axes only."""
    import math
    if not math.isfinite(tolerance) or not 0 <= tolerance <= 0.02:
        raise ValueError('panel tolerance must be finite and between 0 and 0.02')
    axes = [a for a in figure.axes if a.get_visible() and a.get_label() != '<colorbar>']
    groups = groups if groups is not None else {'peers': axes}
    covered = [a for items in groups.values() for a in items]
    if len(covered) != len(set(covered)) or set(covered) != set(axes):
        raise ValueError('panel groups must cover each visible non-colorbar axes exactly once')
    violations, measurements = [], []
    for name, items in groups.items():
        sizes = [{'panel': a.get_label() or f'axes[{figure.axes.index(a)}]',
                  'width_pt': a.bbox.width * 72 / figure.dpi,
                  'height_pt': a.bbox.height * 72 / figure.dpi} for a in items]
        if not sizes:
            continue
        dw = max(s['width_pt'] for s in sizes) / min(s['width_pt'] for s in sizes) - 1
        dh = max(s['height_pt'] for s in sizes) / min(s['height_pt'] for s in sizes) - 1
        reason = (justifications or {}).get(name, '')
        record = {'group': name, 'panels': sizes, 'width_difference': dw, 'height_difference': dh,
                  'justification': reason, 'exception_applied': bool(str(reason).strip()) and max(dw, dh) > tolerance}
        measurements.append(record)
        if max(dw, dh) > tolerance + 1e-9 and not str(reason).strip():
            violations.append(record)
    return {'status': 'fail' if violations else 'pass', 'method': 'drawn plotting-area max/min - 1',
            'tolerance': tolerance, 'groups': measurements, 'violations': violations}


def _tick_side_active(axis: Any, *, secondary: bool) -> bool:
    """True when the tick line or label on that side is actually drawn.

    ``Axis.get_ticks_position()`` reports ``unknown`` after several ``tick_params``
    combinations, so the drawn artists are the only reliable signal.
    """
    for tick in axis.get_major_ticks():
        line = getattr(tick, "tick2line" if secondary else "tick1line", None)
        label = getattr(tick, "label2" if secondary else "label1", None)
        if line is not None and line.get_visible():
            return True
        if label is not None and label.get_visible():
            return True
    return False


def _visible_tick_sides(ax: Any) -> list[str]:
    """Report which sides actually carry ticks; the closed frame is enforced separately."""
    sides = []
    if ax.xaxis.get_visible():
        if _tick_side_active(ax.xaxis, secondary=False):
            sides.append("bottom")
        if _tick_side_active(ax.xaxis, secondary=True):
            sides.append("top")
    if ax.yaxis.get_visible():
        if _tick_side_active(ax.yaxis, secondary=False):
            sides.append("left")
        if _tick_side_active(ax.yaxis, secondary=True):
            sides.append("right")
    return sides


def inspect_axes_frame(figure: Any, *, exemptions: dict | None = None,
                       required_sides: tuple = ("left", "right", "top", "bottom"),
                       default_tick_sides: tuple = ("left", "bottom"),
                       skip_projections: tuple = (),
                       tick_side_justifications: dict | None = None,
                       require_tick_side_justification: bool = True) -> dict[str, Any]:
    """Every rectangular data axes must draw all four spines.

    Ticks and tick labels stay on the left and bottom by default. Enabling top or right
    ticks is a per-figure decision, so it needs a recorded reason unless
    ``require_tick_side_justification`` is turned off. Polar, 3D, projected map and
    ``axison=False`` axes are reported as skipped, not failed.
    """
    exemptions = {str(k): str(v) for k, v in (exemptions or {}).items() if str(v).strip()}
    tick_reasons = {str(k): str(v) for k, v in (tick_side_justifications or {}).items() if str(v).strip()}
    skip = {str(item).lower() for item in skip_projections}
    default_sides = {str(side).lower() for side in default_tick_sides}
    panels, violations, skipped = [], [], []
    for index, ax in enumerate(figure.axes):
        if not ax.get_visible():
            continue
        label = ax.get_label() or f"axes[{index}]"
        if label == "<colorbar>":
            skipped.append({"panel": label, "reason": "colorbar axes"})
            continue
        projection = str(getattr(ax, "name", "") or "").lower()
        if projection in skip:
            skipped.append({"panel": label, "reason": f"{projection} projection has no rectangular frame"})
            continue
        if not bool(getattr(ax, "axison", True)):
            skipped.append({"panel": label, "reason": "axison disabled: no coordinate frame to close"})
            continue
        spines = {side: bool(ax.spines[side].get_visible()) for side in required_sides if side in ax.spines}
        hidden = sorted(side for side, shown in spines.items() if not shown)
        tick_sides = _visible_tick_sides(ax)
        non_default = sorted(side for side in tick_sides if side not in default_sides)
        frame_reason = exemptions.get(label, "")
        tick_reason = tick_reasons.get(label, "")
        record = {"panel": label, "spines": spines, "hidden_spines": hidden, "tick_sides": tick_sides,
                  "non_default_tick_sides": non_default,
                  "justification": frame_reason, "tick_side_justification": tick_reason,
                  "exception_applied": bool(frame_reason) and bool(hidden)}
        panels.append(record)
        if hidden and not frame_reason:
            violations.append(record)
        if non_default and require_tick_side_justification and not tick_reason:
            violations.append({**record, "kind": "undeclared_tick_side",
                               "detail": f"{', '.join(non_default)} ticks are off by default; record why this panel needs them in style_policy.tick_side_justifications"})
    return {"status": "fail" if violations else "pass",
            "method": "per-axes spine visibility and tick sides at final figure size",
            "required_sides": list(required_sides), "default_tick_sides": sorted(default_sides),
            "require_tick_side_justification": bool(require_tick_side_justification),
            "panels": panels, "skipped": skipped, "violations": violations}


def inspect_panel_aspects(figure: Any, *, whitelist: tuple = ((1, 1), (4, 3), (16, 9)), tolerance: float = 0.02,
                          allow_reciprocal: bool = True, min_data_axes: int = 2,
                          justifications: dict | None = None, groups: dict | None = None) -> dict[str, Any]:
    """Composite figures must keep every data panel inside the allowed aspect whitelist.

    Judged on the drawn plotting area (axes bbox), not on the panel plus its labels.
    A single-panel figure is out of scope; that is reported, not silently passed.
    """
    import math
    if not math.isfinite(tolerance) or not 0 < tolerance <= 0.05:
        raise ValueError("panel aspect tolerance must be finite and between 0 and 0.05")
    axes = [a for a in figure.axes if a.get_visible() and a.get_label() != "<colorbar>"
            and bool(getattr(a, "axison", True))]
    candidates = []
    for pair in whitelist:
        width, height = float(pair[0]), float(pair[1])
        if width <= 0 or height <= 0:
            raise ValueError("whitelist ratios must be positive")
        candidates.append((width / height, f"{int(width)}:{int(height)}"))
        if allow_reciprocal:
            candidates.append((height / width, f"{int(height)}:{int(width)}"))
    whitelist_labels = [f"{int(float(p[0]))}:{int(float(p[1]))}" for p in whitelist]
    if len(axes) < min_data_axes:
        return {"status": "pass", "applies": False, "whitelist": whitelist_labels, "tolerance": tolerance,
                "method": "drawn plotting-area width/height against the ratio whitelist",
                "note": f"composite rule; found {len(axes)} data axes, threshold is {min_data_axes}",
                "panels": [], "violations": []}
    group_of = {id(a): name for name, items in (groups or {}).items() for a in items}
    measurements, violations = [], []
    for ax in axes:
        label = ax.get_label() or f"axes[{figure.axes.index(ax)}]"
        aspect = ax.bbox.width / max(ax.bbox.height, 1e-9)
        ratio, name = min(candidates, key=lambda item: abs(aspect - item[0]) / item[0])
        deviation = abs(aspect - ratio) / ratio
        reason = str((justifications or {}).get(label, "")
                     or (justifications or {}).get(group_of.get(id(ax), ""), "")).strip()
        record = {"panel": label, "width_pt": round(ax.bbox.width * 72 / figure.dpi, 3),
                  "height_pt": round(ax.bbox.height * 72 / figure.dpi, 3), "aspect": round(aspect, 4),
                  "nearest_allowed": name, "deviation": round(deviation, 4),
                  "justification": reason, "exception_applied": bool(reason) and deviation > tolerance}
        measurements.append(record)
        if deviation > tolerance + 1e-9 and not reason:
            violations.append(record)
    return {"status": "fail" if violations else "pass", "applies": True, "whitelist": whitelist_labels,
            "allow_reciprocal": bool(allow_reciprocal), "tolerance": tolerance,
            "method": "drawn plotting-area width/height against the ratio whitelist",
            "panels": measurements, "violations": violations}


def _turn_angles(points: Any) -> Any:
    """Interior-vertex turn angle in degrees for a display-space polyline."""
    import numpy as np
    if len(points) < 3:
        return np.zeros(0)
    segments = np.diff(points, axis=0)
    first, second = segments[:-1], segments[1:]
    norm_first = np.linalg.norm(first, axis=1)
    norm_second = np.linalg.norm(second, axis=1)
    good = (norm_first > 1e-12) & (norm_second > 1e-12)
    cosine = np.ones(len(first))
    cosine[good] = np.clip(np.sum(first[good] * second[good], axis=1)
                           / (norm_first[good] * norm_second[good]), -1.0, 1.0)
    angles = np.degrees(np.arccos(cosine))
    angles[~good] = 0.0
    return angles


def _is_straight(points: Any, tolerance_deg: float = 0.5) -> bool:
    angles = _turn_angles(points)
    return len(angles) == 0 or float(max(angles)) <= tolerance_deg


def _extrema_count(values: Any, eps: float) -> int:
    """Turning points in a sequence, ignoring plateaus and sub-epsilon wobble."""
    import numpy as np
    if len(values) < 3:
        return 0
    delta = np.diff(np.asarray(values, dtype=float))
    sign = np.sign(np.where(np.abs(delta) <= eps, 0.0, delta))
    sign = sign[sign != 0]
    return int(np.count_nonzero(sign[1:] != sign[:-1])) if len(sign) > 1 else 0


def _max_off_path_distance(path: Any, points: Any) -> float:
    """Largest display-space distance from a sample point to the rendered polyline."""
    import numpy as np
    if len(path) < 2 or not len(points):
        return float("inf")
    starts, ends = path[:-1], path[1:]
    delta = ends - starts
    denominator = np.sum(delta * delta, axis=1)
    denominator[denominator <= 0] = 1e-30
    worst = 0.0
    for point in points:
        offset = point - starts
        position = np.clip(np.sum(offset * delta, axis=1) / denominator, 0.0, 1.0)
        closest = starts + position[:, None] * delta
        worst = max(worst, float(np.min(np.linalg.norm(point - closest, axis=1))))
    return worst


def _normalise_declaration(value: Any) -> dict[str, Any]:
    """Accept the short ``{"name": kind}`` form or the full declaration object."""
    if isinstance(value, str):
        return {"kind": value}
    if isinstance(value, dict):
        return dict(value)
    raise ValueError("a continuity declaration must be a kind string or an object with a kind")


def _envelope(declared: dict, key: str) -> tuple[float, float] | None:
    import math
    value = declared.get(key)
    if isinstance(value, (list, tuple)) and len(value) == 2:
        low, high = float(value[0]), float(value[1])
        if math.isfinite(low) and math.isfinite(high) and low <= high:
            return low, high
    return None


def inspect_curve_smoothing(figure: Any, *, declarations: dict | None = None,
                            kinds: tuple = ("continuous", "discrete", "step", "piecewise_linear"),
                            min_dense_samples: int = 24, max_turn_deg: float = 12.0,
                            max_segment_fraction: float = 0.06,
                            overshoot_fraction: float = 0.01) -> dict[str, Any]:
    """Enforce the declared continuity of every visible solid data line.

    ``continuous`` lines must be drawn as a smooth curve: densely sampled, without
    angular corners between long segments, and inside the original data envelope
    declared in ``y_range``/``x_range`` so a smoothed curve cannot overshoot or invent
    turning points. ``discrete`` and ``piecewise_linear`` lines must stay on their
    original sample points. ``step`` lines need a ``steps-*`` drawstyle. Axis-aligned
    two-point reference lines are reported as skipped, not failed.
    """
    import math
    import numpy as np
    declarations = {str(k): v for k, v in (declarations or {}).items()}
    if not math.isfinite(max_turn_deg) or not 0 < max_turn_deg <= 90:
        raise ValueError("max_turn_deg must be finite and between 0 and 90")
    if not math.isfinite(max_segment_fraction) or not 0 < max_segment_fraction <= 1:
        raise ValueError("max_segment_fraction must be finite and between 0 and 1")
    if not math.isfinite(overshoot_fraction) or not 0 <= overshoot_fraction <= 0.1:
        raise ValueError("overshoot_fraction must be finite and between 0 and 0.1")
    lines, violations, skipped = [], [], []
    for ax in figure.axes:
        if not ax.get_visible() or not bool(getattr(ax, "axison", True)) or ax.get_label() == "<colorbar>":
            continue
        diagonal = max(float(np.hypot(ax.bbox.width, ax.bbox.height)), 1e-9)
        for index, line in enumerate(ax.lines):
            if not line.get_visible() or str(line.get_linestyle()).lower() in ("none", "", " ", "null"):
                continue
            panel = ax.get_label() or f"axes[{figure.axes.index(ax)}]"
            key = str(line.get_gid() or "").strip() or str(line.get_label() or "").strip()
            record = {"panel": panel, "line": key or f"{panel}#line[{index}]"}
            try:
                data_x = np.asarray(line.get_xdata(), dtype=float)
                data_y = np.asarray(line.get_ydata(), dtype=float)
            except (TypeError, ValueError):
                skipped.append({**record, "reason": "non-numeric x/y data (categorical or datetime)"})
                continue
            finite = np.isfinite(data_x) & np.isfinite(data_y)
            data_x, data_y = data_x[finite], data_y[finite]
            if len(data_y) < 2:
                skipped.append({**record, "reason": "fewer than two finite samples"})
                continue
            axis_aligned = len(data_y) == 2 and (abs(data_x[1] - data_x[0]) <= 1e-12 or abs(data_y[1] - data_y[0]) <= 1e-12)
            if axis_aligned and key not in declarations:
                skipped.append({**record, "reason": "unnamed axis-aligned two-point reference line"})
                continue
            if not key or key not in declarations:
                violations.append({**record, "kind": "missing_declaration",
                                   "detail": "set the line gid and record it in style_policy.continuity_declarations"})
                continue
            declared = _normalise_declaration(declarations[key])
            kind = declared.get("kind")
            if kind not in kinds:
                violations.append({**record, "kind": "unknown_declaration", "detail": str(kind)})
                continue
            record["declared"] = kind
            path = np.asarray(line.get_path().vertices, dtype=float)
            display = line.get_transform().transform(path)
            display = display[np.isfinite(display).all(axis=1)]
            samples = line.get_transform().transform(np.column_stack([data_x, data_y]))
            record["path_vertices"] = int(len(display))
            record["data_points"] = int(len(data_y))
            span = float(np.max(data_y) - np.min(data_y))
            eps = max(span * 1e-9, 1e-12)

            if kind == "step":
                if not str(line.get_drawstyle() or "").startswith("steps"):
                    violations.append({**record, "kind": "step_drawstyle",
                                       "detail": "piecewise-constant lines need a steps-* drawstyle"})
                lines.append(record)
                continue

            if kind == "continuous":
                if 2 < len(display) < min_dense_samples and not _is_straight(display):
                    violations.append({**record, "kind": "sparse_sampling",
                                       "detail": f"{len(display)} path vertices; a continuous curve needs >= {min_dense_samples} dense samples or a straight line"})
                if len(display) >= 3:
                    angles = _turn_angles(display)
                    lengths = np.linalg.norm(np.diff(display, axis=0), axis=1)
                    adjacent = np.minimum(lengths[:-1], lengths[1:])
                    record["max_turn_deg"] = round(float(np.max(angles)), 3)
                    coarse = (angles > max_turn_deg) & (adjacent / diagonal > max_segment_fraction)
                    if bool(np.any(coarse)):
                        worst = int(np.argmax(np.where(coarse, angles, 0.0)))
                        violations.append({**record, "kind": "coarse_corner",
                                           "detail": f"{round(float(angles[worst]), 2)} deg corner between long segments; interpolate instead of joining raw samples"})
                path_y = path[np.isfinite(path[:, 1]), 1]
                path_x = path[np.isfinite(path[:, 0]), 0]
                data_low, data_high = float(np.min(data_y)), float(np.max(data_y))
                tolerance = max(overshoot_fraction * span, 1e-12)
                if len(path_y) and (float(np.min(path_y)) < data_low - tolerance or float(np.max(path_y)) > data_high + tolerance):
                    violations.append({**record, "kind": "overshoot",
                                       "detail": "the drawn curve leaves its own sample range"})
                envelope_y = _envelope(declared, "y_range")
                if envelope_y is None:
                    violations.append({**record, "kind": "missing_data_envelope",
                                       "detail": "declare y_range from the original data so smoothing cannot silently overshoot it"})
                elif len(path_y):
                    low, high = envelope_y
                    margin = max(overshoot_fraction * (high - low), 1e-12)
                    record["y_range"] = [low, high]
                    record["path_range"] = [round(float(np.min(path_y)), 9), round(float(np.max(path_y)), 9)]
                    if float(np.min(path_y)) < low - margin or float(np.max(path_y)) > high + margin:
                        violations.append({**record, "kind": "envelope_overshoot",
                                           "detail": f"drawn range {record['path_range']} leaves the declared data range {record['y_range']}; use an interpolant without overshoot"})
                envelope_x = _envelope(declared, "x_range")
                if envelope_x is not None and len(path_x):
                    low, high = envelope_x
                    margin = max(overshoot_fraction * (high - low), 1e-12)
                    if float(np.min(path_x)) < low - margin or float(np.max(path_x)) > high + margin:
                        violations.append({**record, "kind": "envelope_overshoot",
                                           "detail": "the drawn curve leaves the declared x range"})
                turning = declared.get("turning_points")
                path_extrema = _extrema_count(path_y, eps) if len(path_y) else 0
                data_extrema = _extrema_count(data_y, eps)
                record["extrema"] = {"path": path_extrema, "data": data_extrema,
                                     "declared": None if turning is None else int(turning)}
                if turning is not None and path_extrema > int(turning):
                    violations.append({**record, "kind": "fabricated_extremum",
                                       "detail": f"the drawn curve turns {path_extrema} times against {int(turning)} in the original data"})
                elif turning is None and path_extrema > data_extrema:
                    violations.append({**record, "kind": "fabricated_extremum",
                                       "detail": f"the drawn curve turns {path_extrema} times against {data_extrema} in the plotted samples"})
                lines.append(record)
                continue

            if len(path) != len(data_y):
                violations.append({**record, "kind": "rendered_vertices",
                                   "detail": f"{len(path)} path vertices for {len(data_y)} plotted samples"})
            declared_samples = declared.get("sample_count")
            if not isinstance(declared_samples, int) or isinstance(declared_samples, bool) or declared_samples < 2:
                violations.append({**record, "kind": "missing_sample_count",
                                   "detail": f"declare sample_count from the original data so a {kind} line cannot be silently densified"})
            else:
                record["sample_count"] = declared_samples
                if declared_samples != len(data_y):
                    violations.append({**record, "kind": "interpolated_samples",
                                       "detail": f"{len(data_y)} plotted samples against {declared_samples} original samples; a declared {kind} line must not be densified"})
                else:
                    offset = _max_off_path_distance(display, samples)
                    record["max_off_path_pt"] = round(offset * 72 / figure.dpi, 9)
                    if offset > 1e-6 * diagonal:
                        violations.append({**record, "kind": "moved_sample",
                                           "detail": "the rendered path does not pass through the declared sample points"})
            lines.append(record)
    return {"status": "fail" if violations else "pass",
            "method": "declared continuity versus rendered path geometry (sampling density, corner angle, data envelope, turning points, sample fidelity)",
            "kinds": list(kinds), "min_dense_samples": min_dense_samples, "max_turn_deg": max_turn_deg,
            "max_segment_fraction": max_segment_fraction, "overshoot_fraction": overshoot_fraction,
            "lines": lines, "skipped": skipped, "violations": violations}


def _drawn_text(figure):
    """Matplotlib retains visible=True tick artists outside the draw interval."""
    from matplotlib.text import Text
    import numpy as np
    hidden = set()
    for ax in figure.axes:
        if not ax.get_visible():
            hidden.update(id(a) for a in ax.findobj())
        for axis in (ax.xaxis, ax.yaxis):
            bounds = sorted(axis.get_transform().transform(axis.get_view_interval()))
            for tick in [*axis.get_major_ticks(), *axis.get_minor_ticks()]:
                loc = axis.get_transform().transform([tick.get_loc()])[0]
                if not ax.axison or not axis.get_visible() or not np.isfinite(loc) or not bounds[0]-1e-9 <= loc <= bounds[1]+1e-9:
                    hidden.update((id(tick.label1), id(tick.label2)))
            if not ax.axison or not axis.get_visible():
                hidden.update((id(axis.label), id(axis.offsetText)))
    return [a for a in figure.findobj(match=Text) if id(a) not in hidden and a.get_visible() and a.get_text().strip()]


def _segments(path, transform, clip):
    """Flatten transformed curves and clip line segments to their actual clip box."""
    from matplotlib.path import Path
    import numpy as np
    previous = first = None
    for vertices, code in transform.transform_path(path).iter_segments(curves=False, simplify=False):
        point = np.asarray(vertices[-2:])
        if code == Path.MOVETO:
            previous = first = point
            continue
        if code == Path.CLOSEPOLY:
            point = first
        if previous is not None and point is not None and np.isfinite([*previous, *point]).all():
            a, b = previous.copy(), point.copy()
            delta = b - a
            lo, hi = 0., 1.
            if clip is not None:
                for p, q in ((-delta[0], a[0]-clip.x0), (delta[0], clip.x1-a[0]),
                             (-delta[1], a[1]-clip.y0), (delta[1], clip.y1-a[1])):
                    if p == 0:
                        if q < 0: hi = -1
                    elif p < 0: lo = max(lo, q/p)
                    else: hi = min(hi, q/p)
            if lo <= hi:
                yield a + lo*delta, a + hi*delta
        previous = point


def _distance(box, a, b):
    """Exact segment-to-rectangle distance, not overlapping enclosing boxes."""
    import numpy as np
    from matplotlib.path import Path
    path = Path([a, b])
    if path.intersects_bbox(box, filled=False) or box.contains(*a) or box.contains(*b):
        return 0.
    def point_segment(p, x, y):
        d = y-x
        t = np.clip(np.dot(p-x, d) / max(np.dot(d, d), 1e-30), 0, 1)
        return float(np.linalg.norm(p-x-t*d))
    corners = [np.array(p) for p in ((box.x0,box.y0),(box.x1,box.y0),(box.x1,box.y1),(box.x0,box.y1))]
    return min([point_segment(p,a,b) for p in corners] +
               [point_segment(p,corners[i],corners[(i+1)%4]) for p in (a,b) for i in range(4)])


def _stroke_geometry(figure):
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch
    from matplotlib.collections import Collection
    from matplotlib.transforms import Affine2D
    from matplotlib.markers import MarkerStyle
    import numpy as np
    backgrounds = {figure.patch, *(a.patch for a in figure.axes)}
    for obj in figure.findobj(lambda a: isinstance(a, (Line2D, Patch, Collection))):
        if obj in backgrounds or not obj.get_visible() or obj.get_alpha() == 0:
            continue
        clip = obj.get_clip_box() if obj.get_clip_on() else None
        if clip is None and obj.get_clip_on() and obj.axes is not None:
            clip = obj.axes.bbox
        geometries = []
        if isinstance(obj, Line2D):
            if obj.get_linestyle() in ('-', 'solid'):
                geometries.append((obj.get_path(), obj.get_transform(), obj.get_linewidth(), False))
            if obj.get_marker() not in (None, 'None', '', ' '):
                marker = MarkerStyle(obj.get_marker())
                for xy in obj.get_transform().transform(obj.get_xydata()):
                    transform = marker.get_transform() + Affine2D().scale(obj.get_markersize()*figure.dpi/72).translate(*xy)
                    geometries.append((marker.get_path(), transform, obj.get_markeredgewidth(), True))
        elif isinstance(obj, Patch):
            if obj.get_linestyle() in ('-', 'solid', None) and obj.get_linewidth() > 0 and obj.get_edgecolor()[3] > 0:
                geometries.append((obj.get_path(), obj.get_transform(), obj.get_linewidth(), False))
        else:
            paths, transforms = obj.get_paths(), obj.get_transforms()
            offsets = obj.get_offset_transform().transform(obj.get_offsets())
            widths, styles = obj.get_linewidths(), obj.get_linestyles()
            edges, faces = obj.get_edgecolors(), obj.get_facecolors()
            for i in range(max(len(paths), len(offsets))):
                if not paths: break
                style = styles[i % len(styles)] if len(styles) else (0, None)
                if style[1] is not None: continue
                edge = edges[i % len(edges)] if len(edges) else (0,0,0,0)
                face = faces[i % len(faces)] if len(faces) else (0,0,0,0)
                if edge[3] == 0 and face[3] == 0: continue
                transform = Affine2D(transforms[i % len(transforms)]) if len(transforms) else Affine2D()
                transform = transform + obj.get_transform()
                if len(offsets): transform += Affine2D().translate(*offsets[i % len(offsets)])
                geometries.append((paths[i % len(paths)], transform, float(widths[i % len(widths)]) if len(widths) and edge[3] else 0., face[3] > 0))
        for path, transform, width, filled in geometries:
            segments = list(_segments(path, transform, clip))
            if segments:
                yield obj, segments, width * figure.dpi / 144, transform.transform_path(path) if filled else None


def inspect_stroke_clearance(figure, renderer, clearance_pt=4., legend_pt=4., exemptions=()):
    from matplotlib.text import Text, Annotation
    from matplotlib.legend import Legend
    import math
    if any(not math.isfinite(v) or v < 0 for v in (clearance_pt, legend_pt)):
        raise ValueError('clearances must be finite nonnegative points')
    exempt = {}
    for text, stroke, reason in exemptions:
        if not str(reason).strip(): raise ValueError('stroke exemption needs a reason')
        exempt[(id(text), id(stroke))] = reason
    legends = figure.findobj(match=Legend)
    legend_members = {id(l): {id(a) for a in l.findobj()} for l in legends}
    geometry = list(_stroke_geometry(figure))
    failures, legend_failures = [], []
    point_px = figure.dpi / 72
    exemptions_used = []
    for text in _drawn_text(figure):
        if not text.get_visible() or not text.get_text().strip(): continue
        # Annotation extent includes its own arrow. Check the text alone.
        box = Text.get_window_extent(text, renderer=renderer)
        for stroke, segments, radius, filled in geometry:
            if stroke is text.get_bbox_patch() or (isinstance(text, Annotation) and stroke is text.arrow_patch):
                continue  # Own callout frame/leader is a structural relationship.
            if any(id(text) in ids and id(stroke) in ids for ids in legend_members.values()):
                continue  # Legend handles/frame are measured by legend padding + visual review.
            distance = min(_distance(box, a, b) for a, b in segments) - radius
            if filled is not None and filled.contains_point(((box.x0+box.x1)/2, (box.y0+box.y1)/2)):
                distance = min(distance, -radius)
            if distance / point_px >= clearance_pt and distance > 0: continue
            record = {'text': text.get_text(), 'panel': text.axes.get_label() if text.axes else 'figure',
                      'stroke': stroke.get_gid() or stroke.get_label() or type(stroke).__name__,
                      'distance_pt': round(distance/point_px, 3), 'required_pt': clearance_pt,
                      'severity': 'contact' if distance <= 0 else 'clearance'}
            if (id(text),id(stroke)) in exempt and distance > 0:
                exemptions_used.append({**record, 'reason': exempt[(id(text),id(stroke))]})
            else: failures.append(record)  # Contact cannot be exempted.
    for legend in legends:
        if not legend.get_visible(): continue
        box = legend.get_window_extent(renderer)
        for stroke, segments, radius, filled in geometry:
            if any(id(stroke) in ids for ids in legend_members.values()): continue
            # Only data marks, not the owning axes frame or ticks.
            ax = stroke.axes
            if ax is None or stroke not in [*ax.lines, *ax.collections, *ax.patches]: continue
            distance = min(_distance(box,a,b) for a,b in segments)-radius
            if filled is not None and filled.contains_point(((box.x0+box.x1)/2,(box.y0+box.y1)/2)):
                distance = min(distance, -radius)
            if distance/point_px < legend_pt or distance <= 0:
                legend_failures.append({'legend': legend.get_title().get_text() or 'legend',
                                        'stroke': stroke.get_gid() or stroke.get_label(), 'distance_pt': round(distance/point_px,3)})
    method = 'final-size transformed paths, segment-to-text bbox distance minus half linewidth (pt)'
    return ({'status': 'fail' if failures else 'pass', 'method': method, 'violations': failures,
             'exemptions': exemptions_used, 'clearance_pt': clearance_pt},
            {'status': 'fail' if legend_failures else 'pass', 'method': 'legend frame versus data paths/markers',
             'violations': legend_failures, 'clearance_pt': legend_pt})


def assert_figure_layout(figure: Any, **kwargs: Any) -> dict[str, Any]:
    result = inspect_figure_layout(figure, **kwargs)
    if result["status"] != "pass":
        raise AssertionError(
            f"layout QA failed: {len(result['collisions'])} collision(s), {len(result['clipped'])} clipped text item(s), {len(result['glyph_warnings'])} missing-glyph warning(s)"
        )
    return result
