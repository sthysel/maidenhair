"""3D turtle interpreter for L-system derivation strings.

Consumes a list of Symbol objects and produces Geometry (segments + leaves).
Coordinate system: Y-up, right-handed. Turtle starts facing +Y.
Gravity (tropism) bends toward -Y.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from maidenhair.core.parametric import Symbol


@dataclass
class Geometry:
    """Output of the turtle interpreter."""

    # Each segment: (start_point, end_point, radius)
    segments: list[tuple[np.ndarray, np.ndarray, float]] = field(default_factory=list)
    # Each leaf: (position, normal_vector)
    leaves: list[tuple[np.ndarray, np.ndarray]] = field(default_factory=list)

    def bounding_box(self) -> tuple[np.ndarray, np.ndarray]:
        """Return (min_corner, max_corner) of all segment endpoints."""
        if not self.segments:
            return np.zeros(3), np.zeros(3)
        points = []
        for start, end, _ in self.segments:
            points.append(start)
            points.append(end)
        all_points = np.array(points)
        return all_points.min(axis=0), all_points.max(axis=0)

    def centre(self) -> np.ndarray:
        """Return the centre of the bounding box."""
        mn, mx = self.bounding_box()
        return (mn + mx) / 2.0


@dataclass
class TurtleState:
    """Turtle position and orientation state."""

    pos: np.ndarray  # 3D position
    frame: np.ndarray  # 3x3 rotation matrix, columns = H, L, U
    radius: float


def _rotation_matrix(axis: np.ndarray, angle_rad: float) -> np.ndarray:
    """Create a 3x3 rotation matrix for rotation around an arbitrary axis."""
    c = np.cos(angle_rad)
    s = np.sin(angle_rad)
    t = 1.0 - c
    x, y, z = axis
    return np.array(
        [
            [t * x * x + c, t * x * y - s * z, t * x * z + s * y],
            [t * x * y + s * z, t * y * y + c, t * y * z - s * x],
            [t * x * z - s * y, t * y * z + s * x, t * z * z + c],
        ]
    )


# Gravity vector for tropism (points down in Y-up system)
GRAVITY = np.array([0.0, -1.0, 0.0])


def interpret(
    symbols: list[Symbol],
    *,
    step_length: float = 1.0,
    angle_default: float = 25.0,
    radius_start: float = 0.05,
    radius_ratio: float = 0.75,
    tropism_weight: float = 0.0,
) -> Geometry:
    """Interpret a list of symbols using a 3D turtle.

    All angle parameters are in degrees. Conversion to radians happens here.

    Args:
        symbols: Tokenised L-system derivation string.
        step_length: Default forward distance for F/f.
        angle_default: Default rotation angle in degrees for +, -, &, ^, /, \\.
        radius_start: Initial branch radius.
        radius_ratio: Multiplier applied to radius on '!' symbol.
        tropism_weight: Strength of gravity bending (0 = none).
    """
    geometry = Geometry()

    # Initial state: position at origin, heading +Y, left +X, up -Z (right-handed, Y-up)
    initial_frame = np.array(
        [
            [0.0, 1.0, 0.0],  # H = +X? No: col0=H, col1=L, col2=U
            [1.0, 0.0, 0.0],
            [0.0, 0.0, 1.0],
        ],
        dtype=np.float64,
    )
    # Columns: H (heading) = +Y, L (left) = +X, U (up) = +Z
    # So frame[:, 0] = H = [0, 1, 0] (heading up)
    #    frame[:, 1] = L = [1, 0, 0] (left)
    #    frame[:, 2] = U = [0, 0, 1] (up/out of screen)
    initial_frame = np.eye(3, dtype=np.float64)
    # Redefine: H=+Y, L=+X, U=+Z
    initial_frame[:, 0] = [0.0, 1.0, 0.0]  # heading = +Y (growth direction)
    initial_frame[:, 1] = [1.0, 0.0, 0.0]  # left = +X
    initial_frame[:, 2] = [0.0, 0.0, 1.0]  # up = +Z

    state = TurtleState(
        pos=np.zeros(3, dtype=np.float64),
        frame=initial_frame.copy(),
        radius=radius_start,
    )
    stack: list[TurtleState] = []

    deg2rad = np.pi / 180.0

    for sym in symbols:
        name = sym.name
        params = sym.params

        if name == "F":
            # Move forward, emit segment
            length = params[0] if params else step_length
            heading = state.frame[:, 0]
            new_pos = state.pos + heading * length

            geometry.segments.append((state.pos.copy(), new_pos.copy(), state.radius))
            state.pos = new_pos

            # Apply tropism
            if tropism_weight > 0:
                _apply_tropism(state, tropism_weight)

        elif name == "f":
            # Move forward, no segment
            length = params[0] if params else step_length
            heading = state.frame[:, 0]
            state.pos = state.pos + heading * length

        elif name == "+":
            # Yaw left (rotate around U axis)
            angle = (params[0] if params else angle_default) * deg2rad
            u_axis = state.frame[:, 2]
            rot = _rotation_matrix(u_axis, angle)
            state.frame = rot @ state.frame

        elif name == "-":
            # Yaw right
            angle = (params[0] if params else angle_default) * deg2rad
            u_axis = state.frame[:, 2]
            rot = _rotation_matrix(u_axis, -angle)
            state.frame = rot @ state.frame

        elif name == "&":
            # Pitch down (rotate around L axis)
            angle = (params[0] if params else angle_default) * deg2rad
            l_axis = state.frame[:, 1]
            rot = _rotation_matrix(l_axis, angle)
            state.frame = rot @ state.frame

        elif name == "^":
            # Pitch up
            angle = (params[0] if params else angle_default) * deg2rad
            l_axis = state.frame[:, 1]
            rot = _rotation_matrix(l_axis, -angle)
            state.frame = rot @ state.frame

        elif name == "/":
            # Roll clockwise (rotate around H axis)
            angle = (params[0] if params else angle_default) * deg2rad
            h_axis = state.frame[:, 0]
            rot = _rotation_matrix(h_axis, angle)
            state.frame = rot @ state.frame

        elif name == "\\":
            # Roll counter-clockwise
            angle = (params[0] if params else angle_default) * deg2rad
            h_axis = state.frame[:, 0]
            rot = _rotation_matrix(h_axis, -angle)
            state.frame = rot @ state.frame

        elif name == "[":
            # Push state
            stack.append(
                TurtleState(
                    pos=state.pos.copy(),
                    frame=state.frame.copy(),
                    radius=state.radius,
                )
            )

        elif name == "]":
            # Pop state
            if stack:
                state = stack.pop()

        elif name == "!":
            # Decrement radius
            state.radius *= radius_ratio

        elif name == "~":
            # Emit leaf
            geometry.leaves.append((state.pos.copy(), state.frame[:, 0].copy()))

        # else: unknown symbol, ignore (identity)

    return geometry


def _apply_tropism(state: TurtleState, weight: float) -> None:
    """Bend the turtle heading toward gravity.

    Uses the method from Prusinkiewicz: rotate heading toward the gravity
    vector by an amount proportional to the weight and the cross product
    of heading and gravity.
    """
    heading = state.frame[:, 0]
    torque = np.cross(heading, GRAVITY)
    torque_len = np.linalg.norm(torque)
    if torque_len < 1e-10:
        return

    torque_axis = torque / torque_len
    angle = float(weight * torque_len)
    rot = _rotation_matrix(torque_axis, angle)
    state.frame = rot @ state.frame
