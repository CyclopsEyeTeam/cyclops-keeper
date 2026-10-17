"""Shared terminal raster math adapted from Prism painter.py (17 October 2026).
Only geometry, seeded spray, additive raster and tone mapping are reused.
No parser, templates, model calls, story playback or peer writes.
"""
import math
import time
from typing import Dict, List, Tuple
RGBFloat = Tuple[float, float, float]

def tonemap_light(r: float, g: float, b: float) -> RGBFloat:
    """§6 Colour depth: when light adds past full, keep the hue at full strength and
    spill only the excess toward white. Fully white at 2.5x full; anything <= 1 is untouched.
    """
    r = max(0.0, float(r))
    g = max(0.0, float(g))
    b = max(0.0, float(b))
    m = max(r, g, b)
    if m <= 1.0:
        return (r, g, b)
    rn, gn, bn = r / m, g / m, b / m
    spill = min(1.0, (m - 1.0) / 1.5)
    return (
        rn + (1.0 - rn) * spill,
        gn + (1.0 - gn) * spill,
        bn + (1.0 - bn) * spill,
    )

def _rng(seed: int):
    """Deterministic LCG matching Spark's seeded spray generator."""
    s = (int(seed) & 0xFFFFFFFF) or 1

    def _next() -> float:
        nonlocal s
        s = (s * 1664525 + 1013904223) & 0xFFFFFFFF
        return s / 4294967296.0

    return _next

def _smooth_catmull_rom(pts: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
    """Catmull-Rom spline interpolation (8 steps per span)."""
    if len(pts) < 3:
        return list(pts)
    out: List[Tuple[float, float]] = []
    n = len(pts)
    for i in range(n - 1):
        p0 = pts[max(0, i - 1)]
        p1 = pts[i]
        p2 = pts[i + 1]
        p3 = pts[min(n - 1, i + 2)]
        for s in range(8):
            t = s / 8.0
            t2 = t * t
            t3 = t2 * t
            x = 0.5 * (
                2.0 * p1[0]
                + (-p0[0] + p2[0]) * t
                + (2.0 * p0[0] - 5.0 * p1[0] + 4.0 * p2[0] - p3[0]) * t2
                + (-p0[0] + 3.0 * p1[0] - 3.0 * p2[0] + p3[0]) * t3
            )
            y = 0.5 * (
                2.0 * p1[1]
                + (-p0[1] + p2[1]) * t
                + (2.0 * p0[1] - 5.0 * p1[1] + 4.0 * p2[1] - p3[1]) * t2
                + (-p0[1] + 3.0 * p1[1] - 3.0 * p2[1] + p3[1]) * t3
            )
            out.append((x, y))
    out.append(pts[-1])
    return out

def painting_scene(painting: dict, W: int, H: int, reveal: float = 1.0) -> List[dict]:
    """Compile normalized [0..1] painting marks into raster primitives in scene space."""
    marks = painting.get("marks") or []
    if not marks:
        return []
    unit = 2.4 / max(1.0, float(min(W, H)))
    X = lambda u: (u - 0.5) * W * unit
    Y = lambda v: (v - 0.5) * H * unit
    R = lambda r: r * 2.4
    TAU = math.pi * 2.0

    n = len(marks)
    q = max(0.0, min(1.0, reveal)) * n
    mirror = painting.get("mirror")
    views = [(1, 1)]
    if mirror in ("x", "xy"):
        views.append((-1, 1))
    if mirror in ("y", "xy"):
        views.append((1, -1))
    if mirror == "xy":
        views.append((-1, -1))

    out: List[dict] = []
    for i, m in enumerate(marks):
        if i >= math.ceil(q):
            break
        part = min(1.0, q - i)
        if part <= 0.0:
            continue
        k = m["k"]
        c0 = tuple(m["c"])
        c1 = tuple(m.get("c2") or m["c"])
        for v_idx, (fx, fy) in enumerate(views):
            px = lambda u, _fx=fx: X((1.0 - u) if _fx < 0 else u)
            py = lambda w, _fy=fy: Y((1.0 - w) if _fy < 0 else w)

            def _flip_a(turns: float, _fx=fx, _fy=fy) -> float:
                a = (0.5 - turns) if _fx < 0 else turns
                return -a if _fy < 0 else a

            if k in ("line", "curve"):
                pts = [(pt[0], pt[1]) for pt in m["pts"]]
                if k == "curve" and len(pts) >= 3:
                    pts = _smooth_catmull_rom(pts)
                if part < 1.0:
                    cut = max(2, int(math.ceil(len(pts) * part)))
                    pts = pts[:cut]
                out.append({
                    "k": "path",
                    "pts": [(px(x), py(y)) for (x, y) in pts],
                    "w": R(m["w"]),
                    "c0": c0,
                    "c1": c1,
                    "a": m["a"] * (0.6 + 0.4 * part if part < 1.0 else 1.0),
                    "mark_idx": i,
                })
            elif k == "fill":
                out.append({
                    "k": "poly",
                    "pts": [(px(x), py(y)) for (x, y) in m["pts"]],
                    "c0": c0,
                    "c1": c1,
                    "grad": _flip_a(m.get("grad", 0.25)) * TAU,
                    "a": m["a"] * part,
                    "mark_idx": i,
                })
            elif k == "arc":
                a0 = _flip_a(m["a0"])
                a1 = _flip_a(m["a1"])
                lo, hi = (a1, a0) if ((fx < 0) != (fy < 0)) else (a0, a1)
                span_turns = ((hi - lo) % 1.0 + 1.0) % 1.0 or 1.0
                out.append({
                    "k": "arc",
                    "x": px(m["x"]),
                    "y": py(m["y"]),
                    "r": R(m["r"]),
                    "w": R(m["w"]),
                    "a0": lo * TAU,
                    "a1": (lo + span_turns * part) * TAU,
                    "c": c0,
                    "a": m["a"],
                    "mark_idx": i,
                })
            elif k == "spray":
                rng = _rng(int(m.get("seed", i + 1)) * 7919 + v_idx)
                count = int(round(m["n"] * part))
                for _ in range(count):
                    ang = rng() * TAU
                    dist = math.sqrt(rng()) * m["r"]
                    sx = m["x"] + math.cos(ang) * dist
                    sy = m["y"] + math.sin(ang) * dist
                    sr = R(m["s"]) * (0.5 + rng())
                    sa = m["a"] * (0.4 + 0.6 * rng())
                    out.append({
                        "k": "dot",
                        "x": px(sx),
                        "y": py(sy),
                        "r": sr,
                        "c": c0,
                        "a": sa,
                        "mark_idx": i,
                        "is_spray": True,
                    })
            else:
                out.append({
                    "k": k,
                    "x": px(m["x"]),
                    "y": py(m["y"]),
                    "r": R(m["r"]) * (0.6 + 0.4 * part if k == "dot" else 1.0),
                    "w": R(m["w"]) if "w" in m else 0.0,
                    "c": c0,
                    "a": m["a"] * part,
                    "mark_idx": i,
                })
    return out

def rasterize_scene(
    scene: List[dict],
    W: int,
    H: int,
    *,
    min_r_px: float = 0.6,
    min_hw_px: float = 0.45,
    yield_burst: bool = True,
) -> List[List[float]]:
    """Rasterize compiled scene primitives onto a WxH premultiplied-alpha buffer with additive light.
    Yields briefly between ~20ms bursts (§6: Stay responsive).
    """
    px = [[0.0, 0.0, 0.0, 0.0] for _ in range(W * H)]
    scale = min(W, H) / 2.4
    ox = W / 2.0
    oy = H / 2.0
    P = lambda x, y: (ox + x * scale, oy + y * scale)
    TAU = math.pi * 2.0
    last_yield = time.monotonic()

    def _blend(idx: int, col: RGBFloat, alpha: float) -> None:
        if alpha <= 0.002:
            return
        cell = px[idx]
        cell[0] += col[0] * alpha
        cell[1] += col[1] * alpha
        cell[2] += col[2] * alpha
        cell[3] = 1.0 - (1.0 - cell[3]) * (1.0 - min(1.0, alpha))

    for p in scene:
        if yield_burst and (time.monotonic() - last_yield >= 0.018):
            time.sleep(0.001)
            last_yield = time.monotonic()

        k = p["k"]
        if k == "glow":
            r = max(1.0, p["r"] * scale * 1.6)
            cx, cy = P(p["x"], p["y"])
            x0, x1 = max(0, int(math.floor(cx - r))), min(W - 1, int(math.ceil(cx + r)))
            y0, y1 = max(0, int(math.floor(cy - r))), min(H - 1, int(math.ceil(cy + r)))
            r2 = r * r
            base_a = p["a"] * 0.9
            c = p["c"]
            for y in range(y0, y1 + 1):
                dy2 = (y + 0.5 - cy) ** 2
                row_off = y * W
                for x in range(x0, x1 + 1):
                    d2 = ((x + 0.5 - cx) ** 2 + dy2) / r2
                    if d2 < 1.0:
                        cov = math.exp(-4.2 * d2) * (1.0 - d2)
                        _blend(row_off + x, c, cov * base_a)
                if yield_burst and (y & 15 == 0) and (time.monotonic() - last_yield >= 0.018):
                    time.sleep(0.001)
                    last_yield = time.monotonic()

        elif k == "dot":
            if p.get("is_spray") and W < 240:
                r = max(0.35, p["r"] * scale * 0.75)
                cx, cy = P(p["x"], p["y"])
                x0, x1 = max(0, int(math.floor(cx - r - 0.5))), min(W - 1, int(math.ceil(cx + r + 0.5)))
                y0, y1 = max(0, int(math.floor(cy - r - 0.5))), min(H - 1, int(math.ceil(cy + r + 0.5)))
                base_a = p["a"] * 0.52
                c = p["c"]
                inv_r2 = 1.0 / max(0.12, r * r)
                for y in range(y0, y1 + 1):
                    dy = y + 0.5 - cy
                    row_off = y * W
                    for x in range(x0, x1 + 1):
                        d2 = ((x + 0.5 - cx) ** 2 + dy * dy) * inv_r2
                        if d2 < 1.2:
                            cov = math.exp(-2.8 * d2)
                            _blend(row_off + x, c, cov * base_a)
            else:
                r = max(min_r_px, p["r"] * scale)
                cx, cy = P(p["x"], p["y"])
                x0, x1 = max(0, int(math.floor(cx - r - 1))), min(W - 1, int(math.ceil(cx + r + 1)))
                y0, y1 = max(0, int(math.floor(cy - r - 1))), min(H - 1, int(math.ceil(cy + r + 1)))
                base_a = p["a"]
                c = p["c"]
                for y in range(y0, y1 + 1):
                    dy = y + 0.5 - cy
                    row_off = y * W
                    for x in range(x0, x1 + 1):
                        d = math.hypot(x + 0.5 - cx, dy)
                        cov = max(0.0, min(1.0, r + 0.5 - d))
                        if cov > 0.0:
                            _blend(row_off + x, c, cov * base_a)

        elif k == "ring":
            r = p["r"] * scale
            hw = max(min_hw_px, (p["w"] * scale) / 2.0)
            cx, cy = P(p["x"], p["y"])
            x0, x1 = max(0, int(math.floor(cx - r - hw - 2))), min(W - 1, int(math.ceil(cx + r + hw + 2)))
            y0, y1 = max(0, int(math.floor(cy - r - hw - 2))), min(H - 1, int(math.ceil(cy + r + hw + 2)))
            base_a = p["a"]
            c = p["c"]
            for y in range(y0, y1 + 1):
                dy = y + 0.5 - cy
                row_off = y * W
                for x in range(x0, x1 + 1):
                    d = abs(math.hypot(x + 0.5 - cx, dy) - r)
                    cov = max(0.0, min(1.0, hw + 0.5 - d))
                    if cov > 0.0:
                        _blend(row_off + x, c, cov * base_a)

        elif k == "arc":
            r = p["r"] * scale
            hw = max(min_hw_px, (p["w"] * scale) / 2.0)
            cx, cy = P(p["x"], p["y"])
            a0 = p["a0"]
            span = ((p["a1"] - a0) % TAU + TAU) % TAU or TAU
            ex0, ey0 = cx + r * math.cos(a0), cy + r * math.sin(a0)
            ex1, ey1 = cx + r * math.cos(a0 + span), cy + r * math.sin(a0 + span)
            x0, x1 = max(0, int(math.floor(cx - r - hw - 2))), min(W - 1, int(math.ceil(cx + r + hw + 2)))
            y0, y1 = max(0, int(math.floor(cy - r - hw - 2))), min(H - 1, int(math.ceil(cy + r + hw + 2)))
            base_a = p["a"]
            c = p["c"]
            for y in range(y0, y1 + 1):
                dy = y + 0.5 - cy
                row_off = y * W
                for x in range(x0, x1 + 1):
                    dx = x + 0.5 - cx
                    at = ((math.atan2(dy, dx) - a0) % TAU + TAU) % TAU
                    if at <= span:
                        d = abs(math.hypot(dx, dy) - r)
                    else:
                        d = min(math.hypot(x + 0.5 - ex0, y + 0.5 - ey0), math.hypot(x + 0.5 - ex1, y + 0.5 - ey1))
                    cov = max(0.0, min(1.0, hw + 0.5 - d))
                    if cov > 0.0:
                        _blend(row_off + x, c, cov * base_a)

        elif k == "poly":
            pts = [P(x, y) for (x, y) in p["pts"]]
            n = len(pts)
            if n < 3:
                continue
            minx = min(pt[0] for pt in pts)
            maxx = max(pt[0] for pt in pts)
            miny = min(pt[1] for pt in pts)
            maxy = max(pt[1] for pt in pts)
            x0, x1 = max(0, int(math.floor(minx))), min(W - 1, int(math.ceil(maxx)))
            y0, y1 = max(0, int(math.floor(miny))), min(H - 1, int(math.ceil(maxy)))
            c0, c1 = p["c0"], p["c1"]
            gx, gy = math.cos(p.get("grad", 0.0)), math.sin(p.get("grad", 0.0))
            projs = [pt[0] * gx + pt[1] * gy for pt in pts]
            lo, hi = min(projs), max(projs)
            span_g = max(1e-6, hi - lo)
            base_a = p["a"]

            for y in range(y0, y1 + 1):
                qy = y + 0.5
                cross: List[float] = []
                for idx_e in range(n):
                    x_i, y_i = pts[idx_e]
                    x_j, y_j = pts[idx_e - 1]
                    if (y_i > qy) != (y_j > qy):
                        cross.append(((x_j - x_i) * (qy - y_i)) / (y_j - y_i) + x_i)
                if len(cross) < 2:
                    continue
                cross.sort()
                row_off = y * W
                for k_i in range(0, len(cross) - 1, 2):
                    xa, xb = cross[k_i], cross[k_i + 1]
                    ix0 = max(x0, int(math.floor(xa)))
                    ix1 = min(x1, int(math.ceil(xb)))
                    for x in range(ix0, ix1 + 1):
                        px_c = x + 0.5
                        cov = max(0.0, min(1.0, min(px_c + 0.5, xb) - max(px_c - 0.5, xa)))
                        if cov > 0.0:
                            u = max(0.0, min(1.0, (px_c * gx + qy * gy - lo) / span_g))
                            col = (
                                c0[0] + (c1[0] - c0[0]) * u,
                                c0[1] + (c1[1] - c0[1]) * u,
                                c0[2] + (c1[2] - c0[2]) * u,
                            )
                            _blend(row_off + x, col, cov * base_a)
                if yield_burst and (y & 15 == 0) and (time.monotonic() - last_yield >= 0.018):
                    time.sleep(0.001)
                    last_yield = time.monotonic()

        elif k == "path":
            pts = [P(x, y) for (x, y) in p["pts"]]
            n = len(pts)
            if n < 2:
                continue
            hw = max(min_hw_px, (p["w"] * scale) / 2.0)
            c0, c1 = p["c0"], p["c1"]
            base_a = p["a"]
            best_cov: Dict[int, Tuple[float, float]] = {}
            for s in range(n - 1):
                ax, ay = pts[s]
                bx, by = pts[s + 1]
                x0 = max(0, int(math.floor(min(ax, bx) - hw - 1)))
                x1 = min(W - 1, int(math.ceil(max(ax, bx) + hw + 1)))
                y0 = max(0, int(math.floor(min(ay, by) - hw - 1)))
                y1 = min(H - 1, int(math.ceil(max(ay, by) + hw + 1)))
                vx, vy = bx - ax, by - ay
                l2 = vx * vx + vy * vy or 1e-6
                for y in range(y0, y1 + 1):
                    qy = y + 0.5 - ay
                    row_off = y * W
                    for x in range(x0, x1 + 1):
                        qx = x + 0.5 - ax
                        u = max(0.0, min(1.0, (qx * vx + qy * vy) / l2))
                        d = math.hypot(qx - u * vx, qy - u * vy)
                        cov = max(0.0, min(1.0, hw + 0.5 - d))
                        if cov > 0.0:
                            cell_i = row_off + x
                            prog = (s + u) / max(1, n - 1)
                            prev = best_cov.get(cell_i)
                            if prev is None or cov > prev[0]:
                                best_cov[cell_i] = (cov, prog)
            for cell_i, (cov, prog) in best_cov.items():
                col = (
                    c0[0] + (c1[0] - c0[0]) * prog,
                    c0[1] + (c1[1] - c0[1]) * prog,
                    c0[2] + (c1[2] - c0[2]) * prog,
                )
                _blend(cell_i, col, cov * base_a)

    return px
