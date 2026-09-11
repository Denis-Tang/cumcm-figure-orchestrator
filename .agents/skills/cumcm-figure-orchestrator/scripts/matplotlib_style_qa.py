#!/usr/bin/env python3
"""Matplotlib style QA for the CUMCM V02-only figure contract.

This module complements, rather than replaces, the existing layout QA.
It checks:
- closed four-spine Cartesian frames;
- top/right ticks disabled by default;
- abnormal panel aspect ratios;
- optional peer-panel area imbalance;
- text-to-data-line clearance for annotations/ax.text().

It intentionally does not certify scientific correctness.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Iterable, Sequence
import json

from matplotlib.axes import Axes
from matplotlib.lines import Line2D
from matplotlib.transforms import Bbox
from matplotlib.text import Text
from matplotlib.path import Path
import numpy as np


@dataclass
class StyleIssue:
    code: str
    severity: str
    message: str
    axes_index: int | None = None

    def to_dict(self):
        return asdict(self)


def apply_closed_cartesian_style(ax: Axes, *, right_ticks: bool = False, top_ticks: bool = False, frame_owner: Axes | None = None) -> Axes:
    """Apply the competition-paper frame policy to one Cartesian axes."""
    if getattr(ax, "name", None) != "rectilinear":
        raise ValueError("Closed frame helper requires a Cartesian axes")
    if frame_owner is not None:
        if frame_owner.figure is not ax.figure or not (
            ax.get_shared_x_axes().joined(ax, frame_owner) or
            ax.get_shared_y_axes().joined(ax, frame_owner)):
            raise ValueError("frame_owner must be a shared twin in the same figure")
        apply_closed_cartesian_style(frame_owner)
    ax._cumcm_frame_owner = frame_owner
    for side in ("left", "bottom", "top", "right"):
        ax.spines[side].set_visible(frame_owner is None)
    ax.tick_params(
        axis="x",
        which="both",
        bottom=not top_ticks,
        labelbottom=not top_ticks,
        top=top_ticks,
        labeltop=top_ticks,
    )
    ax.tick_params(
        axis="y",
        which="both",
        left=not right_ticks,
        labelleft=not right_ticks,
        right=right_ticks,
        labelright=right_ticks,
    )
    return ax


def _is_cartesian(ax: Axes) -> bool:
    return (getattr(ax, "name", None) == "rectilinear" and ax.get_visible()
            and ax.axison and not hasattr(ax, "_colorbar")
            and getattr(ax, "_cumcm_style_role", "data") == "data")


def check_closed_frame(fig) -> list[StyleIssue]:
    issues: list[StyleIssue] = []
    for i, ax in enumerate(fig.axes):
        if not _is_cartesian(ax):
            continue
        owner = getattr(ax, "_cumcm_frame_owner", None)
        if owner is not None:
            if any(sp.get_visible() for sp in ax.spines.values()):
                issues.append(StyleIssue("duplicate_twin_frame", "error", "Twin must use its owner's frame", i))
            if not np.allclose(ax.get_position().bounds, owner.get_position().bounds):
                issues.append(StyleIssue("misaligned_twin_frame", "error", "Twin and owner must align", i))
        target = owner if owner is not None else ax
        missing = [side for side in ("left", "bottom", "top", "right") if not target.spines[side].get_visible()]
        if missing:
            issues.append(StyleIssue(
                "open_cartesian_frame",
                "error",
                f"Cartesian axes must show all four spines; missing: {', '.join(missing)}",
                i,
            ))
    return issues


def check_default_tick_sides(fig, *, allow_axes: Iterable[int] = ()) -> list[StyleIssue]:
    """Flag top/right tick marks or labels unless the axes index is explicitly allowed.

    Twin axes or special coordinate use should pass their axes indexes via allow_axes.
    """
    allow = set(allow_axes)
    issues: list[StyleIssue] = []
    fig.canvas.draw()
    for i, ax in enumerate(fig.axes):
        if i in allow or not _is_cartesian(ax):
            continue
        top_visible = any(
            t.tick2line.get_visible() or t.label2.get_visible()
            for t in ax.xaxis.get_major_ticks() + ax.xaxis.get_minor_ticks()
        )
        right_visible = any(
            t.tick2line.get_visible() or t.label2.get_visible()
            for t in ax.yaxis.get_major_ticks() + ax.yaxis.get_minor_ticks()
        )
        if top_visible:
            issues.append(StyleIssue(
                "unexpected_top_ticks",
                "error",
                "Top ticks/tick labels are disabled by default; enable only for a justified special axis.",
                i,
            ))
        if right_visible:
            issues.append(StyleIssue(
                "unexpected_right_ticks",
                "error",
                "Right ticks/tick labels are disabled by default; enable only for a twin/special axis.",
                i,
            ))
    return issues


def check_panel_aspect_ratios(
    fig,
    *,
    min_ratio: float = 0.45,
    max_ratio: float = 3.0,
    axes: Sequence[Axes] | None = None,
) -> list[StyleIssue]:
    """Hard-gate extreme panel ratios.

    The preferred design range is narrower (around 1:1, 4:3, 16:9), but this
    function only fails clearly abnormal panels by default.
    """
    issues: list[StyleIssue] = []
    fig.canvas.draw()
    selected = list(axes) if axes is not None else [ax for ax in fig.axes if _is_cartesian(ax)]
    for ax in selected:
        bbox = ax.get_window_extent()
        if bbox.height <= 0:
            continue
        ratio = bbox.width / bbox.height
        try:
            idx = fig.axes.index(ax)
        except ValueError:
            idx = None
        if ratio < min_ratio or ratio > max_ratio:
            issues.append(StyleIssue(
                "extreme_panel_aspect",
                "error",
                f"Panel aspect ratio {ratio:.2f}:1 is unusually extreme; prefer conventional proportions unless scientifically necessary.",
                idx,
            ))
        elif ratio < 0.60 or ratio > 2.20:
            issues.append(StyleIssue(
                "panel_aspect_review",
                "warning",
                f"Panel aspect ratio {ratio:.2f}:1 is outside the preferred range; visually review against 1:1, 4:3, or 16:9 alternatives.",
                idx,
            ))
    return issues


def check_peer_panel_area_balance(
    fig,
    axes: Sequence[Axes],
    *,
    max_area_ratio: float = 1.35,
) -> list[StyleIssue]:
    """Check same-level peer panels for unexpected size imbalance."""
    fig.canvas.draw()
    areas = []
    for ax in axes:
        bbox = ax.get_window_extent()
        areas.append(max(0.0, bbox.width * bbox.height))
    positive = [a for a in areas if a > 0]
    if len(positive) < 2:
        return []
    ratio = max(positive) / min(positive)
    if ratio <= max_area_ratio:
        return []
    return [StyleIssue(
        "peer_panel_area_imbalance",
        "error",
        f"Peer panel area ratio is {ratio:.2f}; same-level panels should be approximately equal in area.",
        None,
    )]


def check_text_line_clearance(
    fig,
    *,
    clearance_px: float = 6.0,
    include_dashed: bool = True,
) -> list[StyleIssue]:
    """Check ax.text()/Annotation against plotted Line2D artists.

    Axis labels/tick labels are intentionally excluded here because they are
    governed by normal axis padding. This targets in-plot annotations, where
    accidental line contact is most common.
    """
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    issues: list[StyleIssue] = []

    for i, ax in enumerate(fig.axes):
        if not _is_cartesian(ax):
            continue
        texts = [t for t in list(ax.texts) + [ax.title, ax._left_title, ax._right_title] if t.get_visible() and t.get_text().strip()]
        lines = [ln for ln in ax.lines if ln.get_visible() and ln.get_linestyle() not in ("", " ", "None", None)]
        for text in texts:
            bbox = Text.get_window_extent(text, renderer=renderer)
            if bbox.width == 0 or bbox.height == 0:
                continue
            expanded = Bbox.from_extents(
                bbox.x0 - clearance_px,
                bbox.y0 - clearance_px,
                bbox.x1 + clearance_px,
                bbox.y1 + clearance_px,
            )
            for line in lines:
                linestyle = str(line.get_linestyle())
                if not include_dashed and linestyle not in ("-", "solid"):
                    continue
                path = line.get_transform().transform_path(line.get_path())
                padding = clearance_px + line.get_linewidth() * fig.dpi / 144
                expanded = bbox.padded(padding)
                if line.get_clip_on():
                    clip = line.get_clip_box()
                    if clip is not None:
                        expanded = Bbox.intersection(expanded, clip)
                        if expanded is None:
                            continue
                # Segment intersection, not sparse vertex sampling; MOVETO/NaN gaps stay gaps.
                if _path_hits_box(path, expanded):
                    severity = "error" if linestyle in ("-", "solid") else "warning"
                    issues.append(StyleIssue(
                        "text_line_clearance",
                        severity,
                        f"Text {text.get_text()!r} is too close to a plotted line; move/offset the label before using a background box.",
                        i,
                    ))
                    break
    return issues


def run_style_qa(
    fig,
    *,
    twin_or_special_tick_axes: Iterable[int] = (),
    peer_groups: Sequence[Sequence[Axes]] = (),
    clearance_px: float = 6.0,
) -> dict:
    issues: list[StyleIssue] = []
    issues.extend(check_closed_frame(fig))
    issues.extend(check_default_tick_sides(fig, allow_axes=twin_or_special_tick_axes))
    issues.extend(check_panel_aspect_ratios(fig))
    for group in peer_groups:
        issues.extend(check_peer_panel_area_balance(fig, group))
    issues.extend(check_text_line_clearance(fig, clearance_px=clearance_px))
    return {
        "ok": not any(issue.severity == "error" for issue in issues),
        "issues": [issue.to_dict() for issue in issues],
        "scope": "Screening of Cartesian frames, ticks, panel geometry and text/Line2D segments; markers, bars, spines and legends also require visual review",
        "excluded_axes": [{"index": i, "role": getattr(ax, "_cumcm_style_role", ax.name), "reason": getattr(ax, "_cumcm_style_reason", "hidden, axis-off, colorbar or non-Cartesian")} for i, ax in enumerate(fig.axes) if not _is_cartesian(ax)],
    }


def dump_style_qa(fig, path, **kwargs):
    result = run_style_qa(fig, **kwargs)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    return result


def set_style_role(ax, role: str, *, reason: str):
    """Explicitly classify rectilinear flow/network/map axes; retain reason in QA."""
    if role not in {"data", "flowchart", "network", "map", "auxiliary"} or not reason.strip():
        raise ValueError("A supported role and nonempty scientific reason are required")
    ax._cumcm_style_role = role
    ax._cumcm_style_reason = reason
    return ax


def _path_hits_box(path, bbox):
    previous = None
    for vertices, code in path.iter_segments(remove_nans=True, curves=False, simplify=False):
        point = vertices[-2:]
        if code == Path.MOVETO:
            previous = point
        elif code == Path.LINETO and previous is not None:
            if Path([previous, point]).intersects_bbox(bbox, filled=False):
                return True
            previous = point
        else:
            previous = None
    return False
