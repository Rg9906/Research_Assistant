/**
 * RibbonEngine — the PaperPilot splash background.
 *
 * The hero is a small set (≈6–12 per side) of long, continuous ribbons of light —
 * think glowing silk threads, magnetic field lines, fibre-optic cables drifting in
 * a slow current. Each ribbon spans almost the whole viewport and is drawn as a
 * single smooth Catmull-Rom spline with a *uniform* glow along its length: there is
 * no bright "head", no particle, no comet trail. The canvas is fully cleared every
 * frame (no accumulation buffer), which is what keeps them reading as continuous
 * ribbons rather than swarms of streaks.
 *
 *   WEAVE (slow ocean-current sway) ─▶ ALIGN (curvature eases out, ribbons gather
 *   toward the wordmark band) ─▶ CALM (a faint, near-straight light field behind the
 *   crisp HTML wordmark) ─▶ DISSOLVE (gentle fade on exit)
 *
 * The typography is NOT made of particles — the ribbons simply straighten and gather,
 * and React fades a razor-sharp HTML wordmark in on top, so the type feels like it
 * emerged from the geometry. The engine only needs to know the wordmark's vertical
 * band (cy), which it derives from the viewport, so there is no text sampling here.
 *
 * Colour is a narrow, low-saturation soft-white → ice → restrained-cyan ramp, drawn
 * additively (`lighter`) at low alpha so overlaps bloom gently without ever going
 * neon. Everything is deliberately slow and sparse — calm over complexity.
 */

export interface RibbonEngineConfig {
  reducedMotion: boolean;
  /** Fired once, when the ribbons have gathered enough for the wordmark to appear. */
  onSettle: () => void;
  /** Vertical band the ribbons gather toward, as a fraction of height. Must match
   *  the wordmark's centre (SplashScreen's BAND_Y) so they stay aligned. */
  bandY: number;
}

const TAU = Math.PI * 2;
const clamp = (v: number, lo: number, hi: number) => (v < lo ? lo : v > hi ? hi : v);
const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
const easeInOut = (t: number) => (t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2);
const easeOut = (t: number) => 1 - Math.pow(1 - t, 3);

// Timeline (seconds from start). The ribbons weave in, gather and hand off to the
// wordmark (which materialises around `settle`), then fade out entirely so the
// scene resolves to just the clean wordmark — the lines do not linger.
const T = {
  alignStart: 2.4,
  settle: 3.3, // wordmark begins to materialise
  alignEnd: 4.8,
  fadeOutStart: 4.6, // ribbons begin to fade away
  fadeOutEnd: 7.2, // ribbons fully gone — only the wordmark + faint dust remain
  dissolve: 0.85, // exit fade duration
};

// Residual weave kept while the ribbons straighten, before they fade out.
const CALM_AMP = 0.12;

// Narrow, low-saturation soft-white → ice → restrained-cyan ramp (palette-locked).
const RAMP: [number, number, number][] = [
  [210, 232, 250], // soft white-blue
  [186, 222, 246], // ice
  [150, 206, 240], // soft cyan
  [122, 198, 234], // restrained cyan (never neon)
  [236, 246, 255], // near-white highlight
];

function colorFor(tone: number): [number, number, number] {
  const t = clamp(tone, 0, 0.999) * (RAMP.length - 1);
  const i = Math.floor(t);
  const f = t - i;
  const a = RAMP[i];
  const b = RAMP[Math.min(RAMP.length - 1, i + 1)];
  return [a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f, a[2] + (b[2] - a[2]) * f];
}

/**
 * One ribbon, stored in *normalized* units (fractions of width/height) so it never
 * needs rebuilding on resize — pixel positions are derived per-frame from w/h.
 */
interface Ribbon {
  side: -1 | 1; // travel direction of the weave (counter-flowing left vs right)
  baseYNorm: number; // resting vertical position, 0..1 of height
  ampNorm: number; // weave amplitude, fraction of height
  wlNorm: number; // wavelength, fraction of width
  phase: number; // static phase offset
  phaseSpeed: number; // how fast the weave travels (rad/s) — slow
  driftNorm: number; // whole-ribbon vertical bob, fraction of height
  driftPhase: number;
  driftSpeed: number;
  tone: number; // 0..1 into RAMP
  thickness: number; // core stroke width (css px)
  birth: number; // fade-in delay (s)
  seed: number;
}

// Samples across the width per ribbon — enough for a buttery Catmull-Rom spline.
const SAMPLES = 18;

export class RibbonEngine {
  private canvas: HTMLCanvasElement;
  private ctx: CanvasRenderingContext2D;
  private cfg: RibbonEngineConfig;

  private dpr = 1;
  private w = 0;
  private h = 0;
  private cx = 0;
  private cy = 0;

  private raf = 0;
  private running = false;
  private startTime = 0;
  private lastTime = 0;
  private settled = false;

  private exiting = false;
  private exitStartT = 0;
  private onExitDone: (() => void) | null = null;

  private ribbons: Ribbon[] = [];

  // Faint drifting background motes: [x, y, phase] per mote (normalized x/y).
  private dust: Float32Array = new Float32Array(0);
  private dot: HTMLCanvasElement;

  // Reused scratch buffers for the current ribbon's sampled points.
  private xs = new Float32Array(SAMPLES);
  private ys = new Float32Array(SAMPLES);

  // Smoothed pointer lean (very subtle parallax).
  private pointerActive = false;
  private pointerX = 0;
  private pointerY = 0;
  private leanY = 0;
  private leanPhase = 0;

  constructor(canvas: HTMLCanvasElement, cfg: RibbonEngineConfig) {
    this.canvas = canvas;
    const ctx = canvas.getContext('2d', { alpha: true });
    if (!ctx) throw new Error('2D canvas context unavailable');
    this.ctx = ctx;
    this.cfg = cfg;
    this.dot = this.buildDot();
    this.buildRibbons();
  }

  /** A single soft radial dot sprite, reused for the background dust. */
  private buildDot(): HTMLCanvasElement {
    const s = 16;
    const c = document.createElement('canvas');
    c.width = c.height = s;
    const g = c.getContext('2d')!;
    const grad = g.createRadialGradient(s / 2, s / 2, 0, s / 2, s / 2, s / 2);
    grad.addColorStop(0, 'rgba(210,232,250,0.9)');
    grad.addColorStop(1, 'rgba(210,232,250,0)');
    g.fillStyle = grad;
    g.fillRect(0, 0, s, s);
    return c;
  }

  private buildRibbons(): void {
    const small = Math.min(window.innerWidth, window.innerHeight) < 720;
    const perSide = small ? 5 : 7; // 6–12 per side; kept sparse for calm
    const rnd = () => Math.random();
    const ribbons: Ribbon[] = [];

    for (const side of [-1, 1] as const) {
      for (let i = 0; i < perSide; i++) {
        const frac = (i + 0.5) / perSide;
        // Spread resting positions across the height, with a little jitter.
        const baseYNorm = 0.12 + frac * 0.76 + (rnd() - 0.5) * 0.05;
        // Mostly soft-white/ice, a minority cyan — restrained.
        const tone = rnd() < 0.25 ? rnd() * 0.4 : 0.4 + rnd() * 0.6;
        ribbons.push({
          side,
          baseYNorm,
          ampNorm: 0.05 + rnd() * 0.05,
          wlNorm: 0.62 + rnd() * 0.5, // long wavelengths → broad, gentle curves
          phase: rnd() * TAU,
          phaseSpeed: 0.1 + rnd() * 0.12, // very slow travel
          driftNorm: 0.008 + rnd() * 0.014,
          driftPhase: rnd() * TAU,
          driftSpeed: 0.06 + rnd() * 0.1,
          tone,
          thickness: 1.0 + rnd() * 0.7,
          birth: rnd() * 1.6, // staggered fade-in
          seed: rnd(),
        });
      }
    }
    this.ribbons = ribbons;
  }

  resize(cssW: number, cssH: number, dpr: number): void {
    this.dpr = dpr;
    this.w = cssW;
    this.h = cssH;
    this.cx = cssW / 2;
    this.cy = cssH * this.cfg.bandY; // wordmark band — ribbons gather here
    this.canvas.width = Math.max(1, Math.floor(cssW * dpr));
    this.canvas.height = Math.max(1, Math.floor(cssH * dpr));
    this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    const motes = Math.floor((cssW * cssH) / 60000); // very few
    this.dust = new Float32Array(motes * 3);
    for (let i = 0; i < motes; i++) {
      this.dust[i * 3] = Math.random();
      this.dust[i * 3 + 1] = Math.random();
      this.dust[i * 3 + 2] = Math.random() * TAU;
    }
  }

  start(): void {
    if (this.running) return;
    this.running = true;
    this.startTime = performance.now();
    this.lastTime = this.startTime;
    if (this.cfg.reducedMotion) {
      // Skip the whole intro: jump past the ribbon fade so only the wordmark shows.
      this.startTime = performance.now() - T.fadeOutEnd * 1000;
      for (const r of this.ribbons) {
        r.phaseSpeed = 0;
        r.driftSpeed = 0;
        r.birth = 0;
      }
    }
    this.raf = requestAnimationFrame(this.tick);
  }

  stop(): void {
    this.running = false;
    cancelAnimationFrame(this.raf);
  }

  setPointer(x: number, y: number): void {
    this.pointerActive = true;
    this.pointerX = x;
    this.pointerY = y;
  }

  clearPointer(): void {
    this.pointerActive = false;
  }

  /** Begin the exit fade; `done` is called once the ribbons have fully dissolved. */
  beginExit(done: () => void): void {
    if (this.exiting) return;
    this.exiting = true;
    this.exitStartT = (performance.now() - this.startTime) / 1000;
    this.onExitDone = done;
  }

  /** 1 while weaving → CALM_AMP once aligned: how much curvature remains. */
  private straightenAt(t: number): number {
    if (t <= T.alignStart) return 1;
    if (t >= T.alignEnd) return CALM_AMP;
    const p = easeInOut((t - T.alignStart) / (T.alignEnd - T.alignStart));
    return lerp(1, CALM_AMP, p);
  }

  /** 0 → 1 across the align window: how far ribbons gather toward the band. */
  private clusterAt(t: number): number {
    if (t <= T.alignStart) return 0;
    if (t >= T.alignEnd) return 1;
    return easeInOut((t - T.alignStart) / (T.alignEnd - T.alignStart));
  }

  private tick = (now: number): void => {
    if (!this.running) return;
    const t = (now - this.startTime) / 1000;
    let dt = (now - this.lastTime) / 1000;
    this.lastTime = now;
    dt = clamp(dt, 1 / 240, 1 / 30);

    if (!this.settled && (t >= T.settle || this.cfg.reducedMotion)) {
      this.settled = true;
      this.cfg.onSettle();
    }

    // Smoothly follow the pointer for a whisper of parallax.
    const targetLean = this.pointerActive ? (this.pointerY - this.cy) * 0.03 : 0;
    const targetPhase = this.pointerActive ? (this.pointerX - this.cx) * 0.0006 : 0;
    this.leanY += (targetLean - this.leanY) * clamp(dt * 3, 0, 1);
    this.leanPhase += (targetPhase - this.leanPhase) * clamp(dt * 3, 0, 1);

    this.render(t);

    if (this.exiting && t - this.exitStartT >= T.dissolve) {
      this.running = false;
      this.onExitDone?.();
      this.onExitDone = null;
      return;
    }
    this.raf = requestAnimationFrame(this.tick);
  };

  private render(t: number): void {
    const ctx = this.ctx;
    const { w, h, cx, cy } = this;

    // Fully clear every frame — no accumulation buffer, so ribbons stay crisp and
    // continuous instead of smearing into comet trails. Depth comes from the CSS
    // backdrop showing through the transparent canvas.
    ctx.setTransform(this.dpr, 0, 0, this.dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);
    ctx.globalCompositeOperation = 'lighter';

    const straighten = this.straightenAt(t);
    const cluster = this.clusterAt(t);
    const dissolveP = this.exiting ? clamp((t - this.exitStartT) / T.dissolve, 0, 1) : 0;
    const globalAlpha = 1 - easeOut(dissolveP);
    // The ribbons fade out entirely once the wordmark has taken over, so the lines
    // never linger — the scene resolves to just the wordmark (and faint dust).
    const fieldFade =
      t <= T.fadeOutStart
        ? 1
        : t >= T.fadeOutEnd
          ? 0
          : 1 - easeInOut((t - T.fadeOutStart) / (T.fadeOutEnd - T.fadeOutStart));
    const fieldAlpha = globalAlpha * fieldFade;
    // Let the wordmark dominate once calm: dim the field a touch through align.
    const brightness = lerp(1, 0.72, cluster);

    // A few tiny drifting motes — these persist as gentle ambient depth after the
    // ribbons are gone (they are dust, not lines).
    for (let i = 0; i < this.dust.length; i += 3) {
      const bx = this.dust[i] * w + Math.sin(t * 0.1 + this.dust[i + 2]) * 10;
      const by = this.dust[i + 1] * h + Math.cos(t * 0.08 + this.dust[i + 2]) * 10;
      const a = (0.04 + 0.04 * (0.5 + 0.5 * Math.sin(t * 0.5 + this.dust[i + 2]))) * globalAlpha;
      ctx.globalAlpha = a;
      ctx.drawImage(this.dot, bx - 2.5, by - 2.5, 5, 5);
    }
    ctx.globalAlpha = 1;

    if (fieldAlpha <= 0.01) return;

    // Very faint volumetric fog centred on the band, fading out with the ribbons.
    const fog = easeInOut(clamp(t / (T.alignStart + 1), 0, 1)) * (1 - cluster * 0.4);
    if (fog > 0.01) {
      const rad = Math.max(w, h) * 0.55;
      const g = ctx.createRadialGradient(cx, cy, 0, cx, cy, rad);
      g.addColorStop(0, `rgba(150,206,240,${0.05 * fog * fieldAlpha})`);
      g.addColorStop(1, 'rgba(150,206,240,0)');
      ctx.fillStyle = g;
      ctx.fillRect(0, 0, w, h);
    }

    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    const padX = w * 0.08;

    for (const r of this.ribbons) {
      const life = easeOut(clamp((t - r.birth) / 1.2, 0, 1));
      const alpha = life * fieldAlpha * brightness;
      if (alpha <= 0.01) continue;

      const baseY0 = r.baseYNorm * h;
      // Gather toward the band without collapsing to a single line.
      const targetY = cy + (baseY0 - cy) * 0.42;
      const baseY = lerp(baseY0, targetY, cluster) + this.leanY;

      const ampPx = r.ampNorm * h * straighten;
      const driftPx = r.driftNorm * h;
      const bob = driftPx * Math.sin(t * r.driftSpeed + r.driftPhase);
      const k = TAU / (r.wlNorm * w);
      const travel = t * r.phaseSpeed + r.phase - this.leanPhase;

      for (let s = 0; s < SAMPLES; s++) {
        const u = s / (SAMPLES - 1);
        const x = -padX + u * (w + 2 * padX);
        const arg = r.side * k * x - travel;
        const weave = ampPx * (Math.sin(arg) + 0.4 * Math.sin(arg * 1.9 + r.seed * TAU));
        this.xs[s] = x;
        this.ys[s] = baseY + weave + bob;
      }

      const [cr, cg, cb] = colorFor(r.tone);
      this.pathRibbon(ctx);

      // Uniform glow: wide-faint bloom → mid → crisp core, all the same colour and
      // alpha along the whole length. No head, no gradient, no bright tip.
      ctx.strokeStyle = `rgba(${cr | 0},${cg | 0},${cb | 0},${alpha * 0.05})`;
      ctx.lineWidth = r.thickness * 4.5;
      ctx.stroke();
      ctx.strokeStyle = `rgba(${cr | 0},${cg | 0},${cb | 0},${alpha * 0.12})`;
      ctx.lineWidth = r.thickness * 2.1;
      ctx.stroke();
      ctx.strokeStyle = `rgba(${cr | 0},${cg | 0},${cb | 0},${alpha * 0.5})`;
      ctx.lineWidth = r.thickness;
      ctx.stroke();
    }
  }

  /** Build a smooth Catmull-Rom spline through the current xs/ys sample points. */
  private pathRibbon(ctx: CanvasRenderingContext2D): void {
    const { xs, ys } = this;
    const n = SAMPLES;
    ctx.beginPath();
    ctx.moveTo(xs[0], ys[0]);
    for (let i = 0; i < n - 1; i++) {
      const p0x = xs[i - 1 < 0 ? 0 : i - 1];
      const p0y = ys[i - 1 < 0 ? 0 : i - 1];
      const p1x = xs[i];
      const p1y = ys[i];
      const p2x = xs[i + 1];
      const p2y = ys[i + 1];
      const p3x = xs[i + 2 >= n ? n - 1 : i + 2];
      const p3y = ys[i + 2 >= n ? n - 1 : i + 2];
      // Catmull-Rom → cubic Bézier control points.
      ctx.bezierCurveTo(
        p1x + (p2x - p0x) / 6,
        p1y + (p2y - p0y) / 6,
        p2x - (p3x - p1x) / 6,
        p2y - (p3y - p1y) / 6,
        p2x,
        p2y,
      );
    }
  }
}
