"""Tests for the software rasteriser viewport."""

import numpy as np

from maidenhair.core.turtle3d import Geometry
from maidenhair.render.viewport import Viewport


def _make_simple_geometry() -> Geometry:
    """Create a simple geometry with a few segments."""
    geo = Geometry()
    geo.segments = [
        (np.array([0, 0, 0], dtype=float), np.array([0, 1, 0], dtype=float), 0.05),
        (np.array([0, 1, 0], dtype=float), np.array([0.5, 1.5, 0], dtype=float), 0.04),
        (np.array([0, 1, 0], dtype=float), np.array([-0.5, 1.5, 0], dtype=float), 0.04),
    ]
    return geo


def test_render_returns_bmp_bytes():
    """render() should return valid BMP bytes for interactive use."""
    vp = Viewport(width=400, height=300)
    vp.set_geometry(_make_simple_geometry())
    bmp = vp.render()
    assert isinstance(bmp, bytes)
    assert len(bmp) > 0
    # BMP magic bytes
    assert bmp[:2] == b"BM"


def test_render_png_returns_png_bytes():
    """render_png() should return valid PNG bytes for file export."""
    vp = Viewport(width=400, height=300)
    vp.set_geometry(_make_simple_geometry())
    png = vp.render_png()
    assert isinstance(png, bytes)
    assert png[:4] == b"\x89PNG"


def test_render_empty_geometry():
    """render() with no geometry should still return valid image."""
    vp = Viewport(width=200, height=200)
    bmp = vp.render()
    assert bmp[:2] == b"BM"


def test_render_non_zero_image():
    """Rendered image with geometry should not be a single solid color."""
    vp = Viewport(width=400, height=300)
    vp.set_geometry(_make_simple_geometry())
    img1 = vp.render()

    # Empty render for comparison
    vp2 = Viewport(width=400, height=300)
    img2 = vp2.render()

    # With geometry, the image should be different from empty
    assert img1 != img2


def test_rotate():
    """rotate() should change camera position."""
    vp = Viewport()
    vp.set_geometry(_make_simple_geometry())
    pos_before = vp.camera.position.copy()
    vp.rotate(50, 30)
    assert not np.allclose(vp.camera.position, pos_before)


def test_zoom():
    """zoom() should change camera distance."""
    vp = Viewport()
    vp.set_geometry(_make_simple_geometry())
    dist_before = vp.camera.distance
    vp.zoom(1.0)
    assert vp.camera.distance != dist_before


def test_pan():
    """pan() should shift camera target."""
    vp = Viewport()
    vp.set_geometry(_make_simple_geometry())
    target_before = vp.camera.target.copy()
    vp.pan(50, 30)
    assert not np.allclose(vp.camera.target, target_before)
