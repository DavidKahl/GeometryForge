"""Section and ring math shared by native surfacing helpers and host checks (numpy only)."""
import math

import numpy as np


def chamfered_ring(width, height, chamfer=0.32, radius=6.0, segments=5):
    """Closed rounded-octagon section in the XY plane, centred on the origin.

    chamfer is a fraction of the smaller side; radius rounds each of the eight corners
    with `segments` points, preserving distinct top, chamfer and side planes.
    """
    a, b = width / 2, height / 2
    c = chamfer * min(a, b)
    corners = [(a, b - c), (a - c, b), (-a + c, b), (-a, b - c), (-a, -b + c), (-a + c, -b), (a - c, -b), (a, -b + c)]
    points = []
    for i, corner in enumerate(corners):
        before, after = np.asarray(corners[i - 1]), np.asarray(corners[(i + 1) % 8])
        p = np.asarray(corner)
        u, v = before - p, after - p
        u, v = u / np.linalg.norm(u), v / np.linalg.norm(v)
        half = math.acos(max(-1.0, min(1.0, float(u @ v)))) / 2
        setback = min(radius / math.tan(half), np.linalg.norm(before - p) / 2, np.linalg.norm(after - p) / 2)
        start, end = p + u * setback, p + v * setback
        for k in range(segments):
            t = k / max(segments - 1, 1)
            # Quadratic Bezier through the corner: a local radius, not a global rounding.
            points.append((1 - t) ** 2 * start + 2 * (1 - t) * t * p + t ** 2 * end)
    return np.asarray(points)


def superellipse_ring(width, height, exponent=4.0, segments=48):
    t = np.linspace(0, 2 * math.pi, segments, endpoint=False)
    c, s = np.cos(t), np.sin(t)
    x = width / 2 * np.sign(c) * np.abs(c) ** (2 / exponent)
    y = height / 2 * np.sign(s) * np.abs(s) ** (2 / exponent)
    return np.column_stack((x, y))


def resample_polyline(points, count, closed=True):
    points = np.asarray(points, dtype=float)
    loop = np.vstack((points, points[:1])) if closed else points
    lengths = np.r_[0, np.cumsum(np.linalg.norm(np.diff(loop, axis=0), axis=1))]
    targets = np.linspace(0, lengths[-1], count, endpoint=not closed)
    return np.column_stack([np.interp(targets, lengths, loop[:, i]) for i in range(points.shape[1])])


def ring_frame(points, edges=None, axis_hint=None):
    """Arc-length centroid, unit plane axis and mean radius of a polyline ring.

    edges default to a closed chain. axis_hint orients the axis sign; without it the sign is arbitrary.
    """
    points = np.asarray(points, dtype=float)
    edges = np.asarray(edges if edges is not None else [[i, (i + 1) % len(points)] for i in range(len(points))], dtype=np.int64)
    middle = (points[edges[:, 0]] + points[edges[:, 1]]) / 2
    lengths = np.linalg.norm(points[edges[:, 0]] - points[edges[:, 1]], axis=1)
    centroid = (middle * lengths[:, None]).sum(axis=0) / lengths.sum()
    axis = np.linalg.svd(middle - centroid)[2][-1]
    if axis_hint is not None and axis @ np.asarray(axis_hint, dtype=float) < 0:
        axis = -axis
    return centroid, axis, float(np.linalg.norm(middle - centroid, axis=1).mean())
