"""Tests for the 3D turtle interpreter."""

import numpy as np

from maidenhair.core.parametric import tokenise
from maidenhair.core.turtle3d import interpret


def test_single_forward():
    """A single F should produce one segment growing in +Y."""
    symbols = tokenise("F")
    geo = interpret(symbols, step_length=1.0)
    assert len(geo.segments) == 1

    start, end, radius = geo.segments[0]
    assert np.allclose(start, [0, 0, 0])
    # Heading is +Y
    assert np.allclose(end, [0, 1, 0])


def test_growth_direction_y_up():
    """Multiple F steps should grow in +Y direction."""
    symbols = tokenise("FFF")
    geo = interpret(symbols, step_length=1.0)
    assert len(geo.segments) == 3

    _, end, _ = geo.segments[-1]
    assert end[1] > 0  # growing upward
    assert abs(end[0]) < 1e-10  # no X drift
    assert abs(end[2]) < 1e-10  # no Z drift


def test_parametric_step_length():
    """F(2.5) should move 2.5 units."""
    symbols = tokenise("F(2.5)")
    geo = interpret(symbols, step_length=1.0)
    assert len(geo.segments) == 1

    start, end, _ = geo.segments[0]
    distance = np.linalg.norm(end - start)
    assert abs(distance - 2.5) < 1e-10


def test_push_pop_returns_to_position():
    """[F] should branch and then return."""
    symbols = tokenise("[F(1)]F(1)")
    geo = interpret(symbols, step_length=1.0)
    assert len(geo.segments) == 2

    # First segment in the branch
    _, branch_end, _ = geo.segments[0]
    # Second segment starts at origin (popped back)
    trunk_start, _, _ = geo.segments[1]
    assert np.allclose(trunk_start, [0, 0, 0])


def test_yaw():
    """+(90) should rotate heading from +Y toward -X."""
    symbols = tokenise("+(90)F")
    geo = interpret(symbols, step_length=1.0, angle_default=90.0)
    _, end, _ = geo.segments[0]
    # After +90 yaw around U(+Z), heading rotates from +Y toward -X
    assert end[0] < -0.9 or end[1] < 0.1  # moved away from +Y


def test_bounding_box_nonzero():
    """Any geometry with F should have non-zero bounding box."""
    symbols = tokenise("F[+F][-F]F")
    geo = interpret(symbols, step_length=1.0, angle_default=45.0)
    mn, mx = geo.bounding_box()
    extent = mx - mn
    assert np.any(extent > 0)


def test_radius_decrement():
    """! should reduce the radius by radius_ratio."""
    symbols = tokenise("F!F")
    geo = interpret(symbols, radius_start=0.1, radius_ratio=0.5)
    _, _, r1 = geo.segments[0]
    _, _, r2 = geo.segments[1]
    assert abs(r1 - 0.1) < 1e-10
    assert abs(r2 - 0.05) < 1e-10


def test_leaf_emission():
    """~ should emit a leaf at the current position."""
    symbols = tokenise("F~")
    geo = interpret(symbols, step_length=1.0)
    assert len(geo.leaves) == 1
    pos, heading, _left = geo.leaves[0]
    assert pos[1] > 0  # after moving up


def test_no_segment_on_f_lowercase():
    """Lowercase f should move without emitting a segment."""
    symbols = tokenise("fF")
    geo = interpret(symbols, step_length=1.0)
    assert len(geo.segments) == 1
    start, _, _ = geo.segments[0]
    assert start[1] > 0.9  # moved forward first without segment


def test_tropism_bends_downward():
    """With tropism, repeated F should curve downward (toward -Y).

    We start with a slight yaw so heading isn't exactly parallel to gravity
    (cross product of +Y and -Y is zero, so tropism has no effect on a
    perfectly vertical stem — which is physically correct).
    """
    symbols = tokenise("+(5)" + "F" * 20)
    geo_no_tropism = interpret(symbols, step_length=0.5, angle_default=5.0, tropism_weight=0.0)
    geo_tropism = interpret(symbols, step_length=0.5, angle_default=5.0, tropism_weight=0.3)

    # With no tropism, endpoint should be near-straight
    _, end_straight, _ = geo_no_tropism.segments[-1]
    _, end_bent, _ = geo_tropism.segments[-1]

    # Tropism should make the Y-coordinate lower than straight growth
    assert end_bent[1] < end_straight[1]


def test_centre():
    """centre() should return the midpoint of the bounding box."""
    symbols = tokenise("F[+(90)F][-(90)F]")
    geo = interpret(symbols, step_length=1.0, angle_default=90.0)
    centre = geo.centre()
    mn, mx = geo.bounding_box()
    expected = (mn + mx) / 2.0
    assert np.allclose(centre, expected)
