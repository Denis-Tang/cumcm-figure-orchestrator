"""Renderer-neutral categorical policy, with an optional Matplotlib adapter."""
from __future__ import annotations

import json
from pathlib import Path

ASSETS = Path(__file__).resolve().parents[1] / "assets"


def load_style(profile_path=None, palette_path=None):
    profile_path = Path(profile_path or ASSETS / "personal-figure-style.json")
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    palette_path = Path(palette_path or profile_path.parent / profile["palette_file"])
    palette = json.loads(palette_path.read_text(encoding="utf-8"))
    return profile, palette


def select_colors(objects, *, existing=None, overrides=None, emphasis="blue", profile=None, palette=None):
    """Return traceable object records; overrides require role + scientific/task reason.

    Pass the returned mapping as existing on subsequent figures. Never cycle colors
    for excess categories: the caller must choose markers/hatches/facets explicitly.
    This function is for categorical objects, never continuous colormaps.
    """
    default_profile, default_palette = load_style()
    profile, palette = profile or default_profile, palette or default_palette
    objects = list(objects)
    if len(set(objects)) != len(objects):
        raise ValueError("object IDs must be unique")
    mapping = {key: dict(value) for key, value in (existing or {}).items()}
    overrides = overrides or {}
    for key, record in overrides.items():
        if not str(record.get("reason", "")).strip():
            raise ValueError("semantic/task override requires a reason")
        mapping[key] = dict(record)
    used = {v["role"] for v in mapping.values()}
    order = list(profile["categorical_order"])
    if len(objects) == 1 and emphasis in profile["single_emphasis"]:
        order = [emphasis] + [r for r in order if r != emphasis]
    for key in objects:
        if key not in mapping:
            role = next((r for r in order if r not in used), None)
            if role is None:
                raise ValueError("categorical colors exhausted; use redundant encoding or a justified override")
            mapping[key] = {"role": role, "reason": "personal categorical priority; no implied scientific meaning"}
            used.add(role)
        record = mapping[key]
        role = record["role"]
        for field in ("colors", "large_area_fills", "soft_fills"):
            record[field] = palette[field][role]
        record["baseline_id"] = palette["baseline_id"]
    return {key: mapping[key] for key in objects}


CURVE_KINDS = ("continuous", "discrete", "step", "piecewise_linear")


def declare_continuity(artist, kind, *, name=None, y_range=None, x_range=None,
                       turning_points=None, sample_count=None, profile=None):
    """Name one data line and declare its continuity for the ``curve_smoothing`` gate.

    Every visible solid data line needs a stable ``gid`` and a declaration in
    ``style_policy.continuity_declarations``. ``continuous`` lines must be drawn
    smoothly and must carry the ``y_range`` of the original data so the gate can prove
    that smoothing did not overshoot it. ``discrete``/``piecewise_linear`` lines must
    carry the original ``sample_count`` so densifying them is detectable. ``step`` lines
    use a ``steps-*`` drawstyle. Returns the ``{name: declaration}`` record to merge
    into the batch policy.
    """
    default_profile, _ = load_style()
    profile = profile or default_profile
    kinds = tuple(profile.get("curve", {}).get("kinds", CURVE_KINDS))
    if kind not in kinds:
        raise ValueError(f"unknown continuity kind {kind!r}; expected one of {kinds}")
    key = str(name or artist.get_gid() or artist.get_label() or "").strip()
    if not key or key.startswith("_"):
        raise ValueError("continuity declaration needs a stable line name or gid")
    artist.set_gid(key)
    if kind == "step" and not str(artist.get_drawstyle() or "").startswith("steps"):
        artist.set_drawstyle("steps-post")
    record = {"kind": kind}
    for field, value in (("y_range", y_range), ("x_range", x_range), ("turning_points", turning_points),
                         ("sample_count", sample_count)):
        if value is not None:
            record[field] = list(value) if field.endswith("range") else int(value)
    if kind == "continuous" and "y_range" not in record:
        raise ValueError("a continuous curve needs y_range from the original data")
    if kind in ("discrete", "piecewise_linear") and "sample_count" not in record:
        raise ValueError(f"a {kind} line needs sample_count from the original data")
    return {key: record if len(record) > 1 else kind}


def apply_closed_cartesian_style(ax, *, labels=True, top_ticks=False, right_ticks=False):
    """Force the closed four-spine frame and the default tick sides on one Cartesian axes.

    ``matplotlib_style()`` already makes this the default; call this helper when a
    figure or a third-party renderer resets spines/ticks afterwards. Ticks and tick
    labels stay on the left and bottom unless ``top_ticks``/``right_ticks`` are asked
    for, and enabling either one requires a reason in
    ``style_policy.tick_side_justifications``. Pass ``labels=False`` for a shared grid
    where only the outer axes should carry tick labels.
    """
    for side in ("left", "bottom", "top", "right"):
        if side in ax.spines:
            ax.spines[side].set_visible(True)
    ax.tick_params(axis="x", bottom=True, labelbottom=labels,
                   top=top_ticks, labeltop=top_ticks and labels)
    ax.tick_params(axis="y", left=True, labelleft=labels,
                   right=right_ticks, labelright=right_ticks and labels)
    return ax


def matplotlib_style(profile=None, palette=None):
    """Use with plt.rc_context(...); no global rc mutation or embedded hex colors."""
    from cycler import cycler
    p, c = load_style()
    p, c = profile or p, palette or c
    return {**p["matplotlib"], "axes.prop_cycle": cycler(color=[c["colors"][r] for r in p["categorical_order"]]),
            "figure.facecolor": c["canvas"], "axes.facecolor": c["canvas"],
            "text.color": c["text"], "axes.labelcolor": c["text"],
            "xtick.color": c["text"], "ytick.color": c["text"], "grid.color": c["colors"][p["neutral_role"]]}
