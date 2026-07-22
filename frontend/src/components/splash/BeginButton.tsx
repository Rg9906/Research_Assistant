import { useRef, type PointerEvent } from 'react';

interface BeginButtonProps {
  onBegin: () => void;
}

/**
 * The circular etched-glass BEGIN control. Two live behaviours beyond CSS:
 *  - magnetic pull: the button leans toward the cursor while hovered, then
 *    springs back on leave (transform is transitioned in CSS);
 *  - a screen-spanning water ripple emitted from the exact click point.
 */
export default function BeginButton({ onBegin }: BeginButtonProps) {
  const ref = useRef<HTMLButtonElement>(null);

  const handleMove = (e: PointerEvent<HTMLButtonElement>) => {
    const el = ref.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    const dx = e.clientX - (r.left + r.width / 2);
    const dy = e.clientY - (r.top + r.height / 2);
    // Lean up to ~14px toward the pointer.
    el.style.transform = `translate(${dx * 0.18}px, ${dy * 0.18 - 3}px) scale(1.04)`;
  };

  const handleLeave = () => {
    const el = ref.current;
    if (el) el.style.transform = '';
  };

  const handleClick = (e: PointerEvent<HTMLButtonElement>) => {
    // Emit a ripple from the click point that expands across the whole screen.
    const ripple = document.createElement('div');
    ripple.className = 'pp-ripple';
    ripple.style.left = `${e.clientX}px`;
    ripple.style.top = `${e.clientY}px`;
    document.body.appendChild(ripple);
    window.setTimeout(() => ripple.remove(), 1000);
    onBegin();
  };

  return (
    <button
      ref={ref}
      className="pp-begin"
      onPointerMove={handleMove}
      onPointerLeave={handleLeave}
      onPointerUp={handleClick}
      aria-label="Begin — enter PaperPilot AI"
    >
      Begin
    </button>
  );
}
