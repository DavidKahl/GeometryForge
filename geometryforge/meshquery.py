"""Exact triangle-mesh queries for typed checks, using numpy and scipy only."""
import numpy as np
from scipy.spatial import cKDTree


def as_mesh(objects):
    """Concatenate payload objects (local vertices + matrix_world) into one world-space mesh."""
    from .game import world_vertices
    vertices, faces, offset = [], [], 0
    for obj in objects:
        v = world_vertices(obj) if 'matrix_world' in obj else np.asarray(obj['vertices'], dtype=float)
        f = np.asarray(obj.get('faces', []), dtype=np.int64).reshape(-1, 3)
        vertices.append(v)
        faces.append(f + offset)
        offset += len(v)
    if not vertices:
        return np.zeros((0, 3)), np.zeros((0, 3), dtype=np.int64)
    return np.concatenate(vertices), np.concatenate(faces)


def face_normals(V, F):
    n = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
    length = np.linalg.norm(n, axis=1)
    return n / np.where(length > 0, length, 1)[:, None], length / 2


def vertex_normals(V, F):
    """Angle-weighted vertex pseudonormals."""
    normals, _ = face_normals(V, F)
    result = np.zeros_like(V)
    for i in range(3):
        a, b = V[F[:, (i + 1) % 3]] - V[F[:, i]], V[F[:, (i + 2) % 3]] - V[F[:, i]]
        cos = np.einsum('ij,ij->i', a, b) / np.maximum(np.linalg.norm(a, axis=1) * np.linalg.norm(b, axis=1), 1e-300)
        np.add.at(result, F[:, i], normals * np.arccos(np.clip(cos, -1, 1))[:, None])
    length = np.linalg.norm(result, axis=1)
    return result / np.where(length > 0, length, 1)[:, None]


def edges(F):
    """Unique undirected edges (E,2), and how many faces use each."""
    raw = np.sort(np.concatenate([F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]]), axis=1)
    unique, counts = np.unique(raw, axis=0, return_counts=True)
    return unique, counts


def open_edges(F):
    unique, counts = edges(F)
    return unique[counts == 1]


def boundary_loops(F):
    """Ordered vertex chains of the open boundary."""
    neighbours = {}
    for a, b in open_edges(F):
        neighbours.setdefault(int(a), []).append(int(b))
        neighbours.setdefault(int(b), []).append(int(a))
    loops, seen = [], set()
    for start in neighbours:
        if start in seen:
            continue
        chain, previous, current = [start], None, start
        seen.add(start)
        while True:
            options = [n for n in neighbours[current] if n != previous and n not in seen]
            if not options:
                break
            previous, current = current, options[0]
            seen.add(current)
            chain.append(current)
        loops.append(chain)
    return loops


def _closest_on_triangles(P, A, B, C):
    """Vectorized closest point (Ericson). Returns points and region: 0 face, 1-3 vertex, 4-6 edge AB/BC/CA."""
    ab, ac, ap = B - A, C - A, P - A
    d1, d2 = np.einsum('ij,ij->i', ab, ap), np.einsum('ij,ij->i', ac, ap)
    bp = P - B
    d3, d4 = np.einsum('ij,ij->i', ab, bp), np.einsum('ij,ij->i', ac, bp)
    cp = P - C
    d5, d6 = np.einsum('ij,ij->i', ab, cp), np.einsum('ij,ij->i', ac, cp)
    vc, vb, va = d1 * d4 - d3 * d2, d5 * d2 - d1 * d6, d3 * d6 - d5 * d4
    denom = va + vb + vc
    safe = np.where(np.abs(denom) > 1e-300, denom, 1)
    v, w = vb / safe, vc / safe
    result = A + ab * v[:, None] + ac * w[:, None]
    region = np.zeros(len(P), dtype=np.int8)
    done = np.zeros(len(P), dtype=bool)

    def take(mask, point, code):
        mask = mask & ~done
        result[mask] = point[mask]
        region[mask] = code
        done[mask] = True

    take((d1 <= 0) & (d2 <= 0), A, 1)
    take((d3 >= 0) & (d4 <= d3), B, 2)
    take((d6 >= 0) & (d5 <= d6), C, 3)
    t = d1 / np.where(d1 - d3 != 0, d1 - d3, 1)
    take((vc <= 0) & (d1 >= 0) & (d3 <= 0), A + ab * t[:, None], 4)
    t = (d4 - d3) / np.where((d4 - d3) + (d5 - d6) != 0, (d4 - d3) + (d5 - d6), 1)
    take((va <= 0) & (d4 - d3 >= 0) & (d5 - d6 >= 0), B + (C - B) * t[:, None], 5)
    t = d2 / np.where(d2 - d6 != 0, d2 - d6, 1)
    take((vb <= 0) & (d2 >= 0) & (d6 <= 0), A + ac * t[:, None], 6)
    return result, region


class TriangleIndex:
    """Closest-point and signed-distance queries. Signs assume a closed, outward-oriented mesh."""

    def __init__(self, vertices, faces):
        self.V = np.asarray(vertices, dtype=float)
        self.F = np.asarray(faces, dtype=np.int64).reshape(-1, 3)
        if not len(self.F):
            raise ValueError('Mesh query needs at least one triangle')
        corners = self.V[self.F]
        self.closed = not len(open_edges(self.F))
        if self.closed and np.einsum('ij,ij->i', corners[:, 0], np.cross(corners[:, 1], corners[:, 2])).sum() < 0:
            self.F = self.F[:, ::-1]  # signs below assume outward orientation
        corners = self.V[self.F]
        self.centroids = corners.mean(axis=1)
        self.radii = np.linalg.norm(corners - self.centroids[:, None], axis=2).max(axis=1)
        self.tree = cKDTree(self.centroids)
        # A few oversized triangles would inflate every candidate search; test them exhaustively instead.
        cutoff = max(float(np.percentile(self.radii, 99)) * 4, 1e-9)
        self.large = np.nonzero(self.radii > cutoff)[0] if len(self.radii) > 1000 else np.zeros(0, dtype=np.int64)
        self.bound = float(self.radii[self.radii <= cutoff].max()) if len(self.large) else float(self.radii.max())
        self.face_normals, self.areas = face_normals(self.V, self.F)
        self.vertex_normals = vertex_normals(self.V, self.F)
        self._edge_normals = None

    def edge_normal(self, a, b):
        if self._edge_normals is None:
            table = {}
            for face, tri in enumerate(self.F):
                for i in range(3):
                    key = tuple(sorted((int(tri[i]), int(tri[(i + 1) % 3]))))
                    table[key] = table.get(key, 0) + self.face_normals[face]
            self._edge_normals = table
        value = self._edge_normals[tuple(sorted((int(a), int(b))))]
        return value / max(np.linalg.norm(value), 1e-300)

    def closest(self, points, chunk=2048):
        """Exact nearest surface point: (distance, point, face, region)."""
        points = np.asarray(points, dtype=float).reshape(-1, 3)
        distance = np.full(len(points), np.inf)
        nearest = np.zeros_like(points)
        face = np.zeros(len(points), dtype=np.int64)
        region = np.zeros(len(points), dtype=np.int8)
        large = set(self.large.tolist())
        for start in range(0, len(points), chunk):
            block = points[start:start + chunk]
            first, _ = self.tree.query(block)
            # Any triangle closer than the nearest-centroid distance has its centroid within that plus its radius.
            candidates = self.tree.query_ball_point(block, first + self.bound)
            rows = np.repeat(np.arange(len(block)), [len(c) for c in candidates])
            cols = np.fromiter((c for group in candidates for c in group), dtype=np.int64, count=len(rows))
            if large:
                keep = ~np.isin(cols, self.large)
                rows, cols = np.concatenate((rows[keep], np.repeat(np.arange(len(block)), len(self.large)))), \
                    np.concatenate((cols[keep], np.tile(self.large, len(block))))
            keep = np.linalg.norm(self.centroids[cols] - block[rows], axis=1) - self.radii[cols] <= first[rows] + 1e-9
            rows, cols = rows[keep], cols[keep]
            tri = self.F[cols]
            q, code = _closest_on_triangles(block[rows], self.V[tri[:, 0]], self.V[tri[:, 1]], self.V[tri[:, 2]])
            d = np.linalg.norm(q - block[rows], axis=1)
            order = np.lexsort((d, rows))
            rows, cols, q, code, d = rows[order], cols[order], q[order], code[order], d[order]
            firsts = np.unique(rows, return_index=True)[1]
            index = start + rows[firsts]
            distance[index], nearest[index] = d[firsts], q[firsts]
            face[index], region[index] = cols[firsts], code[firsts]
        return distance, nearest, face, region

    def feature_normals(self, face, region):
        normals = self.face_normals[face].copy()
        for i in np.nonzero(region)[0]:
            tri = self.F[face[i]]
            code = region[i]
            if code <= 3:
                normals[i] = self.vertex_normals[tri[code - 1]]
            else:
                a = code - 4
                normals[i] = self.edge_normal(tri[a], tri[(a + 1) % 3])
        return normals

    def signed_distance(self, points):
        """Positive outside the mesh, negative inside, with surface normals at the closest points."""
        points = np.asarray(points, dtype=float).reshape(-1, 3)
        distance, nearest, face, region = self.closest(points)
        normals = self.feature_normals(face, region)
        sign = np.sign(np.einsum('ij,ij->i', points - nearest, normals))
        sign[sign == 0] = 1
        return distance * sign, nearest, self.face_normals[face], face

    def segment_crossings(self, start, end):
        """Count segments that cross any triangle (Moller-Trumbore with centroid-tree culling)."""
        start, end = np.asarray(start, dtype=float).reshape(-1, 3), np.asarray(end, dtype=float).reshape(-1, 3)
        if not len(start):
            return 0, np.zeros(0, dtype=bool)
        middle = (start + end) / 2
        half = np.linalg.norm(end - start, axis=1) / 2
        candidates = self.tree.query_ball_point(middle, half + self.radii.max())
        rows = np.repeat(np.arange(len(start)), [len(c) for c in candidates])
        cols = np.fromiter((c for group in candidates for c in group), dtype=np.int64, count=len(rows))
        tri = self.F[cols]
        a, b, c = self.V[tri[:, 0]], self.V[tri[:, 1]], self.V[tri[:, 2]]
        direction = end[rows] - start[rows]
        e1, e2 = b - a, c - a
        h = np.cross(direction, e2)
        det = np.einsum('ij,ij->i', e1, h)
        ok = np.abs(det) > 1e-12
        inv = np.where(ok, 1 / np.where(ok, det, 1), 0)
        s = start[rows] - a
        u = inv * np.einsum('ij,ij->i', s, h)
        q = np.cross(s, e1)
        v = inv * np.einsum('ij,ij->i', direction, q)
        t = inv * np.einsum('ij,ij->i', e2, q)
        hit = ok & (u >= 0) & (v >= 0) & (u + v <= 1) & (t > 1e-9) & (t < 1 - 1e-9)
        crossed = np.zeros(len(start), dtype=bool)
        crossed[rows[hit]] = True
        return int(crossed.sum()), crossed


def interpolate(V, F, face, points, values):
    """Barycentric interpolation of per-vertex values at points lying on the given faces."""
    tri = F[face]
    a, b, c = V[tri[:, 0]], V[tri[:, 1]], V[tri[:, 2]]
    v0, v1, v2 = b - a, c - a, points - a
    d00, d01, d11 = (np.einsum('ij,ij->i', x, y) for x, y in ((v0, v0), (v0, v1), (v1, v1)))
    d20, d21 = np.einsum('ij,ij->i', v2, v0), np.einsum('ij,ij->i', v2, v1)
    denom = np.where(np.abs(d00 * d11 - d01 * d01) > 1e-300, d00 * d11 - d01 * d01, 1)
    v = (d11 * d20 - d01 * d21) / denom
    w = (d00 * d21 - d01 * d20) / denom
    u = 1 - v - w
    return values[tri[:, 0]] * u[:, None] + values[tri[:, 1]] * v[:, None] + values[tri[:, 2]] * w[:, None]


def sample_surface(V, F, spacing):
    """Deterministic surface samples: centroids plus sub-centroids on large triangles, with their areas."""
    corners = V[F]
    _, areas = face_normals(V, F)
    points, weights = [corners.mean(axis=1)], [areas.copy()]
    large = np.nonzero(areas > spacing * spacing)[0]
    if len(large):
        # Four-way midpoint split for triangles larger than the spacing.
        a, b, c = corners[large, 0], corners[large, 1], corners[large, 2]
        ab, bc, ca = (a + b) / 2, (b + c) / 2, (c + a) / 2
        quads = [(a, ab, ca), (ab, b, bc), (ca, bc, c), (ab, bc, ca)]
        points[0] = np.delete(points[0], large, axis=0)
        weights[0] = np.delete(weights[0], large)
        for x, y, z in quads:
            points.append((x + y + z) / 3)
            weights.append(areas[large] / 4)
    return np.concatenate(points), np.concatenate(weights)
