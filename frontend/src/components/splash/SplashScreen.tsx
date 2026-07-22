import { useEffect, useMemo, useRef, useState } from 'react';
import { RibbonEngine } from './RibbonEngine';
import { AmbientSound } from './ambientSound';
import BeginButton from './BeginButton';
import './splash.css';

interface SplashScreenProps {
  /**
   * The ribbons and wordmark have dissolved (the splash background is still up):
   * the app should mount and fade in beneath the splash now. The splash logo is
   * already gone at this point, so the app's own logo never coexists with it.
   */
  onExitStart: () => void;
  /** The splash has fully faded out and can be unmounted. */
  onExited: () => void;
}

interface Layout {
  titlePx: number;
  subPx: number;
  blockCenterY: number;
}

const clamp = (v: number, lo: number, hi: number) => Math.max(lo, Math.min(hi, v));

// Vertical band the wordmark sits on (and the ribbons gather toward). Kept high
// enough that the wordmark + "AI" clear the tagline and the BEGIN sphere below.
const BAND_Y = 0.35;

// Shared geometry so the HTML wordmark and paper-plane glyph sit exactly on the
// band the ribbons gather toward (RibbonEngine is passed the same BAND_Y).
function computeLayout(w: number, h: number): Layout {
  const titlePx = clamp(w * 0.075, 28, 100);
  const subPx = titlePx * 0.42;
  return { titlePx, subPx, blockCenterY: h * BAND_Y };
}

// How long the ribbons + wordmark take to dissolve before the app is revealed,
// and how long the splash background then takes to fade away. Kept in sync with
// the CSS transition durations for .pp-exiting / .pp-dismissed.
const DISMISS_MS = 650;

const GoogleMark = () => (
  <svg viewBox="0 0 24 24" aria-hidden="true">
    <path fill="#dfeefc" d="M21.35 11.1H12v2.8h5.35c-.25 1.37-1 2.53-2.13 3.3v2.75h3.45c2.02-1.86 3.18-4.6 3.18-7.85 0-.66-.06-1.3-.17-1.9z" />
    <path fill="#9fc6ea" d="M12 22c2.7 0 4.96-.9 6.62-2.42l-3.45-2.68c-.96.64-2.18 1.02-3.17 1.02-2.44 0-4.5-1.65-5.24-3.87H3.2v2.43C4.86 19.98 8.14 22 12 22z" />
    <path fill="#7fb3e0" d="M6.76 14.05a5.98 5.98 0 0 1 0-4.1V7.52H3.2a10 10 0 0 0 0 8.96l3.56-2.43z" />
    <path fill="#bcdcf5" d="M12 5.98c1.47 0 2.78.5 3.82 1.5l2.86-2.86C16.96 2.98 14.7 2 12 2 8.14 2 4.86 4.02 3.2 7.52l3.56 2.43C7.5 7.63 9.56 5.98 12 5.98z" />
  </svg>
);

const GithubMark = () => (
  <svg viewBox="0 0 24 24" aria-hidden="true" fill="#cfe4f7">
    <path d="M12 2C6.48 2 2 6.58 2 12.25c0 4.53 2.87 8.37 6.84 9.73.5.1.68-.22.68-.49l-.01-1.9c-2.78.62-3.37-1.2-3.37-1.2-.46-1.18-1.11-1.5-1.11-1.5-.9-.63.07-.62.07-.62 1 .07 1.53 1.05 1.53 1.05.9 1.56 2.35 1.11 2.92.85.09-.66.35-1.11.63-1.36-2.22-.26-4.56-1.14-4.56-5.06 0-1.12.39-2.03 1.03-2.75-.1-.26-.45-1.3.1-2.72 0 0 .84-.28 2.75 1.05a9.3 9.3 0 0 1 5 0c1.91-1.33 2.75-1.05 2.75-1.05.55 1.42.2 2.46.1 2.72.64.72 1.03 1.63 1.03 2.75 0 3.93-2.35 4.8-4.58 5.05.36.32.68.94.68 1.9l-.01 2.82c0 .27.18.6.69.49A10.26 10.26 0 0 0 22 12.25C22 6.58 17.52 2 12 2z" />
  </svg>
);

export default function SplashScreen({ onExitStart, onExited }: SplashScreenProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const engineRef = useRef<RibbonEngine | null>(null);
  const soundRef = useRef<AmbientSound | null>(null);

  const [revealed, setRevealed] = useState(false);
  const [exiting, setExiting] = useState(false);
  const [dismissed, setDismissed] = useState(false);
  const [soundOn, setSoundOn] = useState(false);

  const [dims, setDims] = useState(() => ({ w: window.innerWidth, h: window.innerHeight }));
  const layout = useMemo(() => computeLayout(dims.w, dims.h), [dims]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const engine = new RibbonEngine(canvas, {
      reducedMotion,
      onSettle: () => setRevealed(true),
      bandY: BAND_Y,
    });
    engineRef.current = engine;

    const applySize = () => {
      const w = window.innerWidth;
      const h = window.innerHeight;
      const dpr = Math.min(2, window.devicePixelRatio || 1);
      setDims({ w, h });
      engine.resize(w, h, dpr);
    };
    applySize();
    engine.start();

    const onResize = () => applySize();
    const onPointerMove = (e: PointerEvent) => engine.setPointer(e.clientX, e.clientY);
    const onPointerLeave = () => engine.clearPointer();
    window.addEventListener('resize', onResize);
    window.addEventListener('pointermove', onPointerMove);
    window.addEventListener('pointerleave', onPointerLeave);

    return () => {
      window.removeEventListener('resize', onResize);
      window.removeEventListener('pointermove', onPointerMove);
      window.removeEventListener('pointerleave', onPointerLeave);
      engine.stop();
      engineRef.current = null;
    };
    // Engine owns its own animation loop; we intentionally build it once per mount.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleBegin = () => {
    if (exiting) return;
    setExiting(true); // CSS fades the wordmark, plane and UI out
    soundRef.current?.disable();

    // Once the ribbons have dissolved, reveal the app beneath, then fade the (now
    // logo-less) splash background away and unmount it. This ordering guarantees
    // the splash logo and the app's own logo are never on screen together.
    const finishExit = () => {
      onExitStart();
      setDismissed(true);
      window.setTimeout(onExited, DISMISS_MS);
    };

    const engine = engineRef.current;
    if (engine) engine.beginExit(finishExit);
    else finishExit();
  };

  const toggleSound = () => {
    if (!soundRef.current) soundRef.current = new AmbientSound();
    if (soundOn) {
      soundRef.current.disable();
      setSoundOn(false);
    } else {
      void soundRef.current.enable();
      setSoundOn(true);
    }
  };

  return (
    <div
      className={[
        'pp-splash',
        revealed ? 'pp-revealed pp-logo-in' : '',
        exiting ? 'pp-exiting' : '',
        dismissed ? 'pp-dismissed' : '',
      ]
        .filter(Boolean)
        .join(' ')}
    >
      <canvas ref={canvasRef} className="pp-canvas" />
      <div className="pp-vignette" />
      <div className="pp-grain" />

      <div className="pp-overlay">
        <button className="pp-sound" onClick={toggleSound} aria-label="Toggle ambient sound">
          {soundOn ? '♪' : '○'}
        </button>

        <nav className="pp-eyebrow pp-fade pp-d1" aria-hidden={!revealed}>
          <span>Understand</span>
          <span className="pp-dot">•</span>
          <span>Connect</span>
          <span className="pp-dot">•</span>
          <span>Innovate</span>
        </nav>

        {/* Paper-plane glyph — part of the single logo lockup; draws in once. */}
        <svg
          className="pp-plane"
          viewBox="0 0 48 48"
          style={{
            top: `${layout.blockCenterY - layout.titlePx * 1.35}px`,
            width: `${layout.titlePx * 0.78}px`,
            height: `${layout.titlePx * 0.78}px`,
          }}
          aria-hidden="true"
        >
          <path d="M5 26 L43 7 L28 41 L23 28 Z M43 7 L23 28" />
        </svg>

        {/* Razor-sharp HTML wordmark — the one and only logo. Emerges as the ribbons
            straighten and gather onto this band; never rendered as particles. */}
        <div
          className="pp-wordmark"
          style={{ top: `${layout.blockCenterY}px` }}
          aria-label="PaperPilot AI"
        >
          <span
            className="pp-title"
            style={{ fontSize: `${layout.titlePx}px`, letterSpacing: '0.18em' }}
          >
            PaperPilot
          </span>
          <span
            className="pp-sub"
            style={{ fontSize: `${layout.subPx}px`, letterSpacing: '0.34em', marginTop: `${layout.titlePx * 0.2}px` }}
          >
            AI
          </span>
        </div>

        <div className="pp-lower">
          <div className="pp-tagline pp-fade pp-d2">Your Research. Amplified.</div>
          <div className="pp-fade pp-d3">
            <BeginButton onBegin={handleBegin} />
          </div>
          <div className="pp-oauth pp-fade pp-d4">
            <span className="pp-oauth-label">or continue with</span>
            <div className="pp-oauth-row">
              {/* Placeholder providers: no auth backend yet, so these simply enter
                  the app. Wire real OAuth here when a backend endpoint exists. */}
              <button className="pp-chip" onClick={handleBegin}>
                <GoogleMark /> Google
              </button>
              <button className="pp-chip" onClick={handleBegin}>
                <GithubMark /> GitHub
              </button>
            </div>
          </div>
        </div>

        <div className="pp-footer pp-fade pp-d4">
          PaperPilot AI <span className="pp-dot">•</span> Research Assistant
        </div>
      </div>
    </div>
  );
}
