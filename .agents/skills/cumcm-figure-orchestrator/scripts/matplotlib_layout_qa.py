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
) -> dict[str, Any]:
    """Render a figure and report harmful text-text intersections and clipping.

    This is a screening gate. Call it after setting the final physical figure size.
    Deliberate overlaps can be passed in ``ignored_artists`` and must be documented.
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
    for artist in figure.findobj(match=Text):
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

    return {
        "status": "pass" if not collisions and not clipped and not glyph_warnings and not small_text else "fail",
        "method": "Matplotlib rendered artist bounding-box screening at final figure size",
        "collisions": collisions,
        "clipped": clipped,
        "glyph_warnings": glyph_warnings,
        "text_count": len(text_items),
        "small_text": small_text,
        "ignored_collision_artists": len(ignored),
    }


def assert_figure_layout(figure: Any, **kwargs: Any) -> dict[str, Any]:
    result = inspect_figure_layout(figure, **kwargs)
    if result["status"] != "pass":
        raise AssertionError(
            f"layout QA failed: {len(result['collisions'])} collision(s), {len(result['clipped'])} clipped text item(s), {len(result['glyph_warnings'])} missing-glyph warning(s)"
        )
    return result
