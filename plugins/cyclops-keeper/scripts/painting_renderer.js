// Shared drawing math adapted from CyclopsStudio presence-paintings.js.
// Original reference hash and operations retained in tests/fixtures/painting-reference.js.
(()=>{
const ASPECT={wide:2,square:1,tall:.5};
const TAU=Math.PI*2;
const clamp01=v=>Math.max(0,Math.min(1,v));
const rgb=(c,a=1)=>`rgba(${Math.round(clamp01(c[0])*255)},${Math.round(clamp01(c[1])*255)},${Math.round(clamp01(c[2])*255)},${a})`;
  // Spark's seeded spray generator (an LCG), the same numbers as painter.py's _rng.
  function lcg(seed) {
    let s = (seed >>> 0) || 1
    return () => { s = (Math.imul(s, 1664525) + 1013904223) >>> 0; return s / 4294967296 }
  }

  function catmullRom(pts) {
    if (pts.length < 3) return pts.slice()
    const out = [], n = pts.length
    for (let i = 0; i < n - 1; i++) {
      const p0 = pts[Math.max(0, i - 1)], p1 = pts[i], p2 = pts[i + 1], p3 = pts[Math.min(n - 1, i + 2)]
      for (let s = 0; s < 8; s++) {
        const t = s / 8, t2 = t * t, t3 = t2 * t
        const f = k => 0.5 * (2 * p1[k] + (-p0[k] + p2[k]) * t + (2 * p0[k] - 5 * p1[k] + 4 * p2[k] - p3[k]) * t2
          + (-p0[k] + 3 * p1[k] - 3 * p2[k] + p3[k]) * t3)
        out.push([f(0), f(1)])
      }
    }
    out.push(pts[n - 1])
    return out
  }

  // The box a painting of this shape takes inside (x, y, w, h), centred.
  function fitBox(shape, x, y, w, h) {
    const aspect = ASPECT[shape] || 2
    let bw = w, bh = w / aspect
    if (bh > h) { bh = h; bw = h * aspect }
    return { x: x + (w - bw) / 2, y: y + (h - bh) / 2, w: bw, h: bh }
  }

  // Draws a painting into box b of ctx (device pixels), revealed up to `reveal` (0..1, mark by mark).
  // Lays a painting's marks into g (a W × H layer), adding light, revealed up to `reveal` (0..1, mark by mark).
  // Marks are sized against the whole canvas (W × H), so a part of a shared painting is the same size as alone.
  function* paintMarks(g, painting, W, H, { reveal = 1, way = 'fine' } = {}) {
    const marks = (painting && painting.marks) || []
    if (!marks.length) return
    const unit = Math.min(W, H)
    const cell = W / 40
    const minR = way === 'truest' ? 0.6 * cell : 3 * (W / 1920)
    const minW = way === 'truest' ? 0.9 * cell : 4.5 * (W / 1920)
    const n = marks.length, q = clamp01(reveal) * n
    const mirror = painting.mirror
    const views = [[1, 1]]
    if (mirror === 'x' || mirror === 'xy') views.push([-1, 1])
    if (mirror === 'y' || mirror === 'xy') views.push([1, -1])
    if (mirror === 'xy') views.push([-1, -1])
    g.globalCompositeOperation = 'lighter'
    g.lineCap = 'round'; g.lineJoin = 'round'
    for (let i = 0; i < n && i < Math.ceil(q); i++) {
      const part = Math.min(1, q - i)
      if (part <= 0) continue
      const m = marks[i], k = m.k, c0 = m.c, c1 = m.c2 || m.c
      for (const [v, [fx, fy]] of views.entries()) {
        const X = u => (fx < 0 ? 1 - u : u) * W
        const Y = w => (fy < 0 ? 1 - w : w) * H
        const flipA = turns => { const a = fx < 0 ? 0.5 - turns : turns; return fy < 0 ? -a : a }
        if (k === 'line' || k === 'curve') {
          let pts = m.pts.map(p => [p[0], p[1]])
          if (k === 'curve' && pts.length >= 3) pts = catmullRom(pts)
          if (part < 1) pts = pts.slice(0, Math.max(2, Math.ceil(pts.length * part)))
          const P = pts.map(p => [X(p[0]), Y(p[1])])
          const a = m.a * (part < 1 ? 0.6 + 0.4 * part : 1)
          let stroke = rgb(c0, a)
          if (c0 !== c1 && String(c0) !== String(c1)) {
            const [x0, y0] = P[0], [x1, y1] = P[P.length - 1]
            // A closed stroke (it ends where it began) has no direction for its gradient: SVG paints it in the
            // gradient's last colour, and so does this.
            if (Math.hypot(x1 - x0, y1 - y0) < 0.5) stroke = rgb(c1, a)
            else { const gr = g.createLinearGradient(x0, y0, x1, y1); gr.addColorStop(0, rgb(c0, a)); gr.addColorStop(1, rgb(c1, a)); stroke = gr }
          }
          g.strokeStyle = stroke; g.lineWidth = Math.max(minW, m.w * unit)
          g.beginPath(); P.forEach((p, j) => j ? g.lineTo(p[0], p[1]) : g.moveTo(p[0], p[1])); g.stroke()
        } else if (k === 'fill') {
          const P = m.pts.map(p => [X(p[0]), Y(p[1])])
          const a = m.a * part
          let fill = rgb(c0, a)
          if (String(c0) !== String(c1)) {
            const ang = flipA(m.grad ?? 0.25) * TAU, gx = Math.cos(ang), gy = Math.sin(ang)
            const cx = P.reduce((s, p) => s + p[0], 0) / P.length, cy = P.reduce((s, p) => s + p[1], 0) / P.length
            const span = Math.max(W, H) * 0.5
            const gr = g.createLinearGradient(cx - gx * span, cy - gy * span, cx + gx * span, cy + gy * span)
            gr.addColorStop(0, rgb(c0, a)); gr.addColorStop(1, rgb(c1, a)); fill = gr
          }
          g.fillStyle = fill
          g.beginPath(); P.forEach((p, j) => j ? g.lineTo(p[0], p[1]) : g.moveTo(p[0], p[1])); g.closePath(); g.fill()
        } else if (k === 'arc') {
          const a0 = flipA(m.a0), a1 = flipA(m.a1)
          const [lo, hi] = ((fx < 0) !== (fy < 0)) ? [a1, a0] : [a0, a1]
          const span = (((hi - lo) % 1) + 1) % 1 || 1
          const r = Math.max(minR, m.r * unit)
          g.strokeStyle = rgb(c0, m.a); g.lineWidth = Math.max(minW, m.w * unit)
          g.beginPath(); g.arc(X(m.x), Y(m.y), r, lo * TAU, (lo + span * part) * TAU); g.stroke()
        } else if (k === 'spray') {
          const next = lcg(((m.seed || i + 1) * 7919 + v) >>> 0)
          const count = Math.round(m.n * part)
          g.fillStyle = rgb(c0, 1)
          for (let s = 0; s < count; s++) {
            const ang = next() * TAU, dist = Math.sqrt(next()) * m.r
            const sx = m.x + Math.cos(ang) * dist, sy = m.y + Math.sin(ang) * dist
            const sr = m.s * (0.5 + next()) * unit, sa = m.a * (0.4 + 0.6 * next())
            g.globalAlpha = sa
            g.beginPath(); g.arc(X(sx), Y(sy), Math.max(minR, sr), 0, TAU); g.fill(); yield
          }
          g.globalAlpha = 1
        } else if (k === 'glow') {
          const r = Math.max(minR, m.r * unit * 1.6), a = m.a * part * 0.9, cx = X(m.x), cy = Y(m.y)
          const gr = g.createRadialGradient(cx, cy, 0, cx, cy, r)
          gr.addColorStop(0, rgb(c0, a * 0.5)); gr.addColorStop(0.45, rgb(c0, a * 0.167))
          gr.addColorStop(0.7, rgb(c0, a * 0.04)); gr.addColorStop(1, rgb(c0, 0))
          g.fillStyle = gr; g.beginPath(); g.arc(cx, cy, r, 0, TAU); g.fill()
        } else if (k === 'dot') {
          g.fillStyle = rgb(c0, m.a * part)
          g.beginPath(); g.arc(X(m.x), Y(m.y), Math.max(minR, m.r * unit * (0.6 + 0.4 * part)), 0, TAU); g.fill()
        } else if (k === 'ring') {
          g.strokeStyle = rgb(c0, m.a * part); g.lineWidth = Math.max(minW, m.w * unit)
          g.beginPath(); g.arc(X(m.x), Y(m.y), Math.max(minR, m.r * unit), 0, TAU); g.stroke()
        }
        yield
      }
    }
  }


// Rendering belongs to an explicit standalone preview, never the terminal loop.
// Each generator step is at most one bounded mark or one spray speck.
async function paintAsync(g, painting, W, H, options={}) {
  if (!(W>0 && H>0 && W<=960 && H<=960)) throw new Error('Preview dimensions exceed bounds');
  const clock=options.clock || (()=>performance.now());
  const yieldTask=options.yieldTask || (()=>new Promise(resolve=>setTimeout(resolve,0)));
  const cancelled=options.cancelled || (()=>false);
  const steps=paintMarks(g,painting,W,H);
  let bursts=0,maxBurstMs=0;
  await yieldTask();
  for (;;) {
    const start=clock();let elapsed=0;
    do {
      if(cancelled())return {cancelled:true,bursts,maxBurstMs};
      const step=steps.next();
      elapsed=clock()-start;
      if(step.done)return {cancelled:false,bursts:bursts+1,maxBurstMs:Math.max(maxBurstMs,elapsed)};
    } while(elapsed<12);
    bursts++;maxBurstMs=Math.max(maxBurstMs,elapsed);
    await yieldTask();
  }
}
const api={lcg,catmullRom,fitBox,paintMarks,paintAsync};
if(typeof module!=='undefined')module.exports=api;
else globalThis.KeeperPainting=api;
})();
