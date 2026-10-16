"""Synthetic master/panel geometry shared by typed-check and gate tests."""
import math

import numpy as np

R = 500.0


def obj(name, part, V, F, role='design', **extra):
    return {'name': name, 'part': part, 'role': role, 'vertices': np.asarray(V, float).tolist(),
            'faces': np.asarray(F).tolist(), 'matrix_world': np.eye(4).tolist(), 'metadata': {}, **extra}


def sphere(radius=R):
    return lambda phi, theta: radius * np.array([math.cos(theta) * math.sin(phi), math.sin(theta), math.cos(theta) * math.cos(phi)])


def grid(fn, u, v, nu, nv):
    """Outward-wound quad grid over a parametric surface."""
    us, vs = np.linspace(*u, nu), np.linspace(*v, nv)
    V = np.array([fn(a, b) for a in us for b in vs])
    F = []
    for i in range(nu - 1):
        for j in range(nv - 1):
            a, b, c, d = i * nv + j, (i + 1) * nv + j, (i + 1) * nv + j + 1, i * nv + j + 1
            F += [[a, b, c], [a, c, d]]
    F = np.array(F)
    centre = V[F].mean(axis=1)
    normal = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
    if (np.einsum('ij,ij->i', normal, centre) < 0).mean() > .5:
        F = F[:, ::-1]
    return V, F


def closed_sphere(radius=R, segments=160, rings=80):
    """Closed latitude/longitude sphere (orientation is normalized by the checks)."""
    V = [[0, 0, -radius]]
    for i in range(1, rings):
        theta = -math.pi / 2 + math.pi * i / rings
        for k in range(segments):
            phi = 2 * math.pi * k / segments
            V.append([radius * math.cos(theta) * math.cos(phi), radius * math.cos(theta) * math.sin(phi), radius * math.sin(theta)])
    V.append([0, 0, radius])
    F = []
    ring = lambda i, k: 1 + (i - 1) * segments + k % segments
    for k in range(segments):
        F.append([0, ring(1, k + 1), ring(1, k)])
        F.append([len(V) - 1, ring(rings - 1, k), ring(rings - 1, k + 1)])
    for i in range(1, rings - 1):
        for k in range(segments):
            F += [[ring(i, k), ring(i, k + 1), ring(i + 1, k + 1)], [ring(i, k), ring(i + 1, k + 1), ring(i + 1, k)]]
    return np.array(V, float), np.array(F)


def panels(lift=0.0, half_gap=1.5):
    delta = half_gap / R
    AV, AF = grid(sphere(), (delta, .4), (-.25, .25), 90, 50)
    BV, BF = grid(sphere(R + lift), (-.4, -delta), (-.25, .25), 90, 50)
    return (AV, AF), (BV, BF)
